from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from app import db
from app.clock import fast_forward, get_now, offset_days, reset_clock
from app.config import settings
from app.ingestion import ingest_bytes
from app.model_router import current as router_current
from app.model_router import set_simulate
from app.pipeline import SESSIONS, load_demo_chunks, run_pipeline
from app.schemas import (
    ChatRequest,
    Finding,
    LoginRequest,
    ResolveConflictRequest,
    ScenarioRequest,
    SignUpRequest,
    SourceChunk,
    Task,
)
from app.export import generate_pdf, generate_docx
from app.copilot import run_copilot_chat
from app.scenarios import simulate_what_if_scenario
from app.jira_export import generate_jira_csv, generate_linear_json

app = FastAPI(title="Orbius", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()
UPLOADS: dict[str, list] = {}


@app.get("/api/health")
def health():
    return {"ok": True, "name": "Orbius", "now": get_now().isoformat()}


@app.post("/api/auth/signup")
def signup(req: SignUpRequest):
    existing = db.get_user_by_email(req.email)
    if existing:
        return JSONResponse({"error": "An account with this email already exists."}, status_code=400)
    user = db.create_user(req.email, req.password, req.name)
    user_data = {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}
    return {"user": user_data, "token": user["id"]}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = db.get_user_by_email(req.email)
    if not user or not db.verify_password(req.password, user["password_hash"]):
        return JSONResponse({"error": "Invalid email or password."}, status_code=401)
    user_data = {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}
    return {"user": user_data, "token": user["id"]}


@app.get("/api/auth/me")
def get_me(x_user_id: str | None = Header(None)):
    if not x_user_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    user = db.get_user_by_id(x_user_id)
    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)
    return {"user": {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}}


@app.get("/api/user/sessions")
def user_sessions(x_user_id: str | None = Header(None)):
    if not x_user_id:
        return []
    return db.get_user_sessions(x_user_id)


@app.get("/api/calendar")
def get_calendar(x_user_id: str | None = Header(None)):
    db.fire_due_alerts(x_user_id)
    return db.get_calendar_events(x_user_id)


@app.get("/api/clock")
def clock_state():
    return {"now": get_now().isoformat(), "offset_days": offset_days()}


@app.post("/api/clock/fast-forward")
def clock_ff(days: int = 30):
    now = fast_forward(days)
    fired = db.fire_due_alerts()
    followups = []
    for alert in fired:
        task_id = f"t_{uuid.uuid4().hex[:8]}"
        from app.schemas import Task

        task = Task(
            id=task_id,
            type="draft_email",
            context=f"Follow-up after alert: {alert.context}",
            payload={
                "recipient": "Client (unspecified)",
                "subject": f"Reminder: {alert.context}",
                "body": alert.reminder_message + "\n\nThis draft was created when the scheduled alert fired.",
            },
            source_id=alert.source_id,
            source_span=alert.original_phrase,
            confidence=0.8,
            created_at=now,
        )
        db.upsert_task(task)
        followups.append(task.model_dump(mode="json"))
    return {
        "now": now.isoformat(),
        "offset_days": offset_days(),
        "fired": [a.model_dump(mode="json") for a in fired],
        "followups": followups,
        "alerts": [a.model_dump(mode="json") for a in db.list_alerts()],
        "tasks": [t.model_dump(mode="json") for t in db.list_tasks()],
    }


@app.post("/api/clock/reset")
def clock_reset():
    now = reset_clock()
    return {"now": now.isoformat(), "offset_days": offset_days()}


@app.get("/api/router")
def router_get():
    return router_current()


