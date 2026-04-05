import sys
import os
sys.path.append(os.getcwd())

from flask import Flask
from config import Config
from blueprints.admin import admin_bp

def verify():
    app = Flask(__name__)
    app.config.from_object(Config)
    try:
        app.register_blueprint(admin_bp)
        print("✅ Admin blueprint registered successfully.")
        
        # Check routes
        routes = [str(p) for p in app.url_map.iter_rules()]
        expected = [
            "/admin/dashboard", 
            "/admin/login", 
            "/admin/students/add",
            "/admin/students/<student_id>/edit",
            "/admin/audit-logs",
            "/admin/reports/daily"
        ]
        
        missing = []
        for e in expected:
            found = any(e in r for r in routes) # simple check
            if not found:
                missing.append(e)
        
        if missing:
            print(f"❌ Missing routes: {missing}")
            print("Available routes:", routes)
        else:
            print("✅ Key admin routes found.")
            
    except Exception as e:
        print(f"❌ Failed to register blueprint: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify()
