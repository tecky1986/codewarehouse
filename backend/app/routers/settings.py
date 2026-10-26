from fastapi import APIRouter, Depends

from app.deps import get_conn
from app.repos import SettingRepo
from app.response import ok

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "manual_limit_kg": "30",
    "fork_tine_mm": "1220",
    "time_limit_s": "60",
    "gap_mm": "0",
}


def _repo(conn=Depends(get_conn)) -> SettingRepo:
    return SettingRepo(conn)


def _normalize_body(body: dict | None) -> dict:
    if not isinstance(body, dict):
        return {}
    cleaned: dict[str, str] = {}
    for k, v in body.items():
        if k is None or v is None:
            continue
        cleaned[str(k)] = str(v)
    return cleaned


@router.get("")
def get_settings(repo: SettingRepo = Depends(_repo)):
    data = {**DEFAULTS, **repo.get_all()}
    return ok(data)


@router.put("")
def put_settings(body: dict | None, repo: SettingRepo = Depends(_repo)):
    for k, v in _normalize_body(body).items():
        repo.put(str(k), v)
    data = {**DEFAULTS, **repo.get_all()}
    return ok(data)
