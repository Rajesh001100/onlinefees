import os
from flask import Flask, redirect, url_for, send_from_directory
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ✅ Load .env FIRST (before anything else)
load_dotenv()

from config import Config
from blueprints.student.routes import student_bp
from blueprints.admin import admin_bp
from utils.db import close_db

from extensions import csrf, limiter, cache, db, migrate



def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ✅ If you want to confirm which DB Flask uses:
    print("✅ USING DATABASE_PATH =", app.config.get("DATABASE_PATH"))

    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    
    import models

    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    # ✅ close db connection after each request
    app.teardown_appcontext(close_db)

    @app.get("/")
    def home():
        return redirect(url_for("student.select_institute"))


    @app.route('/service-worker.js')
    def service_worker():
        return send_from_directory('static', 'service-worker.js')

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
