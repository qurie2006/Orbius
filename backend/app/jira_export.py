from __future__ import annotations

import csv
import io
import json
from app.schemas import Finding, Task


def generate_jira_csv(findings: list[Finding], tasks: list[Task]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Standard Jira Import Header
    writer.writerow([
        "Issue Type",
        "Summary",
        "Description",
        "Priority",
        "Acceptance Criteria",
        "Component",
        "Labels",
        "Original Source",
    ])

    for f in findings:
        issue_type = "Story" if f.type == "requirement" else "Task" if f.type == "decision" else "Risk"
        priority = f.priority.title()
        
        # Gherkin Acceptance Criteria
        ac = f.acceptance_criteria or f"Given valid system context\nWhen executing: {f.statement}\nThen expected pass condition must be verified."
        desc = f"Requirement statement: {f.statement}\n\nAgent: {f.agent}\nConfidence: {f.confidence:.0%}\nSource Span: {f.source_span}"

        writer.writerow([
            issue_type,
            f.statement[:120],
            desc,
            priority,
            ac,
            f.section.replace("_", " ").title(),
            f"orbius-brd,{f.type}",
            f.source_id,
        ])

    for t in tasks:
        writer.writerow([
            "Action Item",
            f"[Ops Action] {t.context}"[:120],
            f"Payload: {json.dumps(t.payload)}\nSource: {t.source_span}",
            "High" if t.status == "pending" else "Medium",
            "Must be approved/executed by designated stakeholder before release gate.",
            "Operations & Actions",
            "orbius-ops,action-item",
            t.source_id,
        ])

    return output.getvalue()


def generate_linear_json(findings: list[Finding], tasks: list[Task]) -> str:
    issues = []
    
    # Priority mapping for Linear (1 = Urgent, 2 = High, 3 = Normal, 4 = Low)
    priority_map = {"high": 2, "medium": 3, "low": 4}

    for f in findings:
        issues.append({
            "title": f.statement[:120],
            "description": f"## Requirement Details\n{f.statement}\n\n### Acceptance Criteria\n```gherkin\nGiven system is in valid state\nWhen operation occurs\nThen {f.statement}\n```\n\n**Confidence**: {f.confidence:.0%}\n**Source**: `{f.source_id}`",
            "priority": priority_map.get(f.priority.lower(), 3),
            "state": "Todo",
            "labels": ["orbius-brd", f.section, f.type],
        })

    for t in tasks:
        issues.append({
            "title": f"[Ops Action] {t.context}"[:120],
            "description": f"### Operational Follow-up\n**Action**: {t.context}\n**Recipient**: {t.payload.get('recipient', 'Unassigned')}\n\n**Context**: {t.source_span}",
            "priority": 1 if t.status == "pending" else 3,
            "state": "Todo",
            "labels": ["orbius-ops", "action-item"],
        })

    return json.dumps({"issues": issues, "count": len(issues)}, indent=2)
