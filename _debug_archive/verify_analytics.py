import sys
import os
sys.path.append(os.getcwd())

from flask import Flask, session
from config import Config
from blueprints.admin import admin_bp
from utils.db import get_db

def verify():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = 'dev'
    app.register_blueprint(admin_bp)

    with app.test_request_context("/admin/api/analytics"):
        # Mock session
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["institute_id"] = "1"
                sess["role"] = "ADMIN"
            
            # We can't easily mock the session for a direct view call without a request context that has session support fully wired or using client.get
            # Let's use client.get
            
            resp = client.get("/admin/api/analytics")
            if resp.status_code == 200:
                print("✅ API /admin/api/analytics returned 200")
                print("Response JSON keys:", resp.json.keys())
                if "daily_collection" in resp.json and "modes" in resp.json:
                     print("✅ JSON structure looks correct.")
                else:
                     print("❌ JSON structure missing keys.")
                     print(resp.json)
            else:
                print(f"❌ API failed with {resp.status_code}")
                # print(resp.text)

if __name__ == "__main__":
    try:
        verify()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
