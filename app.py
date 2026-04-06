import os
from flask import Flask, redirect, url_for, send_from_directory, render_template
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import logging

# ✅ Load .env FIRST (before anything else)
load_dotenv()

# Configure logging for production troubleshooting
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config import Config
from blueprints.student.routes import student_bp
from blueprints.admin import admin_bp
from utils.db import close_db

from extensions import csrf, limiter, cache, db, migrate



def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # If you want to confirm which DB Flask uses:
    print("USING DATABASE_PATH =", app.config.get("DATABASE_PATH"))

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

    @app.get("/founder")
    def founder_alias():
        """Shortcut for founder access"""
        return redirect(url_for("admin.founder_portal"))

    @app.get("/admin")
    def admin_alias():
        """Shortcut for admin access"""
        return redirect(url_for("admin.index"))


    @app.get("/verify/<receipt_no>")
    def verify_public(receipt_no):
        from models import Receipt, Payment, Student, Institute
        r = Receipt.query.filter_by(receipt_no=receipt_no).first()
        if not r:
            return render_template("verify_public.html", receipt_no=receipt_no, payment=None, student=None, inst=None), 404
        
        pay = Payment.query.get(r.payment_id)
        stu = Student.query.get(pay.student_id) if pay else None
        inst = Institute.query.get(stu.institute_id) if stu else None

        return render_template("verify_public.html", receipt_no=receipt_no, payment=pay, student=stu, inst=inst)

    # ✅ Handle Render/Proxy headers for accurate Rate Limiting
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app


app = create_app()

if __name__ == "__main__":
    # Local development runner
    app.run(debug=True, port=5001)
