# tests/conftest.py
"""
Pytest fixtures for Online College Fees Payment System testing.
"""
import os
import sys
import tempfile
import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def app():
    """Create a test Flask app with a temporary database."""
    # Create temp DB
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    os.environ["SECRET_KEY"] = "test-secret-key"

    from app import create_app
    from config import Config

    class TestConfig(Config):
        TESTING = True
        DATABASE_PATH = db_path
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
        WTF_CSRF_ENABLED = False  # disable CSRF for tests


    app = create_app(TestConfig)

    # Initialize the test database
    with app.app_context():
        from extensions import cache
        cache.clear()

        from utils.db import get_db
        import sqlite3


        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "database", "migrations", "schema.sql"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = f.read()

        db = get_db()
        db.executescript(schema)

        # Seed test data
        from werkzeug.security import generate_password_hash

        # Institute
        db.execute(
            "INSERT INTO institutes (id, short_name, full_name) VALUES (?, ?, ?)",
            ("ENG", "Engineering", "Test Engineering College"),
        )

        # Admin user
        db.execute(
            "INSERT INTO users (username, password_hash, role, institute_id) VALUES (?, ?, 'ADMIN', 'ENG')",
            ("test_admin", generate_password_hash("Admin@123")),
        )

        # Student user
        db.execute(
            "INSERT INTO users (username, password_hash, role, institute_id) VALUES (?, ?, 'STUDENT', 'ENG')",
            ("TEST001", generate_password_hash("01012000")),
        )
        user_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        db.execute(
            """INSERT INTO students
            (user_id, admission_no, name, dob, year, class, course, institute_id)
            VALUES (?, 'TEST001', 'Test Student', '2000-01-01', 1, 'CSE', 'B.E-CSE', 'ENG')""",
            (user_id,),
        )

        # Fee plan
        db.execute(
            """INSERT INTO fee_plans (institute_id, course, year, tuition, hostel, exam, other)
            VALUES ('ENG', 'B.E-CSE', 1, 50000, 50000, 3000, 1500)"""
        )

        db.commit()

    yield app

    # Cleanup
    with app.app_context():
        from extensions import db
        db.session.remove()
        db.engine.dispose()

    try:
        os.close(db_fd)
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def client(app):
    """Test client for HTTP requests."""
    return app.test_client()


@pytest.fixture
def admin_session(client):
    """Client with active admin session."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["role"] = "ADMIN"
        sess["institute_id"] = "ENG"
    return client


@pytest.fixture
def student_session(client):
    """Client with active student session."""
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["role"] = "STUDENT"
        sess["student_id"] = 1
        sess["institute_id"] = "ENG"
    return client
