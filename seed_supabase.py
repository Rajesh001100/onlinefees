from app import app
from models import Institute, Student, User, FeePlan
from extensions import db
from werkzeug.security import generate_password_hash
from datetime import datetime

# Standard Dob to Password: DDMMYYYY
def dob_to_pw(dob):
    y, m, d = dob.split("-")
    return f"{d}{m}{y}"

def seed():
    with app.app_context():
        print("▶ Seeding Institutes...")
        institutes = [
            ("ENG", "Engineering", "JKK Munirajah College of Technology"),
            ("AGRI", "Agriculture", "JKK Munirajah College of Agricultural Sciences"),
            ("PHARM", "Pharmacy", "JKKM Institute of Health Sciences - College of Pharmacy"),
        ]
        for i_id, s_name, f_name in institutes:
            inst = Institute.query.get(i_id)
            if not inst:
                inst = Institute(id=i_id, short_name=s_name, full_name=f_name)
                db.session.add(inst)
        db.session.commit()

        print("▶ Seeding Fee Plans (Required for monitoring)...")
        courses = [
            ("ENG", "B.E-CSE"), ("ENG", "B.Tech-IT"),
            ("AGRI", "B.Sc-Agri"),
            ("PHARM", "B.Pharm")
        ]
        for inst_id, course in courses:
            for year in [1, 2, 3, 4]:
                plan = FeePlan.query.filter_by(institute_id=inst_id, course=course, year=year).first()
                if not plan:
                    plan = FeePlan(
                        institute_id=inst_id, course=course, year=year,
                        tuition=30000, hostel=50000, exam=1000, other=1000
                    )
                    db.session.add(plan)
        db.session.commit()

        print("▶ Seeding Students...")
        demo_students = [
            # admission_no, name, dob, year, class, course, institute_id
            ("ENG24250001", "A.Sanjay", "2007-04-08", 1, "CSE", "B.E-CSE", "ENG"),
            ("ENG24250201", "B.Dhanush", "2006-12-16", 2, "IT", "B.Tech-IT", "ENG"),
            ("AGRI24250001", "K.Karthick", "2006-03-14", 1, "AGRI-SCI", "B.Sc-Agri", "AGRI"),
            ("PHARM24250001", "S.Ashwin", "2006-04-18", 3, "BPHARM", "B.Pharm", "PHARM"),
        ]

        for adm, name, dob, year, cls, course, inst_id in demo_students:
            # Check if student exists
            s = Student.query.filter_by(admission_no=adm).first()
            if not s:
                # 1. Create User
                pw_hash = generate_password_hash(dob_to_pw(dob))
                u = User(username=adm, password_hash=pw_hash, role='STUDENT', institute_id=inst_id)
                db.session.add(u)
                db.session.flush() # get u.id
                
                # 2. Create Student
                s = Student(
                    user_id=u.id, admission_no=adm, name=name, dob=dob, 
                    year=year, class_name=cls, course=course, institute_id=inst_id
                )
                db.session.add(s)
        
        db.session.commit()
        print(f"✅ SUCCESS: Seeding complete. Added {len(demo_students)} students across all institutes.")

if __name__ == "__main__":
    seed()
