from .admin_routes import admin_blueprint
from .avatar_routes import avatar_blueprint
from .feedback_routes import feedback_blueprint
from .interview_routes import interview_blueprint
from .job_application_routes import job_application_blueprint
from .resume_routes import resume_blueprint
from .user_maintenance_routes import user_maintenance_blueprint

__all__ = [
    "admin_blueprint",
    "avatar_blueprint",
    "feedback_blueprint",
    "interview_blueprint",
    "job_application_blueprint",
    "resume_blueprint",
    "user_maintenance_blueprint",
]

