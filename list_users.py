from app import app
from models import User
with app.app_context():
    for u in User.query.all():
        print(f"Username: {u.username}, Role: {u.role}")
