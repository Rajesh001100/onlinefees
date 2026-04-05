import sqlite3

DB_PATH = "instance/fees.db"

def make_phone(i: int, offset: int) -> str:
    # Produces a realistic 10-digit Indian-style number starting with 9
    # Example: 9000000101 etc.
    return f"9{(100000000 + i * 101 + offset) % 1000000000:09d}"

def run():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Ensure columns exist (safe if already added; will error if not)
    # If you already added columns via ALTER TABLE, this is fine to skip.
    # We'll just proceed assuming columns exist.

    rows = cur.execute("""
        SELECT id, admission_no, register_no, student_phone, parent_phone
        FROM students
        ORDER BY institute_id, admission_no
    """).fetchall()

    updated = 0

    for idx, r in enumerate(rows, start=1):
        admission_no = r["admission_no"]

        # Register number: simple and consistent for expo
        new_register = r["register_no"] if r["register_no"] else f"REG-{admission_no}"

        # Phones: unique, deterministic, looks real
        new_student_phone = r["student_phone"] if r["student_phone"] else make_phone(idx, 11)
        new_parent_phone  = r["parent_phone"]  if r["parent_phone"]  else make_phone(idx, 77)

        cur.execute("""
            UPDATE students
            SET register_no = ?,
                student_phone = ?,
                parent_phone = ?
            WHERE id = ?
        """, (new_register, new_student_phone, new_parent_phone, r["id"]))

        updated += 1

    con.commit()
    con.close()

    print(f"✅ Auto-filled register_no + phones for {updated} students.")

if __name__ == "__main__":
    run()
