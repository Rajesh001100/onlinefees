from flask import render_template, request, redirect, url_for, flash, session, current_app
from .. import admin_bp
from utils.db import get_db
from utils.decorators import admin_required
from utils.audit import audit_log
from utils.fees import get_fee_state_for_student, get_full_course_fee_state
from utils.bulk import parse_student_csv
from .utils import (
    to_int, _only_digits, _dob_to_ddmmyyyy, rget, 
    _require_hash_password, _save_student_photo, _is_75,
    QUOTAS
)


# -----------------------------
# Year > Classes > Students
# -----------------------------
@admin_bp.get("/year/<int:year>/classes")
@admin_required
def classes(year):
    from models import Student, Scholarship
    from extensions import db
    from sqlalchemy import func

    inst_id = session["institute_id"]

    rows = db.session.query(Student.class_name, func.count(Student.id).label('c')) \
        .filter(Student.institute_id == inst_id, Student.year == year, Student.is_active != 0) \
        .group_by(Student.class_name).order_by(Student.class_name).all()

    classes_list = [{"class": r.class_name, "count": r.c} for r in rows]
    return render_template("admin/classes.html", year=year, classes=classes_list)

@admin_bp.get("/year/<int:year>/class/<cls>/students")
@admin_required
def students(year, cls):
    from models import Student
    from extensions import db
    from sqlalchemy import or_

    inst_id = session["institute_id"]

    q_search = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "admission")
    order = request.args.get("order", "asc")
    page = max(1, to_int(request.args.get("page"), 1))
    per_page = 25

    sort_map = {"admission": Student.admission_no, "name": Student.name, "regno": Student.register_no}
    sort_col = sort_map.get(sort, Student.admission_no)

    q_base = db.session.query(Student).filter(
        Student.institute_id == inst_id,
        Student.year == year,
        Student.class_name == cls,
        Student.is_active != 0
    )

    if q_search:
        like_str = f"%{q_search}%"
        q_base = q_base.filter(or_(
            Student.admission_no.like(like_str),
            Student.name.like(like_str),
            Student.register_no.like(like_str)
        ))

    total = q_base.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    if order.lower() == "desc":
        q_base = q_base.order_by(sort_col.desc())
    else:
        q_base = q_base.order_by(sort_col.asc())

    students_rows = q_base.offset(offset).limit(per_page).all()

    # Create a dict-like interface for students_rows so jinja templates don't break
    students_dicts = [
        {
            "id": s.id, "name": s.name, "admission_no": s.admission_no,
            "register_no": s.register_no, "class": s.class_name, "year": s.year, "is_active": s.is_active
        } 
        for s in students_rows
    ]

    return render_template(
        "admin/students.html",
        year=year,
        cls=cls,
        students=students_dicts,
        q=q_search,
        sort=sort,
        order=order,
        page=page,
        total_pages=total_pages,
        total=total,
    )

@admin_bp.get("/student/<int:student_id>")
@admin_required
def student_view(student_id):
    from models import Student, Institute, Payment, FeeAdjustment
    from extensions import db

    inst_id = session["institute_id"]

    student = Student.query.filter_by(id=student_id, institute_id=inst_id).first()

    if not student:
        flash("Student not found for your institute.", "danger")
        return redirect(url_for("admin.dashboard"))

    inst = Institute.query.get(student.institute_id)

    # Fee engine state
    fee_state = get_fee_state_for_student(db, student_id=student.id)
    if not fee_state:
        fee_state = {"ok": False, "error": "Fee state not available."}

    # Payments list
    payments = Payment.query.filter_by(student_id=student.id).order_by(Payment.id.desc()).all()

    # Adjustments
    adjustments = FeeAdjustment.query.filter_by(student_id=student.id).order_by(FeeAdjustment.id.desc()).all()

    # Fines
    fine_rows = FeeAdjustment.query.filter_by(student_id=student.id, category="FINE").order_by(FeeAdjustment.id.desc()).all()

    photo_url = (
        url_for("static", filename=f"uploads/students/{student.photo_filename}")
        if student.photo_filename
        else url_for("static", filename="uploads/students/default_student.png")
    )
    
    student_dict = {
        "id": student.id, "user_id": student.user_id, "name": student.name,
        "admission_no": student.admission_no, "register_no": student.register_no,
        "dob": student.dob, "year": student.year, "class": student.class_name,
        "course": student.course, "student_phone": student.student_phone,
        "parent_phone": student.parent_phone, "student_email": student.student_email,
        "parent_email": student.parent_email, "institute_id": student.institute_id,
        "photo_filename": student.photo_filename, "is_active": student.is_active
    }
    inst_dict = {"short_name": inst.short_name, "full_name": inst.full_name} if inst else {}
    payments_dicts = [{"txn_id": p.txn_id, "category": p.category, "amount": p.amount, "method": p.method, "status": p.status, "created_at": str(p.created_at)} for p in payments]
    adj_dicts = [{"category": a.category, "label": a.label, "amount": a.amount, "created_at": str(a.created_at)} for a in adjustments]
    fine_dicts = [{"label": a.label, "amount": a.amount, "created_at": str(a.created_at)} for a in fine_rows]

    return render_template(
        "admin/student_view.html",
        student=student_dict,
        inst=inst_dict,
        photo_url=photo_url,
        payments=payments_dicts,
        adjustments=adj_dicts,
        fine_rows=fine_dicts,
        fee_state=fee_state,
        full_state=get_full_course_fee_state(db, student_id=student_id),
    )

