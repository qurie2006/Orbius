from __future__ import annotations

import json
import re
from app.model_router import generate_json
from app.schemas import Finding, ScenarioAffectedItem, ScenarioResponse, SourceChunk


# Generic presets. All analysis is grounded only in the user's own findings.
PRESET_SCENARIOS = {
    "budget_cut_30": {
        "title": "Budget Cut by 30%",
        "prompt": "Simulate reducing the project budget by 30%. Using ONLY the findings below, identify which items must be deferred or descoped."
    },
    "launch_accelerated": {
        "title": "Deliver 6 Weeks Earlier",
        "prompt": "Simulate delivering 6 weeks earlier than planned. Using ONLY the findings below, identify what must be fast-tracked or dropped."
    },
    "drop_tablet_scope": {
        "title": "Reduce Scope to Must-Haves",
        "prompt": "Simulate cutting scope down to mandatory items only. Using ONLY the findings below, list what stays and what is removed."
    },
    "strict_security_wcag": {
        "title": "Tighten Security & Compliance",
        "prompt": "Simulate raising security and compliance requirements to the strictest level. Using ONLY the findings below, identify the impact."
    }
}


def simulate_what_if_scenario(
    scenario_type: str,
    parameter_value: str,
    custom_prompt: str,
    findings: list[Finding],
    chunks: list[SourceChunk],
) -> ScenarioResponse:
    preset = PRESET_SCENARIOS.get(scenario_type, {})
    title = preset.get("title") or "Custom Scenario Impact Analysis"
    instruction = custom_prompt or preset.get("prompt") or f"Simulate impact of {scenario_type} with parameter {parameter_value}."

    findings_summary = "\n".join([f"- [{f.id}] ({f.section}) {f.statement}" for f in findings[:20]])

    prompt = f"""You are the Orbius What-If Scenario Impact Simulator.
Analyze the downstream cascading impact of this hypothetical scenario change on the existing project requirements:

SCENARIO: {title}
DETAILS: {instruction}
CURRENT BRD FINDINGS:
{findings_summary}

Determine:
1. Executive impact summary (Markdown paragraph).
2. Which requirements are compromised, delayed, enhanced, or removed.
3. What target dates or deadlines shift.
4. What new risks are introduced.
5. A simple Mermaid graph LR or TD showing the downstream ripple effect.
   IMPORTANT: Do NOT prefix node labels with internal hashes or IDs like "f_a4f247e3:". Use clean, human-readable labels (e.g. "Budget Cut" --> "Budget Ceiling Pressure" --> "Risk: SLA Downtime").

Return a JSON object with keys:
- "scenario_title": string
- "impact_summary": string (Markdown)
- "affected_items": array of objects with keys "id", "statement", "impact", "status" ("compromised" | "delayed" | "enhanced" | "removed")
- "shifted_deadlines": array of objects with keys "item", "old_date", "new_date", "reason"
- "new_risks": array of strings
- "diagram_diff_mermaid": string (valid Mermaid diagram showing impact path)
"""

    try:
        raw = generate_json(prompt, purpose="scenario_simulator")
        if raw:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
                cleaned = re.sub(r"```$", "", cleaned).strip()
            data = json.loads(cleaned)
            if isinstance(data, dict) and "impact_summary" in data:
                affected = []
                for item in data.get("affected_items", []):
                    try:
                        affected.append(ScenarioAffectedItem(
                            id=item.get("id", "req"),
                            statement=item.get("statement", ""),
                            impact=item.get("impact", ""),
                            status=item.get("status", "delayed"),
                        ))
                    except Exception:
                        pass
                raw_diff = data.get("diagram_diff_mermaid")
                from app.diagram_agent import sanitize_mermaid
                if raw_diff:
                    # Strip any raw f_xxxx: internal IDs or random hashes
                    raw_diff = re.sub(r'f_[a-zA-Z0-9_]+:\s*', '', raw_diff)
                    raw_diff = re.sub(r'\b[a-f0-9]{8}:?\s*', '', raw_diff)
                sanitized_diff = sanitize_mermaid(raw_diff) if raw_diff else None
                return ScenarioResponse(
                    scenario_title=data.get("scenario_title", title),
                    impact_summary=data.get("impact_summary", ""),
                    affected_items=affected,
                    shifted_deadlines=data.get("shifted_deadlines", []),
                    new_risks=data.get("new_risks", []),
                    diagram_diff_mermaid=sanitized_diff,
                )
    except Exception:
        pass

    # Heuristic fallback — uses ONLY the user's findings
    if not findings:
        return ScenarioResponse(
            scenario_title=title,
            impact_summary="No findings yet. Upload files and click **Generate BRD** first, then run a scenario.",
            affected_items=[],
            shifted_deadlines=[],
            new_risks=[],
            diagram_diff_mermaid=None,
        )

    from app.prototype_agent import _is_budget, _is_deadline, _short

    items = [f for f in findings if f.type != "stakeholder"]
    must = [f for f in items if re.search(r"\b(must|mandatory|required|require|shall)\b", f.statement.lower())]
    optional = [f for f in items if f not in must]
    budgets = [f for f in items if _is_budget(f)]
    deadlines = [f for f in items if _is_deadline(f)]

    affected: list[ScenarioAffectedItem] = []
    shifted: list[dict] = []
    risks: list[str] = []
    if scenario_type == "budget_cut_30":
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Budget limit reduced by 30%.", status="compromised") for f in budgets]
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Non-mandatory item — candidate to defer.", status="delayed") for f in optional[:3]]
        risks.append("Mandatory items may not fit inside the reduced budget.")
    elif scenario_type == "launch_accelerated":
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Date pulled 6 weeks earlier.", status="compromised") for f in deadlines]
        shifted += [{"item": _short(f.statement, 8), "old_date": "As stated in source", "new_date": "6 weeks earlier", "reason": title} for f in deadlines]
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="May need to be dropped to hit the earlier date.", status="delayed") for f in optional[:3]]
        risks.append("Less time for review and testing of mandatory items.")
    elif scenario_type == "drop_tablet_scope":
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Not mandatory — removed from scope.", status="removed") for f in optional[:5]]
        risks.append("Stakeholders who requested removed items must agree.")
    else:
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Requirement strengthened.", status="enhanced") for f in must[:5]]
        risks.append("Stricter rules may add cost and time.")
    if not affected:
        affected = [ScenarioAffectedItem(id=f.id, statement=f.statement, impact=f"Review under '{title}'.", status="delayed") for f in items[:2]]

    def lbl(s: str) -> str:
        return re.sub(r"[\"'`<>\[\]{}()|#;:]", " ", _short(s, 6))

    lines = [
        "graph TD",
        "    classDef change fill:#fee2e2,stroke:#ef4444,stroke-width:2px;",
        "    classDef impact fill:#fef3c7,stroke:#f59e0b,stroke-width:2px;",
        f'    C["{lbl(title)}"]:::change',
    ]
    for i, a in enumerate(affected[:6]):
        lines.append(f'    C --> A{i}["{lbl(a.statement)}"]:::impact')

    return ScenarioResponse(
        scenario_title=title,
        impact_summary=f"**Scenario Evaluation** ({title}): {len(affected)} item(s) from your files are affected. {len(must)} item(s) are marked mandatory in your sources and should be protected.",
        affected_items=affected,
        shifted_deadlines=shifted,
        new_risks=risks,
        diagram_diff_mermaid="\n".join(lines),
    )
