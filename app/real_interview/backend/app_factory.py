from pathlib import Path

from flask import Flask, send_from_directory

from app.real_interview import logger
from app.real_interview.backend.routes import resume_blueprint, user_maintenance_blueprint

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> Flask:
    logger.info("[app_factory] creating Flask app")
    app = Flask(__name__)

    logger.info("[app_factory] registering user_maintenance blueprint")
    app.register_blueprint(user_maintenance_blueprint)

    logger.info("[app_factory] registering resume blueprint")
    app.register_blueprint(resume_blueprint)

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

    logger.info("[app_factory] Flask app created successfully")
    return app

