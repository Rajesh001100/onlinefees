from flask import render_template, request, session
from extensions import db
from models import Institute, Student, Payment
from sqlalchemy import func
from utils.decorators import admin_required
from .. import admin_bp

@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    role = session.get("role")
    
    # Founder can filter: /admin/dashboard?inst=ENG
    selected_inst = (request.args.get("inst") or "").strip() if role == "FOUNDER" else None

    if role == "ADMIN":
        inst_id = session.get("institute_id")
        inst = Institute.query.get(inst_id)

        rows = db.session.query(Student.year, func.count(Student.id).label('c')) \
            .filter(Student.institute_id == inst_id) \
            .filter(Student.is_active != 0) \
            .group_by(Student.year).order_by(Student.year).all()

        counts = {r.year: r.c for r in rows}
        year_cards = [{"year": y, "count": counts.get(y, 0)} for y in [1, 2, 3, 4]]

        return render_template(
            "admin/dashboard.html",
            inst=inst,
            year_cards=year_cards,
            is_founder=False
        )

    # ---------- FOUNDER MODE ----------
    institutes = Institute.query.order_by(Institute.id).all()

    # If founder is looking at a specific institute
    q = db.session.query(Student.year, func.count(Student.id).label('c')) \
        .filter(Student.is_active != 0)
    
    if selected_inst:
        q = q.filter(Student.institute_id == selected_inst)
    
    rows = q.group_by(Student.year).order_by(Student.year).all()
    counts = {r.year: r.c for r in rows}
    year_cards = [{"year": y, "count": counts.get(y, 0)} for y in [1, 2, 3, 4]]

    # NEW: Multi-institute summary for the founder
    inst_summary = []
    if not selected_inst:
        for i in institutes:
            s_count = Student.query.filter_by(institute_id=i.id, is_active=1).count()
            p_sum = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).join(Student).filter(
                Student.institute_id == i.id, Payment.status == "SUCCESS"
            ).scalar()
            inst_summary.append({
                "id": i.id,
                "name": i.short_name,
                "full_name": i.full_name,
                "students": s_count,
                "collected": p_sum
            })

    # If a specific institute is selected, find its object for the header
    current_inst = None
    if selected_inst:
        current_inst = Institute.query.get(selected_inst)

    return render_template(
        "admin/dashboard.html",
        inst=current_inst,
        year_cards=year_cards,
        institutes=institutes,
        selected_inst=selected_inst,
        is_founder=True,
        inst_summary=inst_summary,
    )
