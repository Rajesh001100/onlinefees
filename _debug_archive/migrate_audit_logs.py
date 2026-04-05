import sqlite3

DB = "instance/fees.db"

con = sqlite3.connect(DB)
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institute_id TEXT NOT NULL,
  actor_user_id INTEGER,
  actor_role TEXT,
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id INTEGER,
  details TEXT,
  ip TEXT,
  user_agent TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
""")

# Useful indexes
cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_inst_time ON audit_logs(institute_id, created_at);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);")

con.commit()
con.close()

print("✅ audit_logs table ready")
