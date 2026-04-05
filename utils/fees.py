# utils/fees.py
from __future__ import annotations
from datetime import date, datetime
from typing import Dict, Any, Tuple
from flask import current_app
from utils.helpers import to_int
from extensions import cache

def _norm(s: str) -> str:
    return (s or "").strip().upper()

def _days_overdue(due_date_str: str) -> int:
    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (today - due).days
        return max(0, delta)
    except:
        return 0

def check_and_apply_late_fees(db, student_id: int):
    from models import Student, FeePlan, FeeInstallment, Payment, FeeAdjustment
    from extensions import db as _db
    from sqlalchemy import func

    s = Student.query.get(student_id)
    if not s:
        return

    insts = FeeInstallment.query.filter_by(
        institute_id=s.institute_id, course=s.course, year=s.year
    ).order_by(FeeInstallment.due_date.asc()).all()
    if not insts:
        return

    plan = FeePlan.query.filter_by(
        institute_id=s.institute_id, course=s.course, year=s.year
    ).first()
    base_total = (to_int(plan.tuition, 0) + to_int(plan.other, 0)) if plan else 0

    paid_result = _db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.student_id == student_id,
        Payment.status == "SUCCESS",
        Payment.category.notin_(["FINE", "HOSTEL", "BUS", "GYM", "LAUNDRY"])
    ).scalar()
    total_paid_base = paid_result or 0

    cum_due = 0
    for i in insts:
        amount = int(base_total * (i.percentage / 100))
        cum_due += amount
        days = _days_overdue(i.due_date)
        if days > 0:
            deficit = cum_due - total_paid_base
            if deficit > 0:
                fine_amt = days * i.late_fee_per_day
                if fine_amt > 0:
                    label = f"Late Fee - {i.label}"
                    _upsert_fine(db, student_id, label, fine_amt)

def _upsert_fine(db, student_id, label, amount):
    from models import FeeAdjustment
    from extensions import db as _db
    row = FeeAdjustment.query.filter_by(
        student_id=student_id, category="FINE", label=label
    ).first()
    if row:
        row.amount = amount
    else:
        _db.session.add(FeeAdjustment(
            student_id=student_id, category="FINE", label=label, amount=amount
        ))
    _db.session.commit()


def _is_75(quota_type: str) -> bool:
    qt = _norm(quota_type)
    return qt in {"7.5 RESERVATION", "7.5", "7.5%", "7_5", "75RES", "RES7_5"}

def _sum_payments(db, student_id: int) -> Dict[str, int]:
    from models import Payment
    from sqlalchemy import func
    from extensions import db as _db
    rows = _db.session.query(
        Payment.category,
        func.coalesce(func.sum(Payment.amount), 0).label("total")
    ).filter_by(student_id=student_id, status="SUCCESS").group_by(Payment.category).all()
    return {_norm(r.category): to_int(r.total, 0) for r in rows}

def _get_plan(db, institute_id: str, course: str, year: int) -> Dict[str, int]:
    from models import FeePlan
    row = FeePlan.query.filter_by(institute_id=institute_id, course=course, year=year).first()
    if not row:
        return {"tuition": 1, "other": 1, "hostel": 50000, "exam": 0}
    return {
        "tuition": max(0, to_int(row.tuition, 0)),
        "other": max(0, to_int(row.other, 0)),
        "hostel": max(0, to_int(row.hostel, 50000)),
        "exam": max(0, to_int(row.exam, 0)),
    }

