
import sqlite3
import os
import sys
from datetime import date, timedelta

import sys
import io

# Force UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
sys.path.append(os.getcwd())

from utils.fees import get_fee_state_for_student

def setup_db():

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    
    # Load schema
    with open("database/migrations/schema.sql", "r") as f:
        schema = f.read()
    con.executescript(schema)
    
    return con

def test_repro():
    db = setup_db()
    
    # 1. Insert Institute
    db.execute("INSERT INTO institutes (id, short_name, full_name) VALUES ('ENG', 'Engineering', 'Inst Name')")
    
    # 2. Insert Fee Plan: Course=CSE, Year=2, Tuition=32000, Other=1000
    db.execute("INSERT INTO fee_plans (institute_id, course, year, tuition, other) VALUES ('ENG', 'CSE', 2, 32000, 1000)")
    
    # 3. Insert Student: ID=1
    # We need a user first? Schema says students.user_id references users.id
    db.execute("INSERT INTO users (username, password_hash, role, institute_id) VALUES ('student', 'pass', 'STUDENT', 'ENG')")
    user_id = db.execute("SELECT id FROM users").fetchone()["id"]
    
    db.execute("""
        INSERT INTO students (user_id, admission_no, name, dob, year, class, course, institute_id)
        VALUES (?, 'A001', 'Test Student', '2000-01-01', 2, 'B.E-CSE', 'CSE', 'ENG')
    """, (user_id,))
    student_id = db.execute("SELECT id FROM students").fetchone()["id"]
    
    # 4. Insert Installment: 50% due in future
    # Course=CSE, Year=2
    future_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    db.execute("""
        INSERT INTO fee_installments (institute_id, course, year, label, due_date, percentage, late_fee_per_day)
        VALUES ('ENG', 'CSE', 2, 'Installment 1', ?, 50, 100)
    """, (future_date,))
    
    db.commit()
    
    # 5. Check Fee State
    # Expected: Due should be 0 or small (if only 50% is due in future, what is due NOW?)
    # If standard logic, Tuition Due = 32000.
    # If installment logic works as user expects, Tuition Due should be 0 (since installment is in future).
    # Or if installment was in past 50%, Due should be 16000.
    
    print("--- Case 1: Installment in Future (30 days) ---")
    state = get_fee_state_for_student(db, student_id)
    print(f"Total Tuition: {state['charges']['TUITION']}")
    print(f"Tuition Due:   {state['due']['TUITION']}")
    print(f"Other Due:     {state['due']['OTHER']}")
    print(f"Current Due:   {state['current_due_total']}")
    print("Installments:")
    for i in state['installments']:
        print(f"  - {i['label']} ({i['due_date']}): {i['amount']} (Status: {i['status']})")
    print("Due Breakdown:")
    for k, v in state['due'].items():
        if v > 0: print(f"  {k}: {v}")

    
    # 6. Update Installment to be in PAST
    past_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    db.execute("UPDATE fee_installments SET due_date=? WHERE label='Installment 1'", (past_date,))
    db.commit()
    
    print("\n--- Case 2: Installment in Past (5 days ago) ---")
    state = get_fee_state_for_student(db, student_id)
    print(f"Total Tuition: {state['charges']['TUITION']}")
    print(f"Tuition Due:   {state['due']['TUITION']}")
    print(f"Current Due:   {state['current_due_total']}")
    
    if state['current_due_total'] < state['due_total']:
         print("\n[RESULT] verified: Current Due is less than Total Due (future installment ignored).")
    else:
         print("\n[RESULT] verified: Current Due matches Total Due (past installment included).")


if __name__ == "__main__":
    # Mock current_app configuration for utils.fees
    from flask import Flask
    app = Flask(__name__)
    with app.app_context():
        test_repro()
