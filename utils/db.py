# utils/db.py
from flask import current_app, g
from sqlalchemy import text
from extensions import db as sqlalchemy_db
from datetime import date, datetime

class SQLAlchemyConnectionShim:
    """
    A shim that mimics the sqlite3.Connection interface using SQLAlchemy's session.
    This allows legacy raw SQL code (using '?' placeholders) to work on Postgres/other DBs.
    """
    def __init__(self, session):
        self.session = session

    def execute(self, sql, params=None):
        # Translate '?' to named parameters ':p0', ':p1', etc. for SQLAlchemy compatibility
        if params:
            new_sql = sql
            param_dict = {}
            if isinstance(params, (list, tuple)):
                i = 0
                while '?' in new_sql:
                    placeholder = f":p{i}"
                    new_sql = new_sql.replace('?', placeholder, 1)
                    param_dict[f"p{i}"] = params[i]
                    i += 1
            elif isinstance(params, dict):
                param_dict = params

            result = self.session.execute(text(new_sql), param_dict)
        else:
            result = self.session.execute(text(sql))
        
        # Wrap result to handle date/datetime stringification (SQLite behavior)
        return SQLAlchemyResultWrapper(result)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        pass

class SQLAlchemyResultWrapper:
    """
    Mimics a sqlite3.Cursor or Result object, providing fetchone/fetchall 
    and stringifying dates/datetimes to match SQLite behavior.
    """
    def __init__(self, result):
        self._result = result

    def fetchone(self):
        row = self._result.fetchone()
        return self._wrap_row(row) if row else None

    def fetchall(self):
        rows = self._result.fetchall()
        return [self._wrap_row(r) for r in rows]

    def _wrap_row(self, row):
        if not row:
            return None
        # Convert SQLAlchemy Row to something that behaves like sqlite3.Row
        # and stringifies dates/times for compatibility.
        data = dict(row._mapping)
        for key, value in data.items():
            if isinstance(value, (date, datetime)):
                data[key] = value.isoformat(sep=' ')[:19] # Match 'YYYY-MM-DD HH:MM:SS'
        return data

def get_db():
    if "db" not in g:
        g.db = SQLAlchemyConnectionShim(sqlalchemy_db.session)
    return g.db

def close_db(e=None):
    g.pop("db", None)
