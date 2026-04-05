# utils/mailer.py
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable, Optional, Union


# =========================
# CONFIG (from environment only — no hardcoded defaults)
# =========================
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

FROM_NAME = os.getenv("MAIL_FROM_NAME", "Online College Fees Payment System")
REPLY_TO = os.getenv("MAIL_REPLY_TO", "")

# Set to "0" to fully disable emails without breaking app
MAIL_ENABLED = os.getenv("MAIL_ENABLED", "1").strip() == "1"

# Timeout seconds
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "20"))


# -------------------------
# Public: Send email + optional PDF attachment
# -------------------------
def send_receipt_email(
    to_emails: Union[str, Iterable[str]],
    subject: str,
    body: str,
    pdf_bytes: Optional[bytes] = None,
    filename: str = "receipt.pdf",
):
    msg = _build_message(to_emails=to_emails, subject=subject, body=body)

    if pdf_bytes:
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=filename,
        )

    _send(msg)


# -------------------------
# Public: Simple email (no attachment)
# -------------------------
def send_email(
    to_emails: Union[str, Iterable[str]],
    subject: str,
    body: str,
):
    msg = _build_message(to_emails=to_emails, subject=subject, body=body)
    _send(msg)


# -------------------------
# Internal: Build message
# -------------------------
def _build_message(
    to_emails: Union[str, Iterable[str]],
    subject: str,
    body: str,
) -> EmailMessage:
    if isinstance(to_emails, str):
        recipients = [to_emails.strip()]
    else:
        recipients = [str(x).strip() for x in to_emails if str(x).strip()]

    msg = EmailMessage()
    msg["From"] = f"{FROM_NAME} <{SMTP_USER}>" if SMTP_USER else FROM_NAME
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject.strip()
    msg.set_content(body)

    if REPLY_TO:
        msg["Reply-To"] = REPLY_TO

    return msg


# -------------------------
# Internal: Send via SMTP
# -------------------------
def _send(msg: EmailMessage):
    if not MAIL_ENABLED:
        print("ℹ️ MAIL_ENABLED=0, skipping email send.")
        return

    if not SMTP_USER or not SMTP_PASS:
        raise RuntimeError(
            "SMTP_USER/SMTP_PASS not set. Put them in .env file."
        )

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        print("❌ SMTP send failed:", repr(e))
        raise
