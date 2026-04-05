import pytest
from flask import url_for

def test_database_list_access(admin_session):
    """Test that admin can access the database list page."""
    response = admin_session.get('/admin/database')
    assert response.status_code == 200
    assert b'Tables' in response.data
    # In test DB, these tables should exist from schema.sql
    assert b'users' in response.data or b'students' in response.data

def test_database_table_view_access(admin_session):
    """Test that admin can view a specific table."""
    # We know 'users' table exists as it's used for login
    response = admin_session.get('/admin/database/users')
    assert response.status_code == 200
    assert b'Viewing Table:' in response.data
    assert b'username' in response.data

def test_database_list_unauthorized(client):
    """Test that unauthorized users cannot access the database list."""
    response = client.get('/admin/database')
    assert response.status_code == 302 # Redirects to login
