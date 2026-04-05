import sqlite3

DB_PATH = "instance/fees.db"

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("UPDATE students SET photo_filename = admission_no || '.jpg'")

con.commit()
con.close()
print("✅ photo_filename updated for all students")
