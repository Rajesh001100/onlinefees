import sqlite3

DB = "instance/fees.db"

con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("PRAGMA foreign_keys=OFF;")

cur.execute("BEGIN;")

# 1) rename old table
cur.execute("ALTER TABLE fee_adjustments RENAME TO fee_adjustments_old;")

# 2) recreate with DISCOUNT allowed
cur.execute("""
CREATE TABLE fee_adjustments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  category TEXT NOT NULL CHECK (
    category IN ('TUITION','EXAM','OTHER','HOSTEL','BUS','GYM','LAUNDRY','FINE','DISCOUNT')
  ),
  label TEXT NOT NULL,
  amount INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);
""")

# 3) copy old data
cur.execute("""
INSERT INTO fee_adjustments (id, student_id, category, label, amount, created_at)
SELECT id, student_id, category, label, amount, created_at
FROM fee_adjustments_old;
""")

# 4) drop old table
cur.execute("DROP TABLE fee_adjustments_old;")

cur.execute("COMMIT;")
cur.execute("PRAGMA foreign_keys=ON;")
con.close()

print("✅ fee_adjustments updated: DISCOUNT allowed")
