from app import app
from models import Student, Institute
with app.app_context():
    print("--- Institutes ---")
    for i in Institute.query.all():
        print(f"ID: {i.id!r}, Name: {i.short_name}")
    
    print("\n--- Students Count ---")
    print(f"Total Students: {Student.query.count()}")
    
    # Try specific filters
    eng_count = Student.query.filter_by(institute_id='ENG').count()
    agri_count = Student.query.filter_by(institute_id='AGRI').count()
    pharm_count = Student.query.filter_by(institute_id='PHARM').count()
    
    print(f"ENG Count: {eng_count}")
    print(f"AGRI Count: {agri_count}")
    print(f"PHARM Count: {pharm_count}")
    
    if Student.query.count() > 0:
        sample = Student.query.first()
        print(f"\nSample Student: {sample.name}, InstID: {sample.institute_id!r}, Type: {type(sample.institute_id)}")
