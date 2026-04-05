# utils/db.py
import sqlite3
from flask import current_app, g

def get_db():
    if "db" not in g:
        db_path = current_app.config.get("DATABASE_PATH")
        if not db_path:
            raise RuntimeError("DATABASE_PATH not set in app config")

        # Debug print only if you explicitly enable it
        if current_app.config.get("DB_DEBUG") is True:
            print("✅ Flask DATABASE_PATH =", db_path)

        con = sqlite3.connect(
            db_path,
            timeout=30,
            check_same_thread=False
        )
        con.row_factory = sqlite3.Row

        # Pragmas
        con.execute("PRAGMA foreign_keys = ON;")
        con.execute("PRAGMA journal_mode = WAL;")
        con.execute("PRAGMA synchronous = NORMAL;")
        con.execute("PRAGMA busy_timeout = 5000;")

        g.db = con

    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
