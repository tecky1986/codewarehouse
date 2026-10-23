# 任务 16：Windows 可执行启动

## 16.1 启动脚本

`start.py`：

```python
#!/usr/bin/env python3
"""
Launch script: detect free port, start FastAPI, open browser,
persist SQLite data directory, stop on process close.
"""
import atexit
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.expanduser("~"), ".container-packing")
os.makedirs(DATA_DIR, exist_ok=True)


def find_free_port(start=8000, max_tries=10):
    """Find a free TCP port starting from `start`."""
    for attempt in range(start, start + max_tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", attempt))
            s.close()
            return attempt
        except OSError:
            s.close()
            continue
        finally:
            pass
    raise RuntimeError("no free port found in range")


def wait_for_http(port: int, timeout: float = 30.0) -> bool:
    """Poll http://127.0.0.1:<port>/api/health until it returns 200."""
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


def main():
    # 1. detect free port
    port = find_free_port()
    print(f"[start] using port {port}")

    # 2. set env vars for backend
    env = os.environ.copy()
    env["CP_DATA_DIR"] = DATA_DIR
    env["CP_PORT"] = str(port)

    # 3. start uvicorn
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
        ],
        cwd=BACKEND_DIR,
        env=env,
    )

    # 4. wait for readiness
    print("[start] waiting for backend…")
    if not wait_for_http(port):
        proc.kill()
        raise SystemExit("backend failed to start")

    print(f"[start] backend ready at http://127.0.0.1:{port}")

    # 5. open browser
    webbrowser.open(f"http://127.0.0.1:{port}")

    # 6. on exit, kill the child
    atexit.register(proc.kill)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.kill()
        proc.wait()


if __name__ == "__main__":
    main()
```

## 16.2 PyInstaller 打包配置

`pyinstaller.spec` 或等价的 CLI：

```bash
pyinstaller \
  --onefile \
  --name container-packing \
  --add-data "backend/app:backend/app" \
  --add-data "backend/packing_engine:backend/packing_engine" \
  --add-data "backend/static:backend/static" \
  --hidden-import openpyxl \
  start.py
```

## 数据目录

SQLite 数据库与导入/导出文件统一存放在 `~/.container-packing/`，
`start.py` 通过 `CP_DATA_DIR` 环境变量注入到 FastAPI 应用。

后端 `app/main.py` 启动时读取 `CP_DATA_DIR`，
若不存在则创建并初始化 schema（幂等 `CREATE TABLE IF NOT EXISTS`）。