def _get_adjustments(db, student_id: int) -> Dict[str, int]:
    from models import FeeAdjustment
    rows = FeeAdjustment.query.filter_by(student_id=student_id).all()

    adj = {
        "HOSTEL": 0, "BUS": 0, "GYM": 0, "LAUNDRY": 0, "EXAM": 0, "FINE": 0,
        "DISC_SCHOLARSHIP": 0, "DISC_QUOTA": 0, "DISC_FIRST_GRAD": 0,
    }

    for r in rows:
        cat = _norm(r.category)
        label = (r.label or "").strip()
        amt = to_int(r.amount, 0)

        if cat == "HOSTEL" and label == "Hostel Fee":
            adj["HOSTEL"] += max(0, amt)
        elif cat == "BUS" and label == "Bus Fee":
            adj["BUS"] += max(0, amt)
        elif cat == "GYM" and label == "Gym Fee":
            adj["GYM"] += max(0, amt)
        elif cat == "LAUNDRY" and label == "Laundry Fee":
            adj["LAUNDRY"] += max(0, amt)
        elif cat == "EXAM" and label == "Exam Fee":
            adj["EXAM"] += max(0, amt)
        elif cat == "FINE":
            adj["FINE"] += max(0, amt)
        elif cat == "DISCOUNT":
            if label == "Scholarship":
                adj["DISC_SCHOLARSHIP"] += abs(amt) if amt < 0 else 0
            elif label == "Quota":
                adj["DISC_QUOTA"] += abs(amt) if amt < 0 else 0
            elif label == "First Graduate":
                adj["DISC_FIRST_GRAD"] += abs(amt) if amt < 0 else 0

    return adj

def _pick_benefit_mode(
    quota_type: str,
    is_first_grad: int,
    scholarship_amount: int,
    quota_amount: int,
) -> Tuple[str, int, int, int]:
    if _is_75(quota_type):
        return "7.5", 0, 0, 0
    if to_int(is_first_grad, 0) == 1:
        return "FIRST_GRAD", 1, 0, 0
    if to_int(scholarship_amount, 0) > 0:
        return "SCHOLARSHIP", 0, max(0, to_int(scholarship_amount, 0)), 0
    if to_int(quota_amount, 0) > 0:
        return "QUOTA", 0, 0, max(0, to_int(quota_amount, 0))
    return "NONE", 0, 0, 0

def _apply_discount(
    tuition_base: int,
    hostel_base: int,
    mode: str,
    scholarship_amount: int,
    quota_amount: int,
) -> Tuple[int, int, Dict[str, Any]]:
    tuition = max(0, tuition_base)
    hostel = max(0, hostel_base)

    applied: Dict[str, Any] = {
        "mode": mode,
        "tuition_discount": 0,
        "hostel_discount": 0,
        "requested": {
            "scholarship_amount": scholarship_amount,
            "quota_amount": quota_amount,
        },
    }

    if mode == "7.5":
        applied["tuition_discount"] = tuition
        applied["hostel_discount"] = hostel
        return 0, 0, applied

    if mode == "FIRST_GRAD":
        d = min(tuition, current_app.config.get("FIRST_GRAD_DISCOUNT", 25000))
        applied["tuition_discount"] = d
        return tuition - d, hostel, applied

    if mode == "SCHOLARSHIP":
        pool = max(0, scholarship_amount)
        dt = min(tuition, pool)
        tuition -= dt
        pool -= dt
        applied["tuition_discount"] = dt

        if pool > 0 and tuition == 0:
            dh = min(hostel, pool)
            hostel -= dh
            pool -= dh
            applied["hostel_discount"] = dh

        applied["unused_amount"] = pool
        return tuition, hostel, applied

    if mode == "QUOTA":
        d = min(tuition, max(0, quota_amount))
        applied["tuition_discount"] = d
        return tuition - d, hostel, applied

    return tuition, hostel, applied

def _get_installments_raw(db, institute_id, course, year):
    from models import FeeInstallment
    rows = FeeInstallment.query.filter_by(
        institute_id=institute_id, course=course, year=year
    ).order_by(FeeInstallment.due_date.asc()).all()

    if not rows:
        y = date.today().year
        return [
            {"label": "Semester 1", "due_date": f"{y}-06-10", "percentage": 50},
            {"label": "Semester 2", "due_date": f"{y}-12-10", "percentage": 50},
        ]
    return [{"label": r.label, "due_date": r.due_date, "percentage": r.percentage} for r in rows]

