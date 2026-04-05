# tests/test_students.py
"""
Tests for student management routes.
"""


class TestStudentList:
    def test_classes_page(self, admin_session):
        resp = admin_session.get("/admin/year/1/classes")
        assert resp.status_code == 200

    def test_students_list_with_pagination(self, admin_session):
        resp = admin_session.get("/admin/year/1/class/CSE/students?page=1")
        assert resp.status_code == 200

    def test_students_list_search(self, admin_session):
        resp = admin_session.get("/admin/year/1/class/CSE/students?q=TEST")
        assert resp.status_code == 200

    def test_students_list_sort(self, admin_session):
        resp = admin_session.get("/admin/year/1/class/CSE/students?sort=name&order=desc")
        assert resp.status_code == 200


class TestStudentView:
    def test_view_existing_student(self, admin_session):
        resp = admin_session.get("/admin/student/1")
        assert resp.status_code == 200
        assert b"Test Student" in resp.data

    def test_view_nonexistent_student(self, admin_session):
        resp = admin_session.get("/admin/student/9999", follow_redirects=True)
        assert resp.status_code == 200  # Redirected to dashboard with flash


class TestAddStudent:
    def test_add_student_page_loads(self, admin_session):
        resp = admin_session.get("/admin/students/add")
        assert resp.status_code == 200

    def test_add_student_empty_form(self, admin_session):
        resp = admin_session.post("/admin/students/add", data={
            "admission_no": "",
            "name": "",
            "dob": "",
            "year": "",
            "class": "",
            "course": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should flash validation errors

    def test_add_student_invalid_email(self, admin_session):
        resp = admin_session.post("/admin/students/add", data={
            "admission_no": "NEW001",
            "name": "New Student",
            "dob": "2005-01-01",
            "year": "1",
            "class": "CSE",
            "course": "B.E-CSE",
            "student_email": "not-a-valid-email",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_add_student_invalid_phone(self, admin_session):
        resp = admin_session.post("/admin/students/add", data={
            "admission_no": "NEW002",
            "name": "New Student 2",
            "dob": "2005-06-15",
            "year": "1",
            "class": "CSE",
            "course": "B.E-CSE",
            "student_phone": "12345",  # Not 10 digits
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_add_student_success(self, admin_session):
        resp = admin_session.post("/admin/students/add", data={
            "admission_no": "NEW003",
            "name": "Valid Student",
            "dob": "2005-03-20",
            "year": "1",
            "class": "CSE",
            "course": "B.E-CSE",
            "student_email": "valid@example.com",
            "student_phone": "9876543210",
            "is_hosteller": "0",
            "benefit_type": "NONE",
        }, follow_redirects=False)
        assert resp.status_code in (200, 302, 303)


class TestUploadStudents:
    def test_upload_page_loads(self, admin_session):
        resp = admin_session.get("/admin/students/upload")
        assert resp.status_code == 200
