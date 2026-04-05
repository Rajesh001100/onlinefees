from flask import render_template, request, redirect, url_for, flash, session, send_file
from io import BytesIO
from datetime import datetime
import uuid

from .. import admin_bp
from utils.decorators import admin_required
from utils.fees import get_fee_state_for_student, get_full_course_fee_state
from utils.mailer import send_receipt_email
from blueprints.student.receipt_utils import build_receipt_pdf_bytes

from .utils import to_int, _receipt_no

# -----------------------------
# Fees & Payments
# -----------------------------

@admin_bp.post("/student/<int:student_id>/reset-payments")
@admin_required
def reset_payments(student_id):
    from models import Student, Payment, Receipt
    from extensions import db

    inst_id = session["institute_id"]
    ok = Student.query.filter_by(id=student_id, institute_id=inst_id).first()
    if not ok:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        payment_ids = [p.id for p in Payment.query.filter_by(student_id=student_id).all()]
        if payment_ids:
            Receipt.query.filter(Receipt.payment_id.in_(payment_ids)).delete(synchronize_session=False)
        Payment.query.filter_by(student_id=student_id).delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Reset payments error:", e)

    flash("All payments cleared (demo reset).", "success")
    return redirect(url_for("admin.student_view", student_id=student_id))

@admin_bp.post("/student/<int:student_id>/fine")
@admin_required
def add_fine(student_id):
    from models import Student, FeeAdjustment
    from extensions import db

    inst_id = session["institute_id"]
    ok = Student.query.filter_by(id=student_id, institute_id=inst_id).first()
    if not ok:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    label = (request.form.get("fine_label") or "").strip()
    amount = to_int(request.form.get("fine_amount"), 0)

    if not label:
        flash("Fine label is required.", "danger")
        return redirect(url_for("admin.student_view", student_id=student_id))

    if amount <= 0:
        flash("Fine amount must be > 0.", "danger")
        return redirect(url_for("admin.student_view", student_id=student_id))

    row = FeeAdjustment.query.filter_by(student_id=student_id, category="FINE", label=label).first()
    if row:
        row.amount = amount
    else:
        db.session.add(FeeAdjustment(student_id=student_id, category="FINE", label=label, amount=amount))

    db.session.commit()
    flash(f"Fine added (₹{amount:,}).", "success")
    return redirect(url_for("admin.student_view", student_id=student_id))

