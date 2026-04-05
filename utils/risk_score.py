# utils/risk_score.py
"""
AI-powered Fee Defaulter Risk Scoring Engine.
Uses a rule-based weighted model to classify students as:
  - HIGH RISK   (score >= 70)  🔴
  - MEDIUM RISK (score 40-69)  🟡
  - LOW RISK    (score < 40)   🟢
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Dict, Any


def _days_since(dt_str: str) -> int:
    """Return days since a date string (YYYY-MM-DD)."""
    try:
        dt = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
        return (date.today() - dt).days
    except Exception:
        return 0


def compute_risk_score(student_id: int) -> Dict[str, Any]:
    """
    Computes a risk score (0-100) for the given student.
    Higher = more likely to default.

    Returns:
        {
            "score": int,           # 0-100
            "level": str,           # "HIGH" | "MEDIUM" | "LOW"
            "badge_class": str,     # Bootstrap badge class
            "emoji": str,
            "reasons": [str],       # Human-readable reasons
            "student_id": int
        }
    """
    from models import Student, Payment, FeeAdjustment
    from extensions import db
    from sqlalchemy import func

    reasons = []
    score = 0

    s = Student.query.get(student_id)
    if not s:
        return _result(0, [], student_id)

    # ── Factor 1: Due-to-Total ratio (0-40 pts) ─────────────────────────────
    from utils.fees import get_fee_state_for_student
    fee_state = get_fee_state_for_student(db, student_id)

    net_total = fee_state.get("net_total", 0)
    due_total = fee_state.get("due_total", 0)
    paid_total = fee_state.get("paid_total", 0)

    if net_total > 0:
        due_ratio = due_total / net_total
        factor1 = int(due_ratio * 40)
        score += factor1
        if due_ratio >= 0.75:
            reasons.append(f"Over 75% of total fee unpaid (₹{due_total:,} due)")
        elif due_ratio >= 0.5:
            reasons.append(f"Over 50% of total fee unpaid (₹{due_total:,} due)")

    # ── Factor 2: No payment history (0 or 25 pts) ──────────────────────────
    total_payments = db.session.query(func.count(Payment.id)).filter_by(
        student_id=student_id, status="SUCCESS"
    ).scalar() or 0

    if total_payments == 0 and net_total > 0:
        score += 25
        reasons.append("No payment made yet")
    elif total_payments == 1:
        score += 10
        reasons.append("Only 1 payment recorded so far")

    # ── Factor 3: Last payment recency (0-15 pts) ───────────────────────────
    last_pay = Payment.query.filter_by(
        student_id=student_id, status="SUCCESS"
    ).order_by(Payment.created_at.desc()).first()

    if last_pay:
        days_ago = _days_since(last_pay.created_at)
        if days_ago > 180:
            score += 15
            reasons.append(f"Last payment was {days_ago} days ago (>6 months)")
        elif days_ago > 90:
            score += 8
            reasons.append(f"Last payment was {days_ago} days ago (>90 days)")

    # ── Factor 4: Active Outstanding Fines (0-10 pts) ───────────────────────
    fine_total = db.session.query(func.coalesce(func.sum(FeeAdjustment.amount), 0)).filter_by(
        student_id=student_id, category="FINE"
    ).scalar() or 0

    if fine_total > 0:
        fine_paid = fee_state.get("paid", {}).get("FINE", 0)
        if fine_paid < fine_total:
            score += 10
            reasons.append(f"Unpaid fines: ₹{fine_total - fine_paid:,}")

    # ── Factor 5: Senior year with high dues (0-10 pts) ─────────────────────
    if s.year >= 3 and due_total > 50000:
        score += 10
        reasons.append(f"Year {s.year} student with ₹{due_total:,} outstanding — graduation risk")

    score = min(score, 100)

    if not reasons:
        reasons.append("Good payment history")

    return _result(score, reasons, student_id)


def _result(score: int, reasons: list, student_id: int) -> Dict[str, Any]:
    if score >= 70:
        level, emoji, badge = "HIGH", "🔴", "danger"
    elif score >= 40:
        level, emoji, badge = "MEDIUM", "🟡", "warning"
    else:
        level, emoji, badge = "LOW", "🟢", "success"

    return {
        "score": score,
        "level": level,
        "emoji": emoji,
        "badge_class": badge,
        "reasons": reasons,
        "student_id": student_id,
    }


def bulk_risk_scores(student_ids: list) -> Dict[int, Dict]:
    """Returns a dict mapping student_id → risk result."""
    return {sid: compute_risk_score(sid) for sid in student_ids}
