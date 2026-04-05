# tests/test_auth.py
"""
Tests for authentication routes and decorators.
"""


class TestAdminLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert b"login" in resp.data.lower() or b"Login" in resp.data

    def test_login_invalid_credentials(self, client):
        resp = client.post("/admin/login", data={
            "username": "nonexistent",
            "password": "wrong"
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Invalid" in resp.data or b"invalid" in resp.data

    def test_login_empty_fields(self, client):
        resp = client.post("/admin/login", data={
            "username": "",
            "password": ""
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_success(self, client):
        resp = client.post("/admin/login", data={
            "username": "test_admin",
            "password": "Admin@123"
        }, follow_redirects=False)
        # Should redirect to dashboard
        assert resp.status_code in (302, 303)

    def test_logout(self, admin_session):
        resp = admin_session.get("/admin/logout", follow_redirects=False)
        assert resp.status_code in (302, 303)


class TestStudentLogin:
    def test_student_select_institute(self, client):
        resp = client.get("/student/select-institute")
        assert resp.status_code == 200

    def test_student_login_page_requires_institute(self, client):
        # Set institute in session
        with client.session_transaction() as sess:
            sess["selected_institute"] = "ENG"
        resp = client.get("/student/login")
        assert resp.status_code == 200


class TestAccessControl:
    def test_admin_dashboard_requires_login(self, client):
        resp = client.get("/admin/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 303)

    def test_student_dashboard_requires_login(self, client):
        resp = client.get("/student/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 303)

    def test_admin_can_access_dashboard(self, admin_session):
        resp = admin_session.get("/admin/dashboard")
        assert resp.status_code == 200
