from pathlib import Path

from flask import Flask, send_from_directory

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import validate_jwt_config
from app.real_interview.backend.utils.mongodb import get_shared_mongodb_client
from app.real_interview.backend.routes import (
    admin_blueprint,
    avatar_blueprint,
    feedback_blueprint,
    interview_blueprint,
    job_application_blueprint,
    resume_blueprint,
    user_maintenance_blueprint,
)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> Flask:
    logger.info("[app_factory] creating Flask app")
    validate_jwt_config()
    get_shared_mongodb_client()
    app = Flask(__name__)

    logger.info("[app_factory] registering user_maintenance blueprint")
    app.register_blueprint(user_maintenance_blueprint)

    logger.info("[app_factory] registering resume blueprint")
    app.register_blueprint(resume_blueprint)

    logger.info("[app_factory] registering job_application blueprint")
    app.register_blueprint(job_application_blueprint)

    logger.info("[app_factory] registering interview blueprint")
    app.register_blueprint(interview_blueprint)

    logger.info("[app_factory] registering avatar blueprint")
    app.register_blueprint(avatar_blueprint)

    logger.info("[app_factory] registering admin blueprint")
    app.register_blueprint(admin_blueprint)

    logger.info("[app_factory] registering feedback blueprint")
    app.register_blueprint(feedback_blueprint)

    @app.route("/", methods=["GET"])
    def serve_ui_index():
        logger.info("[app_factory] GET / (UI index)")
        return send_from_directory(str(_FRONTEND_DIR), "index.html")

    @app.route("/styles.css", methods=["GET"])
    def serve_ui_styles():
        return send_from_directory(str(_FRONTEND_DIR), "styles.css")

    @app.route("/app.js", methods=["GET"])
    def serve_ui_script():
        return send_from_directory(str(_FRONTEND_DIR), "app.js")

    @app.route("/admin", methods=["GET"])
    def serve_admin():
        logger.info("[app_factory] GET /admin")
        return send_from_directory(str(_FRONTEND_DIR), "admin.html")

    @app.route("/admin.js", methods=["GET"])
    def serve_admin_script():
        return send_from_directory(str(_FRONTEND_DIR), "admin.js")

    @app.route("/feedback", methods=["GET"])
    def serve_feedback():
        logger.info("[app_factory] GET /feedback")
        return send_from_directory(str(_FRONTEND_DIR), "feedback.html")

    @app.route("/feedback.js", methods=["GET"])
    def serve_feedback_script():
        return send_from_directory(str(_FRONTEND_DIR), "feedback.js")

    logger.info("[app_factory] Flask app created successfully")
    return app

