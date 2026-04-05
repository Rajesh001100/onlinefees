# utils/db_migrate.py
"""
Database migration utility.
Uses relative path based on project structure instead of hardcoded absolute paths.
"""
import sqlite3
import os

# Derive DB path relative to this file's location
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "instance", "fees.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Applying migration: Create fee_installments table...")
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fee_installments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          institute_id TEXT NOT NULL,
          course TEXT NOT NULL,
          year INTEGER NOT NULL,

          label TEXT NOT NULL,          -- e.g. "Semester 1"
          due_date TEXT NOT NULL,       -- YYYY-MM-DD
          percentage INTEGER NOT NULL,  -- e.g. 50
          late_fee_per_day INTEGER NOT NULL DEFAULT 0,

          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

          FOREIGN KEY (institute_id) REFERENCES institutes(id)
        );
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fee_installments_plans
        ON fee_installments(institute_id, course, year);
        """)

        print("Applying migration: Create audit_logs table...")
        cursor.execute("""
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (institute_id) REFERENCES institutes(id),
            FOREIGN KEY (actor_user_id) REFERENCES users(id)
        );
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_inst_time
        ON audit_logs(institute_id, created_at);
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_action
        ON audit_logs(action);
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
        ON audit_logs(entity_type, entity_id);
        """)

        conn.commit()
        print("✅ Migration applied successfully.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
