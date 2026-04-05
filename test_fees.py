import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from extensions import db
from utils.fees import get_full_course_fee_state
from models import Student

app = create_app()
with app.app_context():
    # Try to find a student
    student = Student.query.first()
    if student:
        print(f"Testing for student ID: {student.id}")
        try:
            state = get_full_course_fee_state(db, student_id=student.id)
            print("Success!")
        except NameError as e:
            print(f"NameError: {e}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("No students found in DB.")
