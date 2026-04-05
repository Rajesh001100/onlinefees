
import sqlite3
from datetime import date, datetime

def _get_installments_info(total_plan_amount, total_paid):
    rows = [{"label": "Inst 1", "due_date": "2026-03-20", "percentage": 50}]
    
    installments = []
    current_due = 0
    remaining_paid = total_paid
    today = date.today()
    
    print(f"DEBUG: Plan={total_plan_amount}, Paid={total_paid}")

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
                
        if is_past and status != "PAID":
            current_due += (amt - this_paid)
            
        print(f"Row {r['label']} Amt {amt} Status {status} CurrentDue {current_due}")

    return current_due

if __name__ == "__main__":
    _get_installments_info(33000, 0)
