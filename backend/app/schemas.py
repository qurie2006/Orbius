from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

FindingType = Literal["requirement", "stakeholder", "constraint", "risk", "decision"]
TaskType = Literal["draft_email", "scheduled_alert"]
TaskStatus = Literal["pending", "approved", "dismissed"]
AlertStatus = Literal["pending", "fired", "dismissed"]
BrdSectionId = Literal[
    "objectives",
    "scope",
    "stakeholders",
    "diagrams",
    "functional_requirements",
    "non_functional_requirements",
    "budget",
    "risks",
    "assumptions",
    "open_conflicts",
]


class SourceChunk(BaseModel):
    source_id: str
    file_name: str
    modality: Literal["text", "image", "pdf", "spreadsheet", "audio"]
    page_or_ts: str
    text: str
    bbox: list[float] | None = None


class Finding(BaseModel):
    id: str
    type: FindingType
    statement: str
    source_id: str
    source_span: str
    confidence: float = Field(ge=0, le=1)
    priority: Literal["low", "medium", "high"] = "medium"
    agent: str
    owner: str | None = None
    acceptance_criteria: str | None = None
    section: BrdSectionId = "functional_requirements"


class Conflict(BaseModel):
    id: str
    topic: str
    left: Finding
    right: Finding
    disagreement: str
    suggested_question: str
    status: Literal["open", "resolved"] = "open"
    resolution: str | None = None


class OpsItem(BaseModel):
    type: TaskType
    context: str
    source_id: str
    source_span: str
    confidence: float
    payload: dict[str, Any]


class Task(BaseModel):
    id: str
    type: TaskType
    context: str
    payload: dict[str, Any]
    source_id: str
    source_span: str
    confidence: float
    status: TaskStatus = "pending"
    created_at: datetime


class Alert(BaseModel):
    id: str
    target_date: str
    original_phrase: str
    reminder_message: str
    context: str
    source_id: str
    status: AlertStatus = "pending"
    fired_at: datetime | None = None


class DelegationEvent(BaseModel):
    agent: str
    level: int
    task: str
    status: Literal["running", "kept", "dropped", "timeout"]
    detail: str = ""


class BrdSection(BaseModel):
    id: BrdSectionId
    title: str
    body: str
    finding_ids: list[str] = []
    streaming: bool = False
    diagram_type: str | None = None  # e.g. "flowchart", "sequence", "architecture"
    mermaid_code: str | None = None


class ChangelogEntry(BaseModel):
    version: int
    at: datetime
    summary: str
    sections: list[str]


class GenerateRequest(BaseModel):
    project_description: str = ""
    session_id: str | None = None


class ResolveConflictRequest(BaseModel):
    conflict_id: str
    keep: Literal["left", "right", "both", "neither"]
    note: str = ""


class SignUpRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str


class CalendarEvent(BaseModel):
    id: str
    title: str
    type: Literal["task", "alert"]
    date: str
    status: str
    urgency: Literal["urgent", "due_tomorrow", "normal", "completed"]
    detail: str
    source_span: str | None = None


# --- New Copilot Chat Schemas ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    session_id: str = "demo"
    message: str
    history: list[ChatMessage] = []


class ChatCitation(BaseModel):
    source_id: str
    file_name: str
    snippet: str
    confidence: float


class ChatResponse(BaseModel):
    reply: str
    citations: list[ChatCitation] = []
    suggested_followups: list[str] = []


# --- New What-If Scenario Schemas ---
class ScenarioRequest(BaseModel):
    session_id: str = "demo"
    scenario_type: str
    parameter_value: str = ""
    custom_prompt: str = ""


class ScenarioAffectedItem(BaseModel):
    id: str
    statement: str
    impact: str
    status: Literal["compromised", "delayed", "enhanced", "removed"]


class ScenarioResponse(BaseModel):
    scenario_title: str
    impact_summary: str
    affected_items: list[ScenarioAffectedItem] = []
    shifted_deadlines: list[dict[str, Any]] = []
    new_risks: list[str] = []
    diagram_diff_mermaid: str | None = None

