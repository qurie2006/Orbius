from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, File, Form, Header, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sse_starlette.sse import EventSourceResponse

from app import db
from app.clock import fast_forward, get_now, offset_days, reset_clock
from app.config import settings
from app.ingestion import ingest_bytes
from app.model_router import current as router_current, set_active_model as router_set_active_model
from app.model_router import set_simulate
from app.pipeline import SESSIONS, load_demo_chunks, run_pipeline
from app.rate_limiter import RateLimitMiddleware
from app.file_security import validate_file_upload, sanitize_filename, MAX_FILE_BYTES, MAX_BATCH_BYTES
from app.schemas import (
    ChatRequest,
    Finding,
    LoginRequest,
    ResetPasswordRequest,
    ResolveConflictRequest,
    ScenarioRequest,
    SignUpRequest,
    SourceChunk,
    Task,
)
from app.export import generate_pdf, generate_docx
from app.copilot import run_copilot_chat
from app.scenarios import simulate_what_if_scenario
from app.jira_export import generate_jira_csv, generate_linear_json, push_to_jira_api
from app.mesh.ledger import HashChainedLedger
from app.mesh.relay import mesh_manager


app = FastAPI(title="Orbius", version="0.1.0")
cors_origins_list = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add sliding-window tiered rate limiter
app.add_middleware(RateLimitMiddleware)

db.init_db()
UPLOADS: dict[str, list] = {}


def get_auth_user(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)) -> Optional[dict]:
    token = authorization or x_user_id
    if not token:
        return None
    token_str = token.replace("Bearer ", "").strip()
    session_data = db.verify_session_token(token_str)
    if not session_data:
        return None
    user_id = session_data.get("sub")
    if not user_id:
        return None
    return db.get_user_by_id(user_id)


def get_tenant_folder(session_id: str, user: Optional[dict] = None) -> str:
    """Returns an isolated disk folder and cache namespace for the user/tenant."""
    if user and user.get("id"):
        uid = str(user["id"])
        return uid if uid.startswith("usr_") else f"usr_{uid}"
    if session_id.startswith("usr_"):
        # Derive tenant folder from user-scoped session ID (e.g. usr_12345_workspace -> usr_12345)
        return session_id.split("_workspace")[0]
    # Anonymous isolated workspace namespace
    return session_id if session_id.startswith("anon_") else f"anon_{session_id}"


def check_session_access(session_id: str, user: Optional[dict] = None) -> bool:
    """Multi-tenant security check: verifies that the caller owns this workspace.
    Prevents User B or anonymous callers from accessing or mutating User A's files and BRD data."""
    if session_id == "demo":
        return True
    owner_id = db.get_session_owner(session_id)
    if not owner_id:
        if session_id.startswith("usr_"):
            target_user = session_id.split("_workspace")[0]
            if not user or str(user.get("id")) != target_user:
                return False
        return True
    if not user:
        return False
    user_id = str(user.get("id", ""))
    return user_id == owner_id or user_id.replace("usr_", "") == owner_id.replace("usr_", "")


def get_uploads_cache(session_id: str, user: Optional[dict] = None) -> list:
    """Retrieves uploaded chunks from tenant-isolated in-memory cache."""
    tenant = get_tenant_folder(session_id, user)
    cache_key = f"{tenant}:{session_id}"
    if cache_key in UPLOADS:
        return UPLOADS[cache_key]
    # Check alternate or direct keys
    for k, v in UPLOADS.items():
        if k == session_id or k.endswith(f":{session_id}") or k == f"usr_{session_id}" or k.startswith(f"{tenant}:"):
            if v:
                return v
    return []


def set_uploads_cache(session_id: str, chunks: list, user: Optional[dict] = None) -> None:
    """Persists uploaded chunks into tenant-isolated in-memory cache."""
    tenant = get_tenant_folder(session_id, user)
    cache_key = f"{tenant}:{session_id}"
    UPLOADS[cache_key] = chunks
    # Also register by session_id for guaranteed lookup
    UPLOADS[f":{session_id}"] = chunks


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"ok": True, "name": "Orbius", "now": get_now().isoformat()}


@app.post("/api/auth/signup")
def signup(req: SignUpRequest):
    if len(req.password.strip()) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters long for security."}, status_code=400)
    if not req.email.strip() or "@" not in req.email:
        return JSONResponse({"error": "A valid email address is required."}, status_code=400)
    existing = db.get_user_by_email(req.email)
    if existing:
        return JSONResponse({"error": "An account with this email already exists."}, status_code=400)
    user = db.create_user(req.email, req.password, req.name)
    user_data = {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}
    token = db.create_session_token(user["id"], user["email"])
    return {"user": user_data, "token": token}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = db.get_user_by_email(req.email)
    if not user or not db.verify_password(req.password, user["password_hash"], user.get("salt")):
        return JSONResponse({"error": "Invalid email or password."}, status_code=401)
    user_data = {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}
    token = db.create_session_token(user["id"], user["email"])
    return {"user": user_data, "token": token}


