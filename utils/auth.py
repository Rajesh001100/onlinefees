# utils/auth.py
from __future__ import annotations

from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, flash, request

ROLE_ADMIN = "ADMIN"
ROLE_STUDENT = "STUDENT"
ROLE_FOUNDER = "FOUNDER"

ROLE_SET_ADMIN = {ROLE_ADMIN, ROLE_FOUNDER}


def hash_password(raw: str) -> str:
    return generate_password_hash(raw)


def verify_password(stored_hash: str, raw: str) -> bool:
    return check_password_hash(stored_hash, raw)


def dob_to_password(dob_yyyy_mm_dd: str) -> str:
    # Stored DOB: YYYY-MM-DD  -> Password: DDMMYYYY
    y, m, d = dob_yyyy_mm_dd.split("-")
    return f"{d}{m}{y}"


def is_admin() -> bool:
    return (session.get("role") or "") == ROLE_ADMIN


def is_founder() -> bool:
    return (session.get("role") or "") == ROLE_FOUNDER


def is_student() -> bool:
    return (session.get("role") or "") == ROLE_STUDENT


def require_login_roles(*roles: str):
    roles_set = set(roles)

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if not role or role not in roles_set:
                flash("Please login to continue.", "warning")
                # keep next for later redirect if you want
                return redirect(url_for("admin.login"))
            return fn(*args, **kwargs)
        return wrapper
    return deco


def admin_required(fn):
    # ADMIN + FOUNDER both are allowed to access admin panel
    return require_login_roles(ROLE_ADMIN, ROLE_FOUNDER)(fn)


def founder_required(fn):
    return require_login_roles(ROLE_FOUNDER)(fn)


def student_required(fn):
    # keep your current student protection
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_student():
            flash("Please login as student.", "warning")
            return redirect(url_for("student.login"))
        return fn(*args, **kwargs)
    return wrapper


def scoped_institute_id() -> str | None:
    """
    Returns institute scope for READ queries.
    - ADMIN: forced to their institute
    - FOUNDER: can view ALL (None) or filter by ?inst=ENG
    """
    if is_admin():
        return session.get("institute_id")

    if is_founder():
        inst = (request.args.get("inst") or "").strip()
        return inst or None

    return None


def require_write_institute() -> str:
    """
    For WRITE actions when role is FOUNDER:
    force explicit selection of institute (session['active_institute_id'])
    so founder doesn't accidentally modify wrong institute.
    """
    if is_admin():
        inst = session.get("institute_id")
        if not inst:
            raise RuntimeError("Missing institute_id for ADMIN session")
        return inst

    if is_founder():
        inst = (session.get("active_institute_id") or "").strip()
        if not inst:
            raise PermissionError("Founder must choose an active institute before write actions.")
        return inst

    raise PermissionError("Unauthorized")
