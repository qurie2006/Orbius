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

def sanitize_mermaid(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        return ""

    # Strip markdown code blocks
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:mermaid)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    # Split lines where multiple statements are glued together e.g. "A[Text] B --> C"
    cleaned = re.sub(r'(\])\s+([a-zA-Z0-9_]+(?:\s*-->|\s*-\.->|\s*==>|\s*\[|\s*\{|\s*\())', r'\1\n    \2', cleaned)

    lines = cleaned.split("\n")
    result = []
    sub_count = 0
    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            continue

        # Handle subgraph lines (e.g. subgraph Cloud Infrastructure ($180k Budget Cap) or subgraph Security & Auth)
        if re.match(r"^subgraph\s+", trimmed, re.IGNORECASE):
            rest = re.sub(r"^subgraph\s+", "", trimmed, flags=re.IGNORECASE).strip()
            if rest.startswith('"') or re.match(r"^[a-zA-Z0-9_-]+\s*\[", rest):
                result.append(line)
            else:
                clean_title = re.sub(r'["\[\]]', "", rest).replace("&", "and").strip()
                sub_count += 1
                indent = re.match(r"^\s*", line).group(0)
                result.append(f'{indent}subgraph sg_{sub_count} ["{clean_title}"]')
            continue

        # Replace standalone & with 'and' to prevent Mermaid multi-node link syntax errors
        sanitized_line = re.sub(r"(\s+)&(\s+)", r"\1and\2", line)

        # 1. Database shapes [("text")]
        sanitized_line = re.sub(
            r'([a-zA-Z0-9_]+)\[\(\s*"?([^\n\)]*?)"?\s*\)\]',
            lambda m: f'{m.group(1)}[("{m.group(2).replace(chr(34), chr(39))}")]',
            sanitized_line,
        )

        # 2. Rounded shapes (["text"])
        sanitized_line = re.sub(
            r'([a-zA-Z0-9_]+)\(\[\s*"?([^\n\]]*?)"?\s*\]\)',
            lambda m: f'{m.group(1)}(["{m.group(2).replace(chr(34), chr(39))}"])',
            sanitized_line,
        )

        # 3. Decision shapes {"text"}
        sanitized_line = re.sub(
            r'([a-zA-Z0-9_]+)\{\s*"?([^\n\}]*?)"?\s*\}',
            lambda m: f'{m.group(1)}{{"{m.group(2).replace(chr(34), chr(39))}"}}',
            sanitized_line,
        )

        # 4. Standard rectangle shapes ["text"] (allows parentheses inside labels, e.g. [Budget ($180k)])
        def _rect_rep(m):
            nid = m.group(1)
            inner = m.group(2).strip()
            if inner.startswith('"') and inner.endswith('"') and len(inner) >= 2:
                inner = inner[1:-1]
            inner = inner.replace('"', "'")
            return f'{nid}["{inner}"]'

        sanitized_line = re.sub(
            r'([a-zA-Z0-9_]+)\[(?!\()\s*([^\]]*?)\s*\]',
            _rect_rep,
            sanitized_line,
        )

        result.append(sanitized_line)

    return "\n".join(result)


