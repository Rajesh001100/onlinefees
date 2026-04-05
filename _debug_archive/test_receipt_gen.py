import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from flask import Flask
from blueprints.student import receipt_utils
print(f"DEBUG: receipt_utils file: {receipt_utils.__file__}")
from blueprints.student.routes import _build_receipt_pdf_bytes
from reportlab.pdfgen import canvas

app = Flask(__name__)

def test_generate_receipt():
    print("Testing receipt generation...")
    
    # Dummy data
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
    
    inst = {
        "full_name": "JKK Munirajah College of Technology",
        "short_name": "Engineering"
    }
    
    payment = {
        "txn_id": "TXN-123456",
        "category": "TUITION",
        "method": "UPI",
        "amount": 50000,
        "status": "SUCCESS",
        "created_at": "2023-10-27 10:00:00"
    }
    
    receipt_no = "RCPT-20231027-123456"
    
    with app.app_context():
        # Ensure static/brand/jkkm.png exists or mocking it
        # specific path check
        logo_path = os.path.join(app.root_path, "static", "brand", "jkkm.png")
        print(f"Checking logo path: {logo_path} -> Exists: {os.path.exists(logo_path)}")
        
        try:
            pdf_bytes = _build_receipt_pdf_bytes(student, inst, payment, receipt_no)
            print(f"PDF Generated successfully. Size: {len(pdf_bytes)} bytes")
            
            # Save to a temp file for manual inspection if needed
            output_path = "test_receipt.pdf"
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            print(f"Saved to {output_path}")
            
        except Exception as e:
            print(f"FAILED to generate PDF: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_generate_receipt()
