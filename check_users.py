from app import app
from models import User
with app.app_context():
    users = User.query.all()
    for u in users:
        print(f"User: {u.username}, Role: {u.role}, Inst: {u.institute_id}")
