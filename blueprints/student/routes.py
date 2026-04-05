# blueprints/student/routes.py
from __future__ import annotations

import secrets
import os
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO

from extensions import csrf, limiter
from flask import Blueprint, render_template, session, redirect, url_for, request, flash, send_file, current_app, jsonify
import razorpay

from utils.db import get_db
from utils.decorators import student_required
from utils.fees import get_fee_state_for_student, get_full_course_fee_state, clear_fee_cache_for_student

# Try to import email helpers safely
try:
    from utils.mailer import send_receipt_email  # attachment support
except Exception:
    send_receipt_email = None

try:
    from utils.mailer import send_email  # basic email
except Exception:
    send_email = None


# ✅ MUST be named student_bp (your app.py imports this)
student_bp = Blueprint("student", __name__, url_prefix="/student")

# IMPORTANT: codes must match institutes.id in DB
INSTITUTES_UI = [
    {"code": "ENG", "short": "Engineering", "full": "JKK Munirajah College of Technology", "icon": "icons/eng.png"},
    {"code": "AGRI", "short": "Agriculture", "full": "JKK Munirajah College of Agricultural Sciences", "icon": "icons/agri.png"},
    {"code": "PHARM", "short": "Pharmacy", "full": "JKKM Institute of Health Sciences – College of Pharmacy", "icon": "icons/pharm.png"},
]

ALLOWED_METHODS = {"UPI", "CARD", "NETBANKING"}


# -----------------------------
# Helpers
# -----------------------------
def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _dob_to_ddmmyyyy(dob_value) -> str:
    """
    DB dob usually: 'YYYY-MM-DD'
    Password expected: DDMMYYYY
    """
    if not dob_value:
        return ""
    s = str(dob_value).strip()

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.strftime("%d%m%Y")
        except Exception:
            pass

    digits = _only_digits(s)

    # maybe YYYYMMDD
    if len(digits) == 8 and digits.startswith(("19", "20")):
        try:
            dt = datetime.strptime(digits, "%Y%m%d")
            return dt.strftime("%d%m%Y")
        except Exception:
            pass

    return digits


def _current_institute():
    return session.get("selected_institute")


def _student_row_by_session(db):
    """
    We store student id in session["student_id"] and also session["user_id"]
    to satisfy your decorator.
    """
    sid = session.get("student_id")
    inst = session.get("institute_id")
    if not sid or not inst:
        return None

    return db.execute(
        """
        SELECT id, user_id, admission_no, register_no, name, dob, year, class, course,
               student_email, parent_email, student_phone, parent_phone,
               institute_id, photo_filename, is_hosteller, scholarship_type, quota_type, is_first_graduate
        FROM students
        WHERE id=? AND institute_id=?
        """,
        (sid, inst),
    ).fetchone()


# -----------------------------
# Institute Selection
# -----------------------------
@student_bp.get("/select-institute")
def select_institute():
    return render_template("student/select_institute.html", institutes=INSTITUTES_UI)


@student_bp.get("/set-institute/<code>")
def set_institute(code):
    valid = {i["code"] for i in INSTITUTES_UI}
    if code not in valid:
        return redirect(url_for("student.select_institute"))

    session.clear()
    session["selected_institute"] = code
    return redirect(url_for("student.login"))


# -----------------------------
# Student Login / Logout
# -----------------------------
@student_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    selected = _current_institute()
    if not selected:
        return redirect(url_for("student.select_institute"))

    institute_meta = next((i for i in INSTITUTES_UI if i["code"] == selected), None)

    if request.method == "POST":
        admission_no = (request.form.get("admission_no") or "").strip().upper()
        password = (request.form.get("password") or "").strip()

        if not admission_no or not password:
            flash("Please enter admission number and password.", "danger")
            return render_template("student/login.html", institute=institute_meta)

        db = get_db()

        # ✅ LOGIN from students table (works for IT/MECH/ECE)
        s = db.execute(
            """
            SELECT id, admission_no, dob, institute_id
            FROM students
            WHERE admission_no=? AND institute_id=?
            """,
            (admission_no, selected),
        ).fetchone()

        if not s:
            flash("Invalid admission number / password.", "danger")
            return render_template("student/login.html", institute=institute_meta)

        expected = _dob_to_ddmmyyyy(s["dob"])
        if password != expected:
            flash("Invalid admission number / password.", "danger")
            return render_template("student/login.html", institute=institute_meta)

        # ✅ IMPORTANT: set session correctly for decorator
        session.clear()
        session["role"] = "STUDENT"
        session["user_id"] = s["id"]       # decorator expects user_id
        session["student_id"] = s["id"]    # our internal student id
        session["institute_id"] = s["institute_id"]
        session["selected_institute"] = selected

        print("✅ LOGIN OK:", s["id"], s["institute_id"])
        print("✅ SESSION NOW:", dict(session))

        return redirect(url_for("student.dashboard"))

    return render_template("student/login.html", institute=institute_meta)


