"""Vercel Python entrypoint. FastAPI app lives in backend/app/main.py."""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.main import app  # noqa: E402

__all__ = ["app"]