@admin_bp.route("/students/add", methods=["GET", "POST"])
@admin_required
def add_student():
    from models import Scholarship
    db_conn = get_db()
    inst_id = session["institute_id"]

    scholarships = Scholarship.query.filter_by(institute_id=inst_id, is_active=1).all()
    scholarship_map = {s.scholarship_type: s.amount for s in scholarships}

    course_rows = db.execute(
        "SELECT DISTINCT course FROM fee_plans WHERE institute_id=? ORDER BY course",
        (inst_id,),
    ).fetchall()
    course_options = [r["course"] for r in course_rows]

    def has_fee_plan(course: str, year: int) -> bool:
        row = db.execute(
            "SELECT 1 FROM fee_plans WHERE institute_id=? AND course=? AND year=?",
            (inst_id, course, year),
        ).fetchone()
        return bool(row)

    def upsert_adjustment(student_id: int, category: str, label: str, amount: int):
        # same logic as in main routes
        db.execute(
            "DELETE FROM fee_adjustments WHERE student_id=? AND category=? AND label=?",
            (student_id, category, label),
        )
        amt = int(amount or 0)
        if amt != 0:
            db.execute(
                "INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (?,?,?,?)",
                (student_id, category, label, amt),
            )

    if request.method == "POST":
        # Form handling ... (copied from original)
        admission_no = (request.form.get("admission_no") or "").strip().upper()
        register_no = (request.form.get("register_no") or "").strip()
        name = (request.form.get("name") or "").strip()
        dob = (request.form.get("dob") or "").strip()
        year = to_int(request.form.get("year"), 0)
        class_ = (request.form.get("class") or "").strip().upper()
        course = (request.form.get("course") or "").strip()

        student_email = (request.form.get("student_email") or "").strip()
        parent_email = (request.form.get("parent_email") or "").strip()
        student_phone = (request.form.get("student_phone") or "").strip()
        parent_phone = (request.form.get("parent_phone") or "").strip()
        is_hosteller = 1 if str(request.form.get("is_hosteller", "0")) == "1" else 0
        h_sems = {f"hostel_sem{i}": (1 if request.form.get(f"hostel_sem{i}") == "1" else 0) for i in range(1, 9)}

        gym_fee = to_int(request.form.get("gym_fee"), 0)
        laundry_fee = to_int(request.form.get("laundry_fee"), 0)
        bus_fee = to_int(request.form.get("bus_fee"), 0)
        exam_fee = to_int(request.form.get("exam_fee"), 0)
        admission_fee = to_int(request.form.get("admission_fee"), 0)

        benefit_type = (request.form.get("benefit_type") or "NONE").strip().upper()
        scholarship_type_selected = (request.form.get("scholarship_type_selected") or "NONE").strip().upper()
        quota_type = (request.form.get("quota_type") or "").strip().upper()
        quota_amount = to_int(request.form.get("quota_amount"), 0)

        form = {
            "admission_no": admission_no,
            "register_no": register_no,
            "name": name,
            "dob": dob,
            "year": year,
            "class_": class_,
            "course": course,
            "student_email": student_email,
            "parent_email": parent_email,
            "student_phone": student_phone,
            "parent_phone": parent_phone,
            "is_hosteller": is_hosteller,
            **h_sems,
            "gym_fee": gym_fee,
            "laundry_fee": laundry_fee,
            "bus_fee": bus_fee,
            "benefit_type": benefit_type,
            "scholarship_amount": scholarship_amount if scholarship_amount > 0 else "",
            "quota_type": quota_type,
            "quota_amount": quota_amount if quota_amount > 0 else "",
            "admission_fee": admission_fee if admission_fee > 0 else "",
        }

        # ---- Enhanced Server-Side Validation ----
        import re
        errors = []

        if not admission_no:
            errors.append("Admission number is required.")
        elif len(admission_no) > 20:
            errors.append("Admission number is too long (max 20 chars).")

        if not name:
            errors.append("Student name is required.")
        elif len(name) > 100:
            errors.append("Name is too long (max 100 chars).")

        if not dob:
            errors.append("Date of birth is required.")
        else:
            # Validate DOB format YYYY-MM-DD
            try:
                from datetime import datetime as _dt
                _dt.strptime(dob, "%Y-%m-%d")
            except ValueError:
                errors.append("Date of birth must be in YYYY-MM-DD format.")

        if year not in (1, 2, 3, 4):
            errors.append("Year must be 1, 2, 3, or 4.")

        if not class_:
            errors.append("Class/Branch is required.")

        if not course:
            errors.append("Course is required.")

        # Email format validation
        email_re = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if student_email and not email_re.match(student_email):
            errors.append("Invalid student email format.")
        if parent_email and not parent_email == "" and not email_re.match(parent_email):
            errors.append("Invalid parent email format.")

        # Phone number validation (10 digits)
        if student_phone and (not student_phone.isdigit() or len(student_phone) != 10):
            errors.append("Student phone must be exactly 10 digits.")
        if parent_phone and (not parent_phone.isdigit() or len(parent_phone) != 10):
            errors.append("Parent phone must be exactly 10 digits.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "admin/add_student.html",
                course_options=course_options,
                form=form,
                fee_plan_warning=not has_fee_plan(course, year) if course and year else False,
            )

        dup_user = db.execute(
            "SELECT id FROM users WHERE username=? AND role='STUDENT' AND institute_id=?",
            (admission_no, inst_id),
        ).fetchone()
        if dup_user:
            flash("This admission number already has a login account.", "danger")
            return render_template(
                "admin/add_student.html",
                course_options=course_options,
                form=form,
                fee_plan_warning=not has_fee_plan(course, year),
            )

        dup_student = db.execute(
            "SELECT id FROM students WHERE admission_no=? AND institute_id=?",
            (admission_no, inst_id),
        ).fetchone()
        if dup_student:
            flash("This admission number already exists in students table.", "danger")
            return render_template(
                "admin/add_student.html",
                course_options=course_options,
                form=form,
                fee_plan_warning=not has_fee_plan(course, year),
            )

        if is_hosteller == 1:
            bus_fee = 0
        else:
            gym_fee = 0
            laundry_fee = 0

        is_first_graduate = 0
        student_quota_type = "REGULAR"
        discount_label = None
        discount_amount = 0

        if benefit_type == "NONE":
            pass
        elif benefit_type == "FIRST_GRADUATE":
            is_first_graduate = 1
        elif benefit_type == "RESERVATION_7_5":
            student_quota_type = "7.5 RESERVATION"
        elif benefit_type == "SCHOLARSHIP":
            s_amt = scholarship_map.get(scholarship_type_selected, 0)
            discount_label = f"Scholarship ({scholarship_type_selected})"
            discount_amount = -abs(int(s_amt))
            student_quota_type = scholarship_type_selected # Update quota_type field with scholarship name
        elif benefit_type == "QUOTA":
            if not quota_type or quota_amount <= 0:
                flash("Quota type and amount are required.", "danger")
                return render_template("admin/add_student.html", course_options=course_options, form=form, fee_plan_warning=not has_fee_plan(course, year))
            discount_label = f"Quota ({quota_type})"
            discount_amount = -abs(int(quota_amount))
        else:
            flash("Invalid benefit selection.", "danger")
            return render_template("admin/add_student.html", course_options=course_options, form=form, fee_plan_warning=not has_fee_plan(course, year))

        photo_filename = None
        try:
            photo_filename = _save_student_photo(request.files.get("photo"), admission_no)
        except Exception as e:
            flash(str(e), "danger")
            return render_template("admin/add_student.html", course_options=course_options, form=form, fee_plan_warning=not has_fee_plan(course, year))

        hp = _require_hash_password()
        raw_pwd = _dob_to_ddmmyyyy(dob)
        password_hash = hp(raw_pwd)

        try:
            db.execute(
                "INSERT INTO users (username, password_hash, role, institute_id, is_active) VALUES (?, ?, 'STUDENT', ?, 1)",
                (admission_no, password_hash, inst_id),
            )
            user_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

            db.execute(
                """
                INSERT INTO students (
                    user_id, admission_no, register_no, name, dob, year, class, course,
                    student_email, parent_email, student_phone, parent_phone,
                    institute_id, photo_filename,
                    is_hosteller, hostel_sem1, hostel_sem2,
                    hostel_sem3, hostel_sem4, hostel_sem5, hostel_sem6, hostel_sem7, hostel_sem8,
                    quota_type, is_first_graduate,
                    is_active
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
                """,
                (
                    user_id, admission_no, (register_no or None), name, dob, year, class_, course,
                    (student_email or None), (parent_email or None),
                    (student_phone or None), (parent_phone or None),
                    inst_id, photo_filename,
                    is_hosteller,
                    h_sems["hostel_sem1"], h_sems["hostel_sem2"], h_sems["hostel_sem3"], h_sems["hostel_sem4"],
                    h_sems["hostel_sem5"], h_sems["hostel_sem6"], h_sems["hostel_sem7"], h_sems["hostel_sem8"],
                    student_quota_type, is_first_graduate, admission_fee
                ),
            )

            student_id = db.execute(
                "SELECT id FROM students WHERE user_id=? AND institute_id=?",
                (user_id, inst_id),
            ).fetchone()["id"]

            upsert_adjustment(student_id, "GYM", "Gym Fee", gym_fee)
            upsert_adjustment(student_id, "LAUNDRY", "Laundry Fee", laundry_fee)
            upsert_adjustment(student_id, "BUS", "Bus Fee", bus_fee)
            upsert_adjustment(student_id, "EXAM", "Exam Fee", exam_fee)
            upsert_adjustment(student_id, "ADMISSION", "Admission Fee", admission_fee)

            if discount_label and discount_amount != 0:
                upsert_adjustment(student_id, "DISCOUNT", discount_label, discount_amount)

            audit_log(
                db,
                action="STUDENT_CREATED",
                entity_type="student",
                entity_id=student_id,
                details={"admission_no": admission_no, "name": name, "benefit": benefit_type},
            )

            db.commit()
            flash("Student added successfully.", "success")
            return redirect(url_for("admin.student_view", student_id=student_id))

        except Exception as e:
            db.rollback()
            print("❌ Add student failed:", repr(e))
            flash("Add student failed. Check server logs.", "danger")
            return render_template(
                "admin/add_student.html",
                course_options=course_options,
                form=form,
                fee_plan_warning=not has_fee_plan(course, year),
            )

    return render_template(
        "admin/add_student.html",
        course_options=course_options,
        scholarships=scholarships,
        form=None,
        fee_plan_warning=False
    )

