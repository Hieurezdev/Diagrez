from core.config import configure_logging
from core.transport.http import app

configure_logging()


__all__ = ["app"]
