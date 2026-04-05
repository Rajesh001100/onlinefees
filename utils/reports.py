
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def generate_daily_collection_pdf(db, institute_id: str, date_str: str) -> bytes:
    """
    Generates a PDF report of payments for a specific date.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Title
    elements.append(Paragraph(f"Daily Collection Report - {date_str}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Fetch Data
    rows = db.execute(
        """
        SELECT p.txn_id, s.admission_no, s.name, p.category, p.amount, p.method
        FROM payments p
        JOIN students s ON p.student_id = s.id
        WHERE s.institute_id=? AND date(p.created_at) = date(?) AND p.status='SUCCESS'
        ORDER BY p.id DESC
        """,
        (institute_id, date_str)
    ).fetchall()
    
    if not rows:
        elements.append(Paragraph("No collections found for this date.", styles['Normal']))
    else:
        # Table Header
        data = [["Txn ID", "Admission No", "Student", "Category", "Amount", "Method"]]
        total = 0
        
        for r in rows:
            data.append([
                r["txn_id"][-8:], # Shorten
                r["admission_no"],
                r["name"][:20],
                r["category"],
                f"{r['amount']:,}",
                r["method"]
            ])
            total += r["amount"]
            
        # Total Row
        data.append(["", "", "", "TOTAL", f"{total:,}", ""])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey), # Total row
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        
    doc.build(elements)
    buffer.seek(0)
    return buffer.read()

def generate_dues_csv(db, institute_id: str) -> str:
    """
    Generates CSV string of students with outstanding dues.
    Uses fees.get_fee_state_for_student (can be slow for many students, optimization needed for big data)
    """
    from utils.fees import get_fee_state_for_student
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Admission No", "Name", "Class", "Total Due", "Mobile"])
    
    # Get all active students
    students = db.execute(
        "SELECT id, admission_no, name, class, student_phone FROM students WHERE institute_id=? AND is_active=1",
        (institute_id,)
    ).fetchall()
    
    for s in students:
        state = get_fee_state_for_student(db, s["id"])
        due = state.get("due_total", 0)
        
        if due > 0:
            writer.writerow([
                s["admission_no"],
                s["name"],
                s["class"],
                due,
                s["student_phone"]
            ])
            
    return output.getvalue()


def generate_dues_excel(db, institute_id=None) -> io.BytesIO:
    """
    Generates an Excel spreadsheet of students with outstanding dues.
    If institute_id is None, generates for all institutes (Founder).
    """
    from utils.fees import get_fee_state_for_student
    import pandas as pd
    
    where = "is_active=1"
    params = []
    if institute_id:
        where += " AND institute_id=?"
        params.append(institute_id)
        
    students = db.execute(
        f"SELECT id, institute_id, admission_no, name, course, year, class, student_phone FROM students WHERE {where}",
        params
    ).fetchall()
    
    data = []
    
    for s in students:
        state = get_fee_state_for_student(db, s["id"])
        due = state.get("due_total", 0)
        
        if due > 0:
            data.append({
                "Institute": s["institute_id"],
                "Student ID": s["admission_no"],
                "Name": s["name"],
                "Course": s["course"],
                "Year": s["year"],
                "Class": s["class"],
                "Plan Total (Rs)": state.get("net_total", 0),
                "Paid Total (Rs)": state.get("paid_total", 0),
                "Outstanding Balance (Rs)": due,
                "Mobile Phone": s["student_phone"] or "N/A"
            })
            
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Institute", "Student ID", "Name", "Course", "Year", "Class",
            "Plan Total (Rs)", "Paid Total (Rs)", "Outstanding Balance (Rs)", "Mobile Phone"
        ])
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Outstanding Dues")
        # Auto-adjust column widths
        worksheet = writer.sheets["Outstanding Dues"]
        for idx, col in enumerate(df.columns):
            worksheet.column_dimensions[chr(65 + idx)].width = max(len(col) + 2, 12)
            
    output.seek(0)
    return output