@student_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("student.select_institute"))


# -----------------------------
# Student Dashboard
# -----------------------------
@student_bp.get("/dashboard")
@student_required
def dashboard():
    db = get_db()
    s = _student_row_by_session(db)

    if not s:
        flash("Student profile not found. Login again.", "danger")
        return redirect(url_for("student.logout"))

    fee_state = get_fee_state_for_student(db, student_id=s["id"])
    
    inst = db.execute(
        "SELECT short_name, full_name FROM institutes WHERE id=?",
        (s["institute_id"],),
    ).fetchone()

    photo_url = (
        url_for("static", filename=f"uploads/students/{s['photo_filename']}")
        if s["photo_filename"]
        else url_for("static", filename="uploads/students/default_student.png")
    )

    return render_template(
        "student/dashboard.html", 
        student=s, 
        photo_url=photo_url,
        fee_state=fee_state,
        inst=inst
    )


# -----------------------------
# Student Fees Page
# -----------------------------
@student_bp.get("/fees")
@student_required
def fees():
    db = get_db()
    student = _student_row_by_session(db)

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student.dashboard"))

    inst = db.execute(
        "SELECT short_name, full_name FROM institutes WHERE id=?",
        (student["institute_id"],),
    ).fetchone()

    fee_state = get_fee_state_for_student(db, student_id=student["id"])
    full_state = get_full_course_fee_state(db, student_id=student["id"]) # ✅ NEW

    # ✅ HISTORY: Success Payments
    history = db.execute(
        """
        SELECT txn_id, category, amount, method, status, created_at
        FROM payments
        WHERE student_id=? AND status='SUCCESS'
        ORDER BY id DESC
        """,
        (student["id"],),
    ).fetchall()

    # even if fee_state ok is False, still render the page (show warning)
    if not fee_state:
        fee_state = {"ok": False, "error": "Fee state error. Check fee plan/course mapping."}

    photo_filename = student["photo_filename"]  # sqlite3.Row access by key
    photo_url = (
        url_for("static", filename=f"uploads/students/{photo_filename}")
        if photo_filename
        else url_for("static", filename="uploads/students/default_student.png")
    )

    return render_template(
        "student/fees.html",
        student=student,
        inst=inst,
        fee_state=fee_state,
        full_state=full_state, # ✅ Pass 4-year data
        photo_url=photo_url,
        history=history,
    )

