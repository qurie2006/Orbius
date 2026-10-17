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
    lines = raw.strip().split("\n")
    result = []
    sub_count = 0
    for line in lines:
        trimmed = line.strip()
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

        # 4. Standard rectangle shapes ["text"]
        sanitized_line = re.sub(
            r'([a-zA-Z0-9_]+)\[\s*"?([^\n\(\)\]]*?)"?\s*\]',
            lambda m: f'{m.group(1)}["{m.group(2).replace(chr(34), chr(39))}"]',
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


def _label(text: str, words: int = 6) -> str:
    clean = re.sub(r"[\"'`<>\[\]{}()|#;:]", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip().rstrip(".")
    parts = clean.split(" ")
    return " ".join(parts[:words]) + ("..." if len(parts) > words else "")


def _diagrams_from_findings(findings: list[Finding]) -> dict[str, str]:
    if not findings:
        empty = 'graph TD\n    A["Upload files to generate diagrams"]'
        return {"architecture": empty, "user_flow": empty, "sequence": empty}

    people = [re.split(r"\s+—\s+|\s+\(", f.statement, maxsplit=1)[0].strip() for f in findings if f.type == "stakeholder" or f.section == "stakeholders"]
    people = [p for p in dict.fromkeys(people) if p][:4]
    items = [f for f in findings if f.type != "stakeholder" and f.section != "stakeholders"][:8]

    groups = {
        "Requirements": [f for f in items if f.section in ("functional_requirements", "non_functional_requirements", "objectives", "scope")],
        "Budget": [f for f in items if f.section == "budget"],
        "Risks & Other": [f for f in items if f.section not in ("functional_requirements", "non_functional_requirements", "objectives", "scope", "budget")],
    }

    arch = [
        "graph TD",
        "    classDef person fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#374151;",
        "    classDef group fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#374151;",
        "    classDef item fill:#fef3c7,stroke:#d97706,stroke-width:1px,color:#374151;",
        '    P0["Project"]:::group',
    ]
    for i, p in enumerate(people):
        arch.append(f'    S{i}["{_label(p, 4)}"]:::person --> P0')
    for gi, (gname, gitems) in enumerate(groups.items()):
        if not gitems:
            continue
        arch.append(f'    P0 --> G{gi}["{gname}"]:::group')
        for ii, f in enumerate(gitems):
            arch.append(f'    G{gi} --> I{gi}_{ii}["{_label(f.statement)}"]:::item')

    flow = [
        "flowchart LR",
        "    classDef step fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#374151;",
        "    classDef finish fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#374151;",
        "    Start([Start]):::step",
    ]
    prev = "Start"
    for i, f in enumerate(items[:6]):
        flow.append(f'    {prev} --> F{i}["{_label(f.statement)}"]:::step')
        prev = f"F{i}"
    flow.append(f"    {prev} --> Done([Done]):::finish")

    requester = _label(people[0], 3) if people else "Stakeholder"
    seq = ["sequenceDiagram", "    autonumber", f'    actor R as {requester}', "    participant T as Project Team"]
    for f in items[:6]:
        seq.append(f"    R->>T: {_label(f.statement, 8)}")
    seq.append("    T-->>R: Confirms delivery against requirements")

    return {"architecture": "\n".join(arch), "user_flow": "\n".join(flow), "sequence": "\n".join(seq)}
