from __future__ import annotations

import re
from app.model_router import generate_json
from app.schemas import Finding, SourceChunk


DEFAULT_MERMAID = """graph TD
    classDef primary fill:#ffe4e6,stroke:#f43f5e,stroke-width:2px,color:#1f2937;
    classDef secondary fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#1f2937;
    classDef database fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#1f2937;
    classDef auth fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#1f2937;

    Client["📱 Client / User Touchpoint"]:::primary --> API["⚡ API Gateway / Services"]:::secondary
    API --> Auth["🔐 2FA / Security Engine"]:::auth
    API --> CoreLogic["⚙️ Core Processing Pipeline"]:::secondary
    CoreLogic --> Storage[("💾 Data Store & Logs")]:::database
    CoreLogic --> OpsNotify["📬 Ops & Notifications"]:::primary
"""

def generate_mermaid_diagrams(findings: list[Finding], chunks: list[SourceChunk]) -> dict[str, str]:
    context = "\n".join([f"- {f.type.upper()}: {f.statement} (Agent: {f.agent})" for f in findings[:25]])
    
    prompt = f"""You are a Solution Architect AI. Generate 3 valid Mermaid diagrams based on the following project findings:

FINDINGS:
{context}

Return a JSON object with exactly three keys:
1. "architecture": Mermaid graph TD or flowchart TD diagram showing system components, APIs, databases, authentication, and external services.
2. "user_flow": Mermaid flowchart LR or sequenceDiagram showing the user / stakeholder interaction flow.
3. "sequence": Mermaid sequenceDiagram showing message flow between user, frontend, backend API, and database/external services.

Important:
- Return ONLY valid raw JSON with keys "architecture", "user_flow", "sequence".
- In the Mermaid code, ensure all strings and nodes use standard valid Mermaid syntax. Do not wrap with markdown blocks inside the JSON string values.
"""
    try:
        raw = generate_json(prompt, purpose="diagram_agent")
        if raw:
            import json
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
                cleaned = re.sub(r"```$", "", cleaned).strip()
            data = json.loads(cleaned)
            if isinstance(data, dict) and "architecture" in data:
                return {
                    "architecture": data.get("architecture") or DEFAULT_MERMAID,
                    "user_flow": data.get("user_flow") or DEFAULT_MERMAID,
                    "sequence": data.get("sequence") or DEFAULT_MERMAID,
                }
    except Exception:
        pass

    # Heuristic dynamic diagrams based on findings
    statements = [f.statement.lower() for f in findings]
    has_auth = any("2fa" in s or "auth" in s or "login" in s for s in statements)
    has_offline = any("offline" in s for s in statements)
    
    arch = f"""graph TD
    classDef client fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#374151;
    classDef api fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#374151;
    classDef db fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#374151;
    classDef sec fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#374151;

    User["👤 Shopper / Staff Terminal"]:::client --> Gateway["🌐 API Gateway"]:::api
    {"Gateway --> AuthServer['🔒 2FA & Auth Service']:::sec" if has_auth else ""}
    Gateway --> ServiceCore["⚙️ Core Business Engine"]:::api
    {"ServiceCore --> OfflineSync['📡 Offline Cache & Queue']:::sec" if has_offline else ""}
    ServiceCore --> Database[("🗄️ Database & Inventory Store")]:::db
    ServiceCore --> OpsAgent["📋 Ops & Task Dispatcher"]:::client
"""

    user_flow = """flowchart LR
    classDef step fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#374151;
    classDef decision fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#374151;
    classDef finish fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#374151;

    Start([Start Session]):::step --> Select[Identify Intent / Scan]:::step
    Select --> Check{Requires Override?}:::decision
    Check -- Yes --> Auth[Manager 2FA Verification]:::step
    Check -- No --> Process[Process Request / Payment]:::step
    Auth --> Process
    Process --> Complete([Complete & Receipt]):::finish
"""

    sequence = """sequenceDiagram
    autonumber
    actor User as Stakeholder / User
    participant Frontend as Studio UI / Terminal
    participant API as Orbius API Gateway
    participant Agent as Multi-Agent Core
    participant DB as SQLite / Vector Store

    User->>Frontend: Submit Input & Documents
    Frontend->>API: Upload / Streaming Request
    API->>Agent: Parallel Specialists (Text, Doc, Vision)
    Agent->>DB: Ground Chunks & Detect Conflicts
    DB-->>Agent: Evidence & Validation
    Agent-->>Frontend: Stream Validated BRD & Actions
    Frontend-->>User: Interactive Requirements & Gantt Calendar
"""

    return {
        "architecture": arch,
        "user_flow": user_flow,
        "sequence": sequence,
    }
