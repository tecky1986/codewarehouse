from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.deps import get_conn
from app.errors import AppError
from app.excel_io import export_container_types, import_container_types
from app.repos import ContainerTypeRepo
from app.response import fail, ok

router = APIRouter(prefix="/api/container-types", tags=["container-types"])


def _repo(conn=Depends(get_conn)) -> ContainerTypeRepo:
    return ContainerTypeRepo(conn)


def _positive(data: dict) -> str | None:
    for k in ("inner_l", "inner_w", "inner_h", "max_payload"):
        v = data.get(k)
        if v is None:
            return f"{k} is required"
        try:
            if float(v) <= 0:
                return f"{k} must be positive"
        except (TypeError, ValueError):
            return f"{k} must be a number"
    return None


@router.get("")
def list_types(repo: ContainerTypeRepo = Depends(_repo)):
    return ok(repo.list_all())


@router.post("")
def create_type(body: dict, repo: ContainerTypeRepo = Depends(_repo)):
    err = _positive(body)
    if err:
        return fail("E_VALIDATION", err, status=422)
    try:
        return ok(repo.create(body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.get("/export")
def export_types(repo: ContainerTypeRepo = Depends(_repo)):
    content = export_container_types(repo.list_all())
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=container-types.xlsx"},
    )


@router.post("/import")
def import_types(file: UploadFile = File(...), repo: ContainerTypeRepo = Depends(_repo)):
    raw = file.file.read()
    items = import_container_types(raw)
    created = []
    for item in items:
        existing = repo.get_by_code(str(item["code"]))
        payload = {k: item.get(k) for k in item}
        if existing:
            created.append(repo.update(existing["id"], payload))
        else:
            created.append(repo.create(payload))
    return ok(created)


@router.put("/{cid}")
def update_type(cid: int, body: dict, repo: ContainerTypeRepo = Depends(_repo)):
    if any(k in body for k in ("inner_l", "inner_w", "inner_h", "max_payload")):
        merged = {**repo.get(cid), **body}
        err = _positive(merged)
        if err:
            return fail("E_VALIDATION", err, status=422)
    try:
        return ok(repo.update(cid, body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.delete("/{cid}")
def delete_type(cid: int, repo: ContainerTypeRepo = Depends(_repo)):
    try:
        repo.delete(cid)
        return ok(True)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
