import sqlite3

DB_PATH = "instance/fees.db"

def add_column(cur, sql):
    try:
        cur.execute(sql)
        print("OK:", sql)
    except sqlite3.OperationalError as e:
        # If column already exists, SQLite says "duplicate column name"
        msg = str(e).lower()
        if "duplicate column name" in msg:
            print("SKIP (already exists):", sql)
        else:
            raise

def main():
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()

        add_column(cur, "ALTER TABLE students ADD COLUMN is_hosteller INTEGER DEFAULT 0")
        add_column(cur, "ALTER TABLE students ADD COLUMN scholarship_type TEXT DEFAULT 'NONE'")
        add_column(cur, "ALTER TABLE students ADD COLUMN quota_type TEXT DEFAULT 'REGULAR'")
        add_column(cur, "ALTER TABLE students ADD COLUMN is_first_graduate INTEGER DEFAULT 0")

        con.commit()
        print("\n✅ Done. Current students columns:")
        cols = [r[1] for r in cur.execute("PRAGMA table_info(students)").fetchall()]
        print(cols)

    finally:
        con.close()

if __name__ == "__main__":
    main()