@app.post("/api/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    if len(req.new_password.strip()) < 8:
        return JSONResponse({"error": "New password must be at least 8 characters long."}, status_code=400)
    user = db.get_user_by_email(req.email)
    if not user:
        return JSONResponse({"error": "Account not found with this email."}, status_code=404)
    success = db.update_password(req.email, req.new_password)
    if not success:
        return JSONResponse({"error": "Failed to update password."}, status_code=500)
    return {"status": "ok", "message": "Password successfully reset with salted PBKDF2 hash."}


@app.get("/api/auth/me")
def get_me(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    user = get_auth_user(authorization, x_user_id)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return {"user": {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}}


@app.get("/api/user/sessions")
def user_sessions(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    user = get_auth_user(authorization, x_user_id)
    if not user:
        return []
    return db.get_user_sessions(user["id"])




@app.get("/api/calendar")
def get_calendar(x_user_id: Optional[str] = Header(None)):
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


@app.post("/api/router/switch")
def router_switch(payload: dict):
    model = payload.get("model") or settings.primary_model
    return router_set_active_model(model)


ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".eml", ".csv", ".pdf", ".docx", ".xlsx", ".xls", ".zip",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp3", ".wav", ".m4a", ".ogg",
    ".webm", ".weba", ".aac", ".flac", ".wma", ".wmb", ".wmv"
}
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB limit


@app.post("/api/upload")
async def upload(
    files: list[UploadFile] = File(...),
    session_id: str = Form("demo"),
    session_id_query: Optional[str] = Query(None, alias="session_id"),
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    session_id = session_id_query if session_id_query and session_id == "demo" else session_id

    # Security check: Ensure caller has permission to upload to this session
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not own this workspace."}, status_code=403)

    tenant_folder = get_tenant_folder(session_id, user)
    existing = get_uploads_cache(session_id, user)
    dest_dir = settings.upload_dir / tenant_folder / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_chunks = []
    new_names = set()
    total_batch_size = 0

    for f in files:
        data = await f.read()
        total_batch_size += len(data)
        if total_batch_size > MAX_BATCH_BYTES:
            return JSONResponse(
                {"error": f"Total batch upload exceeds maximum allowed size of {MAX_BATCH_BYTES // (1024 * 1024)}MB."},
                status_code=400,
            )

        # Deep Security Validation (magic bytes, path traversal sanitization, dangerous extension blocking)
        is_valid, safe_name, sec_err = validate_file_upload(f.filename or "upload", data)
        if not is_valid:
            return JSONResponse({"error": sec_err}, status_code=400)

        path = dest_dir / safe_name
        file_chunks = ingest_bytes(safe_name, data, path)
        new_chunks.extend(file_chunks)
        new_names.add(safe_name)

    # Merge with existing files for this tenant
    merged_chunks = [c for c in existing if c.file_name not in new_names] + new_chunks
    set_uploads_cache(session_id, merged_chunks, user)
    db.reset_ops(user["id"] if user else None)

    # Automatically index all chunks into Vector Database
    try:
        from app.vector_store import vector_store
        vector_store.add_chunks(f"{tenant_folder}_{session_id}", merged_chunks)
    except Exception:
        pass

    # Return distinct list of uploaded files with metadata
    unique_files = []
    seen = set()
    for c in merged_chunks:
        if c.file_name not in seen:
            seen.add(c.file_name)
            count = sum(1 for ch in merged_chunks if ch.file_name == c.file_name)
            unique_files.append({
                "name": c.file_name,
                "file_name": c.file_name,
                "filename": c.file_name,
                "modality": c.modality,
                "chunks_count": count,
            })

    return {"files": unique_files, "chunks": [c.model_dump() for c in merged_chunks]}


@app.delete("/api/upload/{session_id}/{filename}")
def delete_file(
    session_id: str,
    filename: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not own this workspace."}, status_code=403)

    safe_name = sanitize_filename(filename)
    existing = get_uploads_cache(session_id, user)
    merged = [c for c in existing if c.file_name != safe_name]
    set_uploads_cache(session_id, merged, user)
    unique_files = []
    seen = set()
    for c in merged:
        if c.file_name not in seen:
            seen.add(c.file_name)
            count = sum(1 for ch in merged if ch.file_name == c.file_name)
            unique_files.append({
                "name": c.file_name,
                "file_name": c.file_name,
                "filename": c.file_name,
                "modality": c.modality,
                "chunks_count": count,
            })
    return {"files": unique_files, "count": len(merged)}


@app.delete("/api/upload/{session_id}")
def clear_files(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not own this workspace."}, status_code=403)

    set_uploads_cache(session_id, [], user)
    return {"files": [], "count": 0}


@app.get("/api/upload/{session_id}/preview/{filename}")
def preview_file(
    session_id: str,
    filename: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not own this workspace."}, status_code=403)

    safe_name = sanitize_filename(filename)
    chunks = get_uploads_cache(session_id, user)
    file_chunks = [c for c in chunks if c.file_name == safe_name]

    if not file_chunks:
        tenant_folder = get_tenant_folder(session_id, user)
        dest_path = settings.upload_dir / tenant_folder / session_id / safe_name
        if not dest_path.exists():
            dest_path = settings.upload_dir / session_id / safe_name
        if not dest_path.exists():
            dest_path = Path(__file__).resolve().parent.parent / safe_name
        if dest_path.exists():
            try:
                content = dest_path.read_text(encoding="utf-8", errors="ignore")
                return {
                    "filename": safe_name,
                    "file_name": safe_name,
                    "name": safe_name,
                    "modality": "text",
                    "chunk_count": 1,
                    "chunks_count": 1,
                    "full_text": content,
                    "content": content,
                    "chunks": [{"page_or_ts": "full", "text": content}],
                }
            except Exception:
                pass
        return JSONResponse({"error": f"File '{safe_name}' content is not currently cached."}, status_code=404)

    mod = file_chunks[0].modality
    full_text = "\n\n---\n\n".join(c.text for c in file_chunks)
    return {
        "filename": filename,
        "file_name": filename,
        "name": filename,
        "modality": mod,
        "chunk_count": len(file_chunks),
        "chunks_count": len(file_chunks),
        "full_text": full_text,
        "content": full_text,
        "chunks": [{"page_or_ts": c.page_or_ts, "text": c.text} for c in file_chunks],
    }


@app.get("/api/upload/{session_id}/raw/{filename}")
def get_raw_file(
    session_id: str,
    filename: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    """Serve raw uploaded file for images, audio playback, and document previews with tenant isolation."""
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to view this file."}, status_code=403)

    safe_name = sanitize_filename(filename)
    tenant_folder = get_tenant_folder(session_id, user)
    dest_path = settings.upload_dir / tenant_folder / session_id / safe_name
    if not dest_path.exists():
        dest_path = settings.upload_dir / session_id / safe_name
    if not dest_path.exists():
        dest_path = Path(__file__).resolve().parent.parent / safe_name
    if dest_path.exists():
        return FileResponse(str(dest_path))
    return JSONResponse({"error": "File not found"}, status_code=404)


class RagChatPayload(BaseModel):
    session_id: str = "demo"
    message: str
    history: Optional[List[Dict[str, str]]] = None


@app.post("/api/rag/chat")
async def rag_chat(payload: RagChatPayload):
    """Conversational RAG endpoint: answers dynamic questions using vector search and strict clean formatting."""
    session_id = payload.session_id or "demo"
    user_query = payload.message.strip()
    history = payload.history or []

    if not user_query:
        return {"reply": "Please ask any question about your specifications or uploaded data.", "sources": []}

    # 1. Semantic search in vector store
    from app.vector_store import vector_store
    relevant_chunks = vector_store.search(session_id, user_query, top_k=6)

    # 2. Extract current state specs & tasks
    state = SESSIONS.get(session_id) or db.load_session(session_id) or {}
    sections = state.get("sections", []) if isinstance(state, dict) else [s.model_dump() for s in getattr(state, "sections", [])]
    tasks = state.get("tasks", []) if isinstance(state, dict) else [t.model_dump() for t in getattr(state, "tasks", [])]
    conflicts = state.get("conflicts", []) if isinstance(state, dict) else [c.model_dump() for c in getattr(state, "conflicts", [])]

    context_snippets = []
    sources = []
    for c in relevant_chunks:
        meta = c.get("metadata", {})
        fname = meta.get("file_name", "Ingested Document")
        sources.append({"file_name": fname, "snippet": c.get("text", "")[:120]})
        context_snippets.append(f"Source: {fname} ({meta.get('modality', 'text')}):\n{c.get('text', '')}")

    if not context_snippets:
        all_chunks = state.get("chunks", []) if isinstance(state, dict) else getattr(state, "chunks", [])
        for c in all_chunks[:5]:
            fname = c.get("file_name", "Document") if isinstance(c, dict) else getattr(c, "file_name", "Document")
            txt = c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")
            context_snippets.append(f"Source: {fname}:\n{txt[:500]}")
            sources.append({"file_name": fname, "snippet": txt[:120]})

    specs_summary = []
    for s in sections[:5]:
        s_title = s.get("title", "Spec") if isinstance(s, dict) else getattr(s, "title", "Spec")
        s_content = s.get("content", "") if isinstance(s, dict) else getattr(s, "content", "")
        specs_summary.append(f"- {s_title}: {s_content[:250]}")

    conflicts_summary = []
    for c in conflicts[:4]:
        c_desc = c.get("description", "") if isinstance(c, dict) else getattr(c, "description", "")
        conflicts_summary.append(f"- Conflict: {c_desc}")

    context_text = "\n\n".join(context_snippets) if context_snippets else "No source documents uploaded yet."
    specs_text = "\n".join(specs_summary) if specs_summary else "No formal specifications generated yet."
    conflicts_text = "\n".join(conflicts_summary) if conflicts_summary else "No conflicts detected."

    system_instruction = (
        "You are Orbius Conversational RAG Copilot, an elite technical systems analyst and requirements engineer. "
        "Answer the user's question with direct, insightful, and dynamic analysis based on the retrieved project context, "
        "specifications, and data. NEVER give canned, repetitive, or generic replies. Answer the exact question asked.\n\n"
        "STRICT FORMATTING REQUIREMENTS:\n"
        "1. DO NOT use asterisks for bolding (NEVER output '**').\n"
        "2. DO NOT use escaped backslashes (NEVER output '\\').\n"
        "3. Use clean sentence casing, numbered steps (1., 2.), or bullet points with '•' or dashes '-'.\n"
        "4. Keep your answer highly readable, professional, and clear."
    )

    history_formatted = []
    for h in history[-6:]:
        role = "User" if h.get("role") == "user" else "Assistant"
        content = h.get("content", "").replace("**", "").replace("\\", "")
        history_formatted.append(f"{role}: {content}")
    history_text = "\n".join(history_formatted)

    full_prompt = (
        f"{system_instruction}\n\n"
        f"=== RETRIEVED CONTEXT FROM INGESTED DOCUMENTS ===\n{context_text}\n\n"
        f"=== CURRENT SPECIFICATIONS & ARCHITECTURE ===\n{specs_text}\n\n"
        f"=== KNOWN CONFLICTS ===\n{conflicts_text}\n\n"
        f"=== RECENT CONVERSATION ===\n{history_text}\n\n"
        f"User Question: {user_query}\n\n"
        "Orbius Copilot Response:"
    )

    try:
        from app.config import settings
        import os
        from google import genai
        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=settings.primary_model,
                contents=full_prompt
            )
            raw_reply = getattr(resp, "text", "") or ""
        else:
            raw_reply = f"Based on your documents: {context_snippets[0][:200] if context_snippets else 'No specifications found.'}"
    except Exception as e:
        raw_reply = f"Regarding '{user_query}': {context_snippets[0][:300] if context_snippets else 'Please ensure relevant files are uploaded.'}"

    # Strip any stray '**' and '\\'
    cleaned_reply = raw_reply.replace("**", "").replace("\\", "").replace("\r\n", "\n").strip()
    return {
        "reply": cleaned_reply,
        "sources": sources[:4],
        "model": settings.primary_model
    }


@app.get("/api/graph")
def get_knowledge_graph(
    session_id: str = "demo",
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    """Interactive Knowledge Graph / RAG Graph endpoint with tenant isolation."""
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to view this knowledge graph."}, status_code=403)
    from app.graph_generator import generate_knowledge_graph
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    return generate_knowledge_graph(state)


@app.get("/api/brd/pdf")
def download_brd_pdf_stream(
    session_id: str = "demo",
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    """Download executive Business Requirements Document (BRD) as high-grade PDF with tenant isolation."""
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to download this BRD."}, status_code=403)
    from app.brd_pdf import generate_brd_pdf
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "Session state not found"}, status_code=404)
    state_dict = state if isinstance(state, dict) else (state.model_dump() if hasattr(state, "model_dump") else {})
    pdf_bytes = generate_brd_pdf(state_dict)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Orbius_BRD_{session_id}.pdf"'}
    )


@app.get("/api/mcp/manifest")
def mcp_manifest():
    """Model Context Protocol (MCP) server manifest and tool capabilities."""
    from app.mcp_server import AVAILABLE_MCP_TOOLS
    return {
        "name": "Orbius Autonomous BRD & RAG Server",
        "version": "1.0.0",
        "protocolVersion": "2024-11-05",
        "description": "Model Context Protocol interface for Orbius multi-agent intelligence and specifications.",
        "tools": [t.model_dump() for t in AVAILABLE_MCP_TOOLS]
    }


@app.get("/api/mcp/tools")
def mcp_tools_list():
    """List all available MCP tools."""
    from app.mcp_server import AVAILABLE_MCP_TOOLS
    return {"tools": [t.model_dump() for t in AVAILABLE_MCP_TOOLS]}


@app.post("/api/mcp/tools/call")
async def mcp_tools_call(payload: dict):
    """Directly execute an MCP tool."""
    name = payload.get("name")
    arguments = payload.get("arguments", {})
    from app.mcp_server import execute_mcp_tool
    from app.pipeline import run_pipeline
    res = await execute_mcp_tool(name, arguments, SESSIONS, run_pipeline)
    return {"result": res}


@app.post("/api/mcp/rpc")
async def mcp_rpc(request: dict):
    """Standard Model Context Protocol JSON-RPC 2.0 handler."""
    from app.mcp_server import handle_mcp_rpc, MCPJsonRpcRequest
    from app.pipeline import run_pipeline
    req_obj = MCPJsonRpcRequest.model_validate(request)
    resp = await handle_mcp_rpc(req_obj, SESSIONS, run_pipeline)
    return resp.model_dump()


@app.get("/api/session/new")
@app.post("/api/session/new")
def new_session():
    new_id = f"proj_{uuid.uuid4().hex[:8]}"
    return {"session_id": new_id, "created_at": get_now().isoformat()}


@app.get("/api/projects")
def list_projects(authorization: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None)):
    user = get_auth_user(authorization, x_user_id)
    with db.connect() as conn:
        if user:
            rows = conn.execute(
                "SELECT id, updated_at, context_json FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, updated_at, context_json FROM sessions WHERE user_id IS NULL OR id = 'demo' ORDER BY updated_at DESC"
            ).fetchall()
    projects = []
    seen = set()
    for r in rows:
        seen.add(r["id"])
        try:
            ctx = json.loads(r["context_json"])
            desc = ctx.get("project_description") or "Enterprise Project"
            files_count = len(ctx.get("chunks") or [])
            findings_count = len(ctx.get("findings") or [])
            version = ctx.get("version", 1)
        except Exception:
            desc = "Project"
            files_count = 0
            findings_count = 0
            version = 1
        projects.append({
            "session_id": r["id"],
            "updated_at": r["updated_at"],
            "description": desc,
            "files_count": files_count,
            "findings_count": findings_count,
            "version": version,
        })
    return projects


@app.post("/api/demo/load")
def load_demo(session_id: str = "demo"):
    chunks = load_demo_chunks()
    UPLOADS[session_id] = chunks
    unique = list({c.file_name: c for c in chunks}.values())
    return {
        "status": "loaded",
        "session_id": session_id,
        "count": len(chunks),
        "files": [{"name": c.file_name, "modality": c.modality} for c in unique],
    }


@app.post("/api/session/reset")
def reset_session(session_id: str = "demo", x_user_id: Optional[str] = Header(None)):
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
async def generate(
    session_id: str = "demo",
    project_description: str = "",
    token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id or token)
    if not check_session_access(session_id, user):
        async def denied_events():
            yield {"event": "error", "data": json.dumps({"error": "Access denied: You do not own this workspace."})}
        return EventSourceResponse(denied_events())

    chunks = get_uploads_cache(session_id, user)
    if not chunks:
        # 1. Restore from persisted SQLite session
        saved_state = db.load_session(session_id)
        if saved_state and saved_state.get("chunks"):
            try:
                chunks = [SourceChunk.model_validate(c) for c in saved_state["chunks"]]
                set_uploads_cache(session_id, chunks, user)
            except Exception:
                pass

    if not chunks:
        # 2. Restore from files in upload_dir if available
        tenant_folder = get_tenant_folder(session_id, user)
        candidate_dirs = [
            settings.upload_dir / tenant_folder / session_id,
            settings.upload_dir / session_id,
            settings.upload_dir / f"usr_{tenant_folder}" / session_id,
        ]
        if settings.upload_dir.exists():
            for sub in settings.upload_dir.iterdir():
                if sub.is_dir() and (sub / session_id).is_dir():
                    candidate_dirs.append(sub / session_id)

        disk_chunks = []
        for dest_dir in candidate_dirs:
            if dest_dir.exists():
                for p in sorted(dest_dir.iterdir()):
                    if p.is_file():
                        try:
                            data = p.read_bytes()
                            disk_chunks.extend(ingest_bytes(p.name, data, p))
                        except Exception:
                            pass
                if disk_chunks:
                    chunks = disk_chunks
                    set_uploads_cache(session_id, chunks, user)
                    break

    if not chunks and session_id == "demo":
        # 3. For demo session, fallback to prepackaged demo chunks
        chunks = load_demo_chunks()
        set_uploads_cache(session_id, chunks, user)

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
        set_uploads_cache(session_id, chunks, user)

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

    seq = 0
    effective_user_id = user["id"] if user else (x_user_id or None)

    async def events():
        nonlocal seq
        async for payload in run_pipeline(chunks, project_description, session_id, effective_user_id):
            seq += 1
            if payload.get("type") == "complete":
                state = payload.get("state", {})
                HashChainedLedger.record_entry(
                    session_id=session_id,
                    entry_type="brd_generated",
                    data={
                        "version": state.get("version", 1),
                        "findings_count": len(state.get("findings", [])),
                        "conflicts_count": len(state.get("conflicts", [])),
                    },
                    source_chunk_text=f"{session_id}:{len(chunks)}",
                    signer_id=effective_user_id or "system",
                )
            yield {"id": str(seq), "event": payload.get("type", "message"), "data": json.dumps(payload, default=str)}

    return EventSourceResponse(events())



@app.get("/api/session/{session_id}")
def get_session(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to access this workspace."}, status_code=403)

    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "not found"}, status_code=404)
    caller_id = user["id"] if user else x_user_id
    state = {
        **state,
        "tasks": [t.model_dump(mode="json") for t in db.list_tasks(caller_id)],
        "alerts": [a.model_dump(mode="json") for a in db.list_alerts(caller_id)],
    }
    return state


@app.post("/api/conflicts/resolve")
def resolve(
    req: ResolveConflictRequest,
    session_id: str = "demo",
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to modify this workspace."}, status_code=403)
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    updated = []
    adopted_stmt = None
    adopted_section = "functional_requirements"
    topic_name = "Conflict"

    for c in state.get("conflicts", []):
        if c["id"] == req.conflict_id:
            c["status"] = "resolved"
            chosen_side = "A" if req.keep in ("left", "a") else "B"
            left_obj = c.get("left") or {}
            right_obj = c.get("right") or {}
            if chosen_side == "A":
                adopted_stmt = left_obj.get("statement") or c.get("statement_a") or "Option A requirement adopted."
                adopted_section = left_obj.get("section") or "functional_requirements"
            else:
                adopted_stmt = right_obj.get("statement") or c.get("statement_b") or "Option B requirement adopted."
                adopted_section = right_obj.get("section") or "functional_requirements"

            topic_name = c.get("topic", "Conflict")
            c["resolution"] = f"Adopted Option {chosen_side}: {adopted_stmt}"
            c["adopted_option"] = chosen_side
            c["adopted_statement"] = adopted_stmt
        updated.append(c)
    state["conflicts"] = updated

    from app.pipeline import compose_sections
    from app.schemas import Conflict, Finding

    findings_list = [Finding.model_validate(f) for f in state.get("findings", [])]
    if adopted_stmt:
        # Check if already added to avoid duplicates
        existing_adopted_ids = {f.id for f in findings_list}
        adopted_id = f"f_adopted_{req.conflict_id}"
        if adopted_id not in existing_adopted_ids:
            new_f = Finding(
                id=adopted_id,
                type="requirement",
                statement=f"Adopted Requirement ({topic_name}): {adopted_stmt}",
                source_id="conflict_resolution",
                source_span=adopted_stmt,
                confidence=1.0,
                priority="high",
                agent="Consensus Engine",
                section=adopted_section,
                modality="text",
            )
            findings_list.append(new_f)
            state["findings"] = [f.model_dump() for f in findings_list]

    conflicts = [Conflict.model_validate(c) for c in updated]
    state["sections"] = [s.model_dump() for s in compose_sections(findings_list, conflicts)]
    SESSIONS[session_id] = state
    db.save_session(session_id, state)

    # Record conflict resolution in the tamper-evident ledger
    HashChainedLedger.record_entry(
        session_id=session_id,
        entry_type="conflict_resolved",
        data={
            "conflict_id": req.conflict_id,
            "kept": req.keep,
            "note": req.note,
        },
        source_chunk_text=f"{req.conflict_id}:{req.keep}",
        signer_id="pm_reviewer",
    )

    return state



@app.get("/api/tasks")
def tasks(x_user_id: Optional[str] = Header(None)):
    return [t.model_dump(mode="json") for t in db.list_tasks(x_user_id)]


from app.email_service import send_real_email


@app.post("/api/tasks/{task_id}/{action}")
def task_action(task_id: str, action: str):
    if action not in {"approved", "dismissed"}:
        return JSONResponse({"error": "invalid action"}, status_code=400)
    task = db.set_task_status(task_id, action)

    dispatch_res = None
    if action == "approved":
        payload = getattr(task, "payload", {}) if task else {}
        recipient = payload.get("recipient", "client@company.com") if isinstance(payload, dict) else "client@company.com"
        subject = payload.get("subject", "Action Item Update") if isinstance(payload, dict) else "Action Item Update"
        body = payload.get("body", "Requirement action item approved.") if isinstance(payload, dict) else "Requirement action item approved."
        dispatch_res = send_real_email(recipient, subject, body)

    if not task:
        for sess in SESSIONS.values():
            for t in sess.get("tasks", []):
                if t.get("id") == task_id or t.get("id", "").startswith("t_"):
                    t["status"] = action
                    return {**t, "dispatch": dispatch_res}
        return {
            "id": task_id,
            "type": "draft_email",
            "context": "Ops Task Executed",
            "status": action,
            "dispatch": dispatch_res,
            "created_at": get_now().isoformat(),
        }
    out = task.model_dump(mode="json")
    if dispatch_res:
        out["dispatch"] = dispatch_res
    return out


@app.get("/api/alerts")
def alerts(x_user_id: Optional[str] = Header(None)):
    db.fire_due_alerts(x_user_id)
    return [a.model_dump(mode="json") for a in db.list_alerts(x_user_id)]


@app.get("/api/export/{session_id}")
def export_md(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to export this workspace."}, status_code=403)

    state = SESSIONS.get(session_id) or db.load_session(session_id)
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
def export_pdf(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to export this workspace."}, status_code=403)

    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    out_path = settings.upload_dir / f"{session_id}_brd.pdf"
    generate_pdf(state, session_id, out_path)
    return FileResponse(out_path, media_type="application/pdf", filename=f"orbius-brd-{session_id}.pdf")


@app.get("/api/export/{session_id}/docx")
def export_word(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to export this workspace."}, status_code=403)

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
def copilot_chat(
    req: ChatRequest,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(req.session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to query this workspace."}, status_code=403)

    state = SESSIONS.get(req.session_id) or db.load_session(req.session_id)
    findings = [Finding.model_validate(f) for f in (state.get("findings") if state else [])]
    chunks = [SourceChunk.model_validate(c) for c in (state.get("chunks") if state else get_uploads_cache(req.session_id, user))]
    project_desc = state.get("project_description", "") if state else ""
    return run_copilot_chat(req.message, req.history, findings, chunks, project_desc)


@app.post("/api/scenario/simulate")
def scenario_simulate(
    req: ScenarioRequest,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(req.session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to simulate on this workspace."}, status_code=403)

    state = SESSIONS.get(req.session_id) or db.load_session(req.session_id)
    findings = [Finding.model_validate(f) for f in (state.get("findings") if state else [])]
    chunks = [SourceChunk.model_validate(c) for c in (state.get("chunks") if state else get_uploads_cache(req.session_id, user))]
    return simulate_what_if_scenario(req.scenario_type, req.parameter_value, req.custom_prompt, findings, chunks)


@app.get("/api/export/{session_id}/jira")
def export_jira(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to export this workspace."}, status_code=403)

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
def export_linear(
    session_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    user = get_auth_user(authorization, x_user_id)
    if not check_session_access(session_id, user):
        return JSONResponse({"error": "Access denied: You do not have permission to export this workspace."}, status_code=403)

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


@app.post("/api/export/{session_id}/jira/push")
def export_jira_push(session_id: str):
    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "no session"}, status_code=404)
    findings = [Finding.model_validate(f) for f in state.get("findings", [])]
    tasks = [Task.model_validate(t) for t in state.get("tasks", [])]
    return push_to_jira_api(findings, tasks)


@app.get("/api/scorecard")
def get_scorecard(session_id: Optional[str] = Query(None)):
    from app.prototype_agent import get_accuracy_scorecard
    sess_id = session_id or "demo"
    state = SESSIONS.get(sess_id) or db.load_session(sess_id) or {}
    findings = [Finding.model_validate(f) for f in state.get("findings", [])]
    chunks = [SourceChunk.model_validate(c) for c in (state.get("chunks") or UPLOADS.get(sess_id) or [])]
    conflicts = state.get("conflicts", [])
    gaps = state.get("gaps", [])
    return get_accuracy_scorecard(findings, chunks, conflicts, gaps)


@app.post("/api/meeting/interrupter")
def meeting_interrupter(payload: dict):
    """Flags live speech that contradicts findings extracted from the user's uploaded files using
    Gemini semantic analysis with deterministic heuristic fallback."""
    import re as _re
    from app.prototype_agent import parse_money, _is_budget, _is_deadline, _short, THRESHOLD_RE
    from app.model_router import generate_json
    from app.agents import parse_json_payload

    raw_speech = payload.get("speech", "")
    speech = raw_speech.lower()
    session_id = payload.get("session_id") or "demo"
    state = SESSIONS.get(session_id) or db.load_session(session_id) or {}
    findings = [Finding.model_validate(f) for f in state.get("findings", [])]

    # 1. Live Model Semantic Watchdog (Gemini 3.8 / 3.5 Flash)
    if settings.gemini_api_key and findings and len(raw_speech.strip()) > 8:
        sample_findings = "\n".join(f"- [{f.id}] ({f.section}) {f.statement} (Cited: \"{f.source_span[:60]}\")" for f in findings[:14])
        prompt = f"""You are the Orbius Live Meeting Watchdog & Requirements Sentinel.
A participant in a live project meeting just stated:
"{raw_speech}"

Approved project findings & compliance constraints from uploaded documents:
{sample_findings}

Does the spoken statement contradict, attempt to skip, exceed budget limits, violate regulatory mandates (e.g. 2FA, SLAs, audit retention), or conflict with any approved requirement?
If YES, explain why and provide a polite correction referencing the source.

Return JSON:
{{
  "interrupted": true/false,
  "interruption_reason": "⚠️ CONFLICT DETECTED: [Brief description]",
  "suggested_correction": "Your source specifies: [Quote and recommendation]"
}}
"""
        try:
            raw_res = generate_json(prompt, purpose="meeting_watchdog")
            parsed = parse_json_payload(raw_res)
            if parsed and isinstance(parsed, list) and len(parsed) > 0:
                item = parsed[0]
                if item.get("interrupted"):
                    return {
                        "interrupted": True,
                        "interruption_reason": item.get("interruption_reason", "⚠️ Contradicts an approved requirement in documentation."),
                        "suggested_correction": item.get("suggested_correction", ""),
                        "live_timestamp": get_now().isoformat(),
                        "model_verified": True,
                    }
        except Exception:
            pass

    # 2. Heuristic Semantic Fallback Watchdog
    interrupted = False
    interruption_reason = ""
    suggested_correction = ""

    # Budget check
    spoken_amounts = parse_money(raw_speech)
    for f in findings:
        if not spoken_amounts or not _is_budget(f):
            continue
        cap = max(parse_money(f.statement))
        if max(spoken_amounts) > cap:
            interrupted = True
            interruption_reason = f"⚠️ OVER BUDGET: ${max(spoken_amounts):,.0f} exceeds the ${cap:,.0f} limit in your files."
            suggested_correction = f"Your source says: \"{f.statement}\". Confirm additional budget approval."
            break

    # Requirement bypass / skip
    if not interrupted and _re.search(r"\b(skip|no|remove|drop|bypass|without|ignore|cancel|don't need|not needed)\b", speech):
        stop = {"must", "should", "will", "with", "that", "this", "from", "have", "require", "required", "the", "and", "for", "above"}
        for f in findings:
            if f.type == "stakeholder" or not _re.search(r"\b(must|mandatory|required|require|shall|need)\b", f.statement.lower()):
                continue
            keywords = [w for w in _re.findall(r"[a-z0-9]{3,}", f.statement.lower()) if w not in stop]
            hit = next((k for k in keywords if _re.search(rf"\b{_re.escape(k)}\b", speech)), None)
            if hit:
                interrupted = True
                interruption_reason = f"⚠️ CONFLICTS WITH REQUIREMENT: skipping \"{hit}\" goes against your files."
                suggested_correction = f"Your source says: \"{f.statement}\"."
                break

    # Deadline postponement
    if not interrupted and _re.search(r"\b(delay|postpone|push|later|next week|extend|move the deadline|reschedule)\b", speech):
        f = next((x for x in findings if _is_deadline(x)), None)
        if f:
            interrupted = True
            interruption_reason = "⚠️ DEADLINE AT RISK: this would push back a date committed in your files."
            suggested_correction = f"Your source says: \"{f.statement}\". Confirm with stakeholders before moving it."

    return {
        "interrupted": interrupted,
        "interruption_reason": interruption_reason,
        "suggested_correction": suggested_correction,
        "live_timestamp": get_now().isoformat(),
        "model_verified": False,
    }


# ===========================================================================
# ORBIUS MESH & LIVE STREAMING WEBSOCKETS (Tier 1.6 & Tier 2.5)
# ===========================================================================
@app.websocket("/api/mesh/sync/{session_id}")
async def mesh_sync_ws(websocket: WebSocket, session_id: str):
    """Orbius Mesh Local-First Sync WebSocket: handles HELLO, VEC, DELTA, ACK, CONFLICT, SEAL frames."""
    await mesh_manager.connect(websocket, session_id)
    try:
        while True:
            text = await websocket.receive_text()
            frame = json.loads(text)
            response = await mesh_manager.handle_frame(websocket, session_id, frame)
            if response:
                await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        mesh_manager.disconnect(websocket, session_id)
    except Exception:
        mesh_manager.disconnect(websocket, session_id)


@app.get("/api/mesh/ledger/{session_id}/verify")
def verify_ledger(session_id: str):
    """Cryptographically verifies every block hash and parent link in the session ledger."""
    return HashChainedLedger.verify_chain(session_id)


@app.get("/api/mesh/ledger/{session_id}/entries")
def get_ledger_entries(session_id: str):
    """Returns the immutable hash-chained blocks for the given session."""
    return HashChainedLedger.get_delta_since(session_id, None)


@app.websocket("/api/live/meeting")
async def live_meeting_ws(websocket: WebSocket):
    """Streaming voice & meeting channel with on-device VAD simulation and latency logging."""
    await websocket.accept()
    session_id = "demo"
    import time
    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            speech = data.get("speech", "")
            session_id = data.get("session_id", session_id)
            t0 = time.time()

            res = meeting_interrupter({"speech": speech, "session_id": session_id})
            calc_ms = round((time.time() - t0) * 1000, 1)

            await websocket.send_text(json.dumps({
                "type": "meeting_alert" if res.get("interrupted") else "meeting_ok",
                "speech": speech,
                "interrupted": res.get("interrupted", False),
                "reason": res.get("interruption_reason", ""),
                "suggested_correction": res.get("suggested_correction", ""),
                "latency_budget": {
                    "vad_capture_ms": 38,
                    "uplink_ms": 28,
                    "tool_eval_ms": calc_ms,
                    "total_roundtrip_ms": round(66 + calc_ms, 1),
                },
            }))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.get("/api/session/{session_id}/meeting-triggers")
def meeting_triggers(session_id: str):

    """Sample test phrases generated from the user's own findings (no demo data)."""
    import re as _re
    from app.prototype_agent import parse_money, _is_budget, _is_deadline, _short

    state = SESSIONS.get(session_id) or db.load_session(session_id) or {}
    findings = [Finding.model_validate(f) for f in state.get("findings", [])]
    triggers = []
    budget = next((f for f in findings if _is_budget(f)), None)
    if budget:
        over = max(parse_money(budget.statement)) * 1.4
        triggers.append({"label": "Exceed the budget", "phrase": f"I think we should spend ${over:,.0f} on this."})
    req = next((f for f in findings if f.type != "stakeholder" and _re.search(r"\b(must|mandatory|required|require)\b", f.statement.lower())), None)
    if req:
        words = [w for w in _re.findall(r"[A-Za-z0-9]{3,}", req.statement) if w.lower() not in {"must", "require", "required", "mandatory", "store", "the", "for", "with"}]
        key = next((w for w in words if any(ch.isdigit() for ch in w) or w.isupper()), words[0] if words else "this")
        triggers.append({"label": f"Skip: {_short(req.statement, 5)}", "phrase": f"To save time, let's skip {key} for now."})
    dl = next((f for f in findings if _is_deadline(f)), None)
    if dl:
        triggers.append({"label": f"Delay: {_short(dl.statement, 5)}", "phrase": "Let's postpone this until next week."})
    return {"triggers": triggers}


@app.post("/api/audio/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribes an uploaded audio memo / voice meeting file."""
    import shutil
    import tempfile
    ext = Path(file.filename or "recording.webm").suffix.lower()
    if not ext:
        ext = ".webm"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        shutil.copyfileobj(file.file, temp_file)
        temp_file.close()

        # Try live Gemini speech-to-text if available
        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key, http_options={"timeout": 25.0})
                up = client.files.upload(file=temp_file.name)
                for m in [settings.primary_model, settings.fallback_model, "gemini-3.7-flash"]:
                    try:
                        resp = client.models.generate_content(
                            model=m,
                            contents=[up, "Transcribe this audio meeting or voice recording verbatim. Include timestamps, speaker transitions, and requirements if present."]
                        )
                        txt = getattr(resp, "text", None)
                        if txt and txt.strip():
                            return {"transcript": txt.strip(), "filename": file.filename, "status": "ok"}
                    except Exception:
                        continue
            except Exception:
                pass

        # Robust contextual fallback
        return {
            "transcript": f"Meeting Notes & Audio Dictation ({file.filename}): Ingested audio discussion outlining engineering milestones, user authentication requirements, and budget constraints.",
            "filename": file.filename,
            "status": "fallback"
        }
    finally:
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass


@app.get("/api/brd/export-pdf")
def export_brd_pdf(session_id: str = "demo"):
    """Generates and downloads a clean, professional PDF summary of the BRD specifications."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    import re

    state = SESSIONS.get(session_id) or db.load_session(session_id)
    if not state:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    pdf_path = settings.upload_dir / f"Orbius_BRD_{session_id}.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyTextClean",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "BulletTextClean",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=12,
        spaceAfter=4,
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0284c7"),
    )

    story = []

    # Title & Header
    story.append(Paragraph("ORBIUS — BUSINESS REQUIREMENTS DOCUMENT (BRD)", title_style))
    now_str = get_now().strftime("%B %d, %Y")
    findings_count = len(state.get("findings", []))
    conflicts_count = len(state.get("conflicts", []))
    sources_count = len(state.get("sources", []))
    meta_text = f"Project Session: <b>{session_id}</b> &nbsp;|&nbsp; Generated: <b>{now_str}</b> &nbsp;|&nbsp; Sources Analyzed: <b>{sources_count}</b> &nbsp;|&nbsp; Verified Requirements: <b>{findings_count}</b>"
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    # Executive Overview Table
    open_conflicts = [c for c in state.get("conflicts", []) if c.get("status") == "open"]
    resolved_conflicts = [c for c in state.get("conflicts", []) if c.get("status") != "open"]
    summary_data = [
        [
            Paragraph("<b>Overall Status:</b> Ready for Review", body_style),
            Paragraph(f"<b>Open Discrepancies:</b> {len(open_conflicts)}", body_style),
        ],
        [
            Paragraph(f"<b>Stakeholder Consensus:</b> {len(resolved_conflicts)} Decisions Resolved", body_style),
            Paragraph(f"<b>Specification Sections:</b> {len(state.get('sections', []))}", body_style),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[260, 260])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # Specifications Sections
    sections = state.get("sections", [])
    for sec in sections:
        sec_title = sec.get("title", "Section")
        sec_body = sec.get("body", "")
        if sec.get("id") == "diagrams":
            continue

        story.append(Paragraph(f"<b>{sec_title.upper()}</b>", h1_style))

        # Clean out any leftover raw markdown symbols
        cleaned_body = re.sub(r'\*\*', '', sec_body)
        cleaned_body = re.sub(r'_', '', cleaned_body)
        lines = [l.strip() for l in cleaned_body.split("\n") if l.strip()]

        for line in lines:
            if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                bullet_clean = line.lstrip("•-* ").strip()
                story.append(Paragraph(f"• {bullet_clean}", bullet_style))
            else:
                story.append(Paragraph(line, body_style))
        story.append(Spacer(1, 8))

    # Resolved Conflicts & Stakeholder Decisions
    if state.get("conflicts"):
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>STAKEHOLDER CONFLICTS & ARBITRATED DECISIONS</b>", h1_style))
        for c in state.get("conflicts", []):
            topic = c.get("topic", "Conflict")
            status = "RESOLVED" if c.get("status") != "open" else "PENDING ACTION"
            res = c.get("resolution") or c.get("disagreement", "Pending stakeholder consensus.")
            story.append(Paragraph(f"• <b>{topic}</b> [{status}]: {res}", bullet_style))

    # Build document
    doc.build(story)
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"Orbius_BRD_Specification_{session_id}.pdf"
    )


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


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"service": "orbius-api", "docs": "/docs"}
