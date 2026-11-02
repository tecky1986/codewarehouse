from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import Response

from app.deps import get_conn
from app.encoding import content_disposition
from app.errors import AppError
from app.excel_io import export_packages, import_packages, package_template
from app.repos import PackageMasterRepo
from app.response import fail, ok

_LOADING_MAP = {"人工": "manual", "叉车": "forklift", "manual": "manual", "forklift": "forklift"}

router = APIRouter(prefix="/api/packages", tags=["packages"])


def _repo(conn=Depends(get_conn)) -> PackageMasterRepo:
    return PackageMasterRepo(conn)


@router.get("")
def list_packages(repo: PackageMasterRepo = Depends(_repo)):
    return ok(repo.list_all())


@router.post("")
def create_package(body: dict, repo: PackageMasterRepo = Depends(_repo)):
    try:
        return ok(repo.create(body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.get("/template")
def download_template():
    content = package_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition("包装主数据模板.xlsx")},
    )


@router.get("/export")
def export_all(repo: PackageMasterRepo = Depends(_repo)):
    content = export_packages(repo.list_all())
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition("包装主数据.xlsx")},
    )


@router.post("/import")
def import_all(file: UploadFile = File(...), repo: PackageMasterRepo = Depends(_repo)):
    items = import_packages(file.file.read())
    saved = []
    skipped = 0
    for item in items:
        if item.get("l") is None or item.get("w") is None or item.get("h") is None:
            skipped += 1
            continue
        try:
            saved.append(repo.upsert(item))
        except AppError as e:
            return fail(e.code, e.message, status=e.status)
    return ok({"saved": saved, "saved_count": len(saved), "skipped": skipped})


@router.post("/batch")
def batch_update_packages(body: dict = Body(...), repo: PackageMasterRepo = Depends(_repo)):
    ids = body.get("ids") or []
    fields = dict(body.get("fields") or {})
    if not isinstance(ids, list) or not ids:
        return fail("E_VALIDATION", "请选择至少一条主数据", status=422)
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return fail("E_VALIDATION", "ids 必须为整数列表", status=422)
    patch = {k: fields[k] for k in PackageMasterRepo.BATCH_FIELDS if k in fields}
    if not patch:
        return fail("E_VALIDATION", "未指定可批量更新的字段", status=422)
    if "default_loading" in patch:
        raw = patch["default_loading"]
        mapped = _LOADING_MAP.get(str(raw) if raw is not None else "")
        if mapped is None:
            return fail("E_VALIDATION", "默认装卸仅支持 叉车 / 人工", status=422)
        patch["default_loading"] = mapped
    try:
        return ok(repo.batch_update(ids, patch))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.put("/{pid}")
def update_package(pid: int, body: dict, repo: PackageMasterRepo = Depends(_repo)):
    try:
        return ok(repo.update(pid, body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.delete("/{pid}")
def delete_package(pid: int, repo: PackageMasterRepo = Depends(_repo)):
    try:
        repo.delete(pid)
        return ok(True)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
