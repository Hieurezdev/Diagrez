"""Run the FastAPI development server without watching dependency files."""

import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    from core.config import configure_logging

    configure_logging()
    uvicorn.run(
        "main:app",
        app_dir=str(PROJECT_ROOT),
        host="127.0.0.1",
        port=8000,
        log_level="info",
        log_config=None,
        reload=True,
        # Watch only application code. Watching the project root also watches
        # dependency metadata and package files under .venv.
        reload_dirs=[str(PROJECT_ROOT / "core")],
    )
