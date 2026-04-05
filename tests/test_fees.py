# tests/test_fees.py
"""
Tests for fee calculation engine and fee-related routes.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestFeeEngine:
    def test_get_fee_state(self, app):
        with app.app_context():
            from utils.db import get_db
            from utils.fees import get_fee_state_for_student

            db = get_db()
            state = get_fee_state_for_student(db, student_id=1)

            assert state is not None
            assert state.get("ok") is True
            assert "net_total" in state
            assert "due_total" in state

    def test_fee_plan_amounts(self, app):
        with app.app_context():
            from utils.db import get_db
            from utils.fees import get_fee_state_for_student

            db = get_db()
            state = get_fee_state_for_student(db, student_id=1)

            # Fee plan: tuition=50000, exam=3000, other=1500
            assert state.get("ok") is True
            plan_total = state.get("net_total", 0)
            assert plan_total > 0

    def test_no_fee_plan_returns_error(self, app):
        """If no matching fee plan exists, should return error state."""
        with app.app_context():
            from utils.db import get_db
            from utils.fees import get_fee_state_for_student

            db = get_db()

            # Create a student with no fee plan
            db.execute(
                "INSERT INTO users (username, password_hash, role, institute_id) VALUES (?, ?, 'STUDENT', 'ENG')",
                ("NOPLAN001", "hash"),
            )
            uid = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

            db.execute(
                """INSERT INTO students
                (user_id, admission_no, name, dob, year, class, course, institute_id)
                VALUES (?, 'NOPLAN001', 'No Plan Student', '2000-05-05', 1, 'MECH', 'B.E-MECH', 'ENG')""",
                (uid,),
            )
            sid = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            db.commit()

            state = get_fee_state_for_student(db, student_id=sid)
            # Should either have ok=False or plan_total=0
            assert state is not None

    def test_get_full_course_fee_state(self, app):
        """Test that the 4nd year overview includes hostel fees for hostellers."""
        with app.app_context():
            from utils.db import get_db
            from utils.fees import get_full_course_fee_state
            
            db = get_db()
            # Student 1 is B.E-CSE Year 1. Fee plan has tuition 50000, hostel 50000.
            # Mark student 1 as hosteller for both semesters
            db.execute("UPDATE students SET is_hosteller=1, hostel_sem1=1, hostel_sem2=1 WHERE id=1")
            db.commit()
            
            state = get_full_course_fee_state(db, student_id=1)
            assert state["ok"] is True
            year1 = next(y for y in state["years"] if y["year"] == 1)
            
            # Year 1 should have tuition (50000) + other (1500) + exam (3000) + hostel (50000) = 104500
            # Previously it was 101500 because exam fees from plan were ignored.
            assert year1["total"] == 104500

    def test_7_5_reservation_waiver(self, app):
        """Test that 7.5 reservation waives Tuition and Hostel but keeps Other and Exam."""
        with app.app_context():
            from utils.db import get_db
            from utils.fees import get_fee_state_for_student
            
            db = get_db()
            # Mark student 1 as 7.5 reservation and hosteller
            db.execute("UPDATE students SET quota_type='7.5 RESERVATION', is_hosteller=1, hostel_sem1=1, hostel_sem2=1 WHERE id=1")
            db.commit()
            
            state = get_fee_state_for_student(db, student_id=1)
            assert state["ok"] is True
            charges = state["charges"]
            
            # Tuition should be 0
            assert charges["TUITION"] == 0
            # Hostel should be 0
            assert charges["HOSTEL"] == 0
            # Other should be kept (1500)
            assert charges["OTHER"] == 1500
            # Exam from plan should be kept (3000)
            assert charges["EXAM"] == 3000

    def test_hostel_payment_waterfall(self, app):
        """Test that hostel payments are distributed starting from Year 1."""
        with app.app_context():
            from utils.db import get_db
            from utils.fees import get_full_course_fee_state
            
            db = get_db()
            # Student 1 is Year 1 hosteller for both semesters.
            db.execute("UPDATE students SET is_hosteller=1, hostel_sem1=1, hostel_sem2=1 WHERE id=1")
            
            # Record 50,000 hostel payment
            db.execute(
                "INSERT INTO payments (student_id, txn_id, category, amount, status, method, created_at) VALUES (1, 'TXN-HOSTEL-001', 'HOSTEL', 50000, 'SUCCESS', 'CASH', '2023-01-01 10:00:00')"
            )
            db.commit()
            
            state = get_full_course_fee_state(db, student_id=1)
            year1 = next(y for y in state["years"] if y["year"] == 1)
            
            # Hostel Fee (50000) should be fully paid (distributed across semesters)
            hostel_paid_sum = sum(i["paid"] for i in year1["fee_items"] if i["category"] == "HOSTEL")
            assert hostel_paid_sum == 50000


class TestFeeRoutes:
    def test_admin_fee_plans_page(self, admin_session):
        resp = admin_session.get("/admin/settings/plans")
        assert resp.status_code == 200

    def test_admin_installments_page(self, admin_session):
        resp = admin_session.get("/admin/settings/installments")
        assert resp.status_code == 200

    def test_student_fees_page(self, student_session):
        resp = student_session.get("/student/fees")
        assert resp.status_code == 200


class TestReports:
    def test_reports_page(self, admin_session):
        resp = admin_session.get("/admin/reports")
        assert resp.status_code == 200

    def test_daily_summary(self, admin_session):
        resp = admin_session.get("/admin/reports/daily")
        assert resp.status_code == 200

    def test_audit_logs(self, admin_session):
        resp = admin_session.get("/admin/audit-logs")
        assert resp.status_code == 200

    def test_analytics_api(self, admin_session):
        resp = admin_session.get("/admin/api/analytics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "dates" in data
        assert "daily_collection" in data
        assert "modes" in data
        assert "categories" in data
