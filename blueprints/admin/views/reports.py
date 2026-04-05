from flask import render_template, request, redirect, url_for, flash, session, make_response, Response, jsonify
from datetime import date, timedelta
from .. import admin_bp
from utils.decorators import admin_required
from utils.reports import generate_daily_collection_pdf, generate_dues_csv, generate_dues_excel
from utils.notifications import send_alert
from utils.fees import get_fee_state_for_student
from .utils import to_int


@admin_bp.route("/audit-logs", methods=["GET"])
@admin_required
def audit_logs():
    from models import AuditLog, User, Student
    from extensions import db
    from sqlalchemy import or_, cast, String

    inst_id = session["institute_id"]
    q = (request.args.get("q") or "").strip()
    day = (request.args.get("day") or "").strip()
    action_filter = (request.args.get("action") or "").strip()
    page = max(1, to_int(request.args.get("page"), 1))
    per_page = 50

    query = db.session.query(AuditLog).filter(AuditLog.institute_id == inst_id)

    if day:
        query = query.filter(db.func.date(AuditLog.created_at) == day)

    if action_filter:
        query = query.filter(AuditLog.action == action_filter)

    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            AuditLog.action.like(like),
            AuditLog.entity_type.like(like),
            cast(AuditLog.entity_id, String).like(like),
            AuditLog.details.like(like),
        ))

    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    rows_orm = query.order_by(AuditLog.id.desc()).offset(offset).limit(per_page).all()

    # Build display-friendly dicts with joined data
    rows = []
    for al in rows_orm:
        admin_user = User.query.get(al.actor_user_id) if al.actor_user_id else None
        student = None
        if al.entity_type == "student" and al.entity_id:
            student = Student.query.get(al.entity_id)
        rows.append({
            "id": al.id,
            "created_at": al.created_at,
            "action": al.action,
            "entity_type": al.entity_type,
            "entity_id": al.entity_id,
            "details_json": al.details,
            "ip": al.ip,
            "actor_role": al.actor_role,
            "admin_username": admin_user.username if admin_user else None,
            "student_adm": student.admission_no if student else None,
            "student_name": student.name if student else None,
        })

    actions_q = db.session.query(AuditLog.action).filter_by(
        institute_id=inst_id
    ).distinct().order_by(AuditLog.action).all()
    actions = [r[0] for r in actions_q]

    return render_template(
        "admin/audit_logs.html",
        logs=rows, actions=actions, q=q, day=day, action=action_filter,
        page=page, total_pages=total_pages, total=total,
    )


@admin_bp.route("/reports/daily", methods=["GET"])
@admin_required
def daily_fees_summary():
    from models import Payment, Student
    from extensions import db
    from sqlalchemy import func, case

    inst_id = session["institute_id"]
    day = (request.args.get("day") or "").strip() or date.today().isoformat()
    q = (request.args.get("q") or "").strip()

    base_q = db.session.query(Payment).join(
        Student, Student.id == Payment.student_id
    ).filter(
        Student.institute_id == inst_id,
        Payment.status == "SUCCESS",
        db.func.date(Payment.created_at) == day,
    )

    if q:
        like = f"%{q}%"
        base_q = base_q.filter(or_(
            Student.admission_no.like(like),
            Student.name.like(like)
        ))

    # Category totals
    totals_q = db.session.query(
        Payment.category,
        func.coalesce(func.sum(Payment.amount), 0).label("total")
    ).join(Student, Student.id == Payment.student_id).filter(
        Student.institute_id == inst_id,
        Payment.status == "SUCCESS",
        func.date(Payment.created_at) == day,
    )
    if q:
        like = f"%{q}%"
        totals_q = totals_q.filter(or_(Student.admission_no.like(like), Student.name.like(like)))
    totals_q = totals_q.group_by(Payment.category).order_by(func.sum(Payment.amount).desc())
    totals = [{"category": r.category, "total": r.total} for r in totals_q.all()]

    # Cash vs Online split
    split_q = db.session.query(
        func.coalesce(func.sum(case((Payment.method == "CASH_COUNTER", Payment.amount), else_=0)), 0).label("cash_total"),
        func.coalesce(func.sum(case((Payment.method != "CASH_COUNTER", Payment.amount), else_=0)), 0).label("online_total"),
    ).join(Student, Student.id == Payment.student_id).filter(
        Student.institute_id == inst_id,
        Payment.status == "SUCCESS",
        func.date(Payment.created_at) == day,
    )
    split = split_q.first()
    cash_total = int(split.cash_total or 0)
    online_total = int(split.online_total or 0)

    # Transaction list
    tx_q = base_q.order_by(Payment.id.desc()).limit(400).all()
    tx = [{
        "id": p.id, "created_at": p.created_at,
        "student_id": p.student_id,
        "admission_no": p.student.admission_no, "name": p.student.name,
        "category": p.category, "amount": p.amount,
        "txn_id": p.txn_id, "method": p.method,
    } for p in tx_q]

    grand_total = sum(r["total"] for r in totals)

    return render_template(
        "admin/daily_summary.html",
        day=day, q=q, totals=totals, tx=tx,
        grand_total=grand_total, cash_total=cash_total, online_total=online_total,
    )


