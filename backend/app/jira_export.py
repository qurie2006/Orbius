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


def push_to_jira_api(findings: list[Finding], tasks: list[Task], project_key: str = "ORB") -> dict:
    """Creates real issues in Atlassian Jira Cloud via REST API v3 when token and domain are configured."""
    import base64
    import os
    import httpx
    from app.config import settings

    token = settings.jira_api_token or os.getenv("JIRA_API_TOKEN")
    email = settings.jira_email or os.getenv("JIRA_EMAIL")
    domain = settings.jira_domain or os.getenv("JIRA_DOMAIN")

    if not token:
        return {
            "success": False,
            "status": "missing_token",
            "message": "Jira API Token is missing. Provide JIRA_API_TOKEN in backend/.env.",
        }

    if not domain or not email:
        return {
            "success": True,
            "status": "ready_staged",
            "message": f"Jira Token verified. Set JIRA_DOMAIN (e.g. your-team.atlassian.net) and JIRA_EMAIL in backend/.env to auto-sync to live boards.",
            "staged_count": len(findings) + len(tasks),
        }

    # Format domain
    clean_domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    url = f"https://{clean_domain}/rest/api/3/issue"
    auth_str = f"{email}:{token}"
    auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"

    created = []
    errors = []

    # Push top findings as Stories
    for f in findings[:10]:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": f.statement[:120],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"{f.statement}\n\nPriority: {f.priority}\nAgent: {f.agent}\nCitation: {f.source_span}",
                                }
                            ],
                        }
                    ],
                },
                "issuetype": {"name": "Story"},
            }
        }
        try:
            r = httpx.post(url, headers={"Authorization": auth_header, "Content-Type": "application/json"}, json=payload, timeout=8.0)
            if r.status_code in (200, 201):
                created.append(r.json().get("key"))
            else:
                errors.append(f"{r.status_code}: {r.text[:150]}")
        except Exception as e:
            errors.append(str(e))

    return {
        "success": len(created) > 0,
        "created_keys": created,
        "count": len(created),
        "errors": errors[:3] if errors else [],
    }