def _get_installments_info(db, institute_id, course, year, total_plan_amount, total_paid):
    """
    Returns (current_due_amount, installments_list)
    installments_list = [{label, due_date, amount, status, is_overdue}]
    """
    rows = _get_installments_raw(db, institute_id, course, year)

    installments = []
    accumulated_due = 0
    current_due = 0
    
    # We can't easily attribute 'paid' to specific installments because payments are category-based.
    # So we use a "waterfall" approach: Total Paid fills buckets from earliest to latest.
    
    # NOTE: installment percentages apply to PLAN BASE (Tuition+Other). 
    # Extra charges (Fine, Gym) are usually "due immediately" or handled separately.
    # For simplicity, we assume Installments cover 'Tuition' primarily.
    # But 'total_plan_amount' passed in is Tuition+Other.
    
    remaining_paid = total_paid
    
    
    today = date.today()

    for r in rows:
        amt = int(total_plan_amount * (r["percentage"] / 100))
        due_dt = datetime.strptime(r["due_date"], "%Y-%m-%d").date()
        is_past = due_dt <= today
        
        status = "PENDING"


        this_paid = 0
        
        if remaining_paid >= amt:
            this_paid = amt
            remaining_paid -= amt
            status = "PAID"
        else:
            this_paid = remaining_paid
            remaining_paid = 0
            if is_past:
                status = "OVERDUE"
            else:
                status = "DUE_FUTURE"
                
        # If it's past due, the unpaid portion adds to 'current_due'
        if is_past and status != "PAID":
            current_due += (amt - this_paid)

        installments.append({
            "label": r["label"],
            "due_date": r["due_date"],
            "amount": amt,
            "paid": this_paid,
            "outstanding": amt - this_paid,
            "status": status,
            "is_past": is_past,
            "locked": (status == "PAID"),
        })
        
    return current_due, installments


@cache.memoize(timeout=3600)
def _cached_fee_state(student_id: int) -> Dict[str, Any]:
    from extensions import db as _db
    return _get_fee_state_internal(_db, student_id)

def get_fee_state_for_student(db, student_id: int) -> Dict[str, Any]:
    """Public API — db arg kept for backward compatibility but ORM db is used internally."""
    return _cached_fee_state(student_id)

def clear_fee_cache_for_student(student_id: int):
    cache.delete_memoized(_cached_fee_state, student_id)

