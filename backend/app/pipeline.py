from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

from app import db
from app.agents import run_ops, run_specialist
from app.clock import get_now
from app.demo_pack import write_demo_pack
from app.ingestion import ingest_file
from app.model_router import current as router_current
from app.schemas import (
    Alert,
    BrdSection,
    ChangelogEntry,
    Conflict,
    DelegationEvent,
    Finding,
    SourceChunk,
    Task,
)

from app.diagram_agent import generate_mermaid_diagrams

BRD_TITLES = {
    "objectives": "Objectives",
    "scope": "Scope",
    "stakeholders": "Stakeholders",
    "diagrams": "System Architecture & Visual Flows",
    "functional_requirements": "Functional requirements",
    "non_functional_requirements": "Non-functional requirements",
    "budget": "Budget",
    "risks": "Risks",
    "assumptions": "Assumptions",
    "open_conflicts": "Open conflicts",
}

SESSIONS: dict[str, dict] = {}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def detect_conflicts(findings: list[Finding]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    q3 = [f for f in findings if "q3" in f.statement.lower()]
    q4 = [f for f in findings if "q4" in f.statement.lower() or "october" in f.statement.lower()]
    if q3 and q4:
        conflicts.append(
            Conflict(
                id=_new_id("c"),
                topic="Launch window",
                left=q3[0],
                right=q4[0],
                disagreement="One source locks launch to Q3; another requires Q4 because stores cannot be staffed before October.",
                suggested_question="Which launch window should the BRD treat as canonical — Q3 or Q4?",
            )
        )
    return conflicts


def validate(findings: list[Finding]) -> tuple[list[Finding], list[Conflict], list[dict]]:
    kept: list[Finding] = []
    gaps: list[dict] = []
    seen: set[str] = set()
    for f in findings:
        key = f.statement.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if not f.source_id:
            continue
        if f.confidence < 0.45:
            gaps.append({"kind": "low_confidence", "finding_id": f.id, "statement": f.statement})
            continue
        if f.type == "requirement" and not f.acceptance_criteria and "offline" in f.statement.lower():
            gaps.append(
                {
                    "kind": "missing_acceptance",
                    "finding_id": f.id,
                    "statement": f.statement,
                    "question": "Who owns offline-mode acceptance criteria, and what is the pass condition?",
                }
            )
        kept.append(f)
    conflicts = detect_conflicts(kept)
    return kept, conflicts, gaps


def compose_sections(findings: list[Finding], conflicts: list[Conflict], chunks: list[SourceChunk] | None = None) -> list[BrdSection]:
    grouped: dict[str, list[Finding]] = {k: [] for k in BRD_TITLES}
    for f in findings:
        grouped.setdefault(f.section, []).append(f)
    
    diagrams_data = generate_mermaid_diagrams(findings, chunks or [])

    sections: list[BrdSection] = []
    for sid, title in BRD_TITLES.items():
        if sid == "diagrams":
            sections.append(
                BrdSection(
                    id=sid,
                    title=title,
                    body="System architecture, user interaction flow, and sequence diagrams automatically generated from validated requirements.",
                    finding_ids=[f.id for f in findings[:6]],
                    diagram_type="architecture",
                    mermaid_code=diagrams_data.get("architecture"),
                )
            )
            continue

        if sid == "open_conflicts":
            if not conflicts:
                body = "No open conflicts. Validator found sources consistent after grounding checks."
            else:
                lines = []
                for c in conflicts:
                    flag = "Pending Conflict" if c.status == "open" else "Resolved"
                    lines.append(f"**{flag}: {c.topic}.** {c.disagreement}\nQuestion: {c.suggested_question}")
                body = "\n\n".join(lines)
            sections.append(BrdSection(id=sid, title=title, body=body, finding_ids=[c.id for c in conflicts]))
            continue

        items = grouped.get(sid, [])
        if not items:
            body = "_No validated findings in this section yet._"
        else:
            body = "\n".join(f"- {f.statement} _(confidence {f.confidence:.0%}, {f.agent})_" for f in items)
        sections.append(BrdSection(id=sid, title=title, body=body, finding_ids=[f.id for f in items]))
    return sections


def persist_ops(ops_items, user_id: str | None = None) -> tuple[list[Task], list[Alert]]:
    tasks: list[Task] = []
    alerts: list[Alert] = []
    for item in ops_items:
        if item.type == "draft_email":
            task = Task(
                id=_new_id("t"),
                type="draft_email",
                context=item.context,
                payload=item.payload,
                source_id=item.source_id,
                source_span=item.source_span,
                confidence=item.confidence,
                created_at=get_now(),
            )
            db.upsert_task(task, user_id)
            tasks.append(task)
        else:
            alert = Alert(
                id=_new_id("a"),
                target_date=str(item.payload.get("target_date") or ""),
                original_phrase=str(item.payload.get("original_phrase") or ""),
                reminder_message=str(item.payload.get("reminder_message") or item.context),
                context=item.context,
                source_id=item.source_id,
            )
            db.upsert_alert(alert, user_id)
            alerts.append(alert)
    return tasks, alerts


async def run_pipeline(
    chunks: list[SourceChunk], project_description: str, session_id: str, user_id: str | None = None
) -> AsyncGenerator[dict, None]:
    db.init_db()
    db.reset_ops(user_id)
    text_chunks = [c for c in chunks if c.modality in ("text", "audio")]
    doc_chunks = [c for c in chunks if c.modality in ("pdf", "spreadsheet")]
    vision_chunks = [c for c in chunks if c.modality == "image"]
    if not text_chunks:
        text_chunks = chunks

    events: list[DelegationEvent] = []

    def emit_event(agent, level, task, status, detail=""):
        ev = DelegationEvent(agent=agent, level=level, task=task, status=status, detail=detail)
        events.append(ev)
        return ev.model_dump()

    yield {"type": "plan", "agents": ["text", "vision", "document"], "router": router_current()}
    yield {"type": "delegation", "event": emit_event("orchestrator", 0, "plan parallel extraction", "running")}

    # Yield preliminary section skeletons immediately so UI responds in <100ms
    preliminary_sections = [
        BrdSection(id=sid, title=title, body="*Extracting requirements from multi-modal sources...*", finding_ids=[])
        for sid, title in BRD_TITLES.items()
    ]
    for sec in preliminary_sections:
        yield {"type": "section", "section": sec.model_dump(), "router": router_current()}

    yield {"type": "delegation", "event": emit_event("text_agent", 1, "extracting requirements", "running")}
    yield {"type": "delegation", "event": emit_event("budget_agent", 2, "extracting financial constraints", "running")}
    yield {"type": "delegation", "event": emit_event("risk_agent", 2, "extracting compliance & risks", "running")}
    yield {"type": "delegation", "event": emit_event("ops_agent", 2, "synthesizing action items", "running")}
    if vision_chunks:
        yield {"type": "delegation", "event": emit_event("vision_agent", 1, "parsing wireframes", "running")}
    if doc_chunks:
        yield {"type": "delegation", "event": emit_event("document_agent", 1, "parsing docs & sheets", "running")}
    yield {"type": "router", **router_current()}

    # Run ALL specialist agents in PARALLEL worker threads using asyncio.to_thread
    text_task = asyncio.to_thread(run_specialist, "text_agent", text_chunks, "functional_requirements")
    budget_task = asyncio.to_thread(
        run_specialist, "budget_agent", text_chunks + doc_chunks, "budget", "Focus on money, ceilings, line items."
    )
    risk_task = asyncio.to_thread(
        run_specialist, "risk_agent", text_chunks, "risks", "Focus on compliance, legal, operational risk."
    )
    ops_task = asyncio.to_thread(run_ops, text_chunks)

    vision_task = (
        asyncio.to_thread(
            run_specialist,
            "vision_agent",
            vision_chunks,
            "functional_requirements",
            "Describe UI elements and treat bbox as evidence region.",
        )
        if vision_chunks
        else None
    )

    doc_task = (
        asyncio.to_thread(run_specialist, "document_agent", doc_chunks, "objectives")
        if doc_chunks
        else None
    )

    # Await all parallel LLM agent calls simultaneously
    results = await asyncio.gather(
        text_task,
        budget_task,
        risk_task,
        ops_task,
        vision_task or asyncio.sleep(0, result=[]),
        doc_task or asyncio.sleep(0, result=[]),
    )

    t_findings, budget_findings, risk_findings, ops_items, v_findings, d_findings = results

    t_events = [
        DelegationEvent(agent="text_agent", level=1, task="emails & transcripts", status="kept"),
        DelegationEvent(agent="budget_agent", level=2, task="financial constraints", status="kept"),
        DelegationEvent(agent="risk_agent", level=2, task="compliance & risks", status="kept"),
        DelegationEvent(agent="ops_agent", level=2, task="tasks vs requirements", status="kept"),
    ]
    v_events = [DelegationEvent(agent="vision_agent", level=1, task="wireframes & screenshots", status="kept" if vision_chunks else "dropped")]
    d_events = [DelegationEvent(agent="document_agent", level=1, task="pdfs & spreadsheets", status="kept" if doc_chunks else "dropped")]

    for ev in t_events + v_events + d_events:
        events.append(ev)
        yield {"type": "delegation", "event": ev.model_dump()}

    all_findings = t_findings + budget_findings + risk_findings + v_findings + d_findings
    kept, conflicts, gaps = validate(all_findings)
    tasks, alerts = persist_ops(ops_items)

    # Compose final sections & diagrams in threadpool
    sections = await asyncio.to_thread(compose_sections, kept, conflicts, chunks)
    version = 1
    prev = SESSIONS.get(session_id)
    changelog = []
    if prev:
        version = int(prev.get("version", 1)) + 1
        changelog = list(prev.get("changelog") or [])
        changelog.append(
            ChangelogEntry(
                version=version,
                at=get_now(),
                summary="Incremental update from new or reprocessed sources.",
                sections=[s.id for s in sections],
            ).model_dump(mode="json")
        )
    else:
        changelog = [
            ChangelogEntry(
                version=1, at=get_now(), summary="Initial BRD from ingested sources.", sections=[s.id for s in sections]
            ).model_dump(mode="json")
        ]

    for section in sections:
        yield {"type": "section", "section": section.model_dump(), "router": router_current()}

    state = {
        "session_id": session_id,
        "version": version,
        "project_description": project_description,
        "chunks": [c.model_dump() for c in chunks],
        "findings": [f.model_dump() for f in kept],
        "conflicts": [c.model_dump() for c in conflicts],
        "gaps": gaps,
        "sections": [s.model_dump() for s in sections],
        "tasks": [t.model_dump(mode="json") for t in db.list_tasks(user_id)],
        "alerts": [a.model_dump(mode="json") for a in db.list_alerts(user_id)],
        "events": [e.model_dump() for e in events],
        "changelog": changelog,
        "router": router_current(),
        "questions": [
            *[c.suggested_question for c in conflicts if c.status == "open"],
            *[g.get("question") for g in gaps if g.get("question")],
        ],
    }
    SESSIONS[session_id] = state
    db.save_session(session_id, state, user_id)
    yield {"type": "complete", "state": state}


def load_demo_chunks() -> list[SourceChunk]:
    paths = write_demo_pack()
    chunks: list[SourceChunk] = []
    for path in paths:
        if path.suffix == ".txt" and path.name == "project_brief.txt":
            continue
        chunks.extend(ingest_file(path))
    return chunks
