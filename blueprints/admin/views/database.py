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


@admin_bp.route("/database/<table>/edit/<id>", methods=["GET", "POST"])
@admin_required
def database_edit_row(table, id):
    role = session.get("role")
    inst_id = session.get("institute_id")

    # Blacklist critical tables for safety
    if table in ["payments", "receipts", "audit_logs"] and role != "FOUNDER":
        abort(403)

    inspector = db.inspect(db.engine)
    valid_tables = inspector.get_table_names()
    if table not in valid_tables:
        abort(404)

    columns = [col["name"] for col in inspector.get_columns(table)]
    
    from sqlalchemy import text
    with db.engine.connect() as conn:
        row_raw = conn.execute(
            text(f"SELECT * FROM {table} WHERE id = :id"),
            {"id": id}
        ).fetchone()

    if not row_raw:
        abort(404)

    row = dict(zip(columns, row_raw))

    # Security: Verify institute_id for ADMIN
    if role == "ADMIN" and "institute_id" in row:
        if row["institute_id"] != inst_id:
            abort(403)

    if request.method == "POST":
        # Build update query
        update_parts = []
        params = {"id": id}
        
        for col in columns:
            if col in ["id", "created_at"]: continue
            if col not in request.form: continue
            
            val = request.form.get(col)
            # Basic type conversion attempt (if needed) - here we just use what form sends
            update_parts.append(f"{col} = :{col}")
            params[col] = val

        if update_parts:
            try:
                with db.engine.connect() as conn:
                    conn.execute(
                        text(f"UPDATE {table} SET {', '.join(update_parts)} WHERE id = :id"),
                        params
                    )
                    conn.commit()
                from flask import flash, redirect, url_for
                flash(f"Record {id} in {table} updated successfully.", "success")
                return redirect(url_for("admin.database_table_view", table=table))
            except Exception as e:
                from flask import flash
                flash(f"Update failed: {str(e)}", "danger")

    return render_template(
        "admin/edit_row.html",
        table=table,
        row_id=id,
        columns=columns,
        row=row
    )


@admin_bp.route("/database/<table>/delete/<id>")
@admin_required
def database_delete_row(table, id):
    role = session.get("role")
    inst_id = session.get("institute_id")

    # Blacklist critical tables for safety
    if table in ["payments", "receipts", "audit_logs", "institutes", "users"]:
        flash("Deletion of critical system records is not allowed via the database browser.", "danger")
        return redirect(url_for("admin.database_table_view", table=table))

    inspector = db.inspect(db.engine)
    valid_tables = inspector.get_table_names()
    if table not in valid_tables:
        abort(404)

    from sqlalchemy import text
    with db.engine.connect() as conn:
        # Check if row exists and get institute_id for security
        row_raw = conn.execute(
            text(f"SELECT * FROM {table} WHERE id = :id"),
            {"id": id}
        ).fetchone()

        if not row_raw:
            flash("Record not found.", "danger")
            return redirect(url_for("admin.database_table_view", table=table))

        columns = [col["name"] for col in inspector.get_columns(table)]
        row = dict(zip(columns, row_raw))

        # Security: Verify institute_id for ADMIN
        if role == "ADMIN" and "institute_id" in row:
            if row["institute_id"] != inst_id:
                abort(403)

        # Execute Delete
        try:
            conn.execute(
                text(f"DELETE FROM {table} WHERE id = :id"),
                {"id": id}
            )
            conn.commit()
            flash(f"Record {id} deleted successfully from {table}.", "success")
        except Exception as e:
            flash(f"Delete failed: {str(e)}", "danger")

    return redirect(url_for("admin.database_table_view", table=table))
