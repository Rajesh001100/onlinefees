## Online College Fees Payment System (Flask + SQLite)

A comprehensive college fee management system for **JKK Munirajah Institutions**, supporting multiple institutes (Engineering, Agriculture, Pharmacy) with role-based access for Admin, Founder, and Student users.

---

### Features

- **Multi-Institute Support** — ENG, AGRI, PHARM with institute-scoped data
- **Role-Based Access** — Admin (per-institute), Founder (super-admin), Student
- **Fee Engine** — Complex fee calculations with scholarships, quotas, installments, late fees
- **Payment Flow** — Simulated UPI/Card/NetBanking with PDF receipt generation
- **Email Notifications** — SMTP-based receipt delivery to students and parents
- **Admin Dashboard** — Analytics charts (Chart.js), daily summaries, audit logs
- **Bulk Import** — CSV-based student upload with validation
- **Reports** — Daily collection PDF, outstanding dues CSV, analytics API

---

### Tech Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Backend   | Flask 3.0.3 (Python)              |
| Database  | SQLite (WAL mode)                 |
| Frontend  | Bootstrap 5.3.3 + Jinja2         |
| Styling   | Custom Glassmorphism CSS          |
| PDF       | ReportLab                         |
| Email     | SMTP (Gmail App Password)         |
| Charts    | Chart.js                          |
| Icons     | FontAwesome 6.4 + Google Fonts    |

---

### 1) Setup

```bash
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
MAIL_ENABLED=1
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
MAIL_FROM_NAME=Your Institution Name
MAIL_REPLY_TO=your_email@gmail.com
SMTP_TIMEOUT=20
SECRET_KEY=your-secret-key-here

# Razorpay Keys (from Razorpay Dashboard -> Test Mode/Live Mode)
RAZORPAY_KEY_ID=rzp_test_... OR rzp_live_...
RAZORPAY_KEY_SECRET=your_razorpay_secret
PAYMENT_TEST_MODE=1  # (1=Mock Success, 0=Real Payment)
```

### 3) Initialize Database + Seed Data

If you are starting fresh, run:
```bash
python database/migrations/db_init.py
```

> [!TIP]
> **Migrating Data:** If you are moving to a new laptop and want to keep your existing data (students, payments, etc.), copy the `instance/fees.db` file to the same location on the new machine.

### 4) Run the App

```bash
python app.py
```

### 5) Access

| Portal   | URL                                              |
|----------|--------------------------------------------------|
| Student  | http://127.0.0.1:5000/student/select-institute   |
| Admin    | http://127.0.0.1:5000/admin/login                |

**Default Admin Credentials:**
- `eng_admin` / `Admin@123`
- `agri_admin` / `Admin@123`
- `pharm_admin` / `Admin@123`

**Student Password Format:** DOB as `DDMMYYYY`

---

### 6) Run Tests

```bash
pytest tests/ -v
```

---

### Project Structure

```
├── app.py                  # Flask app factory + rate limiting
├── config.py               # Configuration
├── blueprints/
│   ├── admin/views/        # Admin routes (auth, dashboard, students, fees, reports)
│   └── student/            # Student routes (login, fees, payment, receipts)
├── utils/                  # Fee engine, auth, mailer, audit, bulk import
├── database/migrations/    # Schema + seed script
├── templates/              # Jinja2 templates (admin, student, shared)
├── static/                 # CSS theme, brand assets, uploads
└── tests/                  # pytest test suite
```

---

### Database Schema

The system uses **SQLite** for data storage. Key tables include:

| Table | Description |
|-------|-------------|
| `institutes` | Stores institute metadata (ENG, AGRI, PHARM). |
| `users` | Role-based credentials (Founder, Admin, Student). |
| `students` | Core profile data, quota, scholarship, and hostel status. |
| `fee_plans` | Base fee structure per course and year. |
| `payments` | Ledger of all transaction attempts and successes. |
| `receipts` | Links successful payments to generated receipt IDs. |
| `audit_logs` | Tracks all critical admin actions for transparency. |
| `fee_installments` | Stores semester-wise due dates and percentages. |

Locations:
- `database/migrations/schema.sql` (Full Schema)
- `instance/fees.db` (The Database File)
