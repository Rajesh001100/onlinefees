import sqlite3
import os

db_path = os.path.join('c:\\college_fees_system', 'instance', 'fees.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT year, tuition, exam, other FROM fee_plans WHERE course='B.Tech-IT' ORDER BY year").fetchall()
conn.close()

for r in rows:
    print(f"Year {r['year']}: Tuition={r['tuition']}, Exam={r['exam']}, Other={r['other']}")
