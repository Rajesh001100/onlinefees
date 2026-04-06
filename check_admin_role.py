from app import app
from models import User
with app.app_context():
    u = User.query.filter_by(username='admin').first()
    if u:
        print(f"Username: {u.username}, Role: {u.role}, Inst: {u.institute_id}")
    else:
        print("User 'admin' not found.")
