from __future__ import annotations

import json
import re
from typing import Dict, List, Optional
from app.model_router import generate_json
from app.schemas import Finding, ScenarioAffectedItem, ScenarioResponse, SourceChunk


PRESET_SCENARIOS = {
    "budget_cut": {
        "title": "25% Budget Reduction",
        "prompt": "Simulate reducing the project budget by 25%. Identify which infrastructure or non-essential features must be deferred or descoped."
    },
    "budget_cut_30": {
        "title": "Budget Cut by 30%",
        "prompt": "Simulate reducing the project budget by 30%. Identify which items must be deferred or descoped."
    },
    "timeline_squeeze": {
        "title": "4-Week Timeline Squeeze",
        "prompt": "Simulate fast-tracking the launch date by 4 weeks earlier. Identify critical path items that must be prioritized or dropped."
    },
    "launch_accelerated": {
        "title": "Deliver 6 Weeks Earlier",
        "prompt": "Simulate delivering 6 weeks earlier than planned. Identify what must be fast-tracked or dropped."
    },
    "vendor_drop": {
        "title": "Cloud Vendor Migration & Standards",
        "prompt": "Simulate migrating from proprietary single-cloud dependencies to open multi-cloud standards."
    },
    "drop_tablet_scope": {
        "title": "Reduce Scope to Must-Haves",
        "prompt": "Simulate cutting scope down to mandatory items only. Identify what stays and what is removed."
    },
    "scope_creep": {
        "title": "Scope Expansion + SOC 2 & WCAG Compliance",
        "prompt": "Simulate raising security and compliance requirements to strict SOC-2 Type II and WCAG AAA levels."
    },
    "strict_security_wcag": {
        "title": "Tighten Security & Compliance",
        "prompt": "Simulate raising security and compliance requirements to the strictest level."
    }
}

# Fast cache for simulated scenarios
_SCENARIO_CACHE: Dict[str, ScenarioResponse] = {}


