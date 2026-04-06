from app import app
from models import Student, Institute

with app.app_context():
    s_count = Student.query.count()
    i_count = Institute.query.count()
    eng_s = Student.query.filter_by(institute_id='ENG').count()
    
    with open("db_counts.txt", "w") as f:
        f.write(f"Total Students: {s_count}\n")
        f.write(f"Total Institutes: {i_count}\n")
        f.write(f"ENG Students: {eng_s}\n")
        
    print(f"Stats written to db_counts.txt. Total Students: {s_count}")
