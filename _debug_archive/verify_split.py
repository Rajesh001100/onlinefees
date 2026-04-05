import sqlite3
import sys
import os
from flask import Flask, g

# Add project root to path
sys.path.append(os.getcwd())

from utils.fees import get_full_course_fee_state

app = Flask(__name__)
app.config['DATABASE'] = os.path.join("instance", "fees.db")

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

def verify():
    with app.app_context():
        db = get_db()
        # M.Rohith (ID 14) or M.Rajesh (ID 3)?
        # Let's try M.Rohith first as he was the context of recent fixes.
        # But we need to ensure he HAS a hostel fee.
        
        # Check M.Rohith
        print("--- Checking M.Rohith (ID 14) ---")
        student_id = 14
        
        # Ensure he has a hostel fee adjustment for testing
        adj = db.execute("SELECT * FROM fee_adjustments WHERE student_id=? AND category='HOSTEL'", (student_id,)).fetchone()
        if not adj:
            print("Adding dummy HOSTEL fee for verification...")
            db.execute("INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (?, 'HOSTEL', 'Hostel Fee', 50000)", (student_id,))
            db.execute("UPDATE students SET is_hosteller=1 WHERE id=?", (student_id,))
            db.commit()
        
        state = get_full_course_fee_state(db, student_id)
        
        # Find Year 2
        with open("verify_split_output.txt", "w") as f:
            # Print total adjustment found
            adj_row = db.execute("SELECT amount FROM fee_adjustments WHERE student_id=? AND category='HOSTEL'", (student_id,)).fetchone()
            if adj_row:
                f.write(f"Source Hostel Fee: {adj_row['amount']}\n")

            for y in state['years']:
                if y['year'] == 2:
                    f.write(f"Year 2 Items (Current: {y['is_current']}):\n")
                    for item in y['fee_items']:
                        f.write(f"  - {item['label']} | Amount: {item['amount']} | Status: {item['status']}\n")

if __name__ == "__main__":
    verify()
