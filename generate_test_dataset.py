#!/usr/bin/env python3
"""
Orbius Test Dataset Generator
Generates an empirical Enterprise Cloud SaaS benchmark pack with planted semantic contradictions,
strict regulatory constraints (SOC-2 Type II, ISO 27001, GDPR), and ground-truth validation labels.
"""

import json
import zipfile
from pathlib import Path

DATASET_DIR = Path(__file__).parent / "test_dataset_files"
ZIP_PATH = Path(__file__).parent / "orbius_test_dataset.zip"

DOC1_SECURITY = """AETHERCLOUD ENTERPRISE SECURITY ARCHITECTURE SPECIFICATION
Classification: Confidential — SOC-2 Type II & ISO 27001 Scope

1. High Availability & Multi-Region SLA
The AetherCloud platform must guarantee 99.99% uptime availability across active-active multi-region clusters (US-East and EU-West). Automated failover must complete in under 250 milliseconds with zero data loss.

2. Access Control & Authentication
Zero-Trust architecture mandates hardware-backed FIDO2 WebAuthn multi-factor authentication (2FA) for all administrative and tenant user accounts. Passwords without hardware keys or authenticator verification are strictly prohibited.

3. Comprehensive Audit Logging & Retention
Under SOC-2 Type II Section 4.2 compliance, the platform must retain all immutable telemetry, authentication logs, and data mutation trails for a minimum mandatory period of 7 years without exception.

4. Financial Ceiling
Total infrastructure, third-party observability, and cloud API budget ceiling is capped at $180,000 annually.
"""

DOC2_LEGAL = """From: Elena Vance <elena.vance@aethercloud.io>
To: Jordan Hale <jordan@orbius.dev>
Date: 2026-10-14T09:30:00Z
Subject: Legal & Privacy Review — GDPR Compliance Constraints

Jordan,

Following up on our privacy council audit regarding EU market launch:

1. Right-to-Erasure (GDPR Article 17):
The platform must implement a cryptographically verified data purging mechanism that guarantees complete deletion of all user activity data, telemetry records, and PII within 30 days of an erasure request. Retaining user activity records beyond 30 days violates EU privacy regulations.

2. Budget & Infrastructure Sovereign Guardrails:
Finance has flagged that multi-region active-active clusters will incur $320,000 in egress and compute costs. Finance mandates that we remain strictly within a single-region deployment to preserve the $180,000 budget cap.

3. Timeline:
Legal compliance sign-off is scheduled for Quarter 4 (October/November). Go-live cannot occur before Q4 compliance sign-off.

Best regards,
Elena Vance
Head of Legal & Compliance
"""

DOC3_STANDUP = """Standup Transcript — AetherCloud Core Platform
Date: 2026-10-15
Attendees: Jordan Hale (PM), Marcus Vance (Security Eng), Priya Patel (Lead Architect), Aisha Lin (Design)

Jordan: Let's review launch scope for the Enterprise Cloud SaaS console. Target launch is Q3 according to our customer roadmap.
Priya: Timeline conflict — Elena from legal just confirmed compliance review cannot finish until Q4. Launching in Q3 would mean deploying without ISO 27001 certification.
Marcus: Security requirement — FIDO2 WebAuthn is mandatory for all access. However, sales is asking for password-only guest checkout access for prospective clients.
Jordan: We cannot bypass 2FA for guest links. Zero-Trust requires hardware MFA on all sessions.
Priya: On offline resilience — DevOps engineers in field environments need an offline local-first sync buffer that can queue up to 50 administrative actions and converge with zero lost updates on reconnect.
Aisha: Admin wireframe v3 specifies dark-mode UI with WCAG 2.2 AA accessibility and under 300ms p95 response time.
"""

DOC4_CONTROLS = """Control_ID,Framework,Requirement,Owner,Target_Frequency
AC-1,SOC-2,Hardware Token FIDO2 WebAuthn Enforcement,Marcus Vance,Continuous
AU-2,SOC-2,7-Year Immutable Telemetry & Log Retention,Priya Patel,Continuous
PR-3,GDPR,30-Day User Data Purge on Erasure Request,Elena Vance,Automated Daily
HA-4,SLA,99.99% Multi-Region Uptime Across US and EU,Priya Patel,Quarterly Audit
SC-5,ISO 27001,AES-256 Encryption at Rest and TLS 1.3 in Transit,Marcus Vance,Continuous
"""

GROUND_TRUTH = {
    "dataset_name": "AetherCloud Enterprise Cloud SaaS Benchmark",
    "total_documents": 4,
    "ground_truth_findings_count": 12,
    "planted_contradictions": [
        {
            "id": "conflict_timeline",
            "topic": "Delivery Timeline Conflict (Q3 vs Q4)",
            "left_source": "03_eng_standup_transcript.txt",
            "left_statement": "Target launch is Q3 according to our customer roadmap",
            "right_source": "02_legal_privacy_guidelines.eml",
            "right_statement": "Go-live cannot occur before Q4 compliance sign-off"
        },
        {
            "id": "conflict_retention_vs_erasure",
            "topic": "Compliance Conflict: 7-Year Audit Retention vs. 30-Day GDPR Erasure",
            "left_source": "01_cloud_security_memo.txt",
            "left_statement": "retain all immutable telemetry, authentication logs, and data mutation trails for a minimum mandatory period of 7 years",
            "right_source": "02_legal_privacy_guidelines.eml",
            "right_statement": "complete deletion of all user activity data, telemetry records, and PII within 30 days of an erasure request"
        },
        {
            "id": "conflict_sla_vs_budget",
            "topic": "Infrastructure Conflict: 99.99% Multi-Region SLA vs. Single-Region Budget Cap",
            "left_source": "01_cloud_security_memo.txt",
            "left_statement": "guarantee 99.99% uptime availability across active-active multi-region clusters",
            "right_source": "02_legal_privacy_guidelines.eml",
            "right_statement": "Finance mandates that we remain strictly within a single-region deployment to preserve the $180,000 budget cap"
        }
    ]
}


def generate():
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    
    files = {
        "01_cloud_security_memo.txt": DOC1_SECURITY,
        "02_legal_privacy_guidelines.eml": DOC2_LEGAL,
        "03_eng_standup_transcript.txt": DOC3_STANDUP,
        "04_soc2_iso_controls.csv": DOC4_CONTROLS,
        "ground_truth_labels.json": json.dumps(GROUND_TRUTH, indent=2),
    }

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            fpath = DATASET_DIR / fname
            fpath.write_text(content, encoding="utf-8")
            zf.writestr(fname, content)
            print(f"Generated: {fname}")

    # Also place copy in backend uploads/demo if helpful
    backend_zip = Path(__file__).parent / "backend" / "orbius_test_dataset.zip"
    if ZIP_PATH.exists():
        backend_zip.write_bytes(ZIP_PATH.read_bytes())

    print(f"\nSuccessfully generated {ZIP_PATH} with {len(files)} test files and 3 planted contradictions.")


if __name__ == "__main__":
    generate()
