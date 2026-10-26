"""Jobs service: run packing computations in a worker thread, persist
results to SQLite, track in-memory progress / ETA.

Job identity is the packing_run row id; the in-memory registry survives
the request cycle, and GET /jobs/{id} falls back to the DB view when the
in-memory state is gone (e.g. after a restart).
"""

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.errors import AppError, ConflictError
from app.importing import complete_rows
from app.repos import ImportRowRepo, TaskRepo
from packing_engine import normalize, runner
from packing_engine.place import ProgressReporter
from packing_engine import place2 as _place2  # noqa: F401  (registers algos)
from packing_engine import ALGORITHMS
from packing_engine.model import ContainerInstance

DEFAULT_ALGORITHMS = ["dblf", "maxspace", "extreme_point", "wall_build", "guillotine", "freemix"]


@dataclass
class JobState:
    run_id: int
    task_id: int
    status: str = "running"
    algorithms: list = field(default_factory=list)
    progress: dict = field(default_factory=dict)
    eta_seconds: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None
    plans: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.run_id,
            "task_id": self.task_id,
            "status": self.status,
            "algorithms": self.algorithms,
            "progress": dict(self.progress),
            "eta_seconds": dict(self.eta_seconds),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "plan_ids": [p["id"] for p in self.plans],
        }


_REGISTRY: dict[int, JobState] = {}
_REGISTRY_LOCK = threading.Lock()
_WRITE_LOCK = threading.Lock()


def get_job_state(run_id: int) -> JobState | None:
    with _REGISTRY_LOCK:
        return _REGISTRY.get(run_id)


