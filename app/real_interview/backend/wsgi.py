"""WSGI entry point for production (Gunicorn, etc.)."""
from app.real_interview.backend.app_factory import create_app

app = create_app()
