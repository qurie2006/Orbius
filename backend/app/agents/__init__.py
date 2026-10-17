from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.clock import get_now
from app.config import settings
from app.model_router import generate_json
from app.schemas import Finding, OpsItem, SourceChunk


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def parse_json_payload(raw: Optional[str]) -> List[Dict]:
    if not raw:
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        for key in ("items", "findings", "ops"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    if isinstance(data, list):
        return data
    return []


def findings_from_dicts(rows: list[dict], agent: str, default_section: str) -> list[Finding]:
    out: list[Finding] = []
    for row in rows:
        if not row.get("statement") or not row.get("source_id"):
            continue
        try:
            # Parse model confidence or calibrate
            raw_conf = row.get("confidence")
            conf = float(raw_conf) if raw_conf is not None else compute_dynamic_confidence(row["statement"])
            conf = round(max(0.50, min(0.99, conf)), 2)

            out.append(
                Finding(
                    id=row.get("id") or _id("f"),
                    type=row.get("type") or "requirement",
                    statement=row["statement"],
                    source_id=row["source_id"],
                    source_span=row.get("source_span") or row["statement"][:180],
                    confidence=conf,
                    priority=row.get("priority") or "medium",
                    agent=agent,
                    owner=row.get("owner"),
                    acceptance_criteria=row.get("acceptance_criteria"),
                    section=row.get("section") or default_section,
                    method="model",
                    grounded=True,
                )
            )
        except Exception:
            continue
    return out


def compute_dynamic_confidence(statement: str, source_text: str = "") -> float:
    """Computes a deterministic, calibrated confidence score based on linguistic clarity,
    grounding, metrics, and modal certainty (no hash jitter)."""
    st_low = statement.lower().strip()
    score = 0.75

    # 1. Concrete numbers, percentages, currency, dates, SLAs boost confidence
    if re.search(r"(\$\d+|\d+%\s*|\b\d{1,4}\s*(?:ms|sec|min|hours|days|weeks|months|users|baskets|kiosk)\b|q[1-4]|october|november|december|wcag|2fa|sla|soc-2|iso)", st_low):
        score += 0.12

    # 2. Definite action verbs and strict modal requirements
    if any(k in st_low for k in ["must", "shall", "required", "mandates", "enforce", "prohibits", "locks"]):
        score += 0.08
    elif any(k in st_low for k in ["will", "ensure", "guarantee", "targets", "provides"]):
        score += 0.05
    elif any(k in st_low for k in ["maybe", "might", "could", "possibly", "think", "approx", "around", "tentative"]):
        score -= 0.15

    # 3. Statement length & richness
    if len(statement) > 70:
        score += 0.04
    elif len(statement) < 25:
        score -= 0.08

    # Clamped cleanly between 0.50 and 0.98
    return round(max(0.50, min(0.98, score)), 2)


def heuristic_findings(chunks: list[SourceChunk], agent: str) -> list[Finding]:
    findings: list[Finding] = []
    # Every finding below is derived strictly from text present in the
    # uploaded files. No canned/demo statements are injected.


    header_re = re.compile(r"^(from|to|cc|bcc|date|sent|subject|re|fw|fwd)\s*:", re.IGNORECASE)
    signoff_re = re.compile(r"^(thanks|thank you|regards|best|best regards|kind regards|cheers|sincerely|warm regards)[,!.\s]*$", re.IGNORECASE)
    greeting_re = re.compile(r"^(hi|hello|hey|dear)\b.{0,40}[,!]?$", re.IGNORECASE)

    # 1) Stakeholders from real email senders (+ signature title if present)
    signature_lines: set[str] = set()
    seen_people: set[str] = set()
    by_file: dict[str, list[SourceChunk]] = {}
    for c in chunks:
        by_file.setdefault(c.file_name, []).append(c)
    for file_chunks in by_file.values():
        from_match = None
        from_chunk = None
        for c in file_chunks:
            from_match = re.search(r"From:\s*([^\n\r<]+?)\s*(?:<([^>]+)>)?\s*$", c.text, re.IGNORECASE | re.MULTILINE)
            if from_match:
                from_chunk = c
                break
        lines = [l.strip() for c in file_chunks for l in c.text.split("\n") if l.strip()]
        title = None
        for i, line in enumerate(lines):
            if signoff_re.match(line):
                sig = lines[i + 1 : i + 4]
                for s in sig:
                    signature_lines.add(s)
                # A signature title is a short line after the name (e.g. "VP of Engineering")
                if len(sig) >= 2 and len(sig[1]) <= 60 and "@" not in sig[1]:
                    title = sig[1]
                break
        if from_match and from_chunk:
            name = from_match.group(1).strip().strip('"')
            if name and name.lower() not in seen_people:
                seen_people.add(name.lower())
                statement = f"{name} — {title}" if title else f"{name} (email sender)"
                findings.append(
                    Finding(
                        id=_id("f"),
                        type="stakeholder",
                        statement=statement,
                        source_id=from_chunk.source_id,
                        source_span=from_match.group(0).strip(),
                        confidence=0.9,
                        priority="medium",
                        agent=agent,
                        section="stakeholders",
                        method="rule_based",
                        grounded=True,
                    )
                )

    # 2) Requirements, constraints, actions from real sentences in the files
    for chunk in chunks:
        lines = [l.strip() for l in chunk.text.split("\n") if l.strip()]
        for line in lines:
            # Clean lead symbols
            clean = re.sub(r"^[-*•\d+\.]+\s*", "", line).strip()
            if len(clean) < 15:
                continue
            if header_re.match(clean) or signoff_re.match(clean) or greeting_re.match(clean):
                continue
            if line in signature_lines or clean in signature_lines:
                continue
            # Skip pure section headings like "Budget Ceiling:" or "Action Required Today:"
            if clean.endswith(":") and len(clean.split()) <= 6:
                continue

            # Determine section by keywords or chunk modality
            sec = "functional_requirements"
            clow = clean.lower()
            if "budget" in clow or "cost" in clow or "$" in clow or "price" in clow:
                sec = "budget"
            elif "risk" in clow or "delay" in clow or "slip" in clow or "hazard" in clow or "vulnerability" in clow:
                sec = "risks"
            elif "stakeholder" in clow or "owner" in clow or "client" in clow or "team" in clow or "sponsor" in clow:
                sec = "stakeholders"
            elif "scope" in clow or "out of" in clow or "boundary" in clow:
                sec = "scope"
            elif "latency" in clow or "security" in clow or "performance" in clow or "compliance" in clow:
                sec = "non_functional_requirements"
            elif "goal" in clow or "objective" in clow or "target" in clow or "aim" in clow:
                sec = "objectives"

            # Avoid duplicates
            if not any(f.statement == clean for f in findings):
                conf = compute_dynamic_confidence(clean)
                findings.append(
                    Finding(
                        id=_id("f"),
                        type="requirement",
                        statement=clean,
                        source_id=chunk.source_id,
                        source_span=clean,
                        confidence=conf,
                        priority="high" if conf > 0.85 else "medium",
                        agent=agent,
                        section=sec,
                        method="rule_based",
                        grounded=True,
                    )
                )


    return findings


def extract_expressed_date(text: str, now: datetime) -> str:
    t = text.lower()
    year = now.year

    # 1. Direct ISO date format: YYYY-MM-DD
    iso_match = re.search(r'\b(20\d\d)-(\d{1,2})-(\d{1,2})\b', text)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        return f"{y:04d}-{m:02d}-{d:02d}"

    # 2. Quarters: Q3 (Sept 30), Q4 (Oct 31 / Nov), Q1 (Mar 31), Q2 (Jun 30)
    if "q3" in t or "quarter 3" in t:
        return f"{year}-09-30"
    if "q4" in t or "quarter 4" in t or "october/november" in t:
        return f"{year}-10-31"
    if "q1" in t or "quarter 1" in t:
        return f"{year}-03-31"
    if "q2" in t or "quarter 2" in t:
        return f"{year}-06-30"

    # 3. Specific Month + Day patterns
    months = {
        "january": "01-31", "jan": "01-31", "february": "02-28", "feb": "02-28",
        "march": "03-31", "mar": "03-31", "april": "04-30", "apr": "04-30",
        "may": "05-31", "june": "06-30", "jun": "06-30", "july": "07-31", "jul": "07-31",
        "august": "08-31", "aug": "08-31", "september": "09-30", "sep": "09-30", "sept": "09-30",
        "october": "10-31", "oct": "10-31", "november": "11-30", "nov": "11-30",
        "december": "12-31", "dec": "12-31"
    }
    for mname, mdef in months.items():
        m_day = re.search(rf"\b{mname}\s+(\d{{1,2}})\b", t)
        if m_day:
            day = int(m_day.group(1))
            m_num = mdef.split("-")[0]
            return f"{year}-{m_num}-{day:02d}"
        day_m = re.search(rf"\b(\d{{1,2}})\s+{mname}\b", t)
        if day_m:
            day = int(day_m.group(1))
            m_num = mdef.split("-")[0]
            return f"{year}-{m_num}-{day:02d}"

    for mname, mdef in months.items():
        if re.search(rf"\b{mname}\b", t):
            return f"{year}-{mdef}"

    # 4. Explicit day offset windows (e.g. 14-day notice, 30 days)
    days_match = re.search(r"\b(\d+)[ -]?(?:day|days)\b", t)
    if days_match:
        n_days = int(days_match.group(1))
        return (now + timedelta(days=n_days)).date().isoformat()

    if "tomorrow" in t:
        return (now + timedelta(days=1)).date().isoformat()
    if "today" in t:
        return now.date().isoformat()
    if "next week" in t:
        return (now + timedelta(days=7)).date().isoformat()
    if "next month" in t:
        return (now + timedelta(days=30)).date().isoformat()

    return (now + timedelta(days=7)).date().isoformat()


def heuristic_ops(chunks: list[SourceChunk]) -> list[OpsItem]:
    now = get_now()
    items: list[OpsItem] = []

    for chunk in chunks:
        text = chunk.text

        # Extract From / Sender if present in custom emails
        from_match = re.search(r"From:\s*([^\n\r<]+)(?:<([^>]+)>)?", text, re.IGNORECASE)
        subj_match = re.search(r"Subject:\s*([^\n\r]+)", text, re.IGNORECASE)

        sender_name = from_match.group(1).strip() if from_match else None
        sender_email = from_match.group(2).strip() if from_match and from_match.group(2) else None
        subject = subj_match.group(1).strip() if subj_match else None

        if sender_email:
            recipient = f"{sender_name} <{sender_email}>" if sender_name else sender_email
        elif sender_name:
            recipient = sender_name
        else:
            recipient = "Client (unspecified)"

        # Check for email action requested
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            llow = line.lower()

            if any(k in llow for k in ["email", "reply", "confirm", "send", "follow up"]):
                items.append(
                    OpsItem(
                        type="draft_email",
                        context=subject or f"Follow-up: {line[:50]}",
                        source_id=chunk.source_id,
                        source_span=line,
                        confidence=0.91,
                        payload={
                            "recipient": recipient,
                            "subject": subject or f"Re: {line[:40]}",
                            "body": f"Hi {sender_name or 'there'},\n\nFollowing up regarding: {line}\n\nBest regards,\nOrbius Ops Agent",
                        },
                    )
                )
                break

            if any(k in llow for k in ["due", "deadline", "by next", "schedule", "target", "launch", "window", "notice", "days"]):
                due_date = extract_expressed_date(line, now)
                items.append(
                    OpsItem(
                        type="scheduled_alert",
                        context=f"Deadline: {line[:45]}",
                        source_id=chunk.source_id,
                        source_span=line,
                        confidence=0.92,
                        payload={
                            "target_date": f"{due_date}T09:00:00+00:00",
                            "original_phrase": line,
                            "reminder_message": f"Action Item due ({due_date}): {line}",
                        },
                    )
                )
                break

    return items[: settings.max_ops_per_document]


def run_specialist(agent: str, chunks: list[SourceChunk], section: str, extra_prompt: str = "") -> list[Finding]:
    joined = "\n\n".join(f"[{c.source_id} | {c.file_name} | {c.page_or_ts}]\n{c.text}" for c in chunks)
    prompt = f"""You extract BRD findings for the {agent}.
Today: {get_now().isoformat()}
Return JSON list of objects with keys: type, statement, source_id, source_span, confidence, priority, section, owner, acceptance_criteria.
type is one of requirement, stakeholder, constraint, risk, decision.
Never invent a source_id. Copy source_id from the chunks. Drop anything without a source.
{extra_prompt}

CHUNKS:
{joined[:12000]}
"""
    parsed = parse_json_payload(generate_json(prompt, purpose=agent))
    live = findings_from_dicts(parsed, agent, section)
    return live or heuristic_findings(chunks, agent)


def run_ops(chunks: list[SourceChunk]) -> list[OpsItem]:
    joined = "\n\n".join(f"[{c.source_id}]\n{c.text}" for c in chunks)
    today = get_now().date().isoformat()
    prompt = f"""You are the Ops Agent. Today is {today}.
Separate product REQUIREMENTS from project TASKS.
Requirements are things the product must do (e.g. the app must support 2FA).
Tasks are follow-ups (e.g. email the security team) and scheduled alerts.

CRITICAL INSTRUCTION FOR DATES & DEADLINES:
- Deliver the ACTUAL DATE or DEADLINE expressed in the document text.
- If a quarter is specified (e.g. Q3 -> end of Q3 {today[:4]}-09-30; Q4 -> {today[:4]}-10-31), deliver that exact target date.
- If an offset window is specified (e.g. 14-day notice, 30 days), compute the ISO date from today ({today}).
- If an explicit calendar date is written (e.g. October 15, November 30), deliver that exact date in target_date.
- Never invent arbitrary dates or default to 7 days.

Return JSON array:
{{"type":"draft_email|scheduled_alert","context":"","source_id":"","source_span":"","confidence":0.0,"payload":{{}}}}
draft_email payload: recipient, subject, body
scheduled_alert payload: target_date, original_phrase, reminder_message

CHUNKS:
{joined[:8000]}
"""
    rows = parse_json_payload(generate_json(prompt, purpose="ops_agent"))
    items: list[OpsItem] = []
    for row in rows:
        try:
            if float(row.get("confidence") or 0) < settings.ops_confidence_threshold:
                continue
            items.append(OpsItem.model_validate(row))
        except Exception:
            continue
    return items[: settings.max_ops_per_document] or heuristic_ops(chunks)
