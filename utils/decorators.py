# utils/decorators.py
# -----------------------------------------------
# Re-exports from utils.auth (single source of truth)
# -----------------------------------------------
# This file is kept for backward compatibility.
# All actual decorator logic lives in utils/auth.py.

from utils.auth import student_required, admin_required  # noqa: F401
