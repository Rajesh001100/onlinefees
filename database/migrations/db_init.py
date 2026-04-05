import os
import sqlite3
from werkzeug.security import generate_password_hash

# -------------------------------------------------
# Paths (absolute, safe)
# -------------------------------------------------
MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(MIGRATIONS_DIR, "..", ".."))

DB_PATH = os.path.join(BASE_DIR, "instance", "fees.db")
SCHEMA_PATH = os.path.join(MIGRATIONS_DIR, "schema.sql")

print("RUNNING:", __file__)
print("DB PATH:", DB_PATH)
print("SCHEMA PATH:", SCHEMA_PATH)


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def dob_to_password(dob_yyyy_mm_dd: str) -> str:
    y, m, d = dob_yyyy_mm_dd.split("-")
    return f"{d}{m}{y}"  # DDMMYYYY


def list_tables(cur) -> set:
    rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] if isinstance(r, tuple) else r["name"] for r in rows}


# -------------------------------------------------
# Main
# -------------------------------------------------
def run():
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema.sql not found at {SCHEMA_PATH}")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Load schema
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        cur.executescript(f.read())

    tables = list_tables(cur)
    print("▶ Tables created:", ", ".join(sorted(tables)))

    # -------------------------------------------------
    # Institutes
    # -------------------------------------------------
    institutes = [
        ("ENG", "Engineering", "JKK Munirajah College of Technology"),
        ("AGRI", "Agriculture", "JKK Munirajah College of Agricultural Sciences"),
        ("PHARM", "Pharmacy", "JKKM Institute of Health Sciences – College of Pharmacy"),
    ]
    cur.executemany(
        "INSERT INTO institutes (id, short_name, full_name) VALUES (?, ?, ?)",
        institutes
    )

    # -------------------------------------------------
    # Admin users
    # -------------------------------------------------
    admins = [
        ("eng_admin", "Admin@123", "ENG"),
        ("agri_admin", "Admin@123", "AGRI"),
        ("pharm_admin", "Admin@123", "PHARM"),
    ]
    for username, raw_pw, inst in admins:
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, institute_id)
            VALUES (?, ?, 'ADMIN', ?)
            """,
            (username, generate_password_hash(raw_pw), inst)
        )

    # -------------------------------------------------
    # Students (course REQUIRED if schema demands it)
    # -------------------------------------------------
    demo_students = [
        # admission_no, name, dob, year, class, course, institute_id
        ("ENG24250006", "V.Sanjay",   "2007-04-08", 2, "CSE",      "B.E-CSE",   "ENG"),
        ("ENG24250200", "K.Dhanush",  "2006-12-16", 2, "IT",       "B.Tech-IT", "ENG"),
        ("ENG24250284", "M.Rajesh",   "2007-02-26", 2, "IT",       "B.Tech-IT", "ENG"),
        ("AGRI24250001","A.Karthick", "2006-03-14", 2, "AGRI-SCI", "B.Sc-Agri", "AGRI"),
        ("PHARM24250001","S.Ashwin",  "2006-04-18", 2, "BPHARM",   "B.Pharm",   "PHARM"),
    ]

    # Detect if students table has column "course"
    student_cols = {r["name"] for r in cur.execute("PRAGMA table_info(students)").fetchall()}
    has_course = "course" in student_cols

    for admission_no, name, dob, year, cls, course, inst in demo_students:
        pw_hash = generate_password_hash(dob_to_password(dob))

        # Create user
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role, institute_id)
            VALUES (?, ?, 'STUDENT', ?)
            """,
            (admission_no, pw_hash, inst)
        )
        user_id = cur.lastrowid

        # Create student
        if has_course:
            cur.execute(
                """
                INSERT INTO students
                (user_id, admission_no, name, dob, year, class, course, institute_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, admission_no, name, dob, year, cls, course, inst)
            )
        else:
            cur.execute(
                """
                INSERT INTO students
                (user_id, admission_no, name, dob, year, class, institute_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, admission_no, name, dob, year, cls, inst)
            )

    # -------------------------------------------------
    # Fee seeding (auto-detect fee_structure vs fee_plans)
    # -------------------------------------------------
    tables = list_tables(cur)  # refresh

    if "fee_structure" in tables:
        fee_rows = []
        for inst in ["ENG", "AGRI", "PHARM"]:
            for year in (1, 2, 3, 4):
                # Constant fees for demo/testing
                fee_rows.append((inst, year, 30000, 1000, 1000))

        cur.executemany(
            """
            INSERT INTO fee_structure (institute_id, year, tuition, exam, other)
            VALUES (?, ?, ?, ?, ?)
            """,
            fee_rows
        )
        print("Seeded fee_structure")

    elif "fee_plans" in tables:
        COURSES = ["B.Tech-IT", "B.E-CSE", "B.Tech-AI&DS", "B.Pharm", "B.Sc-Agri"]
        fee_rows = []
        for inst in ["ENG", "AGRI", "PHARM"]:
            for course in COURSES:
                for year in (1, 2, 3, 4):
                    # Constant fees: 30k tuition, 1k exam, 1k other.
                    # Hostel defaults to 50k in schema, total = 82,000.
                    fee_rows.append((inst, course, year, 30000, 1000, 1000))

        cur.executemany(
            """
            INSERT INTO fee_plans (institute_id, course, year, tuition, exam, other)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            fee_rows
        )
        print("Seeded fee_plans")

    else:
        print("⚠️ No fee table found (fee_structure or fee_plans). Fee seed skipped.")

    con.commit()
    con.close()

    print("Database initialized successfully")
    print("Admin login: eng_admin / Admin@123")
    print("Student password format: DOB (DDMMYYYY)")


if __name__ == "__main__":
    run()
