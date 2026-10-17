from __future__ import annotations

import os
import re
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
import httpx


def _reload_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")


def send_real_email(recipient: str, subject: str, body: str) -> dict:
    """Dispatches a real email using Brevo API, Resend API, or Gmail SMTP if credentials exist in .env.
    Defaults to dry-run if no valid recipient email or credentials are present."""
    _reload_env()
    brevo_key = os.getenv("BREVO_API_KEY")
    resend_key = os.getenv("RESEND_API_KEY")
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")

    # Extract email address or default to dry-run
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", recipient)
    if not email_match:
        return {
            "sent": False,
            "method": "dry_run",
            "target": recipient,
            "note": "No valid recipient email address found. Executed in audit dry-run mode.",
        }
    target_email = email_match.group(0)

    # 1. Brevo API (Configured & Live)
    if brevo_key:
        try:
            sender_email = os.getenv("BREVO_SENDER_EMAIL", "studio@orbius.ai")
            r = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": brevo_key, "Content-Type": "application/json"},
                json={
                    "sender": {"name": "Orbius Studio", "email": sender_email},
                    "to": [{"email": target_email}],
                    "subject": subject,
                    "textContent": body,
                },
                timeout=8.0,
            )
            if r.status_code in (200, 201):
                return {"sent": True, "method": "brevo", "target": target_email, "detail": r.json()}
        except Exception as e:
            print("[Email Service] Brevo API error:", e)

    # 2. Resend API
    if resend_key:
        try:
            r = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                json={
                    "from": os.getenv("EMAIL_FROM", "Orbius Studio <onboarding@resend.dev>"),
                    "to": [target_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=8.0,
            )
            if r.status_code in (200, 201):
                return {"sent": True, "method": "resend", "target": target_email, "detail": r.json()}
        except Exception as e:
            print("[Email Service] Resend API error:", e)

    # 3. Gmail SMTP
    if gmail_user and gmail_pass:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = gmail_user
            msg["To"] = target_email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=8.0) as server:
                server.login(gmail_user, gmail_pass)
                server.sendmail(gmail_user, [target_email], msg.as_string())
            return {"sent": True, "method": "gmail_smtp", "target": target_email}
        except Exception as e:
            print("[Email Service] Gmail SMTP error:", e)

    return {
        "sent": False,
        "method": "simulated",
        "target": target_email,
        "note": "No active email credentials configured; action executed in Studio Dispatch mode.",
    }

