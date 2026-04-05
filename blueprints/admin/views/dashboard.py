from flask import render_template, request, session
from utils.db import get_db
from utils.decorators import admin_required
from .. import admin_bp

@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    db = get_db()
    role = session.get("role")

    # founder can filter: /admin/dashboard?inst=ENG
    selected_inst = (request.args.get("inst") or "").strip() if role == "FOUNDER" else None

    if role == "ADMIN":
        inst_id = session.get("institute_id")

        from models import Institute, Student
        from extensions import db
        from sqlalchemy import func

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
        )

    # ---------- FOUNDER MODE ----------
    from models import Institute, Student
    from extensions import db
    from sqlalchemy import func

    institutes = Institute.query.order_by(Institute.id).all()

    q = db.session.query(Student.year, func.count(Student.id).label('c')) \
        .filter(Student.is_active != 0)

    if selected_inst:
        q = q.filter(Student.institute_id == selected_inst)

    rows = q.group_by(Student.year).order_by(Student.year).all()

    counts = {r.year: r.c for r in rows}
    year_cards = [{"year": y, "count": counts.get(y, 0)} for y in [1, 2, 3, 4]]

    # inst is None for founder (or you can set label)
    return render_template(
        "admin/dashboard.html",
        inst=None,
        year_cards=year_cards,
        institutes=institutes,
        selected_inst=selected_inst,
        is_founder=True,
    )
