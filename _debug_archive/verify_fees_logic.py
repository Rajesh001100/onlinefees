import sqlite3
import os
from utils.fees import get_full_course_fee_state

# Mock Flask App context
from flask import Flask
app = Flask(__name__)
app.config['FIRST_GRAD_DISCOUNT'] = 25000

DB_PATH = os.path.join("instance", "fees.db")

def verify():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Get a student (Admission No: ENG24250282 or similar)
    student = conn.execute("SELECT * FROM students LIMIT 1").fetchone()
    print(f"Testing with Student: {student['name']} (Year {student['year']})")
    
    with open("verification_result.txt", "w") as f:
        with app.app_context():
            # Call the function
            state = get_full_course_fee_state(conn, student['id'])
            
            f.write(f"Fee State OK: {state['ok']}\n")
            if not state['ok']:
                f.write(state['error'])
                return

            for y in state['years']:
                f.write(f"\n--- Year {y['year']} (Current: {y['is_current']}) ---\n")
                f.write(f"Status: {y['status']}\n")
                f.write(f"Locked: {y['is_locked']}\n")
                f.write(f"Total: {y['total']}, Paid: {y['paid']}, Due: {y['due']}\n")
                f.write("Items:\n")
                # Look for fee_items OR fallback to semesters if applicable, 
                # but we know it's fee_items now.
                items_list = y.get('fee_items', [])
                for item in items_list:
                    f.write(f"  - {item['label']} ({item['type']}): {item['amount']} [Paid: {item['paid']}, Locked: {item['locked']}]\n")
                
    conn.close()

if __name__ == "__main__":
    verify()
