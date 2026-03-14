"""
Bootstrap launcher:
- Starts FastAPI server
- Data ingestion daemon runs within FastAPI lifespan (same event loop, no threading issues)
Run with: python run.py
"""
import os
import socket
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging early
logging.basicConfig(level=logging.INFO, format='[BOOT] %(message)s')
logger = logging.getLogger(__name__)

# Load .env early, before any imports that use os.getenv()
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"Loaded .env from {env_path}")
    # Verify telegram token loaded
    test_token = os.getenv("EXECUTION_TELEGRAM_BOT_TOKEN", "")
    logger.info(f"EXECUTION_TELEGRAM_BOT_TOKEN: {'✅ Loaded' if test_token else '❌ Not set'}")
else:
    logger.warning(f".env not found at {env_path}")

# Add backend/ to path
_BACKEND = str(Path(__file__).resolve().parent)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import uvicorn  # noqa: E402  (must come after sys.path patch)


def _pick_port(preferred: int, max_tries: int = 10) -> int:
    """Pick first available port starting from preferred."""
    for port in range(preferred, preferred + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    raise RuntimeError(
        f"No free port found in range {preferred}-{preferred + max_tries - 1}"
    )


def main():
    preferred_port = int(os.getenv("PORT", "8000"))
    api_port = _pick_port(preferred_port)
    if api_port != preferred_port:
        print(
            f"[BOOT] Port {preferred_port} is busy, "
            f"using {api_port} instead."
        )

    # Run uvicorn server with FastAPI lifespan handling data daemon
    uvicorn.run("app.main:app", host="0.0.0.0", port=api_port, reload=False)


if __name__ == "__main__":
    main()