@app.post("/api/router/simulate")
def router_sim(on: bool = True):
    return set_simulate(on)


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), session_id: str = Form("demo"), x_user_id: str | None = Header(None)):
    existing = UPLOADS.get(session_id, [])
    dest_dir = settings.upload_dir / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_chunks = []
    for f in files:
        data = await f.read()
        path = dest_dir / f.filename
        file_chunks = ingest_bytes(f.filename, data, path)
        new_chunks.extend(file_chunks)
    
    # Merge with existing files
    new_names = {f.filename for f in files}
    merged_chunks = [c for c in existing if c.file_name not in new_names] + new_chunks
    UPLOADS[session_id] = merged_chunks
    db.reset_ops(x_user_id)

    # Return distinct list of uploaded files with metadata
    unique_files = []
    seen = set()
    for c in merged_chunks:
        if c.file_name not in seen:
            seen.add(c.file_name)
            unique_files.append({"name": c.file_name, "modality": c.modality})

    return {"files": unique_files, "chunks": [c.model_dump() for c in merged_chunks]}


@app.delete("/api/upload/{session_id}/{filename}")
def delete_file(session_id: str, filename: str):
    existing = UPLOADS.get(session_id, [])
    merged = [c for c in existing if c.file_name != filename]
    UPLOADS[session_id] = merged
    unique_files = []
    seen = set()
    for c in merged:
        if c.file_name not in seen:
            seen.add(c.file_name)
            unique_files.append({"name": c.file_name, "modality": c.modality})
    return {"files": unique_files, "count": len(merged)}


@app.delete("/api/upload/{session_id}")
def clear_files(session_id: str):
    UPLOADS[session_id] = []
    return {"files": [], "count": 0}


@app.post("/api/session/reset")
def reset_session(session_id: str = "demo", x_user_id: str | None = Header(None)):
    if session_id in SESSIONS:
        del SESSIONS[session_id]
    if session_id in UPLOADS:
        del UPLOADS[session_id]
    db.reset_ops(x_user_id)
    with db.connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    return {"ok": True}


@app.get("/api/generate")
async def generate(session_id: str = "demo", project_description: str = "", x_user_id: str | None = Header(None)):
    chunks = UPLOADS.get(session_id) or []
    if not chunks and project_description.strip():
        chunks = [
            SourceChunk(
                source_id=f"proj_note_{uuid.uuid4().hex[:6]}",
                file_name="Project Notes & Context",
                modality="text",
                page_or_ts="note",
                text=project_description.strip(),
            )
        ]
        UPLOADS[session_id] = chunks

    if not chunks:
        async def empty_events():
            yield {
                "event": "section",
                "data": json.dumps({
                    "section": {
                        "id": "notice",
                        "title": "Awaiting Documents or Notes",
                        "body": "Please upload at least one document (emails, transcripts, PDFs, sheets, wireframes) or enter project notes in the left panel to generate your BRD."
                    },
                    "router": router_current()
                })
            }
            yield {
                "event": "complete",
                "data": json.dumps({
                    "state": {
                        "session_id": session_id,
                        "version": 1,
                        "project_description": project_description,
                        "chunks": [],
                        "findings": [],
                        "conflicts": [],
                        "gaps": [],
                        "sections": [{
                            "id": "notice",
                            "title": "Awaiting Documents or Notes",
                            "body": "Please upload project files or input project notes to begin multi-agent extraction."
                        }],
                        "tasks": [],
                        "alerts": [],
                        "events": [],
                        "changelog": [],
                        "router": router_current(),
                        "questions": []
                    }
                })
            }
        return EventSourceResponse(empty_events())

    async def events():
        async for payload in run_pipeline(chunks, project_description, session_id, x_user_id):
            yield {"event": payload.get("type", "message"), "data": json.dumps(payload, default=str)}

    return EventSourceResponse(events())


@app.get("/api/session/{session_id}")
def get_session(session_id: str, x_user_id: str | None = Header(None)):
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "not found"}, status_code=404)
    state = {
        **state,
        "tasks": [t.model_dump(mode="json") for t in db.list_tasks(x_user_id)],
        "alerts": [a.model_dump(mode="json") for a in db.list_alerts(x_user_id)],
    }
    return state


