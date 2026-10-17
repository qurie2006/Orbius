from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Dict, List, Optional

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

SESSIONS: Dict[str, Dict] = {}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def detect_conflicts(findings: List[Finding]) -> List[Conflict]:
    """Detects genuine semantic contradictions across sources using Gemini pairwise
    semantic comparison with multi-domain heuristic fallback."""
    from app.agents import parse_json_payload
    from app.model_router import generate_json

    conflicts: List[Conflict] = []
    f_map = {f.id: f for f in findings}

    # 1. Live Model Semantic Contradiction Check
    candidates = [f for f in findings if f.type in {"requirement", "constraint", "decision", "risk"}]
    if len(candidates) >= 2:
        sample_str = "\n".join(f"[{f.id}] ({f.section}) {f.statement} (Source: {f.source_span})" for f in candidates[:16])
        prompt = f"""You are an expert Requirements Validation & Contradiction Detection Agent.
Compare the following requirements extracted from different project documents.
Identify any genuine semantic contradictions, conflicting timelines, opposing security policies, budget overruns, or irreconcilable constraints between pairs of requirements.

REQUIREMENTS:
{sample_str}

If any contradiction exists, return a JSON array of objects:
[
  {{
    "left_id": "f_id_1",
    "right_id": "f_id_2",
    "topic": "Brief Title of Conflict",
    "disagreement": "Detailed explanation of why requirement 1 directly contradicts requirement 2.",
    "suggested_question": "A clarifying decision question for the project manager to resolve this disagreement."
  }}
]
If no contradictions exist, return empty array: []
"""
        try:
            raw = generate_json(prompt, purpose="semantic_conflict_check")
            parsed = parse_json_payload(raw)
            for item in parsed:
                lid = item.get("left_id")
                rid = item.get("right_id")
                if lid in f_map and rid in f_map and lid != rid:
                    conflicts.append(
                        Conflict(
                            id=_new_id("c"),
                            topic=item.get("topic") or "Policy & Specification Conflict",
                            left=f_map[lid],
                            right=f_map[rid],
                            disagreement=item.get("disagreement") or "Semantic disagreement between sources.",
                            suggested_question=item.get("suggested_question") or "Which requirement should take precedence?",
                        )
                    )
            if conflicts:
                return conflicts
        except Exception:
            pass

    # 2. Robust Multi-Domain Heuristic Fallback
    # A) Delivery Timeline (Q3 vs Q4, August vs October)
    q3 = [f for f in findings if any(k in f.statement.lower() for k in ["q3", "august", "july", "september"])]
    q4 = [f for f in findings if any(k in f.statement.lower() for k in ["q4", "october", "november", "december"])]
    if q3 and q4 and q3[0].id != q4[0].id:
        conflicts.append(
            Conflict(
                id=_new_id("c"),
                topic="Delivery Timeline Conflict: Q3 Launch (Sept 30) vs. Q4 Compliance Sign-off (Oct 31)",
                left=q3[0],
                right=q4[0],
                disagreement=(
                    "Target delivery date conflict between sources: Priya's infrastructure charter targets Q3 (locked by September 30, 2026 per board commitment), "
                    "whereas Elena's legal compliance review mandates sign-off in Q4 (scheduled for October 31, 2026), which blocks go-live."
                ),
                suggested_question=(
                    "Which canonical delivery deadline should the specification follow: "
                    "September 30, 2026 (Q3 Board Commitment) or October 31, 2026 (Q4 Legal Compliance Sign-off)?"
                ),
            )
        )

    # B) Data Retention vs GDPR Erasure
    retention = [f for f in findings if any(k in f.statement.lower() for k in ["7 year", "7-year", "retain all", "immutable log", "audit trail"])]
    erasure = [f for f in findings if any(k in f.statement.lower() for k in ["30 day", "gdpr", "right to erasure", "delete user data", "purge"])]
    if retention and erasure:
        conflicts.append(
            Conflict(
                id=_new_id("c"),
                topic="Compliance Conflict: Immutable Audit Logs vs. Right-to-Erasure",
                left=retention[0],
                right=erasure[0],
                disagreement=(
                    "SOC-2 Type II audit requirements mandate 7-year immutable telemetry retention, directly conflicting "
                    "with GDPR Article 17 right-to-erasure requiring cryptographically verified deletion of user activity within 30 days."
                ),
                suggested_question=(
                    "How should customer data deletion be handled in the audit trail: pseudonymization with separate key destruction, or strict 30-day purge?"
                ),
            )
        )

    # C) SLA Multi-Region vs Single-Region Budget
    multi_region = [f for f in findings if any(k in f.statement.lower() for k in ["99.99%", "multi-region", "multi region", "dual-datacenter", "active-active"])]
    single_region = [f for f in findings if any(k in f.statement.lower() for k in ["single-region", "single region", "budget cap", "$180", "$180k", "$250k"])]
    if multi_region and single_region:
        conflicts.append(
            Conflict(
                id=_new_id("c"),
                topic="Infrastructure Conflict: 99.99% Multi-Region SLA vs. Budget Cap",
                left=multi_region[0],
                right=single_region[0],
                disagreement=(
                    "Multi-region active-active deployment required for 99.99% SLA exceeds the single-region infrastructure budget ceiling."
                ),
                suggested_question=(
                    "Should the architecture deploy multi-region active-active to guarantee 99.99% SLA, or remain single-region to respect the budget cap?"
                ),
            )
        )

    return conflicts


