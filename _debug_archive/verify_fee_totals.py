
import sqlite3
import os
import sys

# Ensure we can import utils
sys.path.append(os.getcwd())

from utils.fees import get_fee_state_for_student

def setup_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Schema
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, institute_id TEXT, course TEXT, year INTEGER, is_hosteller INTEGER, quota_type TEXT, is_first_graduate INTEGER)")
    conn.execute("CREATE TABLE fee_plans (institute_id TEXT, course TEXT, year INTEGER, tuition INTEGER, other INTEGER)")
    conn.execute("CREATE TABLE fee_adjustments (id INTEGER PRIMARY KEY, student_id INTEGER, category TEXT, label TEXT, amount INTEGER)")
    conn.execute("CREATE TABLE payments (id INTEGER PRIMARY KEY, student_id INTEGER, category TEXT, amount INTEGER, status TEXT)")
    conn.execute("CREATE TABLE fee_installments (institute_id TEXT, course TEXT, year INTEGER, label TEXT, due_date TEXT, percentage REAL, late_fee_per_day INTEGER)")
    
    return conn

def test_fee_totals():
    db = setup_db()
    
    # 1. Setup Data
    # Student 1: Year 1, Hosteller
    db.execute("INSERT INTO students (id, institute_id, course, year, is_hosteller, quota_type, is_first_graduate) VALUES (1, 'ENG', 'BE', 1, 1, 'GOVT', 0)")
    # Student 2: Year 2, Day Scholar
    db.execute("INSERT INTO students (id, institute_id, course, year, is_hosteller, quota_type, is_first_graduate) VALUES (2, 'ENG', 'BE', 2, 0, 'GOVT', 0)")
    
    # Fee Plan
    # Year 1: Tuition 50k, Other (Admission) 10k
    db.execute("INSERT INTO fee_plans (institute_id, course, year, tuition, other) VALUES ('ENG', 'BE', 1, 50000, 10000)")
    # Year 2: Tuition 50k, Other 5k
    db.execute("INSERT INTO fee_plans (institute_id, course, year, tuition, other) VALUES ('ENG', 'BE', 2, 50000, 5000)")
    
    # Adjustments
    # Student 1: Hostel 20k, Gym 1k, Exam 2k
    db.execute("INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (1, 'HOSTEL', 'Hostel Fee', 20000)")
    db.execute("INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (1, 'GYM', 'Gym Fee', 1000)")
    db.execute("INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (1, 'EXAM', 'Exam Fee', 2000)")
    
    # Student 2: Bus 15k, Exam 2k
    db.execute("INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (2, 'BUS', 'Bus Fee', 15000)")
    db.execute("INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (2, 'EXAM', 'Exam Fee', 2000)")

    # 2. Test Student 1 (Year 1)
    print("--- Testing Year 1 Student (Hosteller) ---")
    s1 = get_fee_state_for_student(db, 1)
    
    print(f"Charges: {s1['charges']}")
    print(f"Net Total: {s1['net_total']}")
    
    # Expected Logic:
    # Tuition (50k) + Hostel (20k) + Bus (0) + Admission/Other (10k) = 80k
    # Excluded: Gym (1k), Exam (2k)
    # Total should be 80,000
    
    expected_s1 = 50000 + 20000 + 10000
    if s1['net_total'] == expected_s1:
        print("[OK] Student 1 Total Correct")
    else:
        print(f"[FAIL] Student 1 Total Mismatch. Goal: {expected_s1}, Got: {s1['net_total']}")

    # 3. Test Student 2 (Year 2)
    print("\n--- Testing Year 2 Student (Day Scholar) ---")
    s2 = get_fee_state_for_student(db, 2)
    
    # print(f"Charges: {s2['charges']}")
    print(f"Net Total: {s2['net_total']}")
    
    # Expected Logic:
    # Tuition (50k) + Hostel (0) + Bus (15k)
    # Excluded: Exam (2k), Other (5k - not year 1)
    # Total should be 65,000
    
    expected_s2 = 50000 + 15000
    if s2['net_total'] == expected_s2:
        print("[OK] Student 2 Total Correct")
    else:
        print(f"[FAIL] Student 2 Total Mismatch. Goal: {expected_s2}, Got: {s2['net_total']}")

if __name__ == "__main__":
    test_fee_totals()
