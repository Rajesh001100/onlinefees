import sys
from app import app
from models import Student, Institute

with app.app_context():
    print("--- Institutes ---")
    insts = Institute.query.all()
    for i in insts:
        print(f"ID: '{i.id}', Short: '{i.short_name}', Full: '{i.full_name}'")

    print("\n--- Students (First 10) ---")
    students = Student.query.limit(10).all()
    for s in students:
        print(f"Name: '{s.name}', InstID: '{s.institute_id}'")
        
    print("\n--- Summary Count ---")
    for i in insts:
        count = Student.query.filter_by(institute_id=i.id).count()
        print(f"Institute {i.id}: {count} students")
