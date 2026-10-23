from typing import Any

from fastapi import APIRouter, Body, Depends

from app.deps import get_conn
from app.errors import AppError, ConflictError, NotFoundError
from app.jobs import JobsService, get_job_state, run_status_from_db
from app.repos import TaskRepo
from app.response import fail, ok

router = APIRouter(tags=["jobs-plans"])


def _jobs(conn=Depends(get_conn)) -> JobsService:
    return JobsService(conn)


def _task(conn=Depends(get_conn)) -> TaskRepo:
    return TaskRepo(conn)


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------


@router.post("/api/tasks/{tid}/compute")
def compute(
    tid: int,
    body: Any = Body(default=None),
    jobs: JobsService = Depends(_jobs),
    conn=Depends(get_conn),
):
    if not isinstance(body, dict):
        body = {}
    try:
        job = jobs.start(tid, body)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
    return ok(job.as_dict())


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------


@router.get("/api/jobs/{job_id}")
def get_job(job_id: int, conn=Depends(get_conn)):
    state = get_job_state(job_id)
    if state is not None:
        data = state.as_dict()
        if state.status != "running":
            db = run_status_from_db(conn, state.run_id)
            data["plans"] = db.get("plans", [])
        return ok(data)
    db = run_status_from_db(conn, job_id)
    if not db:
        return fail("E_NOT_FOUND", f"job {job_id} not found", status=404)
    run = db["run"]
    return ok(
        {
            "id": job_id,
            "task_id": run["task_id"],
            "status": run["status"],
            "algorithms": _json_list(run.get("algorithms_json")),
            "progress": {},
            "eta_seconds": {},
            "error": run.get("error"),
            "plans": db.get("plans", []),
        }
    )


def _json_list(v):
    import json

    if not v:
        return []
    try:
        out = json.loads(v)
        return out if isinstance(out, list) else [out]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# plans
# ---------------------------------------------------------------------------


@router.get("/api/tasks/{tid}/plans")
def list_plans(tid: int, conn=Depends(get_conn)):
    TaskRepo(conn).get(tid)
    rows = conn.execute(
        """SELECT p.id, p.run_id, p.algorithm, p.is_adopted, p.kpi_json, p.created_ms,
                  (SELECT COUNT(*) FROM container_instance ci WHERE ci.plan_id = p.id) AS container_count
           FROM packing_plan p
           JOIN packing_run r ON r.id = p.run_id
           WHERE r.task_id = ?
           ORDER BY p.run_id DESC, p.id""",
        (tid,),
    ).fetchall()
    import json

    out = []
    for r in rows:
        d = dict(r)
        d["kpi"] = json.loads(d.pop("kpi_json") or "{}")
        out.append(d)
    return ok(out)


@router.get("/api/plans/{pid}")
def get_plan(pid: int, conn=Depends(get_conn)):
    row = dict(
        conn.execute(
            "SELECT p.*, r.task_id FROM packing_plan p JOIN packing_run r ON r.id = p.run_id WHERE p.id = ?",
            (pid,),
        ).fetchone()
    )
    if row is None:
        return fail("E_NOT_FOUND", "plan not found", status=404)
    import json

    row["kpi"] = json.loads(row.pop("kpi_json") or "{}")
    return ok(row)


@router.get("/api/plans/{pid}/placements")
def get_placements(pid: int, conn=Depends(get_conn)):
    row = dict(
        conn.execute(
            "SELECT p.id FROM packing_plan p WHERE p.id = ?",
            (pid,),
        ).fetchone()
    )
    if row is None:
        return fail("E_NOT_FOUND", "plan not found", status=404)
    items = conn.execute(
        """SELECT pl.container_id, ci.label, pl.import_row_id,
                  ir.row_no, ir.k_pn, ir.g_packmatls,
                  pl.x, pl.y, pl.z, pl.dim_x, pl.dim_y, pl.dim_z,
                  pl.rotation, pl.load_seq, pl.unassigned_reason
           FROM placement pl
           LEFT JOIN container_instance ci ON ci.id = pl.container_id
           LEFT JOIN import_row ir ON ir.id = pl.import_row_id
           WHERE pl.plan_id = ?
           ORDER BY ci.seq_no, ci.label, pl.load_seq""",
        (pid,),
    ).fetchall()
    return ok([dict(x) for x in items])


@router.put("/api/tasks/{tid}/adopt-plan")
def adopt_plan(
    tid: int,
    body: Any = Body(...),
    conn=Depends(get_conn),
):
    plan_id = (body or {}).get("plan_id") if isinstance(body, dict) else None
    if not plan_id:
        return fail("E_VALIDATION", "plan_id is required", status=422)
    row = dict(
        conn.execute(
            "SELECT p.run_id FROM packing_plan p JOIN packing_run r ON r.id = p.run_id WHERE p.id = ? AND r.task_id = ?",
            (plan_id, tid),
        ).fetchone()
    )
    if row is None:
        return fail("E_NOT_FOUND", "plan not found for this task", status=404)
    conn.execute("UPDATE packing_plan SET is_adopted = 0 WHERE run_id = ?", (row["run_id"],))
    conn.execute("UPDATE packing_plan SET is_adopted = 1 WHERE id = ?", (plan_id,))
    TaskRepo(conn).update(tid, {"adopted_plan_id": plan_id})
    conn.commit()
    return ok({"adopted_plan_id": plan_id})
