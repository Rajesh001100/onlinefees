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
        
        # Check routes
        routes = [str(p) for p in app.url_map.iter_rules()]
        expected = [
            "/admin/students/upload"
        ]
        
        missing = []
        for e in expected:
            found = any(e in r for r in routes)
            if not found:
                missing.append(e)
        
        if missing:
            print(f"❌ Missing routes: {missing}")
        else:
            print("✅ All check routes found (including upload).")
            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    verify()
