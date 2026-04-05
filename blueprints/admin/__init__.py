from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Import views to register routes
from .views import auth, dashboard, students, fees, reports, database
