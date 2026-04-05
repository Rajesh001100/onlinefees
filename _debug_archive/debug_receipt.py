import sys
import os
sys.path.append(os.getcwd())

from reportlab.pdfgen import canvas

# Monkey patch BEFORE importing routes
original_drawString = canvas.Canvas.drawString
original_drawRightString = canvas.Canvas.drawRightString
original_drawCentredString = canvas.Canvas.drawCentredString

import inspect

def log(msg):
    with open("debug_log.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def get_caller():
    try:
        frame = inspect.currentframe()
        # stack: debug_drawString -> caller
        caller = frame.f_back.f_back
        info = inspect.getframeinfo(caller)
        return f"{info.filename}:{info.lineno}"
    except:
        return "unknown"

def debug_drawString(self, x, y, text, *args, **kwargs):
    log(f"DEBUG: drawString at {get_caller()} x={x}, y={y}, text={repr(text)}")
    return original_drawString(self, x, y, text, *args, **kwargs)

def debug_drawRightString(self, x, y, text, *args, **kwargs):
    log(f"DEBUG: drawRightString at {get_caller()} x={x}, y={y}, text={repr(text)}")
    return original_drawRightString(self, x, y, text, *args, **kwargs)

def debug_drawCentredString(self, x, y, text, *args, **kwargs):
    log(f"DEBUG: drawCentredString at {get_caller()} x={x}, y={y}, text={repr(text)}")
    return original_drawCentredString(self, x, y, text, *args, **kwargs)

canvas.Canvas.drawString = debug_drawString
canvas.Canvas.drawRightString = debug_drawRightString
canvas.Canvas.drawCentredString = debug_drawCentredString

from flask import Flask
from blueprints.student.routes import _build_receipt_pdf_bytes

app = Flask(__name__)

def test():
    student = {
        "name": "Test Student",
        "admission_no": "2023001",
        "register_no": "810023001",
        "class": "B.E. CSE",
        "year": 3,
        "student_phone": "9876543210",
        "student_email": "test@example.com",
        "parent_email": "parent@example.com",
        "institute_id": "ENG"
    }
    inst = {"full_name": "JKK Munirajah College of Technology", "short_name": "Engineering"}
    payment = {
        "txn_id": "TXN-123456",
        "category": "TUITION",
        "method": "UPI",
        "amount": 50000,
        "status": "SUCCESS",
        "created_at": "2023-10-27 10:00:00"
    }
    receipt_no = "RCPT-2023"

    with app.app_context():
        try:
            _build_receipt_pdf_bytes(student, inst, payment, receipt_no)
            print("Finished successfully")
        except Exception as e:
            import traceback
            msg = traceback.format_exc()
            log("CAUGHT EXCEPTION")
            log(msg)
            print("CAUGHT EXCEPTION")
            traceback.print_exc()

if __name__ == "__main__":
    test()
