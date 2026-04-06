from flask import render_template, request, session, redirect, url_for, flash
from utils.db import get_db
from utils.auth import verify_password
from extensions import limiter
from .. import admin_bp


@admin_bp.route("/")
@admin_bp.route("/index")
def index():
    """Shortcut for /admin entry point"""
    role = session.get("role")
    if role in ["ADMIN", "FOUNDER"]:
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.login"))


@admin_bp.route("/founder-portal")
def founder_portal():
    """Shortcut for /founder entry point"""
    if session.get("role") == "FOUNDER":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.login", role="founder"))


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        # Server-side validation
        errors = []
        if not username:
            errors.append("Username is required.")
        if not password:
            errors.append("Password is required.")
        if len(username) > 50:
            errors.append("Username is too long.")
        if len(password) > 128:
            errors.append("Password is too long.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/login.html")

        from models import User
        user = User.query.filter(
            User.username == username,
            User.role.in_(['ADMIN', 'FOUNDER'])
        ).first()

        if (
            not user
            or user.is_active != 1
            or not verify_password(user.password_hash, password)
        ):
            flash("Invalid username/password.", "danger")
            return render_template("admin/login.html")

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role

        # ADMIN is tied to one institute
        if user.role == "ADMIN":
            session["institute_id"] = user.institute_id
            session.pop("active_institute_id", None)
        else:
            # Founder can READ ALL by default
            session.pop("institute_id", None)
            session["active_institute_id"] = None

        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


@admin_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