# -----------------------------
# Pay Method (Category + amount)
# -----------------------------
@student_bp.route("/pay-method", methods=["GET", "POST"])
@student_required
def pay_method():
    db = get_db()
    student = _student_row_by_session(db)

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student.dashboard"))

    def _get_due_map():
        fee_state = get_fee_state_for_student(db, student_id=student["id"]) or {}
        
        # ✅ NEW: For Tuition/Other, check 4-year total capability
        full_state = get_full_course_fee_state(db, student_id=student["id"]) or {}
        
        # Prefer canonical key, fallback to old key
        current_due_map = fee_state.get("due", {}).copy() # Current year dues
        if not isinstance(current_due_map, dict):
            current_due_map = fee_state.get("category_due", {}).copy()
        
        if not isinstance(current_due_map, dict):
            return None, None, fee_state
            
        # Initialize max_due_map with current dues
        max_due_map = current_due_map.copy()

        # ✅ OVERRIDE Max Tuition with 4-Year Outstanding logic if available
        if full_state.get("ok"):
            grand_plan_due = full_state.get("grand_total_due", 0)
            current_tuition_due = current_due_map.get("TUITION", 0)
            
            # The dropdown will show 'current_tuition_due', but validation will allow 'grand_plan_due'
            max_due_map["TUITION"] = max(current_tuition_due, grand_plan_due)

        # normalize to int >= 0
        clean_current = {}
        clean_max = {}
        
        all_cats = set(current_due_map.keys()) | set(max_due_map.keys())
        for cat_raw in all_cats:
            cat = (cat_raw or "").strip().upper()
            clean_current[cat] = max(0, int(current_due_map.get(cat, 0)))
            clean_max[cat] = max(0, int(max_due_map.get(cat, 0)))
            
        return clean_current, clean_max, fee_state

    # Always load a fresh due map
    category_due, category_max, fee_state = _get_due_map()
    if category_due is None:
        flash("Fee calculation error (due map missing).", "danger")
        return redirect(url_for("student.dashboard"))

    # Only categories with max_due > 0 are payable
    categories = sorted([c for c, max_val in category_max.items() if max_val > 0])

    if not categories:
        flash("No due amount to pay.", "info")
        return redirect(url_for("student.fees"))

    # Pre-fill from query parameters (from Fees page links)
    cat_arg = request.args.get("cat", "").strip().upper()
    amt_arg = request.args.get("amt", "").strip()

    if cat_arg in categories:
        selected_category = cat_arg
        # ✅ If specific amount in URL, treat it as the "display due" for this session
        if amt_arg.isdigit():
            req_amt = int(amt_arg)
            if req_amt <= category_max.get(selected_category, 0):
                category_due[selected_category] = req_amt
    else:
        selected_category = categories[0]

    selected_due = int(category_due.get(selected_category, 0))
    entered_amount = amt_arg if amt_arg else selected_due

    if request.method == "POST":
        # Re-fetch again on POST so it never uses stale due values
        category_due, category_max, _ = _get_due_map()
        if category_due is None:
            flash("Fee calculation error (due map missing).", "danger")
            return redirect(url_for("student.dashboard"))

        categories = sorted([c for c, max_val in category_max.items() if max_val > 0])
        if not categories:
            flash("No due amount to pay.", "info")
            return redirect(url_for("student.fees"))

        selected_category = (request.form.get("category") or "").strip().upper()
        method = (request.form.get("method") or "").strip().upper()
        amount_raw = (request.form.get("amount") or "").strip()
        entered_amount = amount_raw

        if selected_category not in categories:
            flash("Choose a valid fee category.", "danger")
            selected_category = categories[0]
            selected_due = int(category_due.get(selected_category, 0))
            return render_template(
                "student/pay_method.html",
                categories=categories,
                category_due=category_due,
                category_max=category_max,
                selected_category=selected_category,
                selected_due=selected_due,
                entered_amount=entered_amount,
                fee_state=fee_state,
            )


        selected_due = int(category_due.get(selected_category, 0))

        if method not in ALLOWED_METHODS:
            flash("Choose a valid payment method.", "danger")
            return render_template(
                "student/pay_method.html",
                categories=categories,
                category_due=category_due,
                category_max=category_max,
                selected_category=selected_category,
                selected_due=selected_due,
                entered_amount=entered_amount,
                fee_state=fee_state,
            )


        try:
            amount = int(amount_raw)
        except (TypeError, ValueError):
            flash("Enter a valid amount.", "danger")
            return render_template(
                "student/pay_method.html",
                categories=categories,
                category_due=category_due,
                category_max=category_max,
                selected_category=selected_category,
                selected_due=selected_due,
                entered_amount=entered_amount,
                fee_state=fee_state,
            )


        if amount <= 0:
            flash("Amount must be greater than 0.", "danger")
            return render_template(
                "student/pay_method.html",
                categories=categories,
                category_due=category_due,
                category_max=category_max,
                selected_category=selected_category,
                selected_due=selected_due,
                entered_amount=entered_amount,
                fee_state=fee_state,
            )


        selected_max = int(category_max.get(selected_category, 0))
        if amount > selected_max:
            flash(f"Amount cannot be greater than total due for {selected_category} (₹{selected_max:,}).", "danger")
            return render_template(
                "student/pay_method.html",
                categories=categories,
                category_due=category_due,
                category_max=category_max,
                selected_category=selected_category,
                selected_due=selected_due,
                entered_amount=entered_amount,
                fee_state=fee_state,
            )


        session["pay_amount"] = amount
        session["pay_method"] = method
        session["pay_category"] = selected_category
        return redirect(url_for("student.generate_txn"))

    return render_template(
        "student/pay_method.html",
        categories=categories,
        category_due=category_due,
        category_max=category_max,
        selected_category=selected_category,
        selected_due=selected_due,
        entered_amount=entered_amount,
        fee_state=fee_state,
    )


