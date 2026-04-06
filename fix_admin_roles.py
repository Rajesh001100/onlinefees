from app import app
from models import User
from extensions import db
with app.app_context():
    # Fix Admin
    u = User.query.filter_by(username='admin').first()
    if u:
        u.role = 'ADMIN'
        u.institute_id = 'ENG'
        db.session.commit()
        print(f"✅ Reset admin to ADMIN role (ENG).")
    else:
        print("❌ User 'admin' not found.")
        
    # Ensure Founder
    f = User.query.filter_by(username='founder').first()
    if f:
        f.role = 'FOUNDER'
        f.institute_id = None
        db.session.commit()
        print(f"✅ Verified founder is still FOUNDER role.")
    else:
        print("❌ User 'founder' not found.")
