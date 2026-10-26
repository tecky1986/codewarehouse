from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles

from app.deps import get_conn
from app.errors import AppError
from app.response import fail, ok
from app.routers import container_types, export, packages, plans, settings, tasks


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_conn()
    yield


app = FastAPI(title="Container Packing", lifespan=lifespan)
app.include_router(container_types.router)
app.include_router(packages.router)
app.include_router(settings.router)
app.include_router(tasks.router)
app.include_router(plans.router)
app.include_router(export.router)


@app.get("/api/health")
def health():
    return ok({"status": "ok"})


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return fail(exc.code, exc.message, status=exc.status)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError):
    return fail("E_VALIDATION", str(exc), status=422)


@app.exception_handler(Exception)
async def unhandled_handler(_request: Request, exc: Exception):
    return fail("E_ENGINE", str(exc), status=500)


class SPAStaticFiles(StaticFiles):
    """Serve static assets and fall back to index.html for SPA routes."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
            if response.status_code != 404:
                return response
        except StarletteHTTPException:
            pass

        scope2 = dict(scope)
        scope2["path"] = "/"
        index_response = await super().get_response("index.html", scope2)
        if index_response.status_code == 200 and path:
            index_response.headers["Cache-Control"] = "no-cache"
        return index_response


def _static_dir() -> Path:
    """Resolve the static dir in both source and PyInstaller onedir modes."""
    import sys
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # onedir: sys._MEIPASS points to the _internal dir itself,
        # so resources live at <_MEIPASS>/backend/static
        base = Path(meipass)
        return base / "backend" / "static"
    return Path(__file__).resolve().parents[1] / "static"


_STATIC = _static_dir()
if _STATIC.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(_STATIC), html=True), name="static")