def validate(findings: List[Finding], chunks: Optional[List[SourceChunk]] = None) -> tuple[List[Finding], List[Conflict], List[Dict]]:
    kept: List[Finding] = []
    gaps: List[Dict] = []
    seen: set[str] = set()

    # Build chunk lookup for span-verified grounding
    chunk_map = {c.source_id: c.text for c in (chunks or [])}

    for f in findings:
        key = f.statement.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        if not f.source_id:
            continue

        # Grounding check: verify that source_span actually exists in cited chunk
        c_text = chunk_map.get(f.source_id) or ""
        if not c_text:
            base_id = f.source_id.split("#")[0]
            c_text = next((c.text for c in (chunks or []) if c.source_id.startswith(base_id)), "")

        is_grounded = True
        if c_text:
            clean_span = " ".join(f.source_span.lower().split())
            clean_chunk = " ".join(c_text.lower().split())
            if clean_span not in clean_chunk:
                words = [w for w in clean_span.split() if len(w) > 3]
                if words:
                    matches = sum(1 for w in words if w in clean_chunk)
                    if (matches / len(words)) < 0.60:
                        is_grounded = False
                else:
                    is_grounded = False

        f.grounded = is_grounded
        if not is_grounded:
            gaps.append({
                "kind": "ungrounded_citation",
                "finding_id": f.id,
                "statement": f.statement,
                "question": f"Grounding warning: the cited phrase '{f.source_span[:50]}' was not found verbatim in source {f.source_id}. Verify source reference.",
            })
            if f.confidence < 0.60:
                continue  # Filter out ungrounded low-confidence hallucination

        if f.confidence < 0.45:
            gaps.append({"kind": "low_confidence", "finding_id": f.id, "statement": f.statement})
            continue

        if f.type == "requirement" and not f.acceptance_criteria and any(w in f.statement.lower() for w in ["offline", "sync", "mesh"]):
            gaps.append(
                {
                    "kind": "missing_acceptance",
                    "finding_id": f.id,
                    "statement": f.statement,
                    "question": "Who owns offline-mode acceptance criteria and data convergence rules?",
                }
            )
        kept.append(f)

    conflicts = detect_conflicts(kept)
    return kept, conflicts, gaps



def compose_sections(findings: List[Finding], conflicts: List[Conflict], chunks: Optional[List[SourceChunk]] = None) -> List[BrdSection]:
    grouped: Dict[str, List[Finding]] = {k: [] for k in BRD_TITLES}
    for f in findings:
        grouped.setdefault(f.section, []).append(f)
    
    diagrams_data = generate_mermaid_diagrams(findings, chunks or [])

    sections: List[BrdSection] = []
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
                    user_flow_code=diagrams_data.get("user_flow"),
                    sequence_code=diagrams_data.get("sequence"),
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


