import sqlite3
import os

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "instance", "fees.db")

def reset_database():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Disable foreign keys temporarily if needed, but better to follow order
        cursor.execute("PRAGMA foreign_keys = OFF;")

        print("Deleting receipts...")
        cursor.execute("DELETE FROM receipts;")

        print("Deleting payments...")
        cursor.execute("DELETE FROM payments;")

        print("Deleting fee adjustments...")
        cursor.execute("DELETE FROM fee_adjustments;")

        print("Deleting students...")
        cursor.execute("DELETE FROM students;")

        print("Deleting student user accounts...")
        cursor.execute("DELETE FROM users WHERE role = 'STUDENT';")

        print("Deleting audit logs...")
        cursor.execute("DELETE FROM audit_logs;")

        # Optional: Reset autoincrement sequences
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('receipts', 'payments', 'fee_adjustments', 'students', 'users', 'audit_logs');")

        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()
        print("✅ Database reset successfully. All student data and payments cleared.")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during reset: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_database()
