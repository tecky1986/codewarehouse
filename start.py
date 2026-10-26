#!/usr/bin/env python3
"""
Launch script: detect free port, start FastAPI, open browser.
Persist SQLite data in ~/.container-packing/.
Stop the service when this process is killed.

Works in two modes:
- Source mode: run `python start.py` — spawns uvicorn as a child process
- Frozen mode (PyInstaller onedir): run uvicorn in-process and keep the
  browser launch behavior consistent with source mode
"""

import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def _resource_dir() -> str:
    """Return the directory containing backend/ resources.

    In a PyInstaller onedir bundle the resources live in
    ``_internal/`` alongside the executable; in a normal install
    they sit next to this file.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    return os.path.dirname(os.path.abspath(__file__))


BACKEND_DIR = os.path.join(_resource_dir(), "backend")
DATA_DIR = os.path.join(os.path.expanduser("~"), ".container-packing")

try:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isdir(DATA_DIR) or not os.access(DATA_DIR, os.W_OK):
        print(f"[start] WARNING: data dir {DATA_DIR} is not writable; "
              f"persisted data may be lost after restart")
except OSError as e:
    print(f"[start] ERROR: cannot create data dir {DATA_DIR}: {e}")


def find_free_port(start: int = 8000, tries: int = 10) -> int:
    for port in range(start, start + tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            s.close()
    raise RuntimeError(f"no free port in range {start}..{start + tries - 1}")


def wait_for_http(port: int, timeout: float = 30.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def open_browser(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    try:
        webbrowser.open(url, new=2)
        print(f"[start] opened browser: {url}")
    except Exception as exc:  # pragma: no cover - UI dependent
        print(f"[start] browser unavailable: {exc}")


def _setup_env(port: int) -> None:
    os.environ["CP_DATA_DIR"] = DATA_DIR
    os.environ["CP_PORT"] = str(port)
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, BACKEND_DIR)
        os.chdir(BACKEND_DIR)


def _run_frozen(port: int) -> None:
    """Run uvicorn in-process for PyInstaller onedir bundles."""
    _setup_env(port)
    import uvicorn
    from app.main import app as fastapi_app  # noqa: E402

    print(f"[start] running in-process on port {port}")
    print(f"[start] data dir: {DATA_DIR}")

    def _open_browser():
        if wait_for_http(port):
            webbrowser.open(f"http://127.0.0.1:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()
    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    def _stop(signum, frame):
        print(f"\n[start] signal {signum}, shutting down …")
        server.should_exit = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    print("[start] waiting for backend …")
    if not wait_for_http(port):
        server.should_exit = True
        thread.join(timeout=5)
        raise SystemExit("backend failed to start")

    url = f"http://127.0.0.1:{port}"
    print(f"[start] ready: {url}")
    open_browser(port)

    try:
        while thread.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=5)


def _run_source(port: int) -> None:
    """Spawn uvicorn as a child process for source-mode execution."""
    _setup_env(port)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
    )

    def _sig_handler(signum, frame):
        if proc.poll() is None:
            proc.kill()
        os._exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    print("[start] waiting for backend …")
    if not wait_for_http(port):
        proc.kill()
        raise SystemExit("backend failed to start")

    url = f"http://127.0.0.1:{port}"
    print(f"[start] ready: {url}")
    open_browser(port)
    proc.wait()


def main() -> None:
    port = find_free_port()
    print(f"[start] using port {port}")

    if getattr(sys, "frozen", False):
        _run_frozen(port)
    else:
        _run_source(port)


if __name__ == "__main__":
    main()
