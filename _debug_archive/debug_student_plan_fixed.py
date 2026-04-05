import sqlite3
import os

DB_PATH = os.path.join("instance", "fees.db")

def debug():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Get M.Rohith
    cursor = conn.cursor()
    student = cursor.execute("SELECT * FROM students WHERE admission_no='ENG24250140'").fetchone()
    
    if not student:
        print("Student M.Rohith (ENG24250140) not found!")
        return

    # Write to file
    with open("debug_analysis.txt", "w") as f:
        f.write(f"Student: {student['name']}, ID: {student['id']}, Course: {student['course']}, Year: {student['year']}\n")
        
        # Check Plan for this student's course and year
        plan = cursor.execute("SELECT * FROM fee_plans WHERE course=? AND year=?", 
                              (student['course'], student['year'])).fetchone()
        
        if not plan:
            f.write(f"No Fee Plan found for Course '{student['course']}' Year {student['year']}\n")
        else:
            f.write(f"Plan Found: ID={plan['id']}, Total={plan['tuition'] + plan['other']}\n")
            
            # Check Installments (Correct Schema: institute_id, course, year)
            installments = cursor.execute("SELECT * FROM fee_installments WHERE institute_id=? AND course=? AND year=?", 
                                          (student['institute_id'], student['course'], student['year'])).fetchall()
            f.write(f"Installments ({len(installments)}):\n")
            for i in installments:
                f.write(f"  - ID={i['id']}, Label='{i['label']}', Due={i['due_date']}\n")

        f.write("\n--- Year 1 Analysis ---\n")
        y1_plan = cursor.execute("SELECT * FROM fee_plans WHERE course=? AND year=1", (student['course'],)).fetchone()
        if y1_plan:
             f.write(f"Year 1 Plan: Total={y1_plan['tuition'] + y1_plan['other']}\n")
        
        payments = cursor.execute("SELECT * FROM payments WHERE student_id=?", (student['id'],)).fetchall()
        f.write(f"Total Payments: {len(payments)}\n")
        for p in payments:
            f.write(f"  - [{p['created_at']}] {p['category']} : {p['amount']}\n")
    
    conn.close()

if __name__ == "__main__":
    debug()