def generate_mermaid_diagrams(findings: list[Finding], chunks: list[SourceChunk]) -> dict[str, str]:
    context = "\n".join([f"- {f.type.upper()}: {f.statement} (Agent: {f.agent})" for f in findings[:25]])
    
    prompt = f"""You are a Solution Architect AI. Generate 3 valid Mermaid diagrams based on the following project findings:

FINDINGS:
{context}

Return a JSON object with exactly three keys:
1. "architecture": Mermaid graph TD or flowchart TD diagram showing system components, APIs, databases, authentication, and external services.
2. "user_flow": Mermaid flowchart LR or sequenceDiagram showing the user / stakeholder interaction flow.
3. "sequence": Mermaid sequenceDiagram showing message flow between user, frontend, backend API, and database/external services.

CRITICAL SYNTAX RULES FOR MERMAID 12:
- Always put double quotes inside every node bracket: e.g. A["API Gateway"] or DB[("Postgres DB")] or D{{"Auth Check"}}.
- Never use unquoted parentheses or unquoted brackets inside labels.
- Subgraphs MUST ALWAYS use the format: subgraph sg_id ["Subgraph Title"]. Never write raw unquoted subgraph titles.
- Never use the raw '&' character anywhere; always write 'and'.
- Return ONLY valid raw JSON with keys "architecture", "user_flow", "sequence".
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
                fallback = _diagrams_from_findings(findings)
                arch = sanitize_mermaid(data.get("architecture") or fallback["architecture"])
                flow = sanitize_mermaid(data.get("user_flow") or fallback["user_flow"])
                seq = data.get("sequence") or fallback["sequence"]
                return {
                    "architecture": arch or fallback["architecture"],
                    "user_flow": flow or fallback["user_flow"],
                    "sequence": seq or fallback["sequence"],
                }
    except Exception:
        pass

    # Heuristic diagrams built ONLY from the user's findings (no demo template)
    return _diagrams_from_findings(findings)


def _short_concept(text: str) -> str:
    clean = re.sub(r"[\"'`<>\[\]{}()|#;:\*]", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    clow = clean.lower()

    if "fido2" in clow or "webauthn" in clow or "2fa" in clow or "mfa" in clow or "override" in clow:
        return "FIDO2 2FA Auth"
    if "rbac" in clow or "role-based" in clow or "tenant" in clow:
        return "Zero-Trust RBAC"
    if "failover" in clow or "gateway" in clow or "routing" in clow or "multi-region" in clow:
        return "Edge Failover Gateway"
    if "cryptographic" in clow or "deletion" in clow or "erasure" in clow:
        return "Cryptographic Erasure"
    if "latency" in clow or "p99" in clow or "sla" in clow or "availability" in clow or "300ms" in clow:
        return "SLA and Latency Engine"
    if "mesh" in clow or "offline" in clow or "sync" in clow or "buffer" in clow:
        return "Offline Mesh Sync"
    if "audit" in clow or "soc-2" in clow or "log" in clow:
        return "Immutable Audit Store"
    if "governance" in clow or "compliance" in clow or "cloud" in clow:
        return "Cloud Governance Core"
    if "budget" in clow or "ceiling" in clow or "$" in clow or "cost" in clow:
        return "Budget Ceiling Manager"
    if "notification" in clow or "alert" in clow or "email" in clow:
        return "Alert and Dispatcher"
    if "database" in clow or "store" in clow or "repository" in clow:
        return "Primary Data Store"
    if "api" in clow or "rest" in clow or "graphql" in clow:
        return "Core API Gateway"

    stopwords = {"the", "a", "an", "and", "or", "to", "for", "of", "with", "in", "on", "by", "from", "brief", "saas", "enterprise", "specification", "extract", "pdf", "docx"}
    words = [w.capitalize() for w in clean.split() if w.lower() not in stopwords]
    if len(words) >= 3:
        return " ".join(words[:3])
    elif len(words) >= 1:
        return " ".join(words)
    return "Service Module"


def _diagrams_from_findings(findings: list[Finding]) -> dict[str, str]:
    if not findings:
        empty = 'graph TD\n    A["Upload files to generate diagrams"]'
        return {"architecture": empty, "user_flow": empty, "sequence": empty}

    # Extract unique short concepts
    concepts: list[str] = []
    seen: set[str] = set()
    for f in findings:
        sc = _short_concept(f.statement)
        if sc and sc not in seen and sc != "Service Module":
            seen.add(sc)
            concepts.append(sc)

    # Categorize into clean architectural tiers
    client_nodes = ["Web Application", "Mobile Client"]
    security_nodes = [c for c in concepts if any(k in c.lower() for k in ["fido", "2fa", "rbac", "erasure", "auth"])]
    if not security_nodes:
        security_nodes = ["Identity and Access", "Zero-Trust RBAC"]

    core_nodes = [c for c in concepts if any(k in c.lower() for k in ["governance", "gateway", "failover", "latency", "core", "sla"])]
    if not core_nodes:
        core_nodes = ["Cloud Governance Core", "Edge Gateway"]

    data_nodes = [c for c in concepts if any(k in c.lower() for k in ["audit", "mesh", "sync", "store", "budget", "database"])]
    if not data_nodes:
        data_nodes = ["Audit Store", "Offline Mesh Buffer"]

    # Deduplicate across tiers
    security_nodes = security_nodes[:3]
    core_nodes = [c for c in core_nodes if c not in security_nodes][:3]
    data_nodes = [c for c in data_nodes if c not in security_nodes and c not in core_nodes][:3]

    arch = [
        "graph TD",
        "    classDef client fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;",
        "    classDef security fill:#332230,stroke:#f43f5e,stroke-width:2px,color:#f8fafc;",
        "    classDef core fill:#143823,stroke:#10b981,stroke-width:2px,color:#f8fafc;",
        "    classDef data fill:#3b321c,stroke:#f59e0b,stroke-width:2px,color:#f8fafc;",
        "",
        '    subgraph c_tier ["Client and Edge Access"]',
    ]
    for ci, c in enumerate(client_nodes[:2]):
        arch.append(f'        C{ci}["{c}"]:::client')
    arch.append("    end")
    arch.append("")
    arch.append('    subgraph s_tier ["Security and Identity Layer"]')
    for si, s in enumerate(security_nodes):
        arch.append(f'        S{si}["{s}"]:::security')
    arch.append("    end")
    arch.append("")
    arch.append('    subgraph m_tier ["Core Application Services"]')
    for mi, m in enumerate(core_nodes):
        arch.append(f'        M{mi}["{m}"]:::core')
    arch.append("    end")
    arch.append("")
    arch.append('    subgraph d_tier ["Data and Synchronization"]')
    for di, d in enumerate(data_nodes):
        arch.append(f'        D{di}[("{d}")]:::data')
    arch.append("    end")
    arch.append("")
    arch.append("    C0 --> C1")
    arch.append("    C1 --> S0")
    if len(security_nodes) > 1:
        arch.append("    S0 --> S1")
    arch.append(f"    S{len(security_nodes)-1} --> M0")
    if len(core_nodes) > 1:
        arch.append("    M0 --> M1")
    arch.append(f"    M0 --> D0")
    if len(data_nodes) > 1:
        arch.append("    D0 --> D1")

    # Clean, concise 5-step User Journey
    sec_step = security_nodes[0] if security_nodes else "2FA Verification"
    core_step = core_nodes[0] if core_nodes else "Governance Execution"
    data_step = data_nodes[0] if data_nodes else "Audit Logged"

    flow = [
        "flowchart LR",
        "    classDef step fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;",
        "    classDef finish fill:#143823,stroke:#10b981,stroke-width:2px,color:#f8fafc;",
        "",
        '    Start([User Request]):::step',
        f'    Step1["{sec_step}"]:::step',
        f'    Step2["{core_step}"]:::step',
        f'    Step3["{data_step}"]:::step',
        '    Done([Operation Confirmed]):::finish',
        "",
        "    Start --> Step1",
        "    Step1 --> Step2",
        "    Step2 --> Step3",
        "    Step3 --> Done",
    ]

    seq = [
        "sequenceDiagram",
        "    autonumber",
        "    actor User as Client / User",
        "    participant Gate as Edge Gateway",
        f"    participant Auth as {sec_step}",
        f"    participant Core as {core_step}",
        f"    participant Storage as {data_step}",
        "",
        "    User->>Gate: Submit Request",
        "    Gate->>Auth: Verify Token and Identity",
        "    Auth-->>Gate: Authentication Verified",
        "    Gate->>Core: Process Governed Rules",
        "    Core->>Storage: Record Immutable State",
        "    Storage-->>Core: Persistence Acknowledged",
        "    Core-->>Gate: Operation Completed",
        "    Gate-->>User: 200 OK Confirmed",
    ]

    return {
        "architecture": "\n".join(arch),
        "user_flow": "\n".join(flow),
        "sequence": "\n".join(seq),
    }
