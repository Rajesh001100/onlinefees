from app import app
from models import User
from extensions import db
from werkzeug.security import generate_password_hash

def fix():
    with app.app_context():
        # 1. Target user 'admin'
        u = User.query.filter_by(username='admin').first()
        
        pw_hash = generate_password_hash('admin123')
        
        if not u:
            print("Creating new 'admin' user...")
            u = User(
                username='admin',
                password_hash=pw_hash,
                role='FOUNDER', # Founder can see all institutes
                is_active=1
            )
            db.session.add(u)
        else:
            print("Updating existing 'admin' user...")
            u.password_hash = pw_hash
            u.role = 'FOUNDER'
            u.is_active = 1
            
        db.session.commit()
        print("✅ SUCCESS: Admin login updated to admin / admin123")
        
        # Also ensure 'eng_admin' and others are active for backup
        admins = User.query.filter(User.role.in_(['ADMIN', 'FOUNDER'])).all()
        for a in admins:
            if a.is_active != 1:
                a.is_active = 1
        db.session.commit()
        print(f"✅ Verified {len(admins)} admin users are active.")

if __name__ == "__main__":
    fix()
