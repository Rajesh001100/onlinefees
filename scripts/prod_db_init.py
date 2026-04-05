import os
import sys
from werkzeug.security import generate_password_hash

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from extensions import db
from models import Institute, User, FeePlan, FeeInstallment

def init_db():
    app = create_app()
    with app.app_context():
        print("Creating all tables...")
        db.create_all()

        # -------------------------------------------------
        # 1. Seed Institutes
        # -------------------------------------------------
        if not Institute.query.first():
            print("Seeding institutes...")
            insts = [
                Institute(id="ENG", short_name="Engineering", full_name="JKK Munirajah College of Technology"),
                Institute(id="AGRI", short_name="Agriculture", full_name="JKK Munirajah College of Agricultural Sciences"),
                Institute(id="PHARM", short_name="Pharmacy", full_name="JKKM Institute of Health Sciences – College of Pharmacy"),
            ]
            db.session.add_all(insts)
            db.session.commit()

        # -------------------------------------------------
        # 2. Seed Admin Users
        # -------------------------------------------------
        if not User.query.filter_by(role='ADMIN').first():
            print("Seeding admin users...")
            admins = [
                ("eng_admin", "Admin@123", "ENG"),
                ("agri_admin", "Admin@123", "AGRI"),
                ("pharm_admin", "Admin@123", "PHARM"),
            ]
            for username, password, inst_id in admins:
                user = User(
                    username=username,
                    password_hash=generate_password_hash(password),
                    role='ADMIN',
                    institute_id=inst_id
                )
                db.session.add(user)
            db.session.commit()

        # -------------------------------------------------
        # 3. Seed Basic Fee Plans (Templates)
        # -------------------------------------------------
        if not FeePlan.query.first():
            print("Seeding basic fee plans...")
            courses = ["B.Tech-IT", "B.E-CSE", "B.Tech-AI&DS", "B.Pharm", "B.Sc-Agri"]
            inst_ids = ["ENG", "AGRI", "PHARM"]
            
            plans = []
            for inst in inst_ids:
                for course in courses:
                    for year in range(1, 5):
                        plans.append(FeePlan(
                            institute_id=inst,
                            course=course,
                            year=year,
                            tuition=30000,
                            exam=1000,
                            other=1000,
                            hostel=50000
                        ))
            db.session.add_all(plans)
            db.session.commit()

        print("✅ Database initialization complete!")

if __name__ == "__main__":
    init_db()
