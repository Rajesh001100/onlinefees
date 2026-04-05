import os
from dotenv import load_dotenv
load_dotenv()

from utils.mailer import send_email

print("GMAIL_USER =", os.getenv("GMAIL_USER"))
print("APP_PASSWORD loaded =", "YES" if os.getenv("GMAIL_APP_PASSWORD") else "NO")

ok = send_email("YOUR_EMAIL_TO_TEST@gmail.com", "Test Mail", "Hello from fees system")
print("RESULT:", ok)
