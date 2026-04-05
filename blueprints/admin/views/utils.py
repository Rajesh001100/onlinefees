from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

# Constants
QUOTAS = ["REGULAR", "MGMT", "SPORTS", "NRI", "OTHER", "7.5 RESERVATION"]
ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def rget(row, key, default=None):
    """Safe getter for sqlite3.Row (no .get())."""
    if row is None:
        return default
    try:
        return row[key] if key in row.keys() else default
    except Exception:
        return default

def to_int(val, default=0):
    try:
        if val is None:
            return default
        s = str(val).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _dob_to_ddmmyyyy(dob_value) -> str:
    """
    DB dob usually: YYYY-MM-DD
    Student password convention: DDMMYYYY
    """
    if not dob_value:
        return ""
    s = str(dob_value).strip()
    
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        # YYYY-MM-DD
        return f"{s[8:10]}{s[5:7]}{s[:4]}"
        
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.strftime("%d%m%Y")
        except Exception:
            pass

    digits = _only_digits(s)
    if len(digits) == 8 and digits.startswith(("19", "20")):
        try:
            dt = datetime.strptime(digits, "%Y%m%d")
            return dt.strftime("%d%m%Y")
        except Exception:
            pass
    return digits


def _require_hash_password():
    # adjust to your project’s hashing helper
    try:
        from utils.auth import hash_password
        return hash_password
    except ImportError:
        from werkzeug.security import generate_password_hash
        return generate_password_hash

def _save_student_photo(file_storage, admission_no: str) -> str | None:
    """
    Save uploaded photo as ADMISSIONNO.ext under static/uploads/students/
    Returns stored filename or None.
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    orig = secure_filename(file_storage.filename)
    ext = Path(orig).suffix.lower()
    if ext not in ALLOWED_PHOTO_EXTS:
        raise ValueError("Invalid photo type. Allowed: jpg, jpeg, png, webp")

    filename = f"{admission_no}{ext}"
    upload_dir = Path(current_app.root_path) / "static" / "uploads" / "students"
    upload_dir.mkdir(parents=True, exist_ok=True)

    save_path = upload_dir / filename
    file_storage.save(str(save_path))
    return filename

def _is_75(quota_type: str) -> bool:
    qt = (quota_type or "").strip().upper()
    return qt in {"7.5 RESERVATION", "7.5", "7.5%", "7_5", "RES7_5", "RESERVATION7_5", "75RES"}

def _receipt_no(txn_id: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    tail = txn_id.replace("TXN-", "").replace("CASH-", "")[-6:]
    return f"RCPT-{today}-{tail}"