def _clean_node_text(text: str, max_words: int = 4) -> str:
    """Produces clean, compact human-readable node labels without punctuation conflicts."""
    clean = re.sub(r'f_[a-zA-Z0-9_]+:\s*', '', text)
    clean = re.sub(r"[\"'`<>\[\]{}()|#;:\*]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    words = clean.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return clean or "System Component"


def _build_structured_mermaid(
    title: str,
    impacted: List[str],
    risks: List[str]
) -> str:
    """Builds an intuitive, properly structured 3-tier cascading flowchart:
    Trigger -> Impacted Components -> Downstream Risks."""
    t_label = _clean_node_text(title, max_words=5)
    
    # 2 impacted items and 2 risks for a clean, digestible graph
    imp1 = _clean_node_text(impacted[0] if len(impacted) > 0 else "Infrastructure Allocation", 4)
    imp2 = _clean_node_text(impacted[1] if len(impacted) > 1 else "Testing and QA Scope", 4)
    
    rsk1 = _clean_node_text(risks[0] if len(risks) > 0 else "Single Region Failover Risk", 5)
    rsk2 = _clean_node_text(risks[1] if len(risks) > 1 else "Compressed Verification Cycle", 5)

    return f"""flowchart TD
    classDef trigger fill:#fee2e2,stroke:#ef4444,stroke-width:2px,color:#991b1b;
    classDef impact fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#92400e;
    classDef risk fill:#ede9fe,stroke:#8b5cf6,stroke-width:2px,color:#5b21b6;

    subgraph S1 ["1. Scenario Trigger"]
        T["{t_label}"]:::trigger
    end

    subgraph S2 ["2. Impacted Components"]
        I1["{imp1}"]:::impact
        I2["{imp2}"]:::impact
    end

    subgraph S3 ["3. Cascading Downstream Risks"]
        R1["{rsk1}"]:::risk
        R2["{rsk2}"]:::risk
    end

    T --> I1 --> R1
    T --> I2 --> R2
"""


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

    # Cache key for rapid sub-second responses
    cache_key = f"{scenario_type}_{title}_{hash(custom_prompt)}_{len(findings)}"
    if cache_key in _SCENARIO_CACHE:
        return _SCENARIO_CACHE[cache_key]

    findings_summary = "\n".join([f"- [{f.id}] ({f.section}) {f.statement}" for f in findings[:15]])

    prompt = f"""You are the Orbius What-If Scenario Impact Simulator.
Analyze the downstream cascading impact of this hypothetical scenario change on the existing project requirements:

SCENARIO: {title}
DETAILS: {instruction}
CURRENT BRD FINDINGS:
{findings_summary}

Determine:
1. Executive impact summary: 2-3 concise sentences explaining the trade-offs and decision consequence.
2. Which requirements are compromised, delayed, enhanced, or removed (2-4 items max).
3. What target dates or deadlines shift.
4. What new risks are introduced (2 key risks).
5. A clean, structured 3-tier Mermaid flowchart TD with subgraphs:
   - Subgraph 1: Scenario Trigger
   - Subgraph 2: 2 Impacted Components
   - Subgraph 3: 2 Cascading Risks
   Use very short labels (2-4 words per node). NEVER use long sentences inside node brackets.

Return a JSON object with keys:
- "scenario_title": string
- "impact_summary": string
- "affected_items": array of objects with keys "id", "statement", "impact", "status" ("compromised" | "delayed" | "enhanced" | "removed")
- "shifted_deadlines": array of objects with keys "item", "old_date", "new_date", "reason"
- "new_risks": array of strings
- "diagram_diff_mermaid": string (Mermaid flowchart TD)
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
                if raw_diff and "subgraph" in raw_diff:
                    raw_diff = re.sub(r'f_[a-zA-Z0-9_]+:\s*', '', raw_diff)
                    sanitized_diff = sanitize_mermaid(raw_diff)
                else:
                    # Guarantee clean 3-tier structure
                    imp_texts = [a.statement for a in affected]
                    sanitized_diff = _build_structured_mermaid(title, imp_texts, data.get("new_risks", []))

                resp = ScenarioResponse(
                    scenario_title=data.get("scenario_title", title),
                    impact_summary=data.get("impact_summary", ""),
                    affected_items=affected,
                    shifted_deadlines=data.get("shifted_deadlines", []),
                    new_risks=data.get("new_risks", []),
                    diagram_diff_mermaid=sanitized_diff,
                )
                _SCENARIO_CACHE[cache_key] = resp
                return resp
    except Exception:
        pass

    # Heuristic fallback — structured and immediate
    if not findings:
        return ScenarioResponse(
            scenario_title=title,
            impact_summary="No findings yet. Ingest documents and click **Generate BRD** first to simulate scenarios.",
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

    if scenario_type in {"budget_cut", "budget_cut_30"}:
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Budget cap enforced; high-cost infrastructure reduced.", status="compromised") for f in budgets[:1]]
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Optional scope item deferred to Phase 2.", status="delayed") for f in optional[:2]]
        risks.append("Single-region deployment limits high availability SLA.")
        risks.append("Deferred components require separate stakeholder approval.")
        summary = f"Reducing budget by 25% enforces single-region deployment to preserve the expenditure ceiling, deferring {len(optional[:2])} secondary components to Phase 2."
    elif scenario_type in {"timeline_squeeze", "launch_accelerated"}:
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Launch milestone accelerated by 4 weeks.", status="compromised") for f in deadlines[:1]]
        shifted += [{"item": _short(f.statement, 8), "old_date": "Original Target", "new_date": "4 Weeks Earlier", "reason": title} for f in deadlines[:1]]
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Testing window compressed; manual audits deferred.", status="delayed") for f in optional[:2]]
        risks.append("Reduced QA testing cycle increases day-1 defect risk.")
        risks.append("Third-party compliance certification may not clear in time.")
        summary = "Fast-tracking the launch by 4 weeks compresses the verification and compliance signoff window, requiring overtime and deselecting non-critical edge cases."
    elif scenario_type in {"vendor_drop", "drop_tablet_scope"}:
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Proprietary vendor dependency decoupled.", status="removed") for f in optional[:2]]
        risks.append("Transition to open standards requires additional data migration.")
        risks.append("Short-term developer ramp-up needed on new tooling.")
        summary = "Migrating away from single-vendor lock-in decouples proprietary dependencies, replacing them with open standards while introducing temporary migration overhead."
    else:
        affected += [ScenarioAffectedItem(id=f.id, statement=f.statement, impact="Elevated to strict compliance requirement.", status="enhanced") for f in must[:2]]
        risks.append("Mandatory FIDO2 and SOC-2 audit logs increase operational overhead.")
        risks.append("Hardware token provisioning adds $42,000 to upfront costs.")
        summary = "Raising security to strict SOC-2 and FIDO2 standards enforces hardware authentication and audit immutability, adding rigorous verification gates to the release."

    impact_statements = [a.statement for a in affected]
    diagram = _build_structured_mermaid(title, impact_statements, risks)

    resp = ScenarioResponse(
        scenario_title=title,
        impact_summary=summary,
        affected_items=affected,
        shifted_deadlines=shifted,
        new_risks=risks,
        diagram_diff_mermaid=diagram,
    )
    _SCENARIO_CACHE[cache_key] = resp
    return resp