def run_status_from_db(conn: sqlite3.Connection, run_id: int) -> dict:
    row = dict(
        conn.execute("SELECT * FROM packing_run WHERE id = ?", (run_id,)).fetchone()
    )
    if row is None:
        return {}
    plans = [
        dict(r)
        for r in conn.execute(
            "SELECT id, algorithm, is_adopted, kpi_json, created_ms FROM packing_plan WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
    ]
    for p in plans:
        p["kpi"] = json.loads(p.pop("kpi_json") or "{}")
        p["container_count"] = conn.execute(
            "SELECT COUNT(*) AS n FROM container_instance WHERE plan_id = ?",
            (p["id"],),
        ).fetchone()["n"]
    return {"run": row, "plans": plans}


class JobsService:
    def __init__(self, conn: sqlite3.Connection, db_path: str | Path | None = None):
        self.conn = conn
        self.db_path = db_path

    # ------------------------------------------------------------------
    # start
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_container_mode(task: dict) -> dict:
        """Parse container_mode_json into a normalized spec.

        Returns:
          fixed:  {"mode": "fixed", "specs": [(code, count), ...]}
          freemix: {"mode": "freemix", "type_lock": [...],
                    "qty_lock": {code: n}, "max_qty": {code: n}}

        Legacy shape {"type_code": "40GP", "count": 2} maps to fixed mode.
        """
        raw = task.get("container_mode_json")
        if isinstance(raw, str):
            raw = json.loads(raw or "{}")
        raw = raw or {}

        if raw.get("mode") == "freemix":
            out = {
                "mode": "freemix",
                "type_lock": list(raw.get("type_lock") or []),
                "qty_lock": {k: int(v) for k, v in (raw.get("qty_lock") or {}).items()},
                "max_qty": {k: int(v) for k, v in (raw.get("max_qty") or {}).items()},
            }
            if not out["type_lock"]:
                raise AppError("E_VALIDATION", "自由组合模式需至少勾选一个箱型", status=422)
            return out

        # fixed mode (legacy or explicit)
        specs: list[tuple[str, int]] = []
        fixed = raw.get("fixed")
        if isinstance(fixed, dict):
            for code, n in fixed.items():
                specs.append((code, int(n)))
        elif raw.get("type_code"):
            specs.append((raw["type_code"], int(raw.get("count", 1))))
        if not specs:
            raise AppError("E_VALIDATION", "固定模式需指定箱型与数量", status=422)
        for code, n in specs:
            if n < 1:
                raise AppError("E_VALIDATION", f"箱型 {code} 数量必须 ≥ 1", status=422)
        return {"mode": "fixed", "specs": specs}

    def start(self, tid: int, body: dict | None) -> JobState:
        body = body or {}
        task = TaskRepo(self.conn).get(tid)
        rows = complete_rows(self.conn, ImportRowRepo(self.conn).list_by_task(tid))
        incomplete = [r for r in rows if not r.get("complete")]
        if incomplete:
            raise AppError(
                "E_IMPORT_INCOMPLETE",
                f"{len(incomplete)} 行缺规格，无法开算",
                status=422,
            )

        algorithms = [
            a for a in (body.get("algorithms") or DEFAULT_ALGORITHMS) if a in ALGORITHMS
        ]
        if not algorithms:
            from app.errors import ConflictError

            raise ConflictError("no valid algorithms selected")

        mode = self._parse_container_mode(task)
        if "freemix" in algorithms and mode.get("mode") != "freemix":
            from app.errors import ConflictError

            raise ConflictError("freemix 算法需要自由组合模式，请先在任务中切换为自由组合模式")

        enabled_rules = body.get("enabled_rules", task.get("rules_json"))
        if isinstance(enabled_rules, str):
            enabled_rules = json.loads(enabled_rules) if enabled_rules else None
        site_groups = body.get("site_groups", task.get("site_groups_json"))
        if isinstance(site_groups, str):
            site_groups = json.loads(site_groups) if site_groups else []

        settings = self._load_settings()
        packages = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM package_master WHERE enabled = 1"
            )
        ]

        with _WRITE_LOCK:
            cur = self.conn.execute(
                "INSERT INTO packing_run (task_id, created_at, status, algorithms_json) VALUES (?, ?, 'running', ?)",
                (
                    tid,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(algorithms),
                ),
            )
            run_id = cur.lastrowid
            self.conn.execute(
                "UPDATE task SET status = 'computing' WHERE id = ?",
                (tid,),
            )
            self.conn.commit()

        job = JobState(run_id=run_id, task_id=tid, algorithms=algorithms)
        with _REGISTRY_LOCK:
            _REGISTRY[run_id] = job

        args = (
            rows,
            packages,
            settings,
            enabled_rules,
            site_groups or [],
            mode,
        )
        threading.Thread(target=self._worker, args=(job,) + args, daemon=True).start()
        return job

    # ------------------------------------------------------------------
    # worker
    # ------------------------------------------------------------------

    def _load_settings(self) -> dict:
        out: dict = {}
        for row in self.conn.execute("SELECT key, value FROM app_setting"):
            try:
                out[row["key"]] = json.loads(row["value"])
            except (ValueError, TypeError):
                out[row["key"]] = row["value"]
        return out

    @staticmethod
    def _progress_cb(job: JobState, algo: str):
        def _cb(frac: float, eta: float) -> None:
            with _REGISTRY_LOCK:
                job.progress[algo] = round(frac, 4)
                job.eta_seconds[algo] = round(eta, 2)

        return _cb

    def _worker(
        self,
        job: JobState,
        rows: list[dict],
        packages: list[dict],
        settings: dict,
        enabled_rules,
        site_groups: list,
        mode: dict,
    ) -> None:
        items = normalize.items_from_rows(
            rows, packages, float(settings.get("manual_limit_kg", 30))
        )
        catalog = self._load_catalog()

        if mode.get("mode") == "freemix":
            # one catalog prototype per type; the freemix algo does the combo search
            base = [self._catalog_proto(code, catalog) for code in mode.get("type_lock", list(catalog.keys()))]
        else:
            base = normalize.fixed_containers_multi(mode["specs"], catalog)

        locks = (
            {
                "type_lock": mode.get("type_lock"),
                "qty_lock": mode.get("qty_lock"),
                "max_qty": mode.get("max_qty"),
            }
            if mode.get("mode") == "freemix"
            else None
        )

        import packing_engine.kpi as kpi_mod

        plans: list = []
        elapsed: dict[str, float] = {}
        for name in job.algorithms:
            fn = ALGORITHMS.get(name)
            containers = [self._clone(c) for c in base]
            rep = ProgressReporter(
                total=len(items),
                deadline_s=float(settings.get("time_limit_s", 60)),
                on_progress=self._progress_cb(job, name),
            )
            t0 = time.monotonic()
            try:
                if name == "freemix":
                    plan = fn(items, containers, settings, enabled_rules, site_groups, rep, locks=locks)
                else:
                    plan = fn(items, containers, settings, enabled_rules, site_groups, rep)
            except Exception as exc:  # E_ENGINE: mark job failed, keep task intact
                self.fail(job, f"{name}: {exc}")
                return
            elapsed[name] = round(time.monotonic() - t0, 3)
            plan.algorithm = name
            plan.elapsed_s = elapsed[name]
            plans.append(plan)

        for p in plans:
            p.kpi = kpi_mod.evaluate(p, len(items), elapsed)

        self._persist(job, rows, plans, elapsed)

    @staticmethod
    def _catalog_proto(code: str, catalog: dict) -> "ContainerInstance":
        row = catalog.get(code)
        if not row:
            raise ValueError(f"container type not found: {code}")
        return ContainerInstance(
            type_code=code,
            seq_no=0,
            label=code,
            inner_l=int(row["inner_l"]),
            inner_w=int(row["inner_w"]),
            inner_h=int(row["inner_h"]),
            max_payload=float(row["max_payload"]),
            volume_m3=float(row.get("volume") or 0),
        )

    @staticmethod
    def _clone(c):
        from packing_engine.model import ContainerInstance

        return ContainerInstance(
            type_code=c.type_code,
            seq_no=c.seq_no,
            label=c.label,
            inner_l=c.inner_l,
            inner_w=c.inner_w,
            inner_h=c.inner_h,
            max_payload=c.max_payload,
            volume_m3=c.volume_m3,
        )

    def _load_catalog(self) -> dict[str, dict]:
        rows = self.conn.execute(
            "SELECT * FROM container_type WHERE enabled = 1"
        ).fetchall()
        return {r["code"]: dict(r) for r in rows}

    def _load_catalog(self) -> dict[str, dict]:
        rows = self.conn.execute(
            "SELECT * FROM container_type WHERE enabled = 1"
        ).fetchall()
        return {r["code"]: dict(r) for r in rows}

    def _worker_conn(self) -> sqlite3.Connection:
        """Return a dedicated connection for worker-thread persistence."""
        from app.db import connect
        return connect(self.db_path)

    def _persist(self, job: JobState, rows: list[dict], plans: list, elapsed: dict):
        # pair engine items (uid "r{import_row_id}") with import_row ids
        uid_to_row_id: dict[str, int] = {f"r{r['id']}": r["id"] for r in rows}
        timed_out = any(getattr(p, "timed_out", False) for p in plans)

        with _WRITE_LOCK:
            wconn = self._worker_conn()
            try:
                for p in plans:
                    plan_cur = wconn.execute(
                        "INSERT INTO packing_plan (run_id, algorithm, is_adopted, kpi_json, created_ms) VALUES (?, ?, 0, ?, ?)",
                        (
                            job.run_id,
                            p.algorithm,
                            json.dumps(p.kpi or {}),
                            int(time.time() * 1000),
                        ),
                    )
                    plan_id = plan_cur.lastrowid
                    job.plans.append(
                        {"id": plan_id, "algorithm": p.algorithm, "elapsed_s": p.elapsed_s}
                    )

                    for c in p.containers:
                        ci_cur = wconn.execute(
                            "INSERT INTO container_instance (plan_id, type_code, seq_no, label) VALUES (?, ?, ?, ?)",
                            (plan_id, c.type_code, c.seq_no, c.label),
                        )
                        ci_id = ci_cur.lastrowid
                        for pl in c.placed:
                            wconn.execute(
                                """INSERT INTO placement
                                (plan_id, container_id, import_row_id, x, y, z, dim_x, dim_y, dim_z, rotation, load_seq, unassigned_reason)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)""",
                                (
                                    plan_id,
                                    ci_id,
                                    uid_to_row_id.get(pl.item.uid),
                                    pl.x,
                                    pl.y,
                                    pl.z,
                                    pl.dx,
                                    pl.dy,
                                    pl.dz,
                                    pl.load_seq,
                                    None,
                                ),
                            )

                    for ui in p.unassigned:
                        wconn.execute(
                            """INSERT INTO placement
                            (plan_id, container_id, import_row_id, x, y, z, dim_x, dim_y, dim_z, rotation, load_seq, unassigned_reason)
                            VALUES (?, NULL, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)""",
                            (plan_id, uid_to_row_id.get(ui.uid), "未分配"),
                        )

                wconn.execute(
                    "UPDATE packing_run SET status = ? WHERE id = ?",
                    ("done", job.run_id),
                )
                wconn.execute(
                    "UPDATE task SET status = 'completed' WHERE id = ?",
                    (job.task_id,),
                )
                wconn.commit()
            finally:
                wconn.close()

        with _REGISTRY_LOCK:
            job.status = "done"
            job.finished_at = time.time()

    def fail(self, job: JobState, message: str) -> None:
        with _WRITE_LOCK:
            wconn = self._worker_conn()
            try:
                wconn.execute(
                    "UPDATE packing_run SET status = 'failed' WHERE id = ?", (job.run_id,)
                )
                wconn.execute(
                    "UPDATE task SET status = 'failed' WHERE id = ?",
                    (job.task_id,),
                )
                wconn.commit()
            finally:
                wconn.close()
        with _REGISTRY_LOCK:
            job.status = "failed"
            job.error = message
            job.finished_at = time.time()
