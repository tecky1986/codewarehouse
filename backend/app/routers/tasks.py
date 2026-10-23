from typing import Any

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import Response

from app.deps import get_conn
from app.encoding import content_disposition
from app.errors import AppError
from app.importing import (
    complete_rows,
    map_raw_rows,
    parse_maintain_xlsx,
    pending_fill_workbook,
    preview_payload,
    rows_from_file,
)
from app.repos import ImportRowRepo, PackageMasterRepo, TaskRepo
from app.response import fail, ok

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_repo(conn=Depends(get_conn)) -> TaskRepo:
    return TaskRepo(conn)


@router.get("")
def list_tasks(repo: TaskRepo = Depends(_task_repo)):
    return ok(repo.list_all())


@router.get("/sample.xlsx")
def sample_xlsx(conn=Depends(get_conn)):
    """下载示例导入表（测试期功能，上线前移除）。"""
    from openpyxl import Workbook

    from app.seed import SAMPLE_IMPORT_ROWS, SAMPLE_IMPORT_ROWS_HEADER

    wb = Workbook()
    ws = wb.active
    ws.title = "sample"
    ws.append(SAMPLE_IMPORT_ROWS_HEADER)
    for row in SAMPLE_IMPORT_ROWS:
        ws.append(row)
    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    headers = {"Content-Disposition": content_disposition("示例导入表.xlsx")}
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("")
def create_task(body: dict, repo: TaskRepo = Depends(_task_repo)):
    return ok(repo.create(body))


@router.get("/{tid}")
def get_task(tid: int, repo: TaskRepo = Depends(_task_repo)):
    try:
        return ok(repo.get(tid))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.put("/{tid}")
def update_task(tid: int, body: dict, repo: TaskRepo = Depends(_task_repo)):
    try:
        return ok(repo.update(tid, body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.delete("/{tid}")
def delete_task(tid: int, repo: TaskRepo = Depends(_task_repo)):
    try:
        repo.delete(tid)
        return ok(True)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.post("/{tid}/import")
def import_task(
    tid: int,
    file: UploadFile = File(...),
    conn=Depends(get_conn),
):
    TaskRepo(conn).get(tid)
    content = file.file.read()
    try:
        raw = rows_from_file(file.filename or "", content)
        mapped = map_raw_rows(raw)
        rows = complete_rows(conn, mapped)
        ImportRowRepo(conn).replace_for_task(tid, rows)
        return ok(preview_payload(rows))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.get("/{tid}/import/preview")
def import_preview(tid: int, conn=Depends(get_conn)):
    TaskRepo(conn).get(tid)
    rows = complete_rows(conn, ImportRowRepo(conn).list_by_task(tid))
    return ok(preview_payload(rows))


@router.get("/{tid}/import/pending.xlsx")
def pending_xlsx(tid: int, conn=Depends(get_conn)):
    TaskRepo(conn).get(tid)
    rows = complete_rows(conn, ImportRowRepo(conn).list_by_task(tid))
    content = pending_fill_workbook(rows)
    headers = {"Content-Disposition": content_disposition("待填规格.xlsx")}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/{tid}/import/batch-maintain")
def batch_maintain(
    tid: int,
    file: UploadFile = File(...),
    conn=Depends(get_conn),
):
    TaskRepo(conn).get(tid)
    items = parse_maintain_xlsx(file.file.read())
    pkg = PackageMasterRepo(conn)
    saved = []
    for item in items:
        if item.get("l") is None or item.get("w") is None or item.get("h") is None:
            continue
        existing = None
        if item.get("pn"):
            existing = pkg.get_by_pn(item["pn"])
        if existing is None and item.get("name"):
            existing = pkg.get_by_packmatls(item["name"])
        if existing:
            saved.append(pkg.update(existing["id"], item))
        else:
            saved.append(pkg.create(item))
    return ok(saved)


@router.post("/{tid}/import/re-match")
def re_match(tid: int, conn=Depends(get_conn)):
    TaskRepo(conn).get(tid)
    rows = complete_rows(conn, ImportRowRepo(conn).list_by_task(tid))
    ImportRowRepo(conn).replace_for_task(tid, rows)
    return ok(preview_payload(rows))


@router.get("/{tid}/site-groups")
def get_site_groups(tid: int, conn=Depends(get_conn)):
    task = TaskRepo(conn).get(tid)
    rows = ImportRowRepo(conn).list_by_task(tid)
    sites: dict[str, dict] = {}
    for r in rows:
        site = r.get("m_site") or ""
        bucket = sites.setdefault(
            site,
            {"site": site, "together": False, "separate": False, "items": []},
        )
        bucket["items"].append(
            {
                "row_no": r.get("row_no"),
                "outcase": r.get("f_outcase"),
                "packmatls": r.get("g_packmatls"),
                "volume": r.get("e_cbm"),
                "gross": r.get("j_gross"),
            }
        )
    saved = task.get("site_groups_json") or []
    if isinstance(saved, str):
        import json

        saved = json.loads(saved) if saved else []
    by_site = {s.get("site"): s for s in saved if isinstance(s, dict)}
    result = []
    for site, bucket in sites.items():
        extra = by_site.get(site) or {}
        bucket["together"] = bool(extra.get("together"))
        bucket["separate"] = bool(extra.get("separate"))
        result.append(bucket)
    return ok(result)


@router.put("/{tid}/site-groups")
def put_site_groups(tid: int, body: Any = Body(...), conn=Depends(get_conn)):
    groups = body if isinstance(body, list) else (body.get("groups") or body.get("data") or [])
    for g in groups:
        if g.get("together") and g.get("separate"):
            return fail("E_VALIDATION", "同一 Site 不能同时同柜与分离", status=422)
    TaskRepo(conn).update(tid, {"site_groups_json": groups})
    return ok(groups)
