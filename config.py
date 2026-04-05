import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret_change_me")

    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    DATABASE_PATH = os.path.join(INSTANCE_DIR, "fees.db")
    _db_url = os.getenv("DATABASE_URL")
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads (future: admin photo upload)
    STUDENT_PHOTO_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "students")
    os.makedirs(STUDENT_PHOTO_FOLDER, exist_ok=True)

    # Business Logic Constants
    TRANSACTION_EXPIRY_MINUTES = 15
    FIRST_GRAD_DISCOUNT = 25000

    # Razorpay Payment Gateway
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_placeholder")
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "8cSj7g4TOWgCcP380PMh5w8j")
    
    # Webhook Secret (vital for security) - fallback to KEY_SECRET if not explicitly set
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", RAZORPAY_KEY_SECRET)

    # ✅ Mock Test Mode (1 = Enable, 0 = Disable)
    PAYMENT_TEST_MODE = os.getenv("PAYMENT_TEST_MODE", "0") == "1"

    # ✅ Flask-Caching Configuration
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")  # Change to "RedisCache" in production
    CACHE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_DEFAULT_TIMEOUT = 300