@student_bp.get("/generate-txn")
@student_required
@limiter.limit("10 per minute")
def generate_txn():
    db = get_db()
    student = _student_row_by_session(db)

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student.dashboard"))

    # --- helper: get fresh due map (canonical first) ---
    fee_state = get_fee_state_for_student(db, student_id=student["id"]) or {}
    
    # ✅ Check 4-year override here too
    full_state = get_full_course_fee_state(db, student_id=student["id"]) or {}
    
    current_due_map = fee_state.get("due", {}).copy()
    if not isinstance(current_due_map, dict):
        current_due_map = fee_state.get("category_due", {}).copy()
    if not isinstance(current_due_map, dict):
        flash("Fee calculation error (due map missing).", "danger")
        return redirect(url_for("student.dashboard"))

    max_due_map = current_due_map.copy()
    if full_state.get("ok"):
        grand_plan_due = full_state.get("grand_total_due", 0)
        current_tuition_due = current_due_map.get("TUITION", 0)
        max_due_map["TUITION"] = max(current_tuition_due, grand_plan_due)

    # normalize due map
    category_max = {}
    for k, v in max_due_map.items():
        cat = (k or "").strip().upper()
        category_max[cat] = max(0, int(v or 0))

    # --- read session payment intent ---
    method = (session.get("pay_method") or "").strip().upper()
    category = (session.get("pay_category") or "").strip().upper()

    try:
        amount = int(session.get("pay_amount") or 0)
    except (TypeError, ValueError):
        amount = 0

    # --- validate intent ---
    if amount <= 0:
        flash("Invalid payment amount. Try again.", "danger")
        return redirect(url_for("student.pay_method"))

    if method not in ALLOWED_METHODS:
        flash("Invalid payment method. Try again.", "danger")
        return redirect(url_for("student.pay_method"))

    if category not in category_max:
        flash("Invalid fee category. Try again.", "danger")
        return redirect(url_for("student.pay_method"))

    max_for_category = int(category_max.get(category, 0))
    if max_for_category <= 0:
        flash("No due for this category.", "info")
        return redirect(url_for("student.fees"))

    if amount > max_for_category:
        flash(f"Amount cannot be greater than total due for {category} (₹{max_for_category:,}).", "danger")
        return redirect(url_for("student.pay_method"))

    # --- (Removed block for pending transactions as per user request) ---

    # --- create txn ---
    txn_id = "TXN-" + secrets.token_hex(6).upper()

    # --- razorpay order creation ---
    try:
        client = razorpay.Client(auth=(current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]))
        # ✅ Use actual amount entered by user (converted to paise: 1 INR = 100 paise)
        rzp_amount_paise = int(amount * 100) 
        order_data = {
            "amount": rzp_amount_paise, 
            "currency": "INR",
            "receipt": txn_id,
            "notes": {
                "student_id": student["id"],
                "category": category,
                "admission_no": student["admission_no"]
            }
        }
        razorpay_order = client.order.create(data=order_data)
        rzp_order_id = razorpay_order["id"]
    except Exception as e:
        print("❌ Razorpay order creation failed:", repr(e))
        flash("Gateway communication failed. Try again.", "danger")
        return redirect(url_for("student.pay_method"))

    try:
        db.execute(
            """
            INSERT INTO payments (student_id, txn_id, category, amount, method, status, razorpay_order_id)
            VALUES (?, ?, ?, ?, ?, 'INITIATED', ?)
            """,
            (student["id"], txn_id, category, amount, method, rzp_order_id),
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print("❌ generate_txn failed:", repr(e))
        flash("Transaction creation failed. Try again.", "danger")
        return redirect(url_for("student.pay_method"))

    # clear session intent only after success
    session.pop("pay_amount", None)
    session.pop("pay_method", None)
    session.pop("pay_category", None)

    flash(f"Transaction created for {category}.", "success")
    return redirect(url_for("student.pay_status", txn_id=txn_id))


# -----------------------------
# Payment Status
# -----------------------------
PENDING_EXPIRE_MINUTES = 10


def _parse_sqlite_dt(v):
    """
    SQLite CURRENT_TIMESTAMP returns UTC like: 'YYYY-MM-DD HH:MM:SS'
    Parse safely.
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


@student_bp.get("/pay/status/<txn_id>")
@student_required
def pay_status(txn_id):
    db = get_db()

    p = db.execute(
        """
        SELECT txn_id, student_id, category, amount, method, status, created_at, razorpay_order_id
        FROM payments
        WHERE txn_id=?
        """,
        (txn_id,),
    ).fetchone()

    if not p:
        flash("Transaction not found.", "danger")
        return redirect(url_for("student.dashboard"))

    student = _student_row_by_session(db)
    if not student or int(student["id"]) != int(p["student_id"]):
        flash("Unauthorized transaction access.", "danger")
        return redirect(url_for("student.dashboard"))

    expired_now = False

    # ✅ IMPORTANT: created_at is UTC (SQLite CURRENT_TIMESTAMP). Use utcnow().
    if (p["status"] or "").upper() == "INITIATED":
        # --- A. Proactive Check with Razorpay (Essential for Localhost/Webhooks missing) ---
        if p["razorpay_order_id"]:
            try:
                client = razorpay.Client(auth=(current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]))
                order_data = client.order.fetch(p["razorpay_order_id"])
                
                # If order is already 'paid', sync DB
                if order_data.get("status") == "paid":
                    # Also try to get the payment ID for records
                    payments = client.order.payments(p["razorpay_order_id"])
                    payment_id = None
                    if payments.get("items"):
                        # Get the most recent successful payment
                        for pay in payments["items"]:
                            if pay.get("status") == "captured":
                                payment_id = pay.get("id")
                                break
                    
                    db.execute(
                        "UPDATE payments SET status='SUCCESS', razorpay_payment_id=? WHERE txn_id=? AND status='INITIATED'",
                        (payment_id, txn_id)
                    )
                    db.commit()
                    clear_fee_cache_for_student(int(p["student_id"]))
                    # Re-read the updated row
                    p = db.execute(
                        "SELECT txn_id, student_id, category, amount, method, status, created_at, razorpay_order_id FROM payments WHERE txn_id=?",
                        (txn_id,)
                    ).fetchone()
            except Exception as e:
                print(f"⚠️ Proactive check failed for {txn_id}:", repr(e))

        # --- B. Expiry Check ---
        created = _parse_sqlite_dt(p["created_at"])
        if created is not None and (p["status"] or "").upper() == "INITIATED":
            expire_min = current_app.config.get("TRANSACTION_EXPIRY_MINUTES", 15)
            if datetime.utcnow() - created > timedelta(minutes=expire_min):
                db.execute(
                    "UPDATE payments SET status='FAILED' WHERE txn_id=? AND status='INITIATED'",
                    (txn_id,),
                )
                db.commit()
                expired_now = True

                # re-read updated row so UI shows FAILED
                p = db.execute(
                    """
                    SELECT txn_id, student_id, category, amount, method, status, created_at
                    FROM payments
                    WHERE txn_id=?
                    """,
                    (txn_id,),
                ).fetchone()

    if expired_now:
        flash("This pending transaction expired. Please try again.", "warning")

    return render_template(
        "student/pay_status.html", 
        p=p, 
        student=student,
        test_mode=current_app.config.get("PAYMENT_TEST_MODE", False),
        rzp_key_id=current_app.config["RAZORPAY_KEY_ID"],
        rzp_amount_paise=int((p["amount"] or 0) * 100)
    )


# -----------------------------
# Razorpay Verify (callback via AJAX)
# -----------------------------
@student_bp.post("/pay/verify")
@student_required
@limiter.limit("10 per minute")
def pay_verify():
    db = get_db()
    data = request.get_json() or {}

    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")
    txn_id = data.get("txn_id")

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, txn_id]):
        return jsonify({"ok": False, "msg": "Missing payment details."}), 400

    # 1. Fetch the transaction from DB
    p = db.execute(
        "SELECT id, status, amount FROM payments WHERE txn_id=? AND razorpay_order_id=?",
        (txn_id, razorpay_order_id),
    ).fetchone()

    if not p:
        return jsonify({"ok": False, "msg": "Transaction not found."}), 404

    if p["status"] == "SUCCESS":
        return jsonify({"ok": True, "msg": "Already processed."})

    # 2. Verify signature using Razorpay SDK
    try:
        client = razorpay.Client(auth=(current_app.config["RAZORPAY_KEY_ID"], current_app.config["RAZORPAY_KEY_SECRET"]))
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        client.utility.verify_payment_signature(params_dict)

        db.execute(
            """
            UPDATE payments 
            SET status='SUCCESS', razorpay_payment_id=?, razorpay_signature=? 
            WHERE txn_id=?
            """,
            (razorpay_payment_id, razorpay_signature, txn_id)
        )
        db.commit()
        
        # Clear student cache
        ps = db.execute("SELECT student_id FROM payments WHERE txn_id=?", (txn_id,)).fetchone()
        if ps:
            clear_fee_cache_for_student(int(ps["student_id"]))
            
        # We don't trigger email here automatically, we do it in pay_complete as before or add it here
        # For simplicity, we'll let the user redirect to pay_complete which now sees it as SUCCESS
        return jsonify({"ok": True, "msg": "Payment verified successfully."})

    except razorpay.errors.SignatureVerificationError:
        db.execute("UPDATE payments SET status='FAILED' WHERE txn_id=?", (txn_id,))
        db.commit()
        return jsonify({"ok": False, "msg": "Invalid signature verification."}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": "Verification failed due to internal error."}), 500


@student_bp.route("/pay/webhook", methods=["POST"])
@csrf.exempt  # Webhooks from Razorpay won't have CSRF
def pay_webhook():
    """
    Razorpay Webhook to handle payment.captured or order.paid events.
    Ensures payment is recorded even if browser is closed.
    """
    secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET")
    signature = request.headers.get("X-Razorpay-Signature")
    data = request.get_data()

    client = razorpay.Client(auth=(current_app.config["RAZORPAY_KEY_ID"], secret))
    
    try:
        # Verify webhook signature
        client.utility.verify_webhook_signature(data.decode('utf-8'), signature, secret)
        
        event_data = request.json
        event_type = event_data.get("event")
        
        if event_type in ["payment.captured", "order.paid"]:
            payload = event_data.get("payload", {})
            payment_obj = payload.get("payment", {}).get("entity", {})
            order_id = payment_obj.get("order_id")
            payment_id = payment_obj.get("id")
            
            if order_id:
                db = get_db()
                # Update only if not already SUCCESS
                db.execute(
                    "UPDATE payments SET status='SUCCESS', razorpay_payment_id=? WHERE razorpay_order_id=? AND status!='SUCCESS'",
                    (payment_id, order_id)
                )
                db.commit()
                ps = db.execute("SELECT student_id FROM payments WHERE razorpay_order_id=?", (order_id,)).fetchone()
                if ps:
                    clear_fee_cache_for_student(int(ps["student_id"]))
                print(f"✅ Webhook processed: {order_id} -> SUCCESS")
                
        return jsonify({"ok": True}), 200
        
    except razorpay.errors.SignatureVerificationError as e:
        print("❌ Webhook Invalid Signature:", repr(e))
        return jsonify({"ok": False, "msg": "Invalid signature"}), 400
    except Exception as e:
        print("❌ Webhook error:", repr(e))
        return jsonify({"ok": False, "msg": str(e)}), 400


@student_bp.route("/pay/test-verify", methods=["POST"])
@student_required
def pay_test_verify():
    """
    Simulate a successful payment for testing.
    Only works if PAYMENT_TEST_MODE is enabled in config.
    """
    if not current_app.config.get("PAYMENT_TEST_MODE"):
        return jsonify({"ok": False, "msg": "Test mode not enabled."}), 403

    data = request.get_json() or {}
    txn_id = data.get("txn_id")
    if not txn_id:
        return jsonify({"ok": False, "msg": "Missing txn_id."}), 400

    db = get_db()
    # Ensure txn belongs to student and is INITIATED
    p = db.execute("SELECT id FROM payments WHERE txn_id=? AND status='INITIATED'", (txn_id,)).fetchone()
    if not p:
        return jsonify({"ok": False, "msg": "Transaction not found or already processed."}), 404

    db.execute(
        "UPDATE payments SET status='SUCCESS', method='MOCK_SUCCESS' WHERE txn_id=?",
        (txn_id,)
    )
    db.commit()
    return jsonify({"ok": True})

# -----------------------------
# Receipt helpers
# -----------------------------
def _receipt_no(txn_id: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    tail = txn_id.replace("TXN-", "")[-6:]
    return f"RCPT-{today}-{tail}"


from .receipt_utils import build_receipt_pdf_bytes as _build_receipt_pdf_bytes

# -----------------------------
# Complete Payment (simulate) + email
# -----------------------------

@student_bp.route("/pay/complete/<txn_id>/<result>", methods=["GET", "POST"])
@student_required
def pay_complete(txn_id, result):
    result = (result or "").strip().upper()
    if result not in ("SUCCESS", "FAILED"):
        flash("Invalid payment result.", "danger")
        return redirect(url_for("student.fees"))

    db = get_db()
    student = _student_row_by_session(db)
    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for("student.dashboard"))

    # Fetch payment
    p = db.execute(
        """
        SELECT id, txn_id, student_id, category, amount, method, status, created_at
        FROM payments
        WHERE txn_id=?
        """,
        (txn_id,),
    ).fetchone()

    if not p:
        flash("Transaction not found.", "danger")
        return redirect(url_for("student.fees"))

    # Security: ensure ownership
    if int(p["student_id"]) != int(student["id"]):
        flash("Unauthorized payment access.", "danger")
        return redirect(url_for("student.dashboard"))

    # Only allow simulation completion for INITIATED
    if (p["status"] or "").upper() != "INITIATED":
        flash("This transaction is already processed.", "info")
        return redirect(url_for("student.pay_status", txn_id=txn_id))

    # ---- Atomic update: update only if still INITIATED ----
    try:
        cur = db.execute(
            """
            UPDATE payments
            SET status=?
            WHERE txn_id=? AND status='INITIATED'
            """,
            (result, txn_id),
        )
        if cur.rowcount != 1:
            db.rollback()
            flash("This transaction was already processed in another tab.", "info")
            return redirect(url_for("student.pay_status", txn_id=txn_id))

        db.commit()
    except Exception as e:
        db.rollback()
        print("❌ pay_complete update failed:", repr(e))
        flash("Payment update failed. Check server logs.", "danger")
        return redirect(url_for("student.pay_status", txn_id=txn_id))

    if result != "SUCCESS":
        flash("Payment failed ❌", "danger")
        return redirect(url_for("student.pay_status", txn_id=txn_id))

    # ---- SUCCESS: create receipt row (idempotent) ----
    receipt_no = _receipt_no(txn_id)

    try:
        # If receipt exists for this payment, reuse it
        existing = db.execute(
            "SELECT receipt_no FROM receipts WHERE payment_id=?",
            (p["id"],),
        ).fetchone()

        if existing and existing["receipt_no"]:
            receipt_no = existing["receipt_no"]
        else:
            # Create receipt
            db.execute(
                """
                INSERT INTO receipts (receipt_no, payment_id)
                VALUES (?, ?)
                """,
                (receipt_no, p["id"]),
            )
        db.commit()
    except sqlite3.IntegrityError:
        # If receipt_no unique conflicts (rare), fallback to existing by payment_id
        db.rollback()
        existing = db.execute(
            "SELECT receipt_no FROM receipts WHERE payment_id=?",
            (p["id"],),
        ).fetchone()
        if existing and existing["receipt_no"]:
            receipt_no = existing["receipt_no"]
        else:
            flash("Receipt creation failed. Check server logs.", "warning")
    except Exception as e:
        db.rollback()
        print("❌ receipt insert failed:", repr(e))
        flash("Receipt creation failed. Check server logs.", "warning")

    # ---- Build PDF + Email (non-blocking) ----
    inst = db.execute(
        "SELECT short_name, full_name FROM institutes WHERE id=?",
        (student["institute_id"],),
    ).fetchone()

    payment_dict = dict(p)
    payment_dict["status"] = "SUCCESS"  # reflect updated state

    pdf_bytes = b""
    try:
        pdf_bytes = _build_receipt_pdf_bytes(student, inst, payment_dict, receipt_no)
    except Exception as e:
        print("❌ PDF build failed:", repr(e))
        # don’t fail the payment because PDF failed
        pdf_bytes = b""

    subject = f"Fee Receipt - {receipt_no}"
    body = (
        f"Hello {student['name']},\n\n"
        f"Your fee payment was successful.\n\n"
        f"Transaction ID: {txn_id}\n"
        f"Category: {p['category']}\n"
        f"Amount Paid: ₹{int(p['amount'] or 0):,}\n"
        f"Receipt No: {receipt_no}\n\n"
        f"Regards,\nJKK Munirajah Institutions\n"
    )

    recipients = [
        (student["student_email"] or "").strip(),
        (student["parent_email"] or "").strip(),
    ]
    recipients = [e for e in recipients if e]

    sent_count = 0
    fail_count = 0

    for to_email in recipients:
        try:
            if pdf_bytes and "send_receipt_email" in globals() and callable(send_receipt_email):
                send_receipt_email(to_email, subject, body, pdf_bytes, f"{receipt_no}.pdf")
            elif "send_email" in globals() and callable(send_email):
                send_email(to_email, subject, body)
            else:
                raise RuntimeError("No email function available (send_receipt_email/send_email missing)")
            sent_count += 1
        except Exception as e:
            fail_count += 1
            print("❌ Email failed:", to_email, "|", repr(e))

    if recipients:
        if sent_count > 0 and fail_count == 0:
            flash("Payment successful ✅ (Receipt emailed)", "success")
        elif sent_count > 0 and fail_count > 0:
            flash("Payment successful ✅ (Some emails failed)", "warning")
        else:
            flash("Payment successful ✅ (Email failed)", "warning")
    else:
        flash("Payment successful ✅ (No email on profile)", "info")

    return redirect(url_for("student.pay_status", txn_id=txn_id))


# -----------------------------
# Receipt PDF download
# -----------------------------
@student_bp.get("/receipt/<txn_id>.pdf")
@student_required
def receipt_pdf(txn_id):
    db = get_db()

    p = db.execute(
        """
        SELECT id, txn_id, student_id, category, amount, method, status, created_at
        FROM payments
        WHERE txn_id=?
        """,
        (txn_id,),
    ).fetchone()

    if not p:
        flash("Transaction not found.", "danger")
        return redirect(url_for("student.fees"))

    if p["status"] != "SUCCESS":
        flash("Receipt is available only for successful payments.", "warning")
        return redirect(url_for("student.pay_status", txn_id=txn_id))

    student = _student_row_by_session(db)
    if not student or student["id"] != p["student_id"]:
        flash("Unauthorized receipt access.", "danger")
        return redirect(url_for("student.fees"))

    inst = db.execute(
        "SELECT short_name, full_name FROM institutes WHERE id=?",
        (student["institute_id"],),
    ).fetchone()

    receipt_no = _receipt_no(p["txn_id"])
    pdf_bytes = _build_receipt_pdf_bytes(student, inst, p, receipt_no)

    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f"{receipt_no}.pdf",
        mimetype="application/pdf",
    )