@admin_bp.route("/reports", methods=["GET"])
@admin_required
def reports():
    return render_template("admin/reports.html", today=date.today())


@admin_bp.route("/reports/daily-pdf", methods=["GET"])
@admin_required
def download_daily_report():
    from extensions import db
    inst_id = session["institute_id"]
    date_str = request.args.get("date") or str(date.today())
    pdf_bytes = generate_daily_collection_pdf(db, inst_id, date_str)
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=DailyCollection_{date_str}.pdf"
    return response


@admin_bp.route("/reports/dues-csv", methods=["GET"])
@admin_required
def download_dues_report():
    from extensions import db
    inst_id = session["institute_id"]
    csv_str = generate_dues_csv(db, inst_id)
    return Response(csv_str, mimetype="text/csv",
                    headers={"Content-disposition": "attachment; filename=Outstanding_Dues.csv"})


@admin_bp.route("/reports/dues-excel", methods=["GET"])
@admin_required
def download_dues_report_excel():
    from extensions import db
    inst_id = session.get("institute_id")
    role = session.get("role")
    if role == "FOUNDER":
        inst_id = request.args.get("inst")
    excel_io = generate_dues_excel(db, inst_id)
    return Response(
        excel_io.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-disposition": "attachment; filename=Outstanding_Dues.xlsx"},
    )


@admin_bp.post("/reports/send-notifications")
@admin_required
def send_notifications():
    from models import Student
    from extensions import db

    inst_id = session["institute_id"]
    students = Student.query.filter_by(institute_id=inst_id, is_active=1).all()

    count = 0
    for s in students:
        state = get_fee_state_for_student(db, s.id)
        if state["ok"] and state["due_total"] > 0:
            msg = f"Dear {s.name}, you have outstanding fees of Rs.{state['due_total']}. Please pay immediately."
            ph = s.parent_phone or s.student_phone
            if ph:
                send_alert(s.id, msg, type="SMS")
                count += 1

    flash(f"Sent alerts to {count} students with outstanding dues.", "success")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/api/analytics", methods=["GET"])
@admin_required
def analytics_api():
    from models import Payment, Student, Institute
    from extensions import db
    from sqlalchemy import func

    role = session.get("role")
    inst_id = session.get("institute_id")

    today = date.today()
    last_7_days = []
    daily_collection = []

    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        last_7_days.append(d.strftime("%d %b"))

        q = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).join(
            Student, Student.id == Payment.student_id
        ).filter(
            Payment.status == "SUCCESS",
            func.date(Payment.created_at) == d.isoformat(),
            Student.is_active == 1,
        )
        if role == "ADMIN":
            q = q.filter(Student.institute_id == inst_id)
        elif request.args.get("inst"):
            q = q.filter(Student.institute_id == request.args.get("inst"))
        daily_collection.append(q.scalar() or 0)

    # Payment mode split
    modes_q = db.session.query(
        Payment.method,
        func.coalesce(func.sum(Payment.amount), 0).label("total")
    ).join(Student, Student.id == Payment.student_id).filter(
        Payment.status == "SUCCESS", Student.is_active == 1
    )
    if role == "ADMIN":
        modes_q = modes_q.filter(Student.institute_id == inst_id)
    modes_rows = modes_q.group_by(Payment.method).all()
    modes_labels = [r.method.replace("_", " ").title() for r in modes_rows]
    modes_data = [r.total for r in modes_rows]

    # Category split
    cat_q = db.session.query(
        Payment.category,
        func.coalesce(func.sum(Payment.amount), 0).label("total")
    ).join(Student, Student.id == Payment.student_id).filter(
        Payment.status == "SUCCESS", Student.is_active == 1
    )
    if role == "ADMIN":
        cat_q = cat_q.filter(Student.institute_id == inst_id)
    cat_rows = cat_q.group_by(Payment.category).all()
    cat_labels = [r.category.title() for r in cat_rows]
    cat_data = [r.total for r in cat_rows]

    # Founder stats
    founder_stats = {}
    if role == "FOUNDER" and not request.args.get("inst"):
        institutes = Institute.query.all()
        founder_stats = {"institutes": [], "collected": [], "outstanding": []}
        for inst in institutes:
            founder_stats["institutes"].append(inst.short_name or inst.id)
            col = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).join(
                Student, Student.id == Payment.student_id
            ).filter(Student.institute_id == inst.id, Payment.status == "SUCCESS").scalar() or 0
            founder_stats["collected"].append(col)

            active_students = Student.query.filter_by(institute_id=inst.id, is_active=1).all()
            out_sum = sum(get_fee_state_for_student(db, s.id).get("due_total", 0) for s in active_students)
            founder_stats["outstanding"].append(out_sum)

    return jsonify({
        "dates": last_7_days,
        "daily_collection": daily_collection,
        "modes": {"labels": modes_labels, "data": modes_data},
        "categories": {"labels": cat_labels, "data": cat_data},
        "founder_stats": founder_stats,
    })