@app.post("/api/conflicts/resolve")
def resolve(req: ResolveConflictRequest, session_id: str = "demo"):
    state = SESSIONS.get(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    updated = []
    for c in state.get("conflicts", []):
        if c["id"] == req.conflict_id:
            c["status"] = "resolved"
            c["resolution"] = f"Kept {req.keep}. {req.note}".strip()
        updated.append(c)
    state["conflicts"] = updated
    from app.pipeline import compose_sections
    from app.schemas import Conflict, Finding

    findings = [Finding.model_validate(f) for f in state["findings"]]
    conflicts = [Conflict.model_validate(c) for c in updated]
    state["sections"] = [s.model_dump() for s in compose_sections(findings, conflicts)]
    SESSIONS[session_id] = state
    return state


@app.get("/api/tasks")
def tasks(x_user_id: str | None = Header(None)):
    return [t.model_dump(mode="json") for t in db.list_tasks(x_user_id)]


@app.post("/api/tasks/{task_id}/{action}")
def task_action(task_id: str, action: str):
    if action not in {"approved", "dismissed"}:
        return JSONResponse({"error": "invalid action"}, status_code=400)
    task = db.set_task_status(task_id, action)
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    return task.model_dump(mode="json")


@app.get("/api/alerts")
def alerts(x_user_id: str | None = Header(None)):
    db.fire_due_alerts(x_user_id)
    return [a.model_dump(mode="json") for a in db.list_alerts(x_user_id)]


@app.get("/api/export/{session_id}")
def export_md(session_id: str):
    state = SESSIONS.get(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    lines = [f"# Orbius BRD — {session_id}", f"_Version {state.get('version', 1)}_", ""]
    for section in state.get("sections", []):
        lines.append(f"## {section['title']}")
        lines.append(section["body"])
        lines.append("")
    out = settings.upload_dir / f"{session_id}_brd.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return FileResponse(out, filename="orbius-brd.md")


@app.get("/api/export/{session_id}/pdf")
def export_pdf(session_id: str):
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    out_path = settings.upload_dir / f"{session_id}_brd.pdf"
    generate_pdf(state, session_id, out_path)
    return FileResponse(out_path, media_type="application/pdf", filename=f"orbius-brd-{session_id}.pdf")


@app.get("/api/export/{session_id}/docx")
def export_word(session_id: str):
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    out_path = settings.upload_dir / f"{session_id}_brd.docx"
    generate_docx(state, session_id, out_path)
    return FileResponse(
        out_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"orbius-brd-{session_id}.docx",
    )


@app.post("/api/chat")
def copilot_chat(req: ChatRequest):
    state = SESSIONS.get(req.session_id) or db.load_session(req.session_id)
    findings = [Finding.model_validate(f) for f in (state.get("findings") if state else [])]
    chunks = [SourceChunk.model_validate(c) for c in (state.get("chunks") if state else (UPLOADS.get(req.session_id) or []))]
    project_desc = state.get("project_description", "") if state else ""
    return run_copilot_chat(req.message, req.history, findings, chunks, project_desc)


@app.post("/api/scenario/simulate")
def scenario_simulate(req: ScenarioRequest):
    state = SESSIONS.get(req.session_id) or db.load_session(req.session_id)
    findings = [Finding.model_validate(f) for f in (state.get("findings") if state else [])]
    chunks = [SourceChunk.model_validate(c) for c in (state.get("chunks") if state else (UPLOADS.get(req.session_id) or []))]
    return simulate_what_if_scenario(req.scenario_type, req.parameter_value, req.custom_prompt, findings, chunks)


@app.get("/api/export/{session_id}/jira")
def export_jira(session_id: str):
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    findings = [Finding.model_validate(f) for f in state.get("findings", [])]
    tasks = [Task.model_validate(t) for t in state.get("tasks", [])]
    csv_content = generate_jira_csv(findings, tasks)
    out_path = settings.upload_dir / f"{session_id}_jira.csv"
    out_path.write_text(csv_content, encoding="utf-8")
    return FileResponse(out_path, media_type="text/csv", filename=f"orbius-jira-{session_id}.csv")


@app.get("/api/export/{session_id}/linear")
def export_linear(session_id: str):
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    findings = [Finding.model_validate(f) for f in state.get("findings", [])]
    tasks = [Task.model_validate(t) for t in state.get("tasks", [])]
    json_content = generate_linear_json(findings, tasks)
    out_path = settings.upload_dir / f"{session_id}_linear.json"
    out_path.write_text(json_content, encoding="utf-8")
    return FileResponse(out_path, media_type="application/json", filename=f"orbius-linear-{session_id}.json")


@app.get("/api/session/{session_id}/test-suite")
def get_test_suite(session_id: str):
    from app.prototype_agent import generate_gherkin_test_suite
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    findings = [Finding.model_validate(f) for f in (state.get("findings", []) if state else [])]
    return {"test_cases": generate_gherkin_test_suite(findings)}


@app.get("/api/session/{session_id}/ripple-graph")
def get_ripple_graph(session_id: str):
    from app.prototype_agent import generate_ripple_graph
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    findings = [Finding.model_validate(f) for f in (state.get("findings", []) if state else [])]
    tasks = [Task.model_validate(t) for t in (state.get("tasks", []) if state else [])]
    return generate_ripple_graph(findings, tasks)


@app.get("/api/scorecard")
def get_scorecard():
    from app.prototype_agent import get_accuracy_scorecard
    return get_accuracy_scorecard()


@app.post("/api/meeting/interrupter")
def meeting_interrupter(payload: dict):
    speech = payload.get("speech", "").lower()
    interrupted = False
    interruption_reason = ""
    suggested_correction = ""

    if "q4" in speech or "october" in speech or "november" in speech or "delay launch" in speech:
        interrupted = True
        interruption_reason = "⚠️ CONFLICT DETECTED: Speaker proposed Q4 launch window, which directly contradicts Priya Mehta's Q3 locked commitment!"
        suggested_correction = "Ask: 'Priya locked Q3 in the kickoff memo — do we have sign-off to shift the target to October/Q4?'"
    elif "200k" in speech or "250k" in speech or "over budget" in speech or "300,000" in speech:
        interrupted = True
        interruption_reason = "⚠️ BUDGET CAP EXCEEDED: Proposed spending exceeds Marcus Chen's strict $180,000 ceiling!"
        suggested_correction = "Ask: 'Marcus Chen capped total budget at $180k. Where is the additional funding sourced from?'"
    elif "no 2fa" in speech or "skip 2fa" in speech or "simple password" in speech:
        interrupted = True
        interruption_reason = "⚠️ SECURITY VIOLATION: Bypassing 2FA violates Elena Rostova's architectural & PCI-DSS mandate!"
        suggested_correction = "Enforce: Store manager overrides must require mandatory 2FA biometric or mobile PIN verification."

    return {
        "interrupted": interrupted,
        "interruption_reason": interruption_reason,
        "suggested_correction": suggested_correction,
        "live_timestamp": get_now().isoformat()
    }


@app.get("/api/download-test-pack")
def download_test_pack():
    zip_path = Path("..") / "orbius_test_dataset.zip"
    if not zip_path.exists():
        zip_path = Path("orbius_test_dataset.zip")
    if not zip_path.exists():
        import subprocess, sys
        subprocess.run([sys.executable, str(Path("..") / "generate_test_dataset.py")], check=False)
    
    if zip_path.exists():
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename="orbius_test_dataset.zip"
        )
    return JSONResponse({"error": "Dataset zip not found"}, status_code=404)


@app.get("/")
def root():
    return {"service": "orbius-api", "docs": "/docs"}
