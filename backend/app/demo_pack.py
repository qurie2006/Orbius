from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from app.clock import get_now
from app.config import settings

EMAIL_1 = """From: Priya Patel <priya.patel@aethercloud.io>
To: Jordan Hale <jordan@orbius.dev>
Date: {today}
Subject: AetherCloud Enterprise Launch — Architecture & SLA Mandates

Hi Jordan,

We need the AetherCloud Enterprise SaaS architecture to guarantee 99.99% multi-region high availability across US-East and EU-West clusters with sub-250ms automated failover.

Under our SOC-2 Type II audit requirements, all administrative authentication must strictly mandate hardware-backed FIDO2 WebAuthn multi-factor authentication (2FA). Passwords alone are prohibited.

Also, our compliance charter requires immutable telemetry retention for 7 years without exception.

Please email the client today confirming we received the architecture blueprints and that the SOC-2 security review is on the calendar.

Target launch is locked for Q3 according to the board commitment.

Budget ceiling is $180,000 including cloud compute, database replication, and Gemini AI agent pipelines.

Thanks,
Priya Patel
VP of Cloud Infrastructure
"""

EMAIL_2 = """From: Elena Vance <elena.vance@aethercloud.io>
To: Jordan Hale <jordan@orbius.dev>
Cc: Priya Patel <priya.patel@aethercloud.io>
Date: {today}
Subject: Legal & Privacy Review — GDPR Compliance & Budget Constraints

Jordan —

Critical corrections following our privacy council audit regarding EU market launch:

1. Right-to-Erasure (GDPR Article 17):
The platform must implement cryptographically verified data purging guaranteeing complete deletion of all user activity and telemetry within 30 days of an erasure request. Retaining user data beyond 30 days directly violates EU privacy regulations.

2. Infrastructure & Budget Sovereign Guardrails:
Finance confirmed that active-active multi-region deployment will incur over $320,000 in egress and replication costs. Finance mandates that we remain strictly within a single-region deployment to preserve the $180,000 budget cap.

3. Timeline:
Legal compliance sign-off is scheduled for Quarter 4 (October/November). Go-live cannot occur before Q4 compliance sign-off.

Also: WCAG 2.2 AA accessibility and AES-256 encryption at rest are mandatory constraints for all tenant interfaces.

Elena Vance
Head of Legal & Compliance
"""

TRANSCRIPT = """Standup Transcript — AetherCloud Core Platform
Attendees: Jordan Hale (PM), Marcus Vance (Security Eng), Priya Patel (Lead Architect), Aisha Lin (Design)

Jordan: Scope is multi-tenant cloud console and CLI administration. Out of scope: legacy on-premise hypervisors.

Aisha: Wireframe v3 shows the Zero-Trust security dashboard with hardware MFA enrollment, RBAC role management, and session revocation. Contrast on warning badges is now fully WCAG 2.2 compliant.

Marcus: Risk — The external IdP SSO provider requires a 14-day change notice window. If we miss it we slip our certification milestone.

Jordan: We need an owner for offline sync acceptance criteria. When DevOps engineers are disconnected, the local buffer must hold up to 50 administrative actions and converge with zero lost updates on reconnect.

Priya: Stakeholders are Priya Patel (infrastructure sponsor), Elena Vance (compliance), and enterprise customer security leads.
"""

PDF_BRIEF = """AETHERCLOUD ENTERPRISE SAAS — SPECIFICATION BRIEF (PDF extract)

Objective: Provide an enterprise-grade cloud governance platform with automated zero-trust enforcement and verifiable audit trails.

Functional Requirements:
- Hardware-backed FIDO2 WebAuthn 2FA enforcement
- Role-Based Access Control (RBAC) with granular tenant isolation
- Automated failover routing across multi-region edge gateways
- Cryptographic verification of user data deletion requests

Non-Functional Requirements:
- P99 API latency under 300ms for authenticated requests
- Offline local mesh sync buffer for up to 50 administrative changes
- 99.99% availability SLA with automated health recovery

Open Question: Who owns the continuous SOC-2 audit logging questionnaire and evidence repository?
"""

SHEET_CSV = """Item,Amount,Owner,Notes
Cloud Infrastructure,78000,Priya,Includes Kubernetes and load balancers
Security & FIDO2 Pipeline,42000,Marcus,Hardware authentication tokens and HSM
Gemini AI Analysis Pipeline,24000,Jordan,Token processing and real-time validation
Compliance & Legal Audit,16000,Elena,ISO 27001 and SOC-2 external auditor fees
Contingency Buffer,20000,Finance,11% contingency reserve
Total,180000,Finance,Ceiling not to exceed
"""

WIREFRAME_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">
  <rect width="960" height="600" fill="#0f172a"/>
  <rect x="40" y="36" width="880" height="528" rx="20" fill="#1e293b" stroke="#334155"/>
  <text x="72" y="92" font-family="system-ui, sans-serif" font-weight="700" font-size="26" fill="#f8fafc">AetherCloud — Zero-Trust Security &amp; Compliance Console</text>
  <rect x="72" y="128" width="240" height="360" rx="14" fill="#0f172a" stroke="#3b82f6"/>
  <text x="92" y="168" font-size="18" font-weight="600" fill="#60a5fa">1. Zero-Trust Gateway</text>
  <text x="92" y="210" font-size="13" fill="#94a3b8">FIDO2 Hardware 2FA</text>
  <text x="92" y="240" font-size="13" fill="#94a3b8">Session Lifetime: 4h</text>
  <text x="92" y="270" font-size="13" fill="#94a3b8">mTLS Mutual Auth</text>
  <rect x="360" y="128" width="240" height="360" rx="14" fill="#0f172a" stroke="#10b981"/>
  <text x="380" y="168" font-size="18" font-weight="600" fill="#34d399">2. Policy &amp; SLA Guard</text>
  <text x="380" y="210" font-size="13" fill="#94a3b8">Multi-Region 99.99%</text>
  <text x="380" y="240" font-size="13" fill="#94a3b8">AES-256 Storage</text>
  <text x="380" y="270" font-size="13" fill="#94a3b8">Failover: &lt;250ms</text>
  <rect x="648" y="128" width="240" height="360" rx="14" fill="#0f172a" stroke="#8b5cf6"/>
  <text x="668" y="168" font-size="18" font-weight="600" fill="#a78bfa">3. Verifiable Audit</text>
  <text x="668" y="210" font-size="13" fill="#94a3b8">SOC-2 Immutable Logs</text>
  <text x="668" y="240" font-size="13" fill="#94a3b8">GDPR 30-Day Purge</text>
  <text x="668" y="270" font-size="13" fill="#94a3b8">Hash-Chained Mesh</text>
</svg>
"""


def write_demo_pack() -> list[Path]:
    root = settings.demo_dir
    root.mkdir(parents=True, exist_ok=True)
    today = get_now().strftime("%Y-%m-%d")
    files = {
        "email_priya.txt": EMAIL_1.format(today=today),
        "email_elena.txt": EMAIL_2.format(today=today),
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
