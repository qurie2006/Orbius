from __future__ import annotations

import json
import re
from app.model_router import generate_json
from app.schemas import Finding, ScenarioAffectedItem, ScenarioResponse, SourceChunk


PRESET_SCENARIOS = {
    "budget_cut_30": {
        "title": "Budget Cut by 30%",
        "prompt": "Simulate reducing total project budget ceiling by 30%. Identify which non-core features, tablet companions, or integrations must be deferred."
    },
    "launch_accelerated": {
        "title": "Accelerate Go-Live by 6 Weeks (Q3 Push)",
        "prompt": "Simulate pulling launch earlier by 6 weeks. Identify what testing, compliance, and multi-language features must be skipped or fast-tracked."
    },
    "drop_tablet_scope": {
        "title": "Drop Staff Tablet Companion Scope",
        "prompt": "Simulate removing the staff tablet companion device from MVP scope to focus purely on the customer-facing checkout kiosk."
    },
    "strict_security_wcag": {
        "title": "Strict Zero-Trust 2FA & WCAG 2.2 AAA Enforcement",
        "prompt": "Simulate upgrading accessibility and security constraints to maximum level. Identify impact on kiosk hardware specs, manager override latency, and training."
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
                return ScenarioResponse(
                    scenario_title=data.get("scenario_title", title),
                    impact_summary=data.get("impact_summary", ""),
                    affected_items=affected,
                    shifted_deadlines=data.get("shifted_deadlines", []),
                    new_risks=data.get("new_risks", []),
                    diagram_diff_mermaid=data.get("diagram_diff_mermaid"),
                )
    except Exception:
        pass

    # Heuristic fallback
    affected = [
        ScenarioAffectedItem(
            id=findings[0].id if findings else "f1",
            statement=findings[0].statement if findings else "Core timeline constraint",
            impact=f"Adjusted priority and dependencies under '{title}' constraint.",
            status="delayed" if "cut" in scenario_type or "accelerated" in scenario_type else "compromised",
        )
    ]
    if len(findings) > 1:
        affected.append(
            ScenarioAffectedItem(
                id=findings[1].id,
                statement=findings[1].statement,
                impact="Requires revised validation from technical architect.",
                status="enhanced" if "security" in scenario_type else "compromised",
            )
        )

    mermaid_diff = """graph TD
    classDef change fill:#fee2e2,stroke:#ef4444,stroke-width:2px;
    classDef impact fill:#fef3c7,stroke:#f59e0b,stroke-width:2px;
    classDef stable fill:#dcfce7,stroke:#10b981,stroke-width:2px;

    Change["⚡ Scenario Trigger: Budget / Timeline Shift"]:::change --> Dep1["Scope Prioritization & Cutbacks"]:::impact
    Dep1 --> Dep2["Postponed Secondary Features"]:::impact
    Change --> Core["Core MVP Requirements"]:::stable
"""

    return ScenarioResponse(
        scenario_title=title,
        impact_summary=f"**Scenario Evaluation**: Under this condition ({instruction}), secondary scope items face schedule reallocations while core security requirements remain baseline.",
        affected_items=affected,
        shifted_deadlines=[
            {"item": "Staff training and rollout", "old_date": "Original target", "new_date": "+3 weeks adjusted", "reason": "Requires revised operational alignment"}
        ],
        new_risks=[
            "Potential friction if store staff are not pre-trained on modified flow",
            "Third-party vendor turnaround buffer reduced"
        ],
        diagram_diff_mermaid=mermaid_diff,
    )