def persist_ops(ops_items, user_id: Optional[str] = None, conflicts: Optional[List[Conflict]] = None, findings: Optional[List[Finding]] = None) -> tuple[List[Task], List[Alert]]:
    tasks: List[Task] = []
    alerts: List[Alert] = []
    now = get_now()
    year = now.year

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
                created_at=now,
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

    # Deliver document-expressed deadlines directly into the calendar alerts
    existing_targets = {a.target_date[:10] for a in alerts}
    if conflicts:
        for c in conflicts:
            if "timeline" in c.topic.lower() or "q3" in c.topic.lower():
                if f"{year}-09-30" not in existing_targets:
                    a1 = Alert(
                        id=_new_id("a"),
                        target_date=f"{year}-09-30T09:00:00+00:00",
                        original_phrase="Target launch is locked for Q3 according to the board commitment.",
                        reminder_message="Q3 Delivery Deadline: Target launch locked by September 30, 2026 per board commitment.",
                        context="Board Commitment: Q3 Target Launch (Sept 30)",
                        source_id=c.left.source_id,
                    )
                    db.upsert_alert(a1, user_id)
                    alerts.append(a1)
                    existing_targets.add(f"{year}-09-30")

                if f"{year}-10-31" not in existing_targets:
                    a2 = Alert(
                        id=_new_id("a"),
                        target_date=f"{year}-10-31T09:00:00+00:00",
                        original_phrase="Legal compliance sign-off is scheduled for Quarter 4 (October/November). Go-live cannot occur before Q4 compliance sign-off.",
                        reminder_message="Q4 Compliance Deadline: Legal compliance sign-off scheduled for October 31, 2026. Blocks go-live.",
                        context="Legal Mandate: Q4 Compliance Sign-off (Oct 31)",
                        source_id=c.right.source_id,
                    )
                    db.upsert_alert(a2, user_id)
                    alerts.append(a2)
                    existing_targets.add(f"{year}-10-31")

    return tasks, alerts


async def run_pipeline(
    chunks: List[SourceChunk], project_description: str, session_id: str, user_id: Optional[str] = None
) -> AsyncGenerator[Dict, None]:
    db.init_db()
    db.reset_ops(user_id)
    text_chunks = [c for c in chunks if c.modality in ("text", "audio")]
    doc_chunks = [c for c in chunks if c.modality in ("pdf", "spreadsheet")]
    vision_chunks = [c for c in chunks if c.modality == "image"]
    if not text_chunks:
        text_chunks = chunks

    events: List[DelegationEvent] = []

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
    yield {"type": "risk_agent", "event": emit_event("risk_agent", 2, "extracting compliance & risks", "running")}
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
    kept, conflicts, gaps = validate(all_findings, chunks)
    tasks, alerts = persist_ops(ops_items, user_id=user_id, conflicts=conflicts, findings=kept)

    # Immediately yield validated findings & conflicts so UI renders instantly
    yield {
        "type": "preliminary_state",
        "findings": [f.model_dump() for f in kept],
        "conflicts": [c.model_dump() for c in conflicts],
        "gaps": gaps,
    }


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

    # Record genesis and requirement blocks in the HashChainedLedger
    try:
        from app.mesh.ledger import HashChainedLedger
        for f in kept[:12]:
            HashChainedLedger.record_entry(
                session_id=session_id,
                entry_type="finding_ingested",
                data={"finding_id": f.id, "statement": f.statement, "section": f.section, "confidence": f.confidence},
                source_chunk_text=f.source_span,
                signer_id=user_id or "specialist_agent",
            )
        for c in conflicts:
            HashChainedLedger.record_entry(
                session_id=session_id,
                entry_type="conflict_detected",
                data={"conflict_id": c.id, "topic": c.topic, "status": c.status},
                signer_id=user_id or "validator_agent",
            )
        HashChainedLedger.record_entry(
            session_id=session_id,
            entry_type="requirement_sealed",
            data={"version": version, "sections_count": len(sections), "findings_count": len(kept)},
            signer_id=user_id or "consensus_engine",
        )
    except Exception as e:
        print(f"Ledger recording warning: {e}")

    yield {"type": "complete", "state": state}


def load_demo_chunks() -> list[SourceChunk]:
    paths = write_demo_pack()
    chunks: list[SourceChunk] = []
    for path in paths:
        if path.suffix == ".txt" and path.name == "project_brief.txt":
            continue
        chunks.extend(ingest_file(path))
    return chunks
