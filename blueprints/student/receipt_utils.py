from io import BytesIO
from datetime import datetime
import os
from flask import current_app, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import qrcode
from reportlab.lib.utils import ImageReader


# ── Brand Colours ──────────────────────────────────────────────
BLUE_DARK   = (0.067, 0.251, 0.502)   # #114080
BLUE_MID    = (0.098, 0.376, 0.722)   # #196090 (approx)
BLUE_LIGHT  = (0.851, 0.918, 0.973)   # #D9EAF8
BLUE_HEADER = (0.039, 0.216, 0.447)   # #0A3772
WHITE       = (1, 1, 1)
GREY_TEXT   = (0.35, 0.35, 0.35)
GREY_LINE   = (0.75, 0.80, 0.88)
GOLD        = (0.718, 0.576, 0.102)   # accent line
# ───────────────────────────────────────────────────────────────


def _set_fill(c, rgb):
    c.setFillColorRGB(*rgb)


def _set_stroke(c, rgb):
    c.setStrokeColorRGB(*rgb)


def _get_base_url() -> str:
    try:
        return request.host_url.rstrip("/")
    except RuntimeError:
        return current_app.config.get("BASE_URL", "http://localhost:5000")


def build_receipt_pdf_bytes(student, inst, payment, receipt_no: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Normalise inputs
    if student and not isinstance(student, dict):
        student = dict(student)
    if inst and not isinstance(inst, dict):
        inst = dict(inst)
    if payment and not isinstance(payment, dict):
        payment = dict(payment)

    LM = 18 * mm          # left margin
    RM = width - 18 * mm  # right margin
    CX = width / 2.0      # centre X
    y  = height           # drawing cursor (top-down)

    # ── 1. TOP HEADER BAND ──────────────────────────────────────
    header_h = 38 * mm
    _set_fill(c, BLUE_DARK)
    c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)

    # Gold accent strip at very top
    _set_fill(c, GOLD)
    c.rect(0, height - 2.5 * mm, width, 2.5 * mm, fill=1, stroke=0)

    # Logo
    try:
        logo_path = os.path.join(current_app.root_path, "static", "brand", "jkkm.png")
        if os.path.exists(logo_path):
            c.drawImage(
                logo_path,
                LM, height - header_h + 5 * mm,
                width=26 * mm, height=26 * mm,
                mask="auto", preserveAspectRatio=True,
            )
    except Exception as e:
        print(f"Logo load error: {e}")

    # College Name & Address (white text)
    _set_fill(c, WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(CX + 8 * mm, height - 13 * mm,
                        inst.get("full_name", "JKK Munirajah College of Technology"))

    c.setFont("Helvetica", 9)
    _set_fill(c, BLUE_LIGHT)
    c.drawCentredString(CX + 8 * mm, height - 20 * mm,
                        "T.N.Palayam, Gobi Tk, Erode Dt – 638 506")
    c.drawCentredString(CX + 8 * mm, height - 25 * mm,
                        "Phone: 04285-262149  |  Email: info@jkkm.ac.in")

    # ── 2. RECEIPT TITLE BAR ────────────────────────────────────
    title_bar_y = height - header_h
    title_bar_h = 11 * mm
    _set_fill(c, BLUE_MID)
    c.rect(0, title_bar_y - title_bar_h, width, title_bar_h, fill=1, stroke=0)

    _set_fill(c, WHITE)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(CX, title_bar_y - 7.5 * mm, "◆  FEE RECEIPT  ◆")

    y = title_bar_y - title_bar_h  # cursor below title bar

    # ── 3. RECEIPT META (Receipt No / Date) ──────────────────────
    y -= 7 * mm
    _set_fill(c, BLUE_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(LM, y, f"Receipt No:")
    _set_fill(c, (0, 0, 0))
    c.setFont("Helvetica", 9)
    c.drawString(LM + 22 * mm, y, receipt_no)

    date_str = datetime.now().strftime("%d %B %Y")
    c.setFont("Helvetica-Bold", 9)
    _set_fill(c, BLUE_DARK)
    c.drawRightString(RM - 22 * mm, y, "Date:")
    c.setFont("Helvetica", 9)
    _set_fill(c, (0, 0, 0))
    c.drawRightString(RM, y, date_str)

    # Thin blue rule
    y -= 4 * mm
    _set_stroke(c, BLUE_MID)
    c.setLineWidth(0.5)
    c.line(LM, y, RM, y)

    # ── 4. STUDENT DETAILS BOX ──────────────────────────────────
    y -= 5 * mm
    box_top = y

    # Box background
    box_h = 52 * mm
    _set_fill(c, BLUE_LIGHT)
    _set_stroke(c, BLUE_MID)
    c.setLineWidth(0.8)
    c.roundRect(LM, box_top - box_h, RM - LM, box_h, 3, fill=1, stroke=1)

    # Section label band inside box
    _set_fill(c, BLUE_MID)
    c.roundRect(LM, box_top - 8 * mm, RM - LM, 8 * mm, 3, fill=1, stroke=0)
    # Clip bottom corners of label band
    _set_fill(c, BLUE_MID)
    c.rect(LM, box_top - 8 * mm, RM - LM, 4 * mm, fill=1, stroke=0)

    _set_fill(c, WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(LM + 5 * mm, box_top - 5.5 * mm, "🎓  STUDENT DETAILS")

    # Student data
    s_name    = str(student.get("name", "-"))
    s_adm     = str(student.get("admission_no", "-"))
    s_cls     = str(student.get("class") or "-")
    s_reg     = str(student.get("register_no") or "-")
    s_yr      = f"Year {student.get('year')}" if student.get("year") else "-"
    s_course  = str(student.get("course") or "-")
    s_ph      = str(student.get("student_phone") or "-")
    s_email   = str(student.get("student_email") or "-")
    s_pname   = str(student.get("parent_name") or "-")
    s_pph     = str(student.get("parent_phone") or "-")

    col1 = LM + 5 * mm
    col2 = CX + 5 * mm
    lh   = 6.5 * mm
    ry   = box_top - 13 * mm

    def _label(cx, cy, label, value):
        c.setFont("Helvetica-Bold", 8.5)
        _set_fill(c, BLUE_DARK)
        c.drawString(cx, cy, label)
        c.setFont("Helvetica", 8.5)
        _set_fill(c, (0.1, 0.1, 0.1))
        c.drawString(cx + 30 * mm, cy, value)

    _label(col1, ry,        "Student Name  :", s_name)
    _label(col2, ry,        "Admission No  :", s_adm)
    ry -= lh
    _label(col1, ry,        "Class / Branch:", s_cls)
    _label(col2, ry,        "Course        :", s_course)
    ry -= lh
    _label(col1, ry,        "Year          :", s_yr)
    _label(col2, ry,        "Register No   :", s_reg)
    ry -= lh
    _label(col1, ry,        "Phone         :", s_ph)
    _label(col2, ry,        "Email         :", s_email)
    ry -= lh
    _label(col1, ry,        "Parent Name   :", s_pname)
    _label(col2, ry,        "Parent Phone  :", s_pph)

    y = box_top - box_h - 8 * mm

    # ── 5. PAYMENT TABLE ────────────────────────────────────────
    # Prepare amount
    try:
        val   = int(payment.get("amount", 0))
        p_amt = f"{val:,.2f}"
    except Exception:
        val   = 0
        p_amt = "0.00"

    p_cat    = str(payment.get("category", "FEE")).title()
    p_method = str(payment.get("method", "CASH"))
    p_txn    = str(payment.get("txn_id", "-"))
    p_status = str(payment.get("status", "SUCCESS"))

    # Table column widths (points)
    TW = RM - LM
    col_w = [
        0.07 * TW,  # S.No
        0.28 * TW,  # Description
        0.28 * TW,  # Mode / Txn ID
        0.18 * TW,  # Status
        0.19 * TW,  # Amount
    ]

    # Header row
    hdr_h = 9 * mm
    _set_fill(c, BLUE_HEADER)
    c.rect(LM, y - hdr_h, TW, hdr_h, fill=1, stroke=0)

    headers = ["S.No", "Description", "Mode / Txn ID", "Status", "Amount (Rs.)"]
    hdr_x = LM
    for i, (hdr, cw) in enumerate(zip(headers, col_w)):
        _set_fill(c, WHITE)
        c.setFont("Helvetica-Bold", 9)
        if i == len(headers) - 1:
            c.drawRightString(hdr_x + cw - 3 * mm, y - 6 * mm, hdr)
        else:
            c.drawString(hdr_x + 3 * mm, y - 6 * mm, hdr)
        hdr_x += cw

    # Data row (alternating shade)
    row_h = 10 * mm
    row_top = y - hdr_h - row_h
    _set_fill(c, (0.96, 0.98, 1.0))
    _set_stroke(c, GREY_LINE)
    c.setLineWidth(0.5)
    c.rect(LM, row_top, TW, row_h, fill=1, stroke=1)

    row_data = ["1", f"{p_cat} Fee", f"{p_method} / {p_txn}", p_status, p_amt]
    rx = LM
    for i, (cell, cw) in enumerate(zip(row_data, col_w)):
        _set_fill(c, (0.05, 0.05, 0.05))
        c.setFont("Helvetica", 8.5)
        if i == len(row_data) - 1:
            # Amount – right-aligned, green if success
            _set_fill(c, (0.05, 0.5, 0.05))
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(rx + cw - 3 * mm, row_top + 3.5 * mm, cell)
        elif i == 3:
            # Status badge colour
            if p_status == "SUCCESS":
                _set_fill(c, (0.05, 0.5, 0.05))
            elif p_status == "FAILED":
                _set_fill(c, (0.8, 0.1, 0.1))
            else:
                _set_fill(c, BLUE_MID)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(rx + 3 * mm, row_top + 3.5 * mm, cell)
        else:
            _set_fill(c, (0.05, 0.05, 0.05))
            c.drawString(rx + 3 * mm, row_top + 3.5 * mm, cell)
        rx += cw

    # Vertical column dividers
    _set_stroke(c, GREY_LINE)
    c.setLineWidth(0.4)
    dx = LM
    for cw in col_w[:-1]:
        dx += cw
        c.line(dx, y - hdr_h, dx, row_top)

    # ── 6. TOTAL ROW ────────────────────────────────────────────
    total_y = row_top - 10 * mm
    _set_fill(c, BLUE_DARK)
    c.rect(LM, total_y, TW, 10 * mm, fill=1, stroke=0)

    _set_fill(c, BLUE_LIGHT)
    c.setFont("Helvetica", 9)
    # Amount in words placeholder
    try:
        from num2words import num2words
        words = num2words(val, lang="en_IN").title() + " Rupees Only"
    except Exception:
        words = ""
    if words:
        c.drawString(LM + 4 * mm, total_y + 3.5 * mm, f"({words})")

    _set_fill(c, WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(RM - 3 * mm, total_y + 3.5 * mm, f"Total:  Rs. {p_amt}")

    y = total_y - 10 * mm

    # ── 7. PAYMENT STATUS BADGE ─────────────────────────────────
    badge_w = 55 * mm
    badge_h = 10 * mm
    badge_x = LM
    if p_status == "SUCCESS":
        _set_fill(c, (0.067, 0.541, 0.133))
    elif p_status == "FAILED":
        _set_fill(c, (0.8, 0.1, 0.1))
    else:
        _set_fill(c, BLUE_MID)
    c.roundRect(badge_x, y - badge_h + 3 * mm, badge_w, badge_h, 4, fill=1, stroke=0)
    _set_fill(c, WHITE)
    c.setFont("Helvetica-Bold", 9)
    badge_label = f"Payment Status: {p_status}"
    c.drawCentredString(badge_x + badge_w / 2, y - badge_h + 7 * mm, badge_label)

    y -= 10 * mm

    # ── 8. FOOTER ───────────────────────────────────────────────
    footer_top = y - 8 * mm
    footer_h   = 42 * mm

    # Footer background rule
    _set_stroke(c, BLUE_LIGHT)
    c.setLineWidth(0.6)
    c.line(LM, footer_top + 2 * mm, RM, footer_top + 2 * mm)

    # QR Code
    try:
        verify_url = f"{_get_base_url()}/admin/verify-receipt/{receipt_no}"
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_pil  = qr.make_image(fill_color=f"rgb{tuple(int(v*255) for v in BLUE_DARK)}", back_color="white")
        qr_io   = BytesIO()
        qr_pil.save(qr_io, format="PNG")
        qr_io.seek(0)
        qr_img  = ImageReader(qr_io)
        qr_size = 28 * mm
        qr_x    = RM - qr_size
        qr_y    = footer_top - footer_h + 8 * mm
        c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)
        _set_fill(c, BLUE_DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(qr_x + qr_size / 2, qr_y - 4 * mm, "Scan to Verify")
    except Exception as e:
        print(f"QR Error: {e}")

    # Terms & Conditions
    _set_fill(c, BLUE_DARK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(LM, footer_top - 5 * mm, "Terms & Conditions:")
    terms = [
        "1. Fees once paid are not refundable.",
        "2. This receipt is valid subject to realisation of cheque/draft.",
        "3. Scan the QR code to verify the authenticity of this receipt.",
        "4. For disputes, contact the accounts office within 7 days.",
    ]
    c.setFont("Helvetica", 8)
    _set_fill(c, GREY_TEXT)
    for i, t in enumerate(terms):
        c.drawString(LM, footer_top - (10 + i * 5) * mm, t)

    # Authorisation
    mid_x = LM + (RM - LM) * 0.52
    _set_fill(c, BLUE_DARK)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawCentredString(mid_x, footer_top - 8 * mm, "For JKK Munirajah Institutions")

    _set_stroke(c, BLUE_MID)
    c.setLineWidth(0.5)
    sig_y = footer_top - 26 * mm
    c.line(mid_x - 25 * mm, sig_y, mid_x + 25 * mm, sig_y)

    _set_fill(c, (0.25, 0.25, 0.25))
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(mid_x, sig_y - 4 * mm, "(Authorised Signatory)")
    c.drawCentredString(mid_x, sig_y - 8 * mm, "Computer Generated Receipt — No Signature Required")

    # ── 9. BOTTOM BLUE BAR ──────────────────────────────────────
    _set_fill(c, BLUE_DARK)
    c.rect(0, 0, width, 8 * mm, fill=1, stroke=0)
    _set_fill(c, BLUE_LIGHT)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(CX, 3 * mm,
                        f"Receipt No: {receipt_no}   |   {_get_base_url()}/verify/{receipt_no}")

    # Gold strip at very bottom
    _set_fill(c, GOLD)
    c.rect(0, 0, width, 1.5 * mm, fill=1, stroke=0)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