@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_student(student_id):
    from models import Scholarship
    db_conn = get_db()
    inst_id = session["institute_id"]

    scholarships = Scholarship.query.filter_by(institute_id=inst_id, is_active=1).all()
    scholarship_map = {s.scholarship_type: s.amount for s in scholarships}

    student = db.execute(
        """
        SELECT id, user_id, admission_no, register_no, name, dob, year, class, course,
               student_email, parent_email, student_phone, parent_phone,
               institute_id, is_hosteller, hostel_sem1, hostel_sem2, hostel_sem3, hostel_sem4,
               hostel_sem5, hostel_sem6, hostel_sem7, hostel_sem8, photo_filename,
               quota_type, is_first_graduate, admission_fee
        FROM students
        WHERE id=? AND institute_id=?
        """,
        (student_id, inst_id),
    ).fetchone()

    if not student:
        flash("Student not found for your institute.", "danger")
        return redirect(url_for("admin.dashboard"))

    course_rows = db.execute(
        "SELECT DISTINCT course FROM fee_plans WHERE institute_id=? ORDER BY course",
        (inst_id,),
    ).fetchall()
    course_options = [r["course"] for r in course_rows]

    def has_fee_plan(course: str, year: int) -> bool:
        row = db.execute(
            "SELECT 1 FROM fee_plans WHERE institute_id=? AND course=? AND year=?",
            (inst_id, course, year),
        ).fetchone()
        return bool(row)

    def _get_adj(label, category):
        r = db.execute(
            "SELECT amount FROM fee_adjustments WHERE student_id=? AND category=? AND label=?",
            (student_id, category, label),
        ).fetchone()
        return int(r["amount"]) if r else 0

    def upsert_adjustment(student_id: int, category: str, label: str, amount: int):
        db.execute(
            "DELETE FROM fee_adjustments WHERE student_id=? AND category=? AND label=?",
            (student_id, category, label),
        )
        amt = int(amount or 0)
        if amt != 0:
            db.execute(
                "INSERT INTO fee_adjustments (student_id, category, label, amount) VALUES (?,?,?,?)",
                (student_id, category, label, amt),
            )

    if request.method == "POST":
        admission_no = student["admission_no"]  # locked
        register_no = (request.form.get("register_no") or "").strip()
        name = (request.form.get("name") or "").strip()
        dob = (request.form.get("dob") or "").strip()
        year = to_int(request.form.get("year"), 0)
        class_ = (request.form.get("class") or "").strip().upper()
        course = (request.form.get("course") or "").strip()

        student_email = (request.form.get("student_email") or "").strip()
        parent_email = (request.form.get("parent_email") or "").strip()
        student_phone = (request.form.get("student_phone") or "").strip()
        parent_phone = (request.form.get("parent_phone") or "").strip()

        is_hosteller = 1 if str(request.form.get("is_hosteller", "0")) == "1" else 0
        h_sems = {f"hostel_sem{i}": (1 if request.form.get(f"hostel_sem{i}") == "1" else 0) for i in range(1, 9)}

        exam_fee = to_int(request.form.get("exam_fee"), 0)
        gym_fee = to_int(request.form.get("gym_fee"), 0)
        laundry_fee = to_int(request.form.get("laundry_fee"), 0)
        bus_fee = to_int(request.form.get("bus_fee"), 0)
        admission_fee = to_int(request.form.get("admission_fee"), 0)

        benefit_type = (request.form.get("benefit_type") or "NONE").strip().upper()
        scholarship_type_selected = (request.form.get("scholarship_type_selected") or "NONE").strip().upper()
        quota_type_input = (request.form.get("quota_type") or "").strip().upper()
        quota_amount = to_int(request.form.get("quota_amount"), 0)

        if not name or not dob or year not in (1, 2, 3, 4) or not class_ or not course:
            flash("Fill all required fields (name, dob, year, class, course).", "danger")
            return redirect(url_for("admin.edit_student", student_id=student_id))

        if is_hosteller == 1:
            bus_fee = 0
        else:
            gym_fee = 0
            laundry_fee = 0

        is_first_graduate = 0
        student_quota_type = "REGULAR"
        discount_label = None
        discount_amount = 0

        if benefit_type == "NONE":
            pass
        elif benefit_type == "FIRST_GRADUATE":
            is_first_graduate = 1
        elif benefit_type == "RESERVATION_7_5":
            student_quota_type = "7.5 RESERVATION"
        elif benefit_type == "SCHOLARSHIP":
            s_amt = scholarship_map.get(scholarship_type_selected, 0)
            discount_label = f"Scholarship ({scholarship_type_selected})"
            discount_amount = -abs(int(s_amt))
            student_quota_type = scholarship_type_selected
        elif benefit_type == "QUOTA":
            if not quota_type_input or quota_amount <= 0:
                flash("Quota type and amount are required.", "danger")
                return redirect(url_for("admin.edit_student", student_id=student_id))
            discount_label = f"Quota ({quota_type_input})"
            discount_amount = -abs(int(quota_amount))
        else:
            flash("Invalid benefit selection.", "danger")
            return redirect(url_for("admin.edit_student", student_id=student_id))

        photo_filename = student["photo_filename"]
        try:
            new_photo = _save_student_photo(request.files.get("photo"), admission_no)
            if new_photo:
                photo_filename = new_photo
        except Exception as e:
            flash(str(e), "danger")
            return redirect(url_for("admin.edit_student", student_id=student_id))

        try:
            db.execute(
                """
                UPDATE students
                SET register_no=?, name=?, dob=?, year=?, class=?, course=?,
                    student_email=?, parent_email=?, student_phone=?, parent_phone=?,
                    is_hosteller=?, hostel_sem1=?, hostel_sem2=?, hostel_sem3=?, hostel_sem4=?,
                    hostel_sem5=?, hostel_sem6=?, hostel_sem7=?, hostel_sem8=?, photo_filename=?,
                    quota_type=?, is_first_graduate=?, admission_fee=?
                WHERE id=? AND institute_id=?
                """,
                (
                    (register_no or None), name, dob, year, class_, course,
                    (student_email or None), (parent_email or None),
                    (student_phone or None), (parent_phone or None),
                    is_hosteller,
                    h_sems["hostel_sem1"], h_sems["hostel_sem2"], h_sems["hostel_sem3"], h_sems["hostel_sem4"],
                    h_sems["hostel_sem5"], h_sems["hostel_sem6"], h_sems["hostel_sem7"], h_sems["hostel_sem8"],
                    photo_filename,
                    student_quota_type, is_first_graduate, admission_fee,
                    student_id, inst_id,
                ),
            )

            if dob != (student["dob"] or ""):
                hp = _require_hash_password()
                new_pwd = _dob_to_ddmmyyyy(dob)
                new_hash = hp(new_pwd)
                db.execute(
                    "UPDATE users SET password_hash=? WHERE id=? AND institute_id=? AND role='STUDENT'",
                    (new_hash, student["user_id"], inst_id),
                )

            upsert_adjustment(student_id, "EXAM", "Exam Fee", exam_fee)
            upsert_adjustment(student_id, "GYM", "Gym Fee", gym_fee)
            upsert_adjustment(student_id, "LAUNDRY", "Laundry Fee", laundry_fee)
            upsert_adjustment(student_id, "BUS", "Bus Fee", bus_fee)
            upsert_adjustment(student_id, "ADMISSION", "Admission Fee", admission_fee)

            # Update discount if applicable
            db.execute("DELETE FROM fee_adjustments WHERE student_id=? AND category='DISCOUNT'", (student_id,))
            if discount_label and discount_amount != 0:
                upsert_adjustment(student_id, "DISCOUNT", discount_label, discount_amount)

            audit_log(
                db,
                action="STUDENT_UPDATED",
                entity_type="student",
                entity_id=student_id,
                details={"admission_no": admission_no, "updated": True},
            )

            db.commit()
            flash("Student updated successfully.", "success")
            return redirect(url_for("admin.student_view", student_id=student_id))

        except Exception as e:
            db.rollback()
            print("❌ Update student failed:", repr(e))
            flash("Update failed. Check server logs.", "danger")
            return redirect(url_for("admin.edit_student", student_id=student_id))

    form = {
        "register_no": student["register_no"] or "",
        "name": student["name"] or "",
        "dob": student["dob"] or "",
        "year": int(student["year"] or 1),
        "class_": student["class"] or "",
        "course": student["course"] or "",
        "student_email": student["student_email"] or "",
        "parent_email": student["parent_email"] or "",
        "student_phone": student["student_phone"] or "",
        "parent_phone": student["parent_phone"] or "",
        "is_hosteller": int(student["is_hosteller"] or 0),
        **{f"hostel_sem{i}": int(student[f"hostel_sem{i}"] or 0) for i in range(1, 9)},
        "exam_fee": _get_adj("Exam Fee", "EXAM"),
        "gym_fee": _get_adj("Gym Fee", "GYM"),
        "laundry_fee": _get_adj("Laundry Fee", "LAUNDRY"),
        "bus_fee": _get_adj("Bus Fee", "BUS"),
        "admission_fee": int(student["admission_fee"] or 0),
        "quota_type": student["quota_type"] or "REGULAR",
        "is_first_graduate": int(student["is_first_graduate"] or 0),
    }

    # Determine benefit_type for form
    if form["is_first_graduate"] == 1:
        form["benefit_type"] = "FIRST_GRADUATE"
    elif _is_75(form["quota_type"]):
        form["benefit_type"] = "RESERVATION_7_5"
    else:
        # Check for Scholarship/Quota in adjustments
        scholarship = db_conn.execute("SELECT label, amount FROM fee_adjustments WHERE student_id=? AND category='DISCOUNT' AND label LIKE 'Scholarship (%)'", (student_id,)).fetchone()
        if scholarship:
            form["benefit_type"] = "SCHOLARSHIP"
            import re
            m = re.search(r'\((.*)\)', scholarship["label"])
            form["scholarship_type"] = m.group(1) if m else "NONE"
            form["scholarship_amount"] = abs(int(scholarship["amount"]))
        else:
            quota = db.execute("SELECT label, amount FROM fee_adjustments WHERE student_id=? AND category='DISCOUNT' AND label LIKE 'Quota%'", (student_id,)).fetchone()
            if quota:
                form["benefit_type"] = "QUOTA"
                import re
                m = re.search(r'\((.*)\)', quota["label"])
                form["quota_type"] = m.group(1) if m else "" # Overwrite with specific type for dropdown
                form["quota_amount"] = abs(int(quota["amount"]))
            else:
                form["benefit_type"] = "NONE"

    fee_plan_warning = not has_fee_plan(form["course"], form["year"]) if form["course"] else False

    return render_template(
        "admin/edit_student.html",
        student=student,
        form=form,
        course_options=course_options,
        scholarships=scholarships,
        fee_plan_warning=fee_plan_warning,
    )

