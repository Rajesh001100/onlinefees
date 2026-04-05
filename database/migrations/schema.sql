PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS fee_installments;
DROP TABLE IF EXISTS common_fees;
DROP TABLE IF EXISTS fee_adjustments;
DROP TABLE IF EXISTS receipts;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS fee_plans;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS institutes;

-- Institutes
CREATE TABLE institutes (
  id TEXT PRIMARY KEY,                 -- ENG / AGRI / PHARM
  short_name TEXT NOT NULL,
  full_name TEXT NOT NULL
);

-- Users (Admin + Student + Founder)
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN','STUDENT','FOUNDER')),

  -- ADMIN/STUDENT must have institute_id; FOUNDER can be NULL
  institute_id TEXT NULL,

  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (institute_id) REFERENCES institutes(id)
);

CREATE INDEX IF NOT EXISTS idx_users_role_inst
ON users(role, institute_id);

-- Students
CREATE TABLE students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,

  admission_no TEXT NOT NULL UNIQUE,
  register_no TEXT,

  name TEXT NOT NULL,
  dob TEXT NOT NULL,

  year INTEGER NOT NULL CHECK (year IN (1,2,3,4)),
  class TEXT NOT NULL,
  course TEXT NOT NULL,

  student_email TEXT,
  parent_email TEXT,
  student_phone TEXT,
  parent_phone TEXT,

  institute_id TEXT NOT NULL,
  photo_filename TEXT,

  is_hosteller INTEGER NOT NULL DEFAULT 0 CHECK (is_hosteller IN (0,1)),
  hostel_sem1 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem1 IN (0,1)),
  hostel_sem2 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem2 IN (0,1)),
  hostel_sem3 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem3 IN (0,1)),
  hostel_sem4 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem4 IN (0,1)),
  hostel_sem5 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem5 IN (0,1)),
  hostel_sem6 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem6 IN (0,1)),
  hostel_sem7 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem7 IN (0,1)),
  hostel_sem8 INTEGER NOT NULL DEFAULT 0 CHECK (hostel_sem8 IN (0,1)),
  scholarship_type TEXT NOT NULL DEFAULT 'NONE',
  quota_type TEXT NOT NULL DEFAULT 'REGULAR',
  is_first_graduate INTEGER NOT NULL DEFAULT 0 CHECK (is_first_graduate IN (0,1)),

  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (institute_id) REFERENCES institutes(id)
);

CREATE INDEX IF NOT EXISTS idx_students_institute
ON students(institute_id);

CREATE INDEX IF NOT EXISTS idx_students_course_year
ON students(institute_id, course, year);

-- Fee plans
CREATE TABLE fee_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institute_id TEXT NOT NULL,
  course TEXT NOT NULL,
  year INTEGER NOT NULL CHECK (year IN (1,2,3,4)),

  tuition INTEGER NOT NULL DEFAULT 0,
  hostel INTEGER NOT NULL DEFAULT 50000,
  exam INTEGER NOT NULL DEFAULT 0,
  other INTEGER NOT NULL DEFAULT 0,

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE (institute_id, course, year),
  FOREIGN KEY (institute_id) REFERENCES institutes(id)
);

CREATE INDEX IF NOT EXISTS idx_fee_plans_institute
ON fee_plans(institute_id);

-- Fee adjustments
CREATE TABLE fee_adjustments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,

  category TEXT NOT NULL CHECK (
    category IN ('TUITION','EXAM','OTHER','HOSTEL','BUS','GYM','LAUNDRY','FINE','DISCOUNT')
  ),

  label TEXT NOT NULL,
  amount INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fee_adjustments_student
ON fee_adjustments(student_id);

CREATE INDEX IF NOT EXISTS idx_fee_adjustments_student_cat
ON fee_adjustments(student_id, category);

-- Payments
CREATE TABLE payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  txn_id TEXT NOT NULL UNIQUE,
  student_id INTEGER NOT NULL,

  category TEXT NOT NULL CHECK (
    category IN ('TUITION','EXAM','OTHER','HOSTEL','BUS','GYM','LAUNDRY','FINE')
  ),

  amount INTEGER NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('INITIATED','SUCCESS','FAILED')),
  razorpay_order_id TEXT,
  razorpay_payment_id TEXT,
  razorpay_signature TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (student_id) REFERENCES students(id)
);

CREATE INDEX IF NOT EXISTS idx_payments_student_time
ON payments(student_id, created_at);

CREATE INDEX IF NOT EXISTS idx_payments_status_time
ON payments(status, created_at);

CREATE INDEX IF NOT EXISTS idx_payments_time
ON payments(created_at);

-- Receipts
CREATE TABLE receipts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  receipt_no TEXT NOT NULL UNIQUE,
  payment_id INTEGER NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (payment_id) REFERENCES payments(id)
);

CREATE INDEX IF NOT EXISTS idx_receipts_time
ON receipts(created_at);

-- Audit Logs
CREATE TABLE audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institute_id TEXT NOT NULL,

  actor_user_id INTEGER,
  actor_role TEXT,

  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id INTEGER,

  details TEXT,
  ip TEXT,
  user_agent TEXT,

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (institute_id) REFERENCES institutes(id),
  FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_inst_time
ON audit_logs(institute_id, created_at);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action
ON audit_logs(action);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
ON audit_logs(entity_type, entity_id);

-- Fee Installments (Phase 4)
CREATE TABLE fee_installments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institute_id TEXT NOT NULL,
  course TEXT NOT NULL,
  year INTEGER NOT NULL,

  label TEXT NOT NULL,          -- e.g. "Semester 1"
  due_date TEXT NOT NULL,       -- YYYY-MM-DD
  percentage INTEGER NOT NULL,  -- e.g. 50, sum to 100 ideally
  late_fee_per_day INTEGER NOT NULL DEFAULT 0,

  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (institute_id) REFERENCES institutes(id)
);

-- Common Fees (applied to all students in an institute)
CREATE TABLE common_fees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institute_id TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'OTHER',
  label TEXT NOT NULL,
  amount INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (institute_id) REFERENCES institutes(id)
);

CREATE INDEX IF NOT EXISTS idx_common_fees_institute
ON common_fees(institute_id);