@admin_bp.post("/student/<int:student_id>/cash-pay")
@admin_required
def admin_cash_pay(student_id):
    from models import Student, Institute, Payment
    from extensions import db

    inst_id = session["institute_id"]
    s = Student.query.filter_by(id=student_id, institute_id=inst_id).first()
    if not s:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    category = (request.form.get("category") or "").strip().upper()
    amount = to_int(request.form.get("cash_amount"), 0)

    if amount <= 0:
        flash("Amount must be greater than 0.", "danger")
        return redirect(url_for("admin.student_view", student_id=student_id))

    full_state = get_full_course_fee_state(db, student_id=student_id)
    if not full_state or not full_state.get("ok"):
        flash("Detailed fee state error.", "danger")
        return redirect(url_for("admin.student_view", student_id=student_id))

    total_due = 0
    if category in ("TUITION", "OTHER"):
        total_due = full_state.get("grand_total_due", 0)
    else:
        fee_state = get_fee_state_for_student(db, student_id=student_id)
        total_due = fee_state.get("due", {}).get(category, 0)

    if amount > total_due and total_due > 0:
        flash(f"Payment amount (₹{amount:,}) exceeds total due for {category} (₹{total_due:,}).", "warning")

    txn_id = f"CASH-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    try:
        new_pay = Payment(
            student_id=student_id,
            txn_id=txn_id,
            category=category,
            amount=amount,
            method="CASH_COUNTER",
            status="SUCCESS",
        )
        db.session.add(new_pay)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("❌ Cash payment insert failed:", repr(e))
        flash("Failed to record cash payment.", "danger")
        return redirect(url_for("admin.student_view", student_id=student_id))

    inst = Institute.query.get(inst_id)
    receipt_no = _receipt_no(txn_id)

    student_dict = {
        "id": s.id, "name": s.name, "admission_no": s.admission_no,
        "register_no": s.register_no, "year": s.year, "class": s.class_name,
        "course": s.course, "student_email": s.student_email,
        "parent_email": s.parent_email, "institute_id": s.institute_id,
    }
    inst_dict = {"short_name": inst.short_name, "full_name": inst.full_name} if inst else {}

    payment_obj = {
        "txn_id": txn_id, "category": category, "amount": amount,
        "method": "CASH_COUNTER", "status": "SUCCESS",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    pdf_bytes = build_receipt_pdf_bytes(student_dict, inst_dict, payment_obj, receipt_no)

    subject = f"Fee Receipt - {receipt_no}"
    body = (
        f"Hello {s.name},\n\n"
        f"Your cash payment was recorded successfully.\n\n"
        f"Receipt No: {receipt_no}\nTransaction ID: {txn_id}\n"
        f"Category: {category}\nAmount Paid: ₹{amount:,}\n\n"
        f"Regards,\n{inst.full_name if inst else 'Institution'}\n"
    )

    recipients = []
    if (s.student_email or "").strip(): recipients.append(s.student_email.strip())
    if (s.parent_email or "").strip(): recipients.append(s.parent_email.strip())

    sent = 0
    for to_email in recipients:
        try:
            send_receipt_email(to_email, subject, body, pdf_bytes, f"{receipt_no}.pdf")
            sent += 1
        except Exception as e:
            print("❌ Email failed:", to_email, repr(e))

    msg = f"Cash payment recorded (₹{amount:,})."
    if recipients:
        msg += " Receipt emailed." if sent > 0 else " Email failed."
    else:
        msg += " No email on file."

    flash(msg, "success" if sent > 0 or not recipients else "warning")
    return redirect(url_for("admin.student_view", student_id=student_id))


@admin_bp.get("/receipt/<txn_id>.pdf")
@admin_required
def admin_receipt_pdf(txn_id):
    from models import Payment, Student, Institute, Receipt
    from extensions import db

    inst_id = session["institute_id"]

    pay = Payment.query.filter_by(txn_id=txn_id).first()
    if not pay:
        flash("Receipt not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    s = Student.query.filter_by(id=pay.student_id, institute_id=inst_id).first()
    if not s:
        flash("Receipt not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    if pay.status != "SUCCESS":
        flash("Receipt available only for successful payments.", "warning")
        return redirect(url_for("admin.student_view", student_id=pay.student_id))

    r = Receipt.query.filter_by(payment_id=pay.id).first()
    if not r:
        receipt_no = _receipt_no(pay.txn_id)
        try:
            db.session.add(Receipt(receipt_no=receipt_no, payment_id=pay.id))
            db.session.commit()
        except Exception:
            db.session.rollback()
            r2 = Receipt.query.filter_by(payment_id=pay.id).first()
            receipt_no = r2.receipt_no if r2 else receipt_no
    else:
        receipt_no = r.receipt_no

    inst = Institute.query.get(s.institute_id)

    student_dict = {
        "id": s.id, "name": s.name, "admission_no": s.admission_no,
        "register_no": s.register_no, "year": s.year, "class": s.class_name,
        "course": s.course, "student_email": s.student_email,
        "parent_email": s.parent_email, "institute_id": s.institute_id,
    }
    inst_dict = {"short_name": inst.short_name, "full_name": inst.full_name} if inst else {}
    payment_dict = {
        "txn_id": pay.txn_id, "category": pay.category, "amount": pay.amount,
        "method": pay.method, "status": pay.status, "created_at": str(pay.created_at),
    }

    pdf_bytes = build_receipt_pdf_bytes(student_dict, inst_dict, payment_dict, receipt_no)

    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f"{receipt_no}.pdf",
        mimetype="application/pdf",
    )


# -----------------------------
# Installment Settings
# -----------------------------
@admin_bp.route("/settings/installments", methods=["GET"])
@admin_required
def installments():
    from models import FeeInstallment, FeePlan
    from extensions import db
    from sqlalchemy import distinct

    inst_id = session["institute_id"]

    installments = FeeInstallment.query.filter_by(institute_id=inst_id).order_by(
        FeeInstallment.course, FeeInstallment.year, FeeInstallment.due_date
    ).all()

    courses_q = db.session.query(distinct(FeePlan.course)).filter_by(institute_id=inst_id).order_by(FeePlan.course).all()
    courses = [r[0] for r in courses_q]

    return render_template("admin/installments.html", installments=installments, courses=courses)

@admin_bp.route("/settings/installments/add", methods=["POST"])
@admin_required
def add_installment():
    from models import FeeInstallment
    from extensions import db

    inst_id = session["institute_id"]

    course = (request.form.get("course") or "").strip()
    year = to_int(request.form.get("year"), 1)
    label = (request.form.get("label") or "").strip()
    due_date = (request.form.get("due_date") or "").strip()
    percentage = to_int(request.form.get("percentage"), 0)
    late_fee = to_int(request.form.get("late_fee"), 0)

    try:
        db.session.add(FeeInstallment(
            institute_id=inst_id, course=course, year=year,
            label=label, due_date=due_date, percentage=percentage, late_fee_per_day=late_fee
        ))
        db.session.commit()
        flash("Installment schedule added.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Failed to add installment.", "danger")

    return redirect(url_for("admin.installments"))

@admin_bp.route("/settings/installments/<int:id>/delete", methods=["POST"])
@admin_required
def delete_installment(id):
    from models import FeeInstallment
    from extensions import db

    inst_id = session["institute_id"]
    FeeInstallment.query.filter_by(id=id, institute_id=inst_id).delete()
    db.session.commit()
    flash("Installment deleted.", "success")
    return redirect(url_for("admin.installments"))

@admin_bp.route("/settings/installments/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def edit_installment(id):
    from models import FeeInstallment
    from extensions import db

    inst_id = session["institute_id"]

    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        due_date = (request.form.get("due_date") or "").strip()
        percentage = to_int(request.form.get("percentage"), 0)
        late_fee = to_int(request.form.get("late_fee"), 0)

        if not label or not due_date:
            flash("Label and Due Date are required.", "danger")
        elif percentage <= 0 or percentage > 100:
            flash("Percentage must be between 1 and 100.", "danger")
        else:
            try:
                item = FeeInstallment.query.filter_by(id=id, institute_id=inst_id).first()
                if item:
                    item.label = label
                    item.due_date = due_date
                    item.percentage = percentage
                    item.late_fee_per_day = late_fee
                    db.session.commit()
                flash("Installment updated.", "success")
                return redirect(url_for("admin.installments"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating installment: {e}", "danger")

    inst = FeeInstallment.query.filter_by(id=id, institute_id=inst_id).first()
    if not inst:
        flash("Installment not found.", "danger")
        return redirect(url_for("admin.installments"))

    return render_template("admin/edit_installment.html", inst=inst)


# -----------------------------
# Fee Plans Management
# -----------------------------
@admin_bp.route("/settings/plans", methods=["GET"])
@admin_required
def fee_plans():
    from models import FeePlan
    from extensions import db
    from sqlalchemy import distinct

    inst_id = session["institute_id"]

    plans = FeePlan.query.filter_by(institute_id=inst_id).order_by(FeePlan.course, FeePlan.year).all()

    courses_q = db.session.query(distinct(FeePlan.course)).filter_by(institute_id=inst_id).order_by(FeePlan.course).all()
    distinct_courses = [r[0] for r in courses_q]

    return render_template("admin/fee_plans.html", plans=plans, distinct_courses=distinct_courses)

@admin_bp.route("/settings/plans/add", methods=["POST"])
@admin_required
def add_fee_plan():
    from models import FeePlan
    from extensions import db

    inst_id = session["institute_id"]
    course = (request.form.get("course") or "").strip()
    year = to_int(request.form.get("year"), 1)
    tuition = to_int(request.form.get("tuition"), 0)
    exam = to_int(request.form.get("exam"), 0)
    other = to_int(request.form.get("other"), 0)
    hostel = to_int(request.form.get("hostel"), 50000)

    if not course:
        flash("Course name is required.", "danger")
        return redirect(url_for("admin.fee_plans"))

    exists = FeePlan.query.filter_by(institute_id=inst_id, course=course, year=year).first()
    if exists:
        flash(f"Fee plan for {course} Year {year} already exists.", "danger")
        return redirect(url_for("admin.fee_plans"))

    try:
        db.session.add(FeePlan(institute_id=inst_id, course=course, year=year, tuition=tuition, exam=exam, other=other, hostel=hostel))
        db.session.commit()
        flash(f"Fee plan added for {course} Year {year}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to add fee plan: {e}", "danger")

    return redirect(url_for("admin.fee_plans"))

@admin_bp.route("/settings/plans/<int:id>/delete", methods=["POST"])
@admin_required
def delete_fee_plan(id):
    from models import FeePlan
    from extensions import db

    inst_id = session["institute_id"]
    try:
        FeePlan.query.filter_by(id=id, institute_id=inst_id).delete()
        db.session.commit()
        flash("Fee plan deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Failed to delete fee plan.", "danger")

    return redirect(url_for("admin.fee_plans"))

@admin_bp.route("/settings/plans/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def edit_fee_plan(id):
    from models import FeePlan
    from extensions import db

    inst_id = session["institute_id"]

    if request.method == "POST":
        tuition = to_int(request.form.get("tuition"), 0)
        exam = to_int(request.form.get("exam"), 0)
        other = to_int(request.form.get("other"), 0)
        hostel = to_int(request.form.get("hostel"), 50000)

        try:
            p = FeePlan.query.filter_by(id=id, institute_id=inst_id).first()
            if p:
                p.tuition = tuition
                p.exam = exam
                p.other = other
                p.hostel = hostel
                db.session.commit()
            flash("Fee plan updated successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to update fee plan: {e}", "danger")

        return redirect(url_for("admin.fee_plans"))

    plan = FeePlan.query.filter_by(id=id, institute_id=inst_id).first()
    if not plan:
        flash("Fee plan not found.", "danger")
        return redirect(url_for("admin.fee_plans"))

    return render_template("admin/edit_fee_plan.html", p=plan)


# -----------------------------
# Common Fees Management
# -----------------------------
@admin_bp.route("/settings/common-fees", methods=["GET"])
@admin_required
def common_fees():
    from models import CommonFee
    inst_id = session["institute_id"]
    fees = CommonFee.query.filter_by(institute_id=inst_id).order_by(CommonFee.created_at.desc()).all()
    return render_template("admin/common_fees.html", fees=fees)

@admin_bp.post("/settings/common-fees/add")
@admin_required
def add_common_fee():
    from models import CommonFee
    from extensions import db

    inst_id = session["institute_id"]
    label = (request.form.get("label") or "").strip()
    amount = to_int(request.form.get("amount"), 0)

    if not label:
        flash("Fee label is required.", "danger")
    elif amount <= 0:
        flash("Amount must be greater than 0.", "danger")
    else:
        try:
            db.session.add(CommonFee(
                institute_id=inst_id,
                category="OTHER",
                label=label,
                amount=amount
            ))
            db.session.commit()
            flash(f"Common fee '{label}' added for all students.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add common fee: {e}", "danger")

    return redirect(url_for("admin.common_fees"))

@admin_bp.post("/settings/common-fees/<int:id>/delete")
@admin_required
def delete_common_fee(id):
    from models import CommonFee
    from extensions import db

    inst_id = session["institute_id"]
    try:
        CommonFee.query.filter_by(id=id, institute_id=inst_id).delete()
        db.session.commit()
        flash("Common fee removed.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete common fee: {e}", "danger")

    return redirect(url_for("admin.common_fees"))

# -----------------------------
# Scholarship Management
# -----------------------------
@admin_bp.route("/settings/scholarships", methods=["GET"])
@admin_required
def scholarships():
    from models import Scholarship
    inst_id = session["institute_id"]
    scholarships = Scholarship.query.filter_by(institute_id=inst_id).order_by(Scholarship.created_at.desc()).all()
    return render_template("admin/scholarships.html", scholarships=scholarships)

@admin_bp.post("/settings/scholarships/add")
@admin_required
def add_scholarship():
    from models import Scholarship
    from extensions import db

    inst_id = session["institute_id"]
    stype = (request.form.get("scholarship_type") or "").strip().upper()
    amount = to_int(request.form.get("amount"), 0)

    if not stype:
        flash("Scholarship type is required.", "danger")
    else:
        try:
            db.session.add(Scholarship(
                institute_id=inst_id,
                scholarship_type=stype,
                amount=amount
            ))
            db.session.commit()
            flash(f"Scholarship '{stype}' added.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add scholarship: {e}", "danger")

    return redirect(url_for("admin.scholarships"))

@admin_bp.post("/settings/scholarships/<int:id>/edit")
@admin_required
def edit_scholarship(id):
    from models import Scholarship
    from extensions import db

    inst_id = session["institute_id"]
    stype = (request.form.get("scholarship_type") or "").strip().upper()
    amount = to_int(request.form.get("amount"), 0)

    try:
        s = Scholarship.query.filter_by(id=id, institute_id=inst_id).first()
        if s:
            s.scholarship_type = stype
            s.amount = amount
            db.session.commit()
            flash("Scholarship updated.", "success")
        else:
            flash("Scholarship not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update scholarship: {e}", "danger")

    return redirect(url_for("admin.scholarships"))

@admin_bp.post("/settings/scholarships/<int:id>/delete")
@admin_required
def delete_scholarship(id):
    from models import Scholarship
    from extensions import db

    inst_id = session["institute_id"]
    try:
        Scholarship.query.filter_by(id=id, institute_id=inst_id).delete()
        db.session.commit()
        flash("Scholarship removed.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to delete scholarship: {e}", "danger")

    return redirect(url_for("admin.scholarships"))

@admin_bp.get("/verify-receipt/<receipt_no>")
@admin_required
def verify_receipt(receipt_no):
    """Admin-only receipt verification page. scanned from QR."""
    from models import Receipt, Payment, Student, Institute
    from extensions import db

    inst_id = session["institute_id"]

    r = Receipt.query.filter_by(receipt_no=receipt_no).first()
    if not r:
        return render_template("admin/verify_receipt.html",
                               receipt_no=receipt_no, payment=None,
                               student=None, inst_name="JKK Munirajah Institutions"), 404

    pay = Payment.query.get(r.payment_id)
    # Security: Ensure receipt belongs to this institute
    stu = Student.query.filter_by(id=pay.student_id, institute_id=inst_id).first() if pay else None
    
    if not stu:
        flash("Unauthorized verification or receipt not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    inst = Institute.query.get(stu.institute_id)

    return render_template(
        "admin/verify_receipt.html",
        receipt_no=receipt_no,
        payment=pay,
        student=stu,
        inst_name=inst.full_name if inst else "JKK Munirajah Institutions",
    )
