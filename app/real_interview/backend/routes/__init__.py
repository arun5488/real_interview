from .job_application_routes import job_application_blueprint
from .resume_routes import resume_blueprint
from .user_maintenance_routes import user_maintenance_blueprint

__all__ = [
    "job_application_blueprint",
    "resume_blueprint",
    "user_maintenance_blueprint",
]

