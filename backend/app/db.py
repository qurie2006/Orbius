from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.clock import get_now
from app.config import settings
from app.schemas import Alert, CalendarEvent, Task, UserResponse


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b"orbius_salt_2026", 100000).hex()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
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
            """
        )
        # Migrations if user_id column missing in pre-existing tables
        for table in ["tasks", "alerts", "sessions"]:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists


def create_user(email: str, password: str, name: str) -> dict[str, Any]:
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now_str = get_now().isoformat()
    hashed = hash_password(password)
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email.lower().strip(), hashed, name.strip(), now_str),
        )
    return {"id": user_id, "email": email.lower().strip(), "name": name.strip(), "created_at": now_str}


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower().strip(),)).fetchone()
    if not row:
        return None
    return dict(row)


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def upsert_task(task: Task, user_id: str | None = None) -> None:
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


def list_tasks(user_id: str | None = None) -> list[Task]:
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


def set_task_status(task_id: str, status: str) -> Task | None:
    with connect() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    for task in list_tasks():
        if task.id == task_id:
            return task
    return None


def upsert_alert(alert: Alert, user_id: str | None = None) -> None:
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


def list_alerts(user_id: str | None = None) -> list[Alert]:
    with connect() as conn:
        if user_id:
            rows = conn.execute("SELECT * FROM alerts WHERE user_id = ? OR user_id IS NULL ORDER BY target_date", (user_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM alerts ORDER BY target_date").fetchall()
    out: list[Alert] = []
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


def fire_due_alerts(user_id: str | None = None) -> list[Alert]:
    now = get_now()
    fired: list[Alert] = []
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


def save_session(session_id: str, payload: dict, user_id: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (id, context_json, updated_at, user_id) VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(payload), get_now().isoformat(), user_id),
        )


def load_session(session_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT context_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return {}
    return json.loads(row["context_json"])


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


def get_calendar_events(user_id: str | None = None) -> list[dict[str, Any]]:
    now = get_now()
    today_date = now.date()
    tomorrow_date = today_date + timedelta(days=1)

    events: list[dict[str, Any]] = []

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