def _get_fee_state_internal(db, student_id: int) -> Dict[str, Any]:
    from models import Student
    s = Student.query.get(student_id)

    if not s:
        return {
            "ok": False, "error": "Student not found",
            "net_total": 0, "paid_total": 0, "due_total": 0,
            "charges": {}, "paid": {}, "due": {},
            "category_total": {}, "category_due": {}, "applied": {},
        }

    institute_id = s.institute_id
    course = s.course
    year = to_int(s.year, 0)
    is_hosteller = to_int(s.is_hosteller, 0)

    sem_a_idx = (year - 1) * 2 + 1
    sem_b_idx = sem_a_idx + 1
    hostel_sem_a = to_int(getattr(s, f"hostel_sem{sem_a_idx}", 0), 0)
    hostel_sem_b = to_int(getattr(s, f"hostel_sem{sem_b_idx}", 0), 0)
    quota_type = s.quota_type or ""
    is_first_grad_flag = to_int(s.is_first_graduate, 0)
    admission_fee_base = to_int(s.admission_fee, 0)

    # ✅ Auto-apply late fees before calc
    check_and_apply_late_fees(db, student_id)

    plan = _get_plan(db, institute_id, course, year)
    tuition_base = plan["tuition"]
    other_base = plan["other"]
    exam_base = plan["exam"]

    adj = _get_adjustments(db, student_id)
    
    # NEW: Fetch Common Fees for the whole Institute
    from models import CommonFee
    comm_rows = CommonFee.query.filter_by(institute_id=institute_id).all()
    common_fees_total = sum(to_int(cf.amount, 0) for cf in comm_rows)

    # Standard Hostel Fee from Plan (split by semester)
    hostel_plan_total = plan.get("hostel", 50000)
    hostel_base = 0
    if hostel_sem_a == 1:
        hostel_base += (hostel_plan_total // 2)
    if hostel_sem_b == 1:
        hostel_base += (hostel_plan_total // 2) 
    # Or should plan fee be the total? User said "the hostel fees 50000".
    # I'll add the adjustment on top if it exists, but the primary is now the plan.
    hostel_base += adj["HOSTEL"] 
    
    bus_base = adj["BUS"] if is_hosteller == 0 else 0

    scholarship_amount = adj["DISC_SCHOLARSHIP"]
    quota_amount = adj["DISC_QUOTA"]

    mode, _, scholarship_amount, quota_amount = _pick_benefit_mode(
        quota_type=quota_type,
        is_first_grad=is_first_grad_flag,
        scholarship_amount=scholarship_amount,
        quota_amount=quota_amount,
    )

    tuition_after, hostel_after, applied = _apply_discount(
        tuition_base=tuition_base,
        hostel_base=hostel_base,
        mode=mode,
        scholarship_amount=scholarship_amount,
        quota_amount=quota_amount,
    )

    charges = {
        "TUITION": tuition_after,
        "OTHER": other_base,
        "HOSTEL": hostel_after,
        "BUS": bus_base,
        "GYM": adj["GYM"] if is_hosteller == 1 else 0,
        "LAUNDRY": adj["LAUNDRY"] if is_hosteller == 1 else 0,
        "EXAM": exam_base + adj["EXAM"],
        "FINE": adj["FINE"],
        "COMMON": common_fees_total, # For internal tracking
        "ADMISSION": admission_fee_base,
    }
    
    # Apply Common Fees to 'OTHER' for payment purposes
    charges["OTHER"] += common_fees_total

    paid = _sum_payments(db, student_id)

    due: Dict[str, int] = {}
    for cat, amt in charges.items():
        pamt = paid.get(cat, 0)
        due[cat] = max(0, to_int(amt, 0) - to_int(pamt, 0))

    # ✅ Define Core Fees (allowed in total)
    # Tuition, Hostel, Bus are always included.
    # "OTHER" is included ONLY if year == 1 (Admission Fees).
    # All else (Gym, Laundry, Exam, Fine) are excluded from Total.
    
    net_total = 0
    paid_total = 0
    due_total = 0
    
    for cat, amt in charges.items():
        pamt = paid.get(cat, 0)
        damt = due.get(cat, 0)
        
        # Unified total: Include ALL categories
        net_total += to_int(amt, 0)
        paid_total += to_int(pamt, 0)
        due_total += to_int(damt, 0)

    # --- Installment Logic ---
    # We track how much of the "Plan Base" (Tuition+Other) is strictly due NOW.
    # Other fees (Hostel, Bus, Fines) are always due immediately if charged.
    
    plan_base_total = tuition_base + other_base
    plan_paid = paid.get("TUITION", 0) + paid.get("OTHER", 0) # approximation

    inst_current_due_plan, installments = _get_installments_info(
        db, institute_id, course, year, plan_base_total, plan_paid
    )
    
    current_due_total = 0
    
    if inst_current_due_plan is None:
        # No installments -> Full due is current due
        current_due_total = due_total
    else:
        # Installments exist.
        # Current Due = (Plan Overdue via Installments) + (Non-Plan Dues)
        # Non-Plan Dues = Total Due - (Tuition Due + Other Due)
        # Wait, easier:
        # Calculate 'installments due' (tuition/other part).
        # Add 'immediate dues' (Hostel, Bus, Fine, Gym, etc).
        
        non_plan_categories = set(charges.keys()) - {"TUITION", "OTHER"}
        non_plan_due = sum(due.get(c, 0) for c in non_plan_categories)
        
        current_due_total = inst_current_due_plan + non_plan_due
        
        # Priority: Ensure Admission fee is always part of current due if not paid
        if due.get("ADMISSION", 0) > 0:
            current_due_total = max(current_due_total, due["ADMISSION"])

    # Ensure we don't say Current Due > Total Due (sanity check)
    current_due_total = min(current_due_total, due_total)


    # ✅ Backward compatible keys your routes/templates expect
    return {
        "ok": True,
        "plan": {
            "tuition": tuition_base,
            "other": other_base,
            "hostel": plan.get("hostel", 50000),
            "exam": exam_base,
            "base_total": tuition_base + other_base,
        },
        "charges": charges,
        "paid": {k: paid.get(k, 0) for k in charges.keys()},
        "due": due,
        "category_total": charges,   # ✅ IMPORTANT
        "category_due": due,         # ✅ IMPORTANT
        "net_total": net_total,
        "paid_total": paid_total,
        "due_total": due_total,
        
        # New Validated Fields
        "current_due_total": current_due_total,
        "installments": installments,
        
        "applied": applied,
    }


def get_full_course_fee_state(db, student_id: int) -> Dict[str, Any]:
    """
    Returns a unified view of ALL 4 YEARS for the student's course.
    db arg kept for backward compat; always uses SQLAlchemy ORM internally.
    """
    from models import Student, FeePlan, Payment
    from sqlalchemy import func
    from extensions import db as _db

    s = Student.query.get(student_id)
    if not s:
        return {"ok": False, "error": "Student not found"}

    institute_id = s.institute_id
    course = s.course
    current_year = to_int(s.year, 0)
    admission_fee_base = to_int(s.admission_fee, 0)

    all_payments = _db.session.query(
        Payment.category,
        func.coalesce(func.sum(Payment.amount), 0).label("total")
    ).filter_by(student_id=student_id, status="SUCCESS").group_by(Payment.category).all()

    paid_map = {r.category: r.total for r in all_payments}

    total_plan_paid = paid_map.get("TUITION", 0) + paid_map.get("OTHER", 0)
    remaining_paid = total_plan_paid
    remaining_hostel_paid = paid_map.get("HOSTEL", 0)
    remaining_bus_paid = paid_map.get("BUS", 0)
    
    adj = _get_adjustments(db, student_id)
    benefit_mode, _, ben_sch_amt, ben_quota_amt = _pick_benefit_mode(
        quota_type=s.quota_type or "",
        is_first_grad=to_int(s.is_first_graduate, 0),
        scholarship_amount=adj["DISC_SCHOLARSHIP"],
        quota_amount=adj["DISC_QUOTA"],
    )
    
    years_data = []
    grand_total_plan = 0
    grand_total_paid_plan = 0
    grand_total_due_plan = 0

    # 2. Iterate Years 1..4
    previous_year_cleared = True # Year 1 is always unlocked

    for yr in range(1, 5):
        plan_orm = FeePlan.query.filter_by(institute_id=institute_id, course=course, year=yr).first()

        if not plan_orm:
            years_data.append({
                "year": yr, "active": False, "msg": "Fee plan not defined",
                "is_locked": not previous_year_cleared, "total": 0,
                "paid": 0, "due": 0, "status": "UNPAID",
                "fee_items": [], "semesters": [], "is_current": (yr == current_year)
            })
            previous_year_cleared = False
            continue

        plan = {"tuition": plan_orm.tuition, "other": plan_orm.other,
                "hostel": plan_orm.hostel, "exam": plan_orm.exam}

        tuition = to_int(plan["tuition"], 0)
        other = to_int(plan["other"], 0)
        
        # --- Discount Logic (same as before) ---
        tuition_base, hostel_plan_total, _ = _apply_discount(
            tuition_base=tuition,
            hostel_base=to_int(plan["hostel"], 50000),
            mode=benefit_mode,
            scholarship_amount=ben_sch_amt,
            quota_amount=ben_quota_amt,
        )

        exam_amt = to_int(plan["exam"], 0)
        plan_total = tuition_base + other + exam_amt
        
        # --- Installments ---
        inst_rows = _get_installments_raw(db, institute_id, course, yr)

        # --- Waterfall for PLAN Categories (Tuition+Other) ---
        this_year_plan_paid = 0
        if remaining_paid >= plan_total:
            this_year_plan_paid = plan_total
            remaining_paid -= plan_total
        else:
            this_year_plan_paid = remaining_paid
            remaining_paid = 0

        # --- Semester Items ---
        items = [] # Combined list of Semesters + (Hostel/Bus if current year)
        
        # Local waterfall for semesters
        sem_paid_pool = this_year_plan_paid
        
        for r in inst_rows:
            s_amt = int(plan_total * (r["percentage"] / 100))
            s_paid = 0
            if sem_paid_pool >= s_amt:
                s_paid = s_amt
                sem_paid_pool -= s_amt
                s_status = "PAID"
            elif sem_paid_pool > 0:
                s_paid = sem_paid_pool
                sem_paid_pool = 0
                s_status = "PARTIAL"
            else:
                s_paid = 0
                s_status = "UNPAID"
                
            items.append({
                "type": "SEMESTER",
                "label": r["label"],
                "amount": s_amt,
                "paid": s_paid,
                "status": s_status,
                "locked": (s_status == "PAID"),
                "category": "TUITION" # Map semesters to TUITION for payment
            })
            
        # (Synthesized semesters from _get_installments_raw now handle the display)

        # --- ADD HOSTEL/BUS (Apply Hostel fee to both semesters if active) ---
        # Hostel fee from plan
        # hostel_plan_total is already calculated above including discounts
        # 8-Semester Hostel: use the two semesters for this year
        yr_sem_a = (yr - 1) * 2 + 1
        yr_sem_b = yr_sem_a + 1
        hostel_sem_a_val = to_int(getattr(s, f"hostel_sem{yr_sem_a}", 0), 0)
        hostel_sem_b_val = to_int(getattr(s, f"hostel_sem{yr_sem_b}", 0), 0)
        hostel_plan_amt = 0
        if hostel_sem_a_val == 1: hostel_plan_amt += (hostel_plan_total // 2)
        if hostel_sem_b_val == 1: hostel_plan_amt += (hostel_plan_total // 2)
        
        # Assumption: Bus fees and extra adjustments apply primarily to the CURRENT active year.
        is_current = (yr == current_year)
        
        # Total fee for this year starts with plan (Tuition + Other)
        year_total_fee = plan_total
        year_total_paid = this_year_plan_paid
        
        # Add Hostel Fee from Plan (with Waterfall distribution)
        if hostel_plan_amt > 0:
            # Waterfall for hostel
            if remaining_hostel_paid >= hostel_plan_amt:
                 this_year_h_paid = hostel_plan_amt
                 remaining_hostel_paid -= hostel_plan_amt
            else:
                 this_year_h_paid = remaining_hostel_paid
                 remaining_hostel_paid = 0
            
            if inst_rows:
                num_inst = len(inst_rows)
                base_split = hostel_plan_amt // num_inst
                remainder = hostel_plan_amt % num_inst
                
                current_paid_pool = this_year_h_paid
                
                for idx, r in enumerate(inst_rows):
                    this_amt = base_split + (remainder if idx == num_inst - 1 else 0)
                    this_paid = 0
                    if current_paid_pool >= this_amt:
                        this_paid = this_amt
                        current_paid_pool -= this_amt
                    else:
                        this_paid = current_paid_pool
                        current_paid_pool = 0
                    
                    h_status = "PAID" if this_paid >= this_amt else "UNPAID"
                    items.append({
                        "type": "EXTRA",
                        "label": f"Hostel Fee - {r['label']}",
                        "amount": this_amt,
                        "paid": this_paid,
                        "status": h_status,
                        "locked": (h_status == "PAID"),
                        "category": "HOSTEL"
                    })
            else:
                 h_status = "PAID" if this_year_h_paid >= hostel_plan_amt else "UNPAID"
                 items.append({
                     "type": "EXTRA",
                     "label": "Hostel Fee",
                     "amount": hostel_plan_amt,
                     "paid": this_year_h_paid,
                     "status": h_status,
                     "locked": (h_status == "PAID"),
                     "category": "HOSTEL"
                 })
            year_total_fee += hostel_plan_amt
            year_total_paid += this_year_h_paid

        # --- ADD ADMISSION FEE (if Year 1) ---
        if yr == 1 and admission_fee_base > 0:
            a_paid = paid_map.get("ADMISSION", 0)
            a_status = "PAID" if a_paid >= admission_fee_base else ("PARTIAL" if a_paid > 0 else "UNPAID")
            items.insert(0, { # Insert at TOP
                "type": "EXTRA",
                "label": "Admission Fee",
                "amount": admission_fee_base,
                "paid": a_paid,
                "status": a_status,
                "locked": (a_status == "PAID"),
                "category": "ADMISSION"
            })
            year_total_fee += admission_fee_base
            year_total_paid += a_paid

        if is_current:
            adj = _get_adjustments(db, student_id)
            if to_int(s.is_hosteller, 0) == 0:
                 b_amt = adj.get("BUS", 0)
                 if b_amt > 0:
                     b_paid_total = remaining_bus_paid
                     remaining_bus_paid = 0 # Currently all to this year
                     
                     if inst_rows:
                         num_inst = len(inst_rows)
                         base_split = b_amt // num_inst
                         remainder = b_amt % num_inst
                         
                         current_paid_pool = b_paid_total
                         
                         for idx, r in enumerate(inst_rows):
                             this_amt = base_split + (remainder if idx == num_inst - 1 else 0)
                             
                             this_paid = 0
                             if current_paid_pool >= this_amt:
                                 this_paid = this_amt
                                 current_paid_pool -= this_amt
                             else:
                                 this_paid = current_paid_pool
                                 current_paid_pool = 0
                                 
                             b_status = "PAID" if this_paid >= this_amt else "UNPAID"
                             
                             items.append({
                                 "type": "EXTRA",
                                 "label": f"Bus Fee - {r['label']}",
                                 "amount": this_amt,
                                 "paid": this_paid,
                                 "status": b_status,
                                 "locked": (b_status == "PAID"),
                                 "category": "BUS"
                             })
                         year_total_fee += b_amt
                         year_total_paid += b_paid_total
                     else:
                         b_status = "PAID" if b_paid_total >= b_amt else "UNPAID"
                         items.append({
                             "type": "EXTRA",
                             "label": "Bus Fee",
                             "amount": b_amt,
                             "paid": b_paid_total,
                             "status": b_status,
                             "locked": (b_status == "PAID"),
                             "category": "BUS"
                         })
                         year_total_fee += b_amt
                         year_total_paid += b_paid_total

        # --- Locking Calculation ---
        # Unlocked ONLY if previous year was fully cleared.
        is_locked_for_user = not previous_year_cleared
        
        # Calculate Due for THIS year
        year_due = year_total_fee - year_total_paid
        
        # Determine strict clearance for NEXT year
        # (Must pay ALL fees of this year to unlock next)
        previous_year_cleared = (year_due <= 0)

        # Status Label
        if year_due == 0:
            status = "PAID"
        elif year_due < year_total_fee:
            status = "PARTIAL"
        else:
            status = "UNPAID"

        years_data.append({
            "year": yr,
            "active": True,
            "total": year_total_fee,
            "paid": year_total_paid,
            "due": year_due,
            "status": status,
            "is_locked": is_locked_for_user,
            "semesters": items, 
            "fee_items": items,     # Renamed to avoid dict.items conflict
            "is_current": is_current
        })
        
        # Add to Grand Totals (Plan only? Or Everything?)
        # For "Pay All 4 Years", we usually mean Tuition/Plan.
        # Hostel/Bus is separate.
        # Let's keep grand_total_* for the Plan (Tuition) to drive the "Advance" logic.
        grand_total_plan += plan_total
        grand_total_paid_plan += this_year_plan_paid
        grand_total_due_plan += (plan_total - this_year_plan_paid)

    return {
        "ok": True,
        "years": years_data,
        "grand_total_plan": grand_total_plan,
        "grand_total_paid": grand_total_paid_plan,
        "grand_total_due": grand_total_due_plan
    }