@admin_bp.post("/student/<int:student_id>/remove")
@admin_required
def remove_student(student_id):
    db = get_db()
    inst_id = session["institute_id"]

    s = db.execute(
        "SELECT id, user_id FROM students WHERE id=? AND institute_id=?",
        (student_id, inst_id),
    ).fetchone()

    if not s:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        db.execute("UPDATE students SET is_active=0 WHERE id=? AND institute_id=?", (student_id, inst_id))
        if s["user_id"]:
            db.execute("UPDATE users SET is_active=0 WHERE id=? AND institute_id=?", (s["user_id"], inst_id))
        
        audit_log(db, action="STUDENT_REMOVED", entity_type="student", entity_id=student_id)
        db.commit()
        flash("Student disabled (soft deleted).", "success")
    except Exception as e:
        db.rollback()
        print("❌ remove_student failed:", repr(e))
        flash("Failed to disable student.", "danger")

    return redirect(url_for("admin.student_view", student_id=student_id))

@admin_bp.post("/student/<int:student_id>/restore")
@admin_required
def restore_student(student_id):
    db = get_db()
    inst_id = session["institute_id"]

    s = db.execute(
        "SELECT id, user_id FROM students WHERE id=? AND institute_id=?",
        (student_id, inst_id),
    ).fetchone()

    if not s:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        db.execute("UPDATE students SET is_active=1 WHERE id=? AND institute_id=?", (student_id, inst_id))
        if s["user_id"]:
            db.execute("UPDATE users SET is_active=1 WHERE id=? AND institute_id=?", (s["user_id"], inst_id))
        
        audit_log(db, action="STUDENT_RESTORED", entity_type="student", entity_id=student_id)
        db.commit()
        flash("Student restored.", "success")
    except Exception as e:
        db.rollback()
        print("❌ restore_student failed:", repr(e))
        flash("Failed to restore student.", "danger")

    return redirect(url_for("admin.student_view", student_id=student_id))


