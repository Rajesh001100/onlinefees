from app import app
from extensions import db
from models import Scholarship, Institute

def seed_scholarships():
    with app.app_context():
        # Ensure table is created (if not using migrations)
        db.create_all()
        
        # Get all institutes
        institutes = Institute.query.all()
        if not institutes:
            print("No institutes found. Please create an institute first.")
            return

        defaults = [
            ("SC", 10000),
            ("ST", 12000),
            ("BC", 5000),
            ("MBC", 7500),
            ("OTHER", 0),
            ("NONE", 0)
        ]

        for inst in institutes:
            for s_type, amt in defaults:
                exists = Scholarship.query.filter_by(institute_id=inst.id, scholarship_type=s_type).first()
                if not exists:
                    db.session.add(Scholarship(institute_id=inst.id, scholarship_type=s_type, amount=amt))
                    print(f"Added {s_type} (₹{amt}) for {inst.id}")
                else:
                    print(f"Scholarship {s_type} already exists for {inst.id}")
        
        db.session.commit()
        print("Scholarship seeding completed.")

if __name__ == "__main__":
    seed_scholarships()
