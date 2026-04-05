# utils/audit.py
from flask import session, request
import json
from datetime import datetime


def audit_log(db, action, entity_type, entity_id, details=None):
    """
    Logs an action to the audit_logs table.
    Column names match schema.sql: ip (not ip_address), user_agent.
    """
    try:
        actor_user_id = session.get("user_id")
        institute_id = session.get("institute_id")
        ip = request.remote_addr
        user_agent = request.headers.get("User-Agent", "")

        details_json = json.dumps(details) if details else None

        db.execute(
            """
            INSERT INTO audit_logs (
                institute_id, actor_user_id, actor_role, action,
                entity_type, entity_id, details, ip, user_agent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                institute_id, actor_user_id, session.get("role"), action,
                entity_type, entity_id, details_json, ip, user_agent,
                datetime.now().isoformat()
            )
        )
    except Exception as e:
        print(f"❌ Audit Log Failed: {e}")
