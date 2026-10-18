from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.clock import get_now
from app.config import settings
from app.schemas import Alert, CalendarEvent, Task, UserResponse


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


import base64
import hmac
import secrets
import time


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: Optional[str] = None) -> bool:
    if salt:
        check_hash, _ = hash_password(password, salt)
        return hmac.compare_digest(check_hash, hashed)
    legacy_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"orbius_salt_2026", 100000).hex()
    return hmac.compare_digest(legacy_hash, hashed)


def create_session_token(user_id: str, email: str, expiry_hours: int = 72) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    exp = int(time.time()) + (expiry_hours * 3600)
    payload_data = {"sub": user_id, "email": email, "exp": exp, "iat": int(time.time())}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    message = f"{header}.{payload}"
    signature = hmac.new(settings.jwt_secret.encode(), message.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{message}.{sig_b64}"


def verify_session_token(token: str) -> Optional[dict]:
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[7:].strip()
    parts = token.split(".")
    if len(parts) == 3:
        header_b64, payload_b64, sig_b64 = parts
        message = f"{header_b64}.{payload_b64}"
        expected_sig = base64.urlsafe_b64encode(hmac.new(settings.jwt_secret.encode(), message.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(expected_sig, sig_b64):
            return None
        try:
            pad = len(payload_b64) % 4
            if pad:
                payload_b64 += "=" * (4 - pad)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
            if payload.get("exp", 0) < int(time.time()):
                return None
            return payload
        except Exception:
            return None
    # Backwards compatibility check for development if token is raw user_id
    if token.startswith("usr_"):
        user = get_user_by_id(token)
        if user:
            return {"sub": user["id"], "email": user["email"]}
    return None


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                context TEXT,
                payload TEXT,
                source_id TEXT,
                source_span TEXT,
                confidence REAL,
                status TEXT,
                created_at TEXT,
                user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                target_date TEXT,
                original_phrase TEXT,
                reminder_message TEXT,
                context TEXT,
                source_id TEXT,
                status TEXT,
                fired_at TEXT,
                user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                context_json TEXT,
                updated_at TEXT,
                user_id TEXT
            );
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                parent_hash TEXT,
                source_hash TEXT,
                data_json TEXT NOT NULL,
                signature TEXT,
                signer_id TEXT,
                entry_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )
        # Migrations if columns missing in pre-existing tables
        for table in ["tasks", "alerts", "sessions"]:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN salt TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN provider TEXT DEFAULT 'local'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
        except sqlite3.OperationalError:
            pass


def create_user(email: str, password: str, name: str) -> Dict[str, Any]:
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now_str = get_now().isoformat()
    hashed, salt = hash_password(password)
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, salt, name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email.lower().strip(), hashed, salt, name.strip(), now_str),
        )
    return {"id": user_id, "email": email.lower().strip(), "name": name.strip(), "created_at": now_str}


def create_or_login_oauth_user(
    email: str,
    name: str,
    provider: str = "google",
    avatar_url: Optional[str] = None,
    google_id: Optional[str] = None,
) -> Dict[str, Any]:
    existing = get_user_by_email(email)
    now_str = get_now().isoformat()
    if existing:
        with connect() as conn:
            conn.execute(
                "UPDATE users SET name = COALESCE(NULLIF(name, ''), ?), avatar_url = COALESCE(avatar_url, ?), google_id = COALESCE(google_id, ?) WHERE LOWER(email) = ?",
                (name.strip(), avatar_url, google_id, email.lower().strip()),
            )
        existing["name"] = name.strip() or existing.get("name")
        if avatar_url:
            existing["avatar_url"] = avatar_url
        return existing

    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    hashed, salt = hash_password(uuid.uuid4().hex)
    clean_name = name.strip() or email.split("@")[0].capitalize()
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, salt, name, created_at, provider, avatar_url, google_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, email.lower().strip(), hashed, salt, clean_name, now_str, provider, avatar_url, google_id),
        )
    return {
        "id": user_id,
        "email": email.lower().strip(),
        "name": clean_name,
        "created_at": now_str,
        "provider": provider,
        "avatar_url": avatar_url,
    }



def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower().strip(),)).fetchone()
    if not row:
        return None
    return dict(row)


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def update_password(email: str, new_password: str) -> bool:
    """Updates user password using cryptographically salted PBKDF2 HMAC-SHA256."""
    hashed, salt = hash_password(new_password)
    with connect() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE LOWER(email) = ?",
            (hashed, salt, email.lower().strip()),
        )
        return cur.rowcount > 0


