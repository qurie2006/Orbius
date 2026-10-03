from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from app.clock import get_now
from app.config import settings


EMAIL_1 = """From: Priya Mehta <priya@lumenretail.com>
To: Jordan Hale <jordan@orbius.dev>
Date: {today}
Subject: Lumen Checkout — kickoff notes

Hi Jordan,

We need the Lumen self-checkout redesign to support 2FA for store managers and guest checkout for shoppers.

Please email the client today confirming we received the wireframes and that security review is on the calendar.

Launch is locked for Q3 according to the board packet I attached last week.

Budget ceiling is $180k including design and the Vertex AI usage.

Thanks,
Priya
"""

EMAIL_2 = """From: Marcus Chen <marcus@lumenretail.com>
To: Jordan Hale <jordan@orbius.dev>
Cc: Priya Mehta <priya@lumenretail.com>
Subject: Timeline correction + design freeze

Jordan —

Quick correction from finance: the go-live window is Q4, not Q3. We cannot staff stores before October.

Final designs due next month. If we miss that, holiday inventory planning slips.

Also: WCAG 2.2 AA is a hard constraint for the kiosk screens.

Marcus
"""

TRANSCRIPT = """Standup transcript — Lumen Checkout
Attendees: Jordan Hale (PM), Aisha Rahman (Design), Leo Park (Eng)

Jordan: Scope is in-store kiosk plus a companion staff tablet. Out of scope: native mobile apps.

Aisha: Wireframe v2 shows a three-step flow: scan, pay, receipt. Accessibility contrast on the pink CTAs is still too low.

Leo: Risk — the current POS vendor has a 14-day change window. If we miss it we slip a sprint.

Jordan: Assumption is that existing SKU data can be imported via CSV. We still need an owner for acceptance criteria on offline mode.

Aisha: Stakeholders are Priya (client sponsor), Marcus (finance), and store ops leads.
"""

PDF_BRIEF = """LUMEN RETAIL — PROJECT BRIEF (PDF extract)

Objective: Reduce average checkout time by 30% in flagship stores using an AI-assisted kiosk.

Functional requirements:
- Scan barcodes and QR codes
- Apply loyalty discounts
- Print or email receipts
- Staff override with 2FA

Non-functional:
- P99 latency under 400ms for scan lookup
- Offline queue for up to 50 baskets

Open question: who owns the PCI-DSS questionnaire?
"""

SHEET_CSV = """Item,Amount,Owner,Notes
Design,42000,Aisha,Includes kiosk + tablet
Engineering,96000,Leo,Includes Vertex pipeline
Gemini/Vertex,18000,Jordan,Estimated tokens
Contingency,24000,Marcus,10%
Total,180000,Finance,Ceiling not to exceed
"""

WIREFRAME_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">
  <rect width="960" height="600" fill="#f4e6ea"/>
  <rect x="40" y="36" width="880" height="528" rx="28" fill="#fff8fb" stroke="#d9b8c4"/>
  <text x="72" y="92" font-family="Georgia" font-size="28" fill="#6b4a55">Lumen Kiosk — Scan / Pay / Receipt</text>
  <rect x="72" y="128" width="240" height="360" rx="18" fill="#e7eef8" stroke="#b7c6de"/>
  <text x="92" y="168" font-size="18" fill="#4d5b78">1. Scan</text>
  <rect x="360" y="128" width="240" height="360" rx="18" fill="#efe6f6" stroke="#c9b4d8"/>
  <text x="380" y="168" font-size="18" fill="#5a4a6d">2. Pay</text>
  <rect x="648" y="128" width="240" height="360" rx="18" fill="#f3e2e8" stroke="#d9b3c0"/>
  <text x="668" y="168" font-size="18" fill="#6b4a55">3. Receipt</text>
  <text x="92" y="220" font-size="14" fill="#6b4a55">Barcode + QR</text>
  <text x="380" y="220" font-size="14" fill="#5a4a6d">Card / wallet / 2FA override</text>
  <text x="668" y="220" font-size="14" fill="#6b4a55">Print or email</text>
</svg>
"""


def write_demo_pack() -> list[Path]:
    root = settings.demo_dir
    root.mkdir(parents=True, exist_ok=True)
    today = get_now().strftime("%Y-%m-%d")
    files = {
        "email_priya.txt": EMAIL_1.format(today=today),
        "email_marcus.txt": EMAIL_2,
        "standup_transcript.txt": TRANSCRIPT,
        "project_brief.txt": PDF_BRIEF,
        "budget.csv": SHEET_CSV,
        "wireframe.svg": WIREFRAME_SVG,
    }
    paths: list[Path] = []
    for name, body in files.items():
        path = root / name
        path.write_text(body, encoding="utf-8")
        paths.append(path)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        pdf_path = root / "project_brief.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        y = 740
        c.setFont("Times-Roman", 14)
        for line in PDF_BRIEF.splitlines():
            c.drawString(56, y, line[:95])
            y -= 18
        c.save()
        paths.append(pdf_path)
    except Exception:
        pass
    return paths


def demo_ops_seed_dates():
    now = get_now()
    return {
        "today_iso": now.date().isoformat(),
        "next_month_iso": (now + timedelta(days=30)).date().isoformat(),
    }
