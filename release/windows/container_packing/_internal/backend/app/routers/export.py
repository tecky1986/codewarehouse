from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import Response

from app.deps import get_conn
from app.errors import AppError
from app.exporting import ExportService
from app.encoding import content_disposition
from app.repos import ExportTemplateRepo
from app.response import fail, ok

router = APIRouter(tags=["export"])

MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MEDIA_CSV = "text/csv"


def _service(conn=Depends(get_conn)) -> ExportService:
    return ExportService(conn)


def _template_repo(conn=Depends(get_conn)) -> ExportTemplateRepo:
    return ExportTemplateRepo(conn)


def _load_cols(v):
    import json

    if isinstance(v, str):
        try:
            return json.loads(v or "[]")
        except json.JSONDecodeError:
            return []
    return v or []


# ---------------------------------------------------------------------------
# export: plan -> xlsx (default) or csv fallback
# ---------------------------------------------------------------------------


@router.get("/api/plans/{pid}/export")
def export_plan(
    pid: int,
    fmt: str = Query("xlsx"),
    template_id: int | None = Query(None),
    svc: ExportService = Depends(_service),
    repo: ExportTemplateRepo = Depends(_template_repo),
    conn=Depends(get_conn),
):
    plan = svc._plan(pid)  # noqa: SLF001
    template = None
    if template_id:
        try:
            template = repo.get(template_id)
        except AppError:
            pass
    if fmt == "csv":
        content = svc.to_csv(pid)
        return Response(
            content=content,
            media_type=MEDIA_CSV,
            headers={
                "Content-Disposition": content_disposition(
                    f"plan-{pid}-{plan['algorithm']}.csv"
                )
            },
        )
    content = svc.to_xlsx(pid, template=template)
    fname = f"plan-{pid}-{plan['algorithm']}.xlsx"
    return Response(
        content=content,
        media_type=MEDIA_XLSX,
        headers={"Content-Disposition": content_disposition(fname)},
    )


# ---------------------------------------------------------------------------
# export templates
# ---------------------------------------------------------------------------


@router.get("/api/export-templates")
def list_templates(repo: ExportTemplateRepo = Depends(_template_repo)):
    out = []
    for t in repo.list_all():
        t["columns_json"] = _load_cols(t.get("columns_json"))
        out.append(t)
    return ok(out)


@router.post("/api/export-templates")
def create_template(
    body: Any = Body(...),
    repo: ExportTemplateRepo = Depends(_template_repo),
):
    try:
        t = repo.create(body)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
    t["columns_json"] = _load_cols(t.get("columns_json"))
    return ok(t)


@router.put("/api/export-templates/{tid}")
def update_template(
    tid: int,
    body: Any = Body(...),
    repo: ExportTemplateRepo = Depends(_template_repo),
):
    if "columns_json" in body and isinstance(body.get("columns_json"), str):
        body["columns_json"] = _load_cols(body["columns_json"])
    try:
        t = repo.update(tid, body)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
    t["columns_json"] = _load_cols(t.get("columns_json"))
    return ok(t)


@router.delete("/api/export-templates/{tid}")
def delete_template(
    tid: int,
    repo: ExportTemplateRepo = Depends(_template_repo),
):
    try:
        repo.delete(tid)
        return ok(True)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