def get_session_owner(session_id: str) -> Optional[str]:
    """Retrieves the owner user_id for a given session, or None if public/unbound."""
    with connect() as conn:
        row = conn.execute("SELECT user_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    return row["user_id"]


def upsert_task(task: Task, user_id: Optional[str] = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks
            (id, type, context, payload, source_id, source_span, confidence, status, created_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.type,
                task.context,
                json.dumps(task.payload),
                task.source_id,
                task.source_span,
                task.confidence,
                task.status,
                task.created_at.isoformat(),
                user_id,
            ),
        )


def list_tasks(user_id: Optional[str] = None) -> List[Task]:
    with connect() as conn:
        if user_id:
            rows = conn.execute("SELECT * FROM tasks WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC", (user_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    return [
        Task(
            id=r["id"],
            type=r["type"],
            context=r["context"],
            payload=json.loads(r["payload"] or "{}"),
            source_id=r["source_id"],
            source_span=r["source_span"] or "",
            confidence=r["confidence"] or 0,
            status=r["status"],
            created_at=datetime.fromisoformat(r["created_at"]),
        )
        for r in rows
    ]


def set_task_status(task_id: str, status: str) -> Optional[Task]:
    with connect() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    for task in list_tasks():
        if task.id == task_id:
            return task
    return None


def upsert_alert(alert: Alert, user_id: Optional[str] = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO alerts
            (id, target_date, original_phrase, reminder_message, context, source_id, status, fired_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.id,
                alert.target_date,
                alert.original_phrase,
                alert.reminder_message,
                alert.context,
                alert.source_id,
                alert.status,
                alert.fired_at.isoformat() if alert.fired_at else None,
                user_id,
            ),
        )


def list_alerts(user_id: Optional[str] = None) -> List[Alert]:
    with connect() as conn:
        if user_id:
            rows = conn.execute("SELECT * FROM alerts WHERE user_id = ? OR user_id IS NULL ORDER BY target_date", (user_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM alerts ORDER BY target_date").fetchall()
    out: List[Alert] = []
    for r in rows:
        out.append(
            Alert(
                id=r["id"],
                target_date=r["target_date"],
                original_phrase=r["original_phrase"],
                reminder_message=r["reminder_message"],
                context=r["context"],
                source_id=r["source_id"],
                status=r["status"],
                fired_at=datetime.fromisoformat(r["fired_at"]) if r["fired_at"] else None,
            )
        )
    return out


def fire_due_alerts(user_id: Optional[str] = None) -> List[Alert]:
    now = get_now()
    fired: List[Alert] = []
    for alert in list_alerts(user_id):
        if alert.status != "pending":
            continue
        try:
            due = datetime.fromisoformat(alert.target_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due <= now:
            alert.status = "fired"
            alert.fired_at = now
            upsert_alert(alert, user_id)
            fired.append(alert)
    return fired


def save_session(session_id: str, payload: Dict, user_id: Optional[str] = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (id, context_json, updated_at, user_id) VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(payload), get_now().isoformat(), user_id),
        )


def load_session(session_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT context_json, user_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return {}
    data = json.loads(row["context_json"])
    if row["user_id"]:
        data["user_id"] = row["user_id"]
    return data


def get_user_sessions(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, updated_at, context_json FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    res = []
    for r in rows:
        data = json.loads(r["context_json"])
        res.append({
            "session_id": r["id"],
            "updated_at": r["updated_at"],
            "version": data.get("version", 1),
            "section_count": len(data.get("sections", []))
        })
    return res


def get_calendar_events(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    now = get_now()
    today_date = now.date()
    tomorrow_date = today_date + timedelta(days=1)

    events: List[Dict[str, Any]] = []

    # Process Alerts
    for alert in list_alerts(user_id):
        date_str = alert.target_date[:10]
        try:
            target_dt = datetime.fromisoformat(alert.target_date.replace("Z", "+00:00")).date()
        except ValueError:
            target_dt = today_date

        if alert.status in ("dismissed", "fired"):
            urgency = "completed"
        elif target_dt <= today_date:
            urgency = "urgent"  # Red badge: Overdue / Due Today
        elif target_dt == tomorrow_date:
            urgency = "due_tomorrow"  # Orange badge
        else:
            urgency = "normal"

        events.append({
            "id": alert.id,
            "title": alert.context,
            "type": "alert",
            "date": date_str,
            "status": alert.status,
            "urgency": urgency,
            "detail": alert.reminder_message,
            "source_span": alert.original_phrase,
        })

    # Process Tasks
    for task in list_tasks(user_id):
        date_str = task.created_at.date().isoformat()
        task_date = task.created_at.date()

        if task.status in ("approved", "dismissed"):
            urgency = "completed"
        elif task_date <= today_date:
            urgency = "urgent"
        elif task_date == tomorrow_date:
            urgency = "due_tomorrow"
        else:
            urgency = "normal"

        events.append({
            "id": task.id,
            "title": task.payload.get("subject") or task.context,
            "type": "task",
            "date": date_str,
            "status": task.status,
            "urgency": urgency,
            "detail": task.payload.get("body") or task.context,
            "source_span": task.source_span,
        })

    return events


def reset_ops(user_id: str | None = None) -> None:
    with connect() as conn:
        if user_id:
            conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM alerts WHERE user_id = ?", (user_id,))
        else:
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM alerts")