@admin_bp.route("/students/upload", methods=["GET", "POST"])
@admin_required
def upload_students():
    db = get_db()
    inst_id = session["institute_id"]

    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            flash("No file selected.", "danger")
            return redirect(url_for("admin.upload_students"))

        if not file.filename.lower().endswith(".csv"):
             flash("Only CSV files are allowed.", "danger")
             return redirect(url_for("admin.upload_students"))

        # Parse
        students, parse_errors = parse_student_csv(file.stream)

        if parse_errors:
            return render_template("admin/upload_students.html", errors=parse_errors)

        success_count = 0
        insert_errors = []
        hp = _require_hash_password()

        try:
            for s in students:
                try:
                    admission_no = s["admission_no"].upper()
                    
                    # 1. Check if student already exists
                    exists = db.execute("SELECT 1 FROM students WHERE admission_no=? AND institute_id=?", (admission_no, inst_id)).fetchone()
                    if exists:
                        insert_errors.append(f"Skipped {admission_no}: Student record already exists.")
                        continue
                        
                    # 2. Check if user already exists
                    user_exists = db.execute("SELECT 1 FROM users WHERE username=? AND institute_id=?", (admission_no, inst_id)).fetchone()
                    if user_exists:
                        insert_errors.append(f"Skipped {admission_no}: User account already exists.")
                        continue

                    # 3. Create User
                    raw_pwd = _dob_to_ddmmyyyy(s["dob"])
                    password_hash = hp(raw_pwd)
                    db.execute("INSERT INTO users (username, password_hash, role, institute_id, is_active) VALUES (?, ?, 'STUDENT', ?, 1)", (admission_no, password_hash, inst_id))
                    user_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

                    # 4. Create Student
                    db.execute("""
                        INSERT INTO students (
                            user_id, admission_no, name, dob, year, class, course,
                            student_email, parent_email, student_phone, parent_phone,
                            institute_id, is_active, is_hosteller, hostel_sem1, hostel_sem2, quota_type, is_first_graduate, admission_fee
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 'REGULAR', 0, 0)
                    """, (
                        user_id, admission_no, s["name"], s["dob"], s["year"], s["class"], s["course"],
                        s["student_email"], s["parent_email"], s["student_phone"], s["parent_phone"],
                        inst_id
                    ))
                    
                    student_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                    
                    # 5. Initialize Default Fee Adjustments (Important!)
                    # For bulk upload, set everything to 0 or defaults. Fines/Exam Fees are important.
                    # We only upsert if they are important or have defaults.
                    # Let's set 0 for Gym/Laundry/Bus to ensure they exist for the UI/Engine.
                    upsert_adjustment(student_id, "GYM", "Gym Fee", 0)
                    upsert_adjustment(student_id, "LAUNDRY", "Laundry Fee", 0)
                    upsert_adjustment(student_id, "BUS", "Bus Fee", 0)
                    upsert_adjustment(student_id, "EXAM", "Exam Fee", 0)

                    audit_log(db, action="STUDENT_IMPORTED", entity_type="student", entity_id=student_id, details={"adm": admission_no})
                    success_count += 1
                except Exception as inner_e:
                    db.rollback() # Rollback only this student's partial work
                    print(f"❌ skipping student {s.get('admission_no')}: {inner_e}")
                    insert_errors.append(f"Error {s.get('admission_no')}: {str(inner_e)}")
                    continue
            
            db.commit()
            if success_count > 0:
                flash(f"Successfully uploaded {success_count} students.", "success")
            
            if insert_errors:
                return render_template("admin/upload_students.html", errors=insert_errors, success_count=success_count)
                
            return redirect(url_for("admin.dashboard"))
            
        except Exception as e:
            db.rollback()
            print("Bulk upload critical failure:", e)
            flash(f"Critical error during processing: {str(e)}", "danger")
            return redirect(url_for("admin.upload_students"))

    return render_template("admin/upload_students.html")


