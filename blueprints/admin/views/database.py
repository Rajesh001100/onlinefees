from flask import render_template, request, session, abort
from utils.decorators import admin_required
from .. import admin_bp
from extensions import db
import math


@admin_bp.get("/database")
@admin_required
def database_list():
    # Use SQLAlchemy engine to list tables
    tables = db.engine.dialect.get_table_names(db.engine.connect())
    tables = sorted([t for t in tables if not t.startswith("sqlite_")])
    return render_template("admin/database.html", tables=tables)


@admin_bp.get("/database/<table>")
@admin_required
def database_table_view(table):
    # Allowlist check via SQLAlchemy's introspection
    inspector = db.inspect(db.engine)
    valid_tables = inspector.get_table_names()

    if table not in valid_tables:
        abort(404)

    # Get column names
    columns = [col["name"] for col in inspector.get_columns(table)]

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    with db.engine.connect() as conn:
        from sqlalchemy import text
        total_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        rows_raw = conn.execute(
            text(f"SELECT * FROM {table} LIMIT :limit OFFSET :offset"),
            {"limit": per_page, "offset": offset}
        ).fetchall()

    total_pages = max(1, math.ceil(total_count / per_page))
    rows = [dict(zip(columns, r)) for r in rows_raw]

    all_tables = sorted([t for t in valid_tables if not t.startswith("sqlite_")])

    return render_template(
        "admin/database.html",
        table=table,
        columns=columns,
        rows=rows,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        tables=all_tables,
    )
