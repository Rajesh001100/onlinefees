import sqlite3
import os
import traceback

DB_PATH = os.path.join("instance", "fees.db")

def setup():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 0. Check Schema (Debug)
        print("Checking Schema...")
        cols = [i[1] for i in c.execute("PRAGMA table_info(fee_plans)").fetchall()]
        print(f"Fee Plans Cols: {cols}")
        
        # 1. Get Institute ID for Engineering (ID is 'ENG')
        inst = c.execute("SELECT id FROM institutes WHERE id='ENG'").fetchone()
        if not inst:
            print("❌ Engineering institute not found.")
            # fallback for robustness
            inst = c.execute("SELECT id FROM institutes WHERE short_name='Engineering'").fetchone() 
            if not inst:
                 return
        inst_id = inst[0]
        
        course = "B.E-MECH"
        
        # 2. Loop Years 1-4
        for yr in range(1, 5):
            # Check Plan
            plan = c.execute(
                "SELECT id FROM fee_plans WHERE institute_id=? AND course=? AND year=?",
                (inst_id, course, yr)
            ).fetchone()
            
            if not plan:
                print(f"Creating Fee Plan for {course} Year {yr}...")
                # Dynamically build insert based on available columns
                if 'exam' in cols:
                     c.execute(
                        "INSERT INTO fee_plans (institute_id, course, year, tuition, exam, other) VALUES (?, ?, ?, ?, ?, ?)",
                        (inst_id, course, yr, 50000, 3000, 10000)
                    )
                else:
                    c.execute(
                        "INSERT INTO fee_plans (institute_id, course, year, tuition, other) VALUES (?, ?, ?, ?, ?)",
                        (inst_id, course, yr, 50000, 10000)
                    )
                
            # Check Installments
            insts = c.execute(
                "SELECT id FROM fee_installments WHERE institute_id=? AND course=? AND year=?",
                (inst_id, course, yr)
            ).fetchall()
            
            if not insts:
                print(f"Creating Installments for {course} Year {yr}...")
                # Sem 1
                c.execute(
                    """
                    INSERT INTO fee_installments (institute_id, course, year, label, due_date, percentage, late_fee_per_day)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (inst_id, course, yr, f"Year {yr} - Sem 1", "2025-08-01", 50, 50)
                )
                # Sem 2
                c.execute(
                    """
                    INSERT INTO fee_installments (institute_id, course, year, label, due_date, percentage, late_fee_per_day)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (inst_id, course, yr, f"Year {yr} - Sem 2", "2026-01-01", 50, 50)
                )

        print("✅ Test Data Setup Complete.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        traceback.print_exc()
    finally:
        if conn:
            conn.commit()
            conn.close()

if __name__ == "__main__":
    setup()