# ─────────────────────────────────────────────────────
#  🤖  AI RISK SCORE  (Feature #2)
# ─────────────────────────────────────────────────────

@admin_bp.get("/student/<int:student_id>/risk-score")
@admin_required
def student_risk_score(student_id):
    """JSON API: returns AI risk score for a single student."""
    from flask import jsonify
    from utils.risk_score import compute_risk_score
    from models import Student

    inst_id = session["institute_id"]
    s = Student.query.filter_by(id=student_id, institute_id=inst_id).first()
    if not s:
        return jsonify({"error": "Not found"}), 404

    result = compute_risk_score(student_id)
    return jsonify(result)


@admin_bp.get("/api/risk-scores")
@admin_required
def class_risk_scores():
    """JSON API: returns risk scores for all students in a class/year."""
    from flask import jsonify
    from utils.risk_score import bulk_risk_scores
    from models import Student

    inst_id = session["institute_id"]
    year = to_int(request.args.get("year"), 0)
    cls = (request.args.get("cls") or "").strip().upper()

    q = Student.query.filter_by(institute_id=inst_id, is_active=1)
    if year:
        q = q.filter_by(year=year)
    if cls:
        q = q.filter(Student.class_name == cls)

    students = q.all()
    ids = [s.id for s in students]
    scores = bulk_risk_scores(ids)

    results = []
    for s in students:
        r = scores.get(s.id, {})
        results.append({
            "student_id": s.id,
            "name": s.name,
            "admission_no": s.admission_no,
            "year": s.year,
            **r
        })

    # Sort by score descending (highest risk first)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return jsonify(results)


