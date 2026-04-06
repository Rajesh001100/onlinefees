import json
from app import app
from models import User
with app.app_context():
    users = []
    for u in User.query.filter(User.role.in_(['ADMIN', 'FOUNDER'])).all():
        users.append({
            "username": u.username,
            "role": u.role,
            "active": u.is_active,
            "institute": u.institute_id
        })
    with open("results.json", "w") as f:
        json.dump(users, f, indent=4)
