import logging
import socket
import uvicorn

from app.config import settings
from app.logging_setup import setup_logging
from app.web import app


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    host = "0.0.0.0"
    port = 8000
    local_ip = get_local_ip()

    logger.info(f"Starting web server at http://{local_ip}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
