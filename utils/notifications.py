
import logging
import os

# Configure logger specific for notifications
logger = logging.getLogger("notifications")
logger.setLevel(logging.INFO)

# Ensure logs dir or file exists
if not os.path.exists("logs"):
    os.makedirs("logs", exist_ok=True)

handler = logging.FileHandler("logs/notifications.log")
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def send_alert(student_id: int, message: str, type="SMS"):
    """
    Simulates sending an SMS/Email.
    In real world: Call Twilio / SendGrid API.
    """
    logger.info(f"[{type}] To StudentID {student_id}: {message}")
    print(f"🔔 SENT {type} to Student {student_id}: {message}")
    return True
