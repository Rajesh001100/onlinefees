# utils/whatsapp.py
"""
WhatsApp notification utility using Twilio API.
Supports: payment reminders, fee due alerts, payment success confirmations.
"""
import os
from typing import Optional

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox default


def _get_client():
    from twilio.rest import Client
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_whatsapp(to_phone: str, message: str) -> Optional[str]:
    """
    Send a WhatsApp message to a phone number.
    to_phone: Indian mobile number, e.g. '9876543210' or '+919876543210'
    Returns: message SID if sent, None if failed.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("⚠️ WhatsApp: TWILIO credentials not configured. Skipping send.")
        return None

    # Normalize phone to international format
    phone = to_phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = f"+91{phone}"  # Default to India country code

    try:
        client = _get_client()
        msg = client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{phone}",
        )
        print(f"✅ WhatsApp sent to {phone}: SID={msg.sid}")
        return msg.sid
    except Exception as e:
        print(f"❌ WhatsApp send failed to {phone}: {e}")
        return None


def send_fee_due_reminder(student_name: str, phone: str, due_amount: int,
                           inst_name: str = "JKK Munirajah Institutions") -> Optional[str]:
    """Send a fee due reminder to student/parent."""
    msg = (
        f"📢 *Fee Reminder — {inst_name}*\n\n"
        f"Dear *{student_name}*,\n\n"
        f"Your outstanding fee amount is *₹{due_amount:,}*.\n\n"
        f"Please pay as soon as possible to avoid late fees.\n\n"
        f"📞 Contact office: 04285-262149\n"
        f"_This is an automated message. Do not reply._"
    )
    return send_whatsapp(phone, msg)


def send_payment_success(student_name: str, phone: str, amount: int,
                          receipt_no: str, inst_name: str = "JKK Munirajah Institutions") -> Optional[str]:
    """Send a payment success confirmation."""
    msg = (
        f"✅ *Payment Confirmed — {inst_name}*\n\n"
        f"Dear *{student_name}*,\n\n"
        f"Your payment of *₹{amount:,}* has been received successfully.\n\n"
        f"🧾 *Receipt No:* {receipt_no}\n\n"
        f"Thank you! Keep this receipt for your records.\n"
        f"_This is an automated message. Do not reply._"
    )
    return send_whatsapp(phone, msg)


def send_bulk_reminders(student_ids: list) -> dict:
    """
    Send fee due reminders to a list of students.
    Returns: {'sent': int, 'failed': int, 'skipped': int}
    """
    from models import Student
    from extensions import db
    from utils.fees import get_fee_state_for_student

    sent = failed = skipped = 0

    for sid in student_ids:
        s = Student.query.get(sid)
        if not s:
            skipped += 1
            continue

        phone = s.parent_phone or s.student_phone
        if not phone:
            skipped += 1
            continue

        state = get_fee_state_for_student(db, sid)
        if not state.get("ok") or state.get("due_total", 0) <= 0:
            skipped += 1
            continue

        result = send_fee_due_reminder(
            student_name=s.name,
            phone=phone,
            due_amount=state["due_total"],
        )
        if result:
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed, "skipped": skipped}