# ─────────────────────────────────────────────────────
#  📱  WHATSAPP NOTIFICATIONS  (Feature #3)
# ─────────────────────────────────────────────────────

@admin_bp.post("/student/<int:student_id>/whatsapp-reminder")
@admin_required
def send_whatsapp_student(student_id):
    """Send a WhatsApp fee reminder to a single student."""
    from models import Student
    from extensions import db
    from utils.whatsapp import send_fee_due_reminder
    from utils.fees import get_fee_state_for_student

    inst_id = session["institute_id"]
    s = Student.query.filter_by(id=student_id, institute_id=inst_id).first()
    if not s:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    phone = s.parent_phone or s.student_phone
    if not phone:
        flash(f"No phone number for {s.name}.", "warning")
        return redirect(url_for("admin.student_view", student_id=student_id))

    state = get_fee_state_for_student(db, student_id)
    due = state.get("due_total", 0)

    if due <= 0:
        flash(f"{s.name} has no outstanding fees. No message sent.", "info")
        return redirect(url_for("admin.student_view", student_id=student_id))

    sid = send_fee_due_reminder(student_name=s.name, phone=phone, due_amount=due)
    if sid:
        flash(f"✅ WhatsApp reminder sent to {phone} for ₹{due:,} due.", "success")
    else:
        flash(f"⚠️ WhatsApp send failed. Check Twilio credentials in .env", "warning")

    return redirect(url_for("admin.student_view", student_id=student_id))


@admin_bp.post("/whatsapp/bulk-remind")
@admin_required
def whatsapp_bulk_remind():
    """Send WhatsApp reminders to ALL students with outstanding dues."""
    from models import Student
    from utils.whatsapp import send_bulk_reminders

    inst_id = session["institute_id"]
    students = Student.query.filter_by(institute_id=inst_id, is_active=1).all()
    ids = [s.id for s in students]

    results = send_bulk_reminders(ids)
    flash(
        f"📱 WhatsApp Bulk Send: ✅ {results['sent']} sent, "
        f"⚠️ {results['failed']} failed, ⏭️ {results['skipped']} skipped (no dues/phone).",
        "success" if results['sent'] > 0 else "warning"
    )
    return redirect(url_for("admin.reports"))
