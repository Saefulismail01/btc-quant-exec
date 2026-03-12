"""
Bootstrap launcher:
- Starts data_engine pipeline process
- Starts FastAPI server
Run with: python run.py
"""
import asyncio
import multiprocessing as mp
import os
import socket
import sys
from pathlib import Path

# Add backend/ to path
_BACKEND = str(Path(__file__).resolve().parent)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import uvicorn  # noqa: E402  (must come after sys.path patch)


def _run_data_engine():
    """Run data pipeline in its own process."""
    # Prevent Windows cp1252 console crashes from unicode banner/log output.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    from data_engine import run_data_pipeline

    run_data_pipeline()


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

    engine_proc = mp.Process(
        target=_run_data_engine,
        name="btc-quant-data-engine",
        daemon=True,
    )
    engine_proc.start()
    print(f"[BOOT] Data engine started (pid={engine_proc.pid})")

    try:
        uvicorn.run("app.main:app", host="0.0.0.0", port=api_port, reload=False)
    finally:
        if engine_proc.is_alive():
            print("[BOOT] Stopping data engine...")
            engine_proc.terminate()
            engine_proc.join(timeout=5)
            if engine_proc.is_alive():
                print("[BOOT] Data engine did not exit cleanly.")
            else:
                print("[BOOT] Data engine stopped.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
