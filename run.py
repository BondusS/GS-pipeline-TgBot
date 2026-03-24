import logging
import requests
import uvicorn

from app.config import settings
from app.logging_setup import setup_logging
from app.web import app


def get_external_ip():
    try:
        return requests.get("https://api.ipify.org").text
    except requests.RequestException:
        return "127.0.0.1"


def main() -> None:
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    host = "0.0.0.0"
    port = 8000
    external_ip = get_external_ip()

    logger.info(f"Starting web server at http://{external_ip}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
