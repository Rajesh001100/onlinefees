from extensions import db
from datetime import datetime

class Institute(db.Model):
    __tablename__ = 'institutes'
    id = db.Column(db.String, primary_key=True)
    short_name = db.Column(db.String, nullable=False)
    full_name = db.Column(db.String, nullable=False)

    users = db.relationship('User', backref='institute', lazy=True)
    students = db.relationship('Student', backref='institute', lazy=True)
    fee_plans = db.relationship('FeePlan', backref='institute', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='institute', lazy=True)
    installments = db.relationship('FeeInstallment', backref='institute', lazy=True)
    common_fees = db.relationship('CommonFee', backref='institute', lazy=True)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, nullable=False, unique=True)
    password_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False) # 'ADMIN', 'STUDENT', 'FOUNDER'
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=True)
    is_active = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_profile = db.relationship('Student', backref='user', uselist=False, cascade="all, delete-orphan")


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    admission_no = db.Column(db.String, nullable=False, unique=True)
    register_no = db.Column(db.String, nullable=True)
    name = db.Column(db.String, nullable=False)
    dob = db.Column(db.String, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    class_name = db.Column('class', db.String, nullable=False)
    course = db.Column(db.String, nullable=False)
    student_email = db.Column(db.String, nullable=True)
    parent_email = db.Column(db.String, nullable=True)
    student_phone = db.Column(db.String, nullable=True)
    parent_phone = db.Column(db.String, nullable=True)
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=False)
    photo_filename = db.Column(db.String, nullable=True)
    
    is_hosteller = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem1 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem2 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem3 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem4 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem5 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem6 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem7 = db.Column(db.Integer, default=0, nullable=False)
    hostel_sem8 = db.Column(db.Integer, default=0, nullable=False)
    scholarship_type = db.Column(db.String, default='NONE', nullable=False)
    quota_type = db.Column(db.String, default='REGULAR', nullable=False)
    is_first_graduate = db.Column(db.Integer, default=0, nullable=False)
    admission_fee = db.Column(db.Integer, default=0, nullable=False)
    
    is_active = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    adjustments = db.relationship('FeeAdjustment', backref='student', cascade="all, delete-orphan")
    payments = db.relationship('Payment', backref='student')


class Scholarship(db.Model):
    __tablename__ = 'scholarships'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=False)
    scholarship_type = db.Column(db.String, nullable=False) # SC, ST, BC, MBC...
    amount = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FeePlan(db.Model):
    __tablename__ = 'fee_plans'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=False)
    course = db.Column(db.String, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    tuition = db.Column(db.Integer, default=0, nullable=False)
    hostel = db.Column(db.Integer, default=50000, nullable=False)
    exam = db.Column(db.Integer, default=0, nullable=False)
    other = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FeeAdjustment(db.Model):
    __tablename__ = 'fee_adjustments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    category = db.Column(db.String, nullable=False)
    label = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    txn_id = db.Column(db.String, nullable=False, unique=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    category = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False) # 'INITIATED','SUCCESS','FAILED'
    razorpay_order_id = db.Column(db.String, nullable=True)
    razorpay_payment_id = db.Column(db.String, nullable=True)
    razorpay_signature = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    receipt = db.relationship('Receipt', backref='payment', uselist=False)


class Receipt(db.Model):
    __tablename__ = 'receipts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    receipt_no = db.Column(db.String, nullable=False, unique=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actor_role = db.Column(db.String, nullable=True)
    action = db.Column(db.String, nullable=False)
    entity_type = db.Column(db.String, nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.String, nullable=True)
    ip = db.Column(db.String, nullable=True)
    user_agent = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FeeInstallment(db.Model):
    __tablename__ = 'fee_installments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=False)
    course = db.Column(db.String, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String, nullable=False)
    due_date = db.Column(db.String, nullable=False)
    percentage = db.Column(db.Integer, nullable=False)
    late_fee_per_day = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CommonFee(db.Model):
    __tablename__ = 'common_fees'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    institute_id = db.Column(db.String, db.ForeignKey('institutes.id'), nullable=False)
    category = db.Column(db.String, nullable=False, default='OTHER')
    label = db.Column(db.String, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
