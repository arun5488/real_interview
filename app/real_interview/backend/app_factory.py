from flask import Flask

from app.real_interview import logger
from app.real_interview.backend.routes import user_maintenance_blueprint


def create_app() -> Flask:
    logger.info("[app_factory] creating Flask app")
    app = Flask(__name__)

    logger.info("[app_factory] registering user_maintenance blueprint")
    app.register_blueprint(user_maintenance_blueprint)

    logger.info("[app_factory] Flask app created successfully")
    return app

