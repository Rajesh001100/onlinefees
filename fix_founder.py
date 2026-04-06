from app import app
from models import User
from extensions import db
from werkzeug.security import generate_password_hash

def fix_founder():
    with app.app_context():
        # Target user 'founder'
        u = User.query.filter_by(username='founder').first()
        
        pw_hash = generate_password_hash('founder123')
        
        if not u:
            print("Creating new 'founder' super admin...")
            u = User(
                username='founder',
                password_hash=pw_hash,
                role='FOUNDER', # Super Admin capacity
                is_active=1
            )
            db.session.add(u)
        else:
            print("Updating existing 'founder' super admin...")
            u.password_hash = pw_hash
            u.role = 'FOUNDER'
            u.is_active = 1
            u.institute_id = None # Founder monitors ALL
            
        db.session.commit()
        print("✅ SUCCESS: Founder login set to founder / founder123")
        
        # Verify all 3 institutes are present to check monitoring
        from models import Institute
        insts = Institute.query.all()
        print(f"Institutes available for monitoring: {[i.id for i in insts]}")

if __name__ == "__main__":
    fix_founder()
