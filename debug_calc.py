
from app import create_app
from utils.db import get_db
from utils.fees import get_full_course_fee_state

app = create_app()
with app.app_context():
    db = get_db()
    # Mocking what conftest does for student 15
    # Check if student exists
    s = db.execute("SELECT * FROM students WHERE id=15").fetchone()
    if s:
        print(f"Student 15: {dict(s)}")
        # Check plan
        p = db.execute("SELECT * FROM fee_plans WHERE course=? AND year=?", (s['course'], s['year'])).fetchone()
        print(f"Plan for {s['course']} Yr {s['year']}: {dict(p) if p else 'NONE'}")
        
        # Check payments
        all_p = db.execute("SELECT category, amount FROM payments WHERE student_id=15 AND status='SUCCESS'").fetchall()
        print(f"Payments for 15: {[dict(x) for x in all_p]}")

        # Call state
        state = get_full_course_fee_state(db, 15)
        print("Years in state:")
        for y in state.get("years", []):
            print(f"Year {y['year']}: Total {y.get('total')}, Paid {y.get('paid')}, Items: {[(i['category'], i['paid']) for i in y.get('items', [])]}")
    else:
        print("Student 15 not found in dev database.")

