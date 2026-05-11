import os

from app.real_interview import logger
from app.real_interview.backend.app_factory import create_app


def main() -> None:
    logger.info("[server] starting server")
    app = create_app()

    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info("[server] listening on %s:%s", host, port)

    app.run(host=host, port=port)


if __name__ == "__main__":
    main()

