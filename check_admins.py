from app import app
from models import User
from extensions import db

with app.app_context():
    admins = User.query.filter(User.role.in_(['ADMIN', 'FOUNDER'])).all()
    print("Found Admins/Founders:")
    for a in admins:
        print(f"- {a.username} (Role: {a.role}, Active: {a.is_active}, Institute: {a.institute_id})")
