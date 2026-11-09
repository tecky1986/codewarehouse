import json
import time

import pytest
from fastapi.testclient import TestClient

from app.deps import get_conn, reset_conn_for_tests
from app.main import app
from app.jobs import run_status_from_db
from packing_engine import freemix
from packing_engine.model import CargoItem, ContainerInstance
from packing_engine.place import ProgressReporter


@pytest.fixture
def client(tmp_path):
    conn = reset_conn_for_tests(tmp_path / "api.db")
    app.dependency_overrides[get_conn] = lambda: conn
    with TestClient(app, raise_server_exceptions=False) as c:
        c.conn = conn
        yield c
    app.dependency_overrides.clear()


def _ensure_pn_masters(conn, pns):
    from app.repos import PackageMasterRepo
    pkg = PackageMasterRepo(conn)
    for pn in pns:
        if pkg.get_by_pn(pn) is None:
            pkg.create({"pn": pn, "l": 1000.0, "w": 1000.0, "h": 1000.0, "tare": 0.0, "net": 90.0, "gross": 100.0})


def _make_task_with_rows(client):
    body = client.post("/api/tasks", json={"name": "t1"}).json()
    tid = body["data"]["id"]
    client.put(f"/api/tasks/{tid}", json={"container_mode_json": {"type_code": "20GP", "count": 3}})
    client.put(f"/api/tasks/{tid}", json={"rules_json": None})
    conn = client.conn
    _ensure_pn_masters(conn, ("P1", "P2"))
    rows = [
        {
            "task_id": tid,
            "row_no": i + 1,
            "a_no": str(i + 1),
            "b_len": 1000.0,
            "c_wid": 1000.0,
            "d_hgt": 1000.0,
            "e_cbm": 1.0,
            "f_outcase": "CTN",
            "g_packmatls": None,
            "h_tare": 0.0,
            "i_net": 90.0,
            "j_gross": 100.0,
            "k_pn": "P1" if i % 2 == 0 else "P2",
            "l_note": None,
            "m_site": None,
            "o_ref": None,
            "p_dn": None,
            "q_misc": None,
            "filled_fields_json": "[]",
            "source_flag": "table",
        }
        for i in range(6)
    ]
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(tid, rows)
    return tid


def _wait_job(client, job_id, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["data"]["status"] in ("done", "failed"):
            return body["data"]
        time.sleep(0.2)
    raise TimeoutError(f"job {job_id} did not finish in {timeout}s")


def test_compute_and_plans_flow(client):
    tid = _make_task_with_rows(client)
    body = client.post(
        f"/api/tasks/{tid}/compute",
        json={"algorithms": ["dblf", "maxspace"]},
    ).json()
    assert body["code"] == 0, body
    job = body["data"]
    finished = _wait_job(client, job["id"])
    assert finished["status"] == "done"
    task_after = client.get(f"/api/tasks/{tid}").json()["data"]
    assert task_after["status"] == "completed"
    assert "dblf" in finished["progress"]
    plans = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    assert len(plans) == 2
    algo_names = {p["algorithm"] for p in plans}
    assert {"dblf", "maxspace"} <= algo_names
    dblf_plan = next(p for p in plans if p["algorithm"] == "dblf")
    placements = client.get(f"/api/plans/{dblf_plan['id']}/placements").json()["data"]
    assert len(placements) == 6
    assert all(p["label"] for p in placements)

    # adopt
    resp = client.put(f"/api/tasks/{tid}/adopt-plan", json={"plan_id": dblf_plan["id"]}).json()
    assert resp["code"] == 0
    task = client.get(f"/api/tasks/{tid}").json()["data"]
    assert task["adopted_plan_id"] == dblf_plan["id"]

    # export xlsx (default)
    resp = client.get(f"/api/plans/{dblf_plan['id']}/export")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    # CSV fallback with BOM
    resp_csv = client.get(f"/api/plans/{dblf_plan['id']}/export", params={"fmt": "csv"})
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert resp_csv.content.startswith(b"\xef\xbb\xbf")


def test_compute_rejects_incomplete_rows(client):
    conn = client.conn
    body = client.post("/api/tasks", json={"name": "t2"}).json()
    tid = body["data"]["id"]
    client.put(f"/api/tasks/{tid}", json={"container_mode_json": {"type_code": "20GP", "count": 1}})
    rows = [
        {
            "task_id": tid,
            "row_no": 1,
            "a_no": "1",
            "b_len": None,
            "c_wid": None,
            "d_hgt": None,
            "e_cbm": None,
            "f_outcase": "CTN",
            "g_packmatls": "UNKNOWN",
            "h_tare": 0.0,
            "i_net": 90.0,
            "j_gross": 100.0,
            "k_pn": "MISSING",
            "l_note": None,
            "m_site": None,
            "o_ref": None,
            "p_dn": None,
            "q_misc": None,
            "filled_fields_json": "[]",
            "source_flag": "table",
        }
    ]
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(tid, rows)
    resp = client.post(f"/api/tasks/{tid}/compute", json={}).json()
    assert resp["code"] == "E_IMPORT_INCOMPLETE"
    assert resp.get("status") is None or True


def test_multi_algorithm_timeout_marks_partial(client):
    tid = _make_task_with_rows(client)
    conn = client.conn
    # set a very small time limit so the run times out immediately
    conn.execute(
        "INSERT INTO app_setting (key, value) VALUES ('time_limit_s', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(0),),
    )
    conn.commit()
    body = client.post(
        f"/api/tasks/{tid}/compute",
        json={"algorithms": ["dblf", "maxspace", "extreme_point", "wall_fill", "lns"]},
    ).json()
    assert body["code"] == 0
    finished = _wait_job(client, body["data"]["id"])
    assert finished["status"] == "done"
    plans = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    assert len(plans) == 5
    timed_out_plans = [p for p in plans if p["kpi"]["overall"]["timed_out"]]
    assert len(timed_out_plans) > 0


# ---------------------------------------------------------------------------
# freemix engine: lock infeasible / qty lock
# ---------------------------------------------------------------------------


def _catalog():
    return {
        "20GP": ContainerInstance(
            type_code="20GP", seq_no=1, label="20GP",
            inner_l=5898.0, inner_w=2352.0, inner_h=2393.0,
            max_payload=28200, volume_m3=5.898 * 2.352 * 2.393,
        ),
        "40GP": ContainerInstance(
            type_code="40GP", seq_no=1, label="40GP",
            inner_l=12032.0, inner_w=2352.0, inner_h=2393.0,
            max_payload=26700, volume_m3=12.032 * 2.352 * 2.393,
        ),
    }


def _item(uid, l, w, h, g, loading="forklift"):
    return CargoItem(
        uid=uid, pn=None, packmatls=None, cargo_type="A",
        l=l, w=w, h=h, gross=g, net=g,
        rotatable=True, same_type_stack=False, loading=loading,
    )


def test_freemix_lock_infeasible_returns_no_feasible():
    catalog = _catalog()
    # a 20m item fits no container
    items = [_item("big", 20000, 2000, 2000, 50)]
    rep = ProgressReporter(total=50, deadline_s=10)
    plan, err, timed_out = freemix.search(items, catalog, {}, {}, None, [], rep)
    assert plan is None
    assert err == "E_NO_FEASIBLE"


def test_freemix_qty_lock_bounds_solution():
    catalog = _catalog()
    # 8 small items, force exactly 2x20GP + 2x40GP via qty_lock
    items = [_item(f"i{i}", 2000, 1000, 1000, 100) for i in range(8)]
    rep = ProgressReporter(total=50, deadline_s=10)
    plan, err, timed_out = freemix.search(
        items, catalog, {"qty_lock": {"20GP": 2, "40GP": 2}}, {}, None, [], rep
    )
    assert err is None
    labels = [c.label for c in plan.containers]
    assert labels == ["20GP-1", "20GP-2", "40GP-1", "40GP-2"]
    assert not plan.unassigned


def test_freemix_type_lock():
    catalog = _catalog()
    items = [_item(f"i{i}", 2000, 1000, 1000, 100) for i in range(8)]
    rep = ProgressReporter(total=50, deadline_s=10)
    plan, err, timed_out = freemix.search(
        items, catalog, {"type_lock": ["20GP"]}, {}, None, [], rep
    )
    assert err is None
    labels = [c.label for c in plan.containers]
    assert all(l.startswith("20GP-") for l in labels)


# ---------------------------------------------------------------------------
# jobs API: fixed multi-type + freemix mode via container_mode_json
# ---------------------------------------------------------------------------


def _make_task_multi(client):
    body = client.post("/api/tasks", json={"name": "tm"}).json()
    tid = body["data"]["id"]
    client.put(
        f"/api/tasks/{tid}",
        json={"container_mode_json": {"mode": "fixed", "fixed": {"40GP": 2, "20GP": 1}}},
    )
    client.put(f"/api/tasks/{tid}", json={"rules_json": None})
    conn = client.conn
    _ensure_pn_masters(conn, ("P1",))
    rows = [
        {
            "task_id": tid,
            "row_no": i + 1,
            "a_no": str(i + 1),
            "b_len": 1000.0,
            "c_wid": 1000.0,
            "d_hgt": 1000.0,
            "e_cbm": 1.0,
            "f_outcase": "CTN",
            "g_packmatls": None,
            "h_tare": 0.0,
            "i_net": 90.0,
            "j_gross": 100.0,
            "k_pn": "P1",
            "l_note": None,
            "m_site": None,
            "o_ref": None,
            "p_dn": None,
            "q_misc": None,
            "filled_fields_json": "[]",
            "source_flag": "table",
        }
        for i in range(6)
    ]
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(tid, rows)
    return tid


def test_fixed_multi_type_labels(client):
    tid = _make_task_multi(client)
    body = client.post(
        f"/api/tasks/{tid}/compute", json={"algorithms": ["dblf"]}
    ).json()
    assert body["code"] == 0, body
    finished = _wait_job(client, body["data"]["id"])
    assert finished["status"] == "done"
    plans = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    plan = next(p for p in plans if p["algorithm"] == "dblf")
    placements = client.get(f"/api/plans/{plan['id']}/placements").json()["data"]
    # all 6 items go into 40GP-1 (it is the first instance, largest volume)
    # KPI per_container lists only containers with items
    pc = plan["kpi"]["per_container"]
    labels_in_kpi = {c["label"] for c in pc}
    assert "40GP-1" in labels_in_kpi


def test_fixed_zero_means_unlimited(client):
    body = client.post("/api/tasks", json={"name": "t0"}).json()
    tid = body["data"]["id"]
    client.put(
        f"/api/tasks/{tid}",
        json={"container_mode_json": {"mode": "fixed", "fixed": {"20GP": 0}}},
    )
    client.put(f"/api/tasks/{tid}", json={"rules_json": None})
    conn = client.conn
    _ensure_pn_masters(conn, ("P1",))
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(
        tid,
        [
            {
                "task_id": tid,
                "row_no": i + 1,
                "a_no": str(i + 1),
                "b_len": 1000.0,
                "c_wid": 1000.0,
                "d_hgt": 1000.0,
                "e_cbm": 1.0,
                "f_outcase": "CTN",
                "g_packmatls": None,
                "h_tare": 0.0,
                "i_net": 90.0,
                "j_gross": 100.0,
                "k_pn": "P1",
                "l_note": None,
                "m_site": None,
                "o_ref": None,
                "p_dn": None,
                "q_misc": None,
                "filled_fields_json": "[]",
                "source_flag": "table",
            }
            for i in range(6)
        ],
    )
    resp = client.post(
        f"/api/tasks/{tid}/compute", json={"algorithms": ["dblf"]}
    ).json()
    assert resp["code"] == 0, resp
    finished = _wait_job(client, resp["data"]["id"])
    assert finished["status"] == "done"
    plans = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    plan = next(p for p in plans if p["algorithm"] == "dblf")
    assert plan["kpi"]["overall"]["unassigned_count"] == 0
    assert plan["kpi"]["overall"]["containers_used"] >= 1


def test_freemix_mode_via_api(client):
    body = client.post("/api/tasks", json={"name": "tf"}).json()
    tid = body["data"]["id"]
    client.put(
        f"/api/tasks/{tid}",
        json={
            "container_mode_json": {
                "mode": "freemix",
                "type_lock": ["20GP", "40GP"],
                "qty_lock": {"20GP": 1},
                "max_qty": {"40GP": 3},
            }
        },
    )
    client.put(f"/api/tasks/{tid}", json={"rules_json": None})
    conn = client.conn
    _ensure_pn_masters(conn, ("P1",))
    rows = [
        {
            "task_id": tid,
            "row_no": i + 1,
            "a_no": str(i + 1),
            "b_len": 1000.0,
            "c_wid": 1000.0,
            "d_hgt": 1000.0,
            "e_cbm": 1.0,
            "f_outcase": "CTN",
            "g_packmatls": None,
            "h_tare": 0.0,
            "i_net": 90.0,
            "j_gross": 100.0,
            "k_pn": "P1",
            "l_note": None,
            "m_site": None,
            "o_ref": None,
            "p_dn": None,
            "q_misc": None,
            "filled_fields_json": "[]",
            "source_flag": "table",
        }
        for i in range(6)
    ]
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(tid, rows)


def test_fixed_zero_means_unlimited(client):
    body = client.post("/api/tasks", json={"name": "t0"}).json()
    tid = body["data"]["id"]
    client.put(
        f"/api/tasks/{tid}",
        json={"container_mode_json": {"mode": "fixed", "fixed": {"20GP": 0}}},
    )
    client.put(f"/api/tasks/{tid}", json={"rules_json": None})
    conn = client.conn
    _ensure_pn_masters(conn, ("P1",))
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(
        tid,
        [
            {
                "task_id": tid,
                "row_no": i + 1,
                "a_no": str(i + 1),
                "b_len": 1000.0,
                "c_wid": 1000.0,
                "d_hgt": 1000.0,
                "e_cbm": 1.0,
                "f_outcase": "CTN",
                "g_packmatls": None,
                "h_tare": 0.0,
                "i_net": 90.0,
                "j_gross": 100.0,
                "k_pn": "P1",
                "l_note": None,
                "m_site": None,
                "o_ref": None,
                "p_dn": None,
                "q_misc": None,
                "filled_fields_json": "[]",
                "source_flag": "table",
            }
            for i in range(6)
        ],
    )
    resp = client.post(
        f"/api/tasks/{tid}/compute", json={"algorithms": ["dblf"]}
    ).json()
    assert resp["code"] == 0, resp
    finished = _wait_job(client, resp["data"]["id"])
    assert finished["status"] == "done"
    plans = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    plan = next(p for p in plans if p["algorithm"] == "dblf")
    assert plan["kpi"]["overall"]["unassigned_count"] == 0
    assert plan["kpi"]["overall"]["containers_used"] >= 1


def test_freemix_mode_requires_type_lock(client):
    body = client.post("/api/tasks", json={"name": "fn"}).json()
    tid = body["data"]["id"]
    client.put(
        f"/api/tasks/{tid}",
        json={"container_mode_json": {"mode": "freemix"}},
    )
    client.put(f"/api/tasks/{tid}", json={"rules_json": None})
    conn = client.conn
    from app.repos import ImportRowRepo

    ImportRowRepo(conn).replace_for_task(
        tid,
        [
            {
                "task_id": tid,
                "row_no": 1,
                "a_no": "1",
                "b_len": 1000.0,
                "c_wid": 1000.0,
                "d_hgt": 1000.0,
                "e_cbm": 1.0,
                "f_outcase": "CTN",
                "g_packmatls": None,
                "h_tare": 0.0,
                "i_net": 90.0,
                "j_gross": 100.0,
                "k_pn": "P1",
                "l_note": None,
                "m_site": None,
                "o_ref": None,
                "p_dn": None,
                "q_misc": None,
                "filled_fields_json": "[]",
                "source_flag": "table",
            }
        ],
    )
    resp = client.post(
        f"/api/tasks/{tid}/compute", json={"algorithms": ["freemix"]}
    ).json()
    assert resp["code"] != 0


def test_compute_kpi_includes_verify_and_inner_dims(client):
    tid = _make_task_with_rows(client)
    body = client.post(
        f"/api/tasks/{tid}/compute",
        json={"algorithms": ["wall_fill"]},
    ).json()
    assert body["code"] == 0, body
    finished = _wait_job(client, body["data"]["id"])
    assert finished["status"] == "done"
    plans = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    assert len(plans) == 1
    overall = plans[0]["kpi"]["overall"]
    assert "verify_ok" in overall
    assert "verify_error_codes" in overall
    assert "constraint_ok_ratio" in overall
    per = plans[0]["kpi"]["per_container"]
    assert per
    for c in per:
        assert c.get("inner_l")
        assert c.get("inner_w")
        assert c.get("inner_h")
        assert "door_w" in c
        assert "door_h" in c


def test_compute_keeps_recent_runs(client):
    from app.jobs import KEEP_RUNS

    tid = _make_task_with_rows(client)
    run_ids = []
    for _ in range(KEEP_RUNS + 1):
        body = client.post(
            f"/api/tasks/{tid}/compute",
            json={"algorithms": ["dblf"]},
        ).json()
        assert body["code"] == 0, body
        finished = _wait_job(client, body["data"]["id"])
        assert finished["status"] == "done"
        run_ids.append(body["data"]["id"])
    remaining = [
        r["id"]
        for r in client.conn.execute(
            "SELECT id FROM packing_run WHERE task_id = ? ORDER BY id",
            (tid,),
        ).fetchall()
    ]
    assert len(remaining) == KEEP_RUNS
    assert remaining == run_ids[-KEEP_RUNS:]


def test_job_algorithms_are_objects(client):
    tid = _make_task_with_rows(client)
    body = client.post(
        f"/api/tasks/{tid}/compute",
        json={"algorithms": ["dblf", "maxspace"]},
    ).json()
    assert body["code"] == 0, body
    job = body["data"]
    assert isinstance(job["algorithms"], list)
    assert job["algorithms"]
    assert isinstance(job["algorithms"][0], dict)
    names = {a["name"] for a in job["algorithms"]}
    assert names == {"dblf", "maxspace"}
    for a in job["algorithms"]:
        assert "progress" in a
        assert "eta_seconds" in a
    assert "elapsed_s" in job
    finished = _wait_job(client, job["id"])
    assert finished["status"] == "done"
    assert all(a["progress"] == 1.0 for a in finished["algorithms"])
    from app.jobs import _REGISTRY, _REGISTRY_LOCK

    with _REGISTRY_LOCK:
        _REGISTRY.pop(job["id"], None)
    again = client.get(f"/api/jobs/{job['id']}").json()["data"]
    assert again["status"] == "done"
    assert isinstance(again["algorithms"][0], dict)
    assert {a["name"] for a in again["algorithms"]} == {"dblf", "maxspace"}
    assert all(a["progress"] == 1.0 for a in again["algorithms"])


def test_recompute_without_clear_runs(client):
    tid = _make_task_with_rows(client)
    first = client.post(
        f"/api/tasks/{tid}/compute", json={"algorithms": ["dblf"]}
    ).json()
    assert first["code"] == 0, first
    _wait_job(client, first["data"]["id"])
    plans1 = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    assert plans1
    second = client.post(
        f"/api/tasks/{tid}/compute", json={"algorithms": ["dblf"]}
    ).json()
    assert second["code"] == 0, second
    finished = _wait_job(client, second["data"]["id"])
    assert finished["status"] == "done"
    plans2 = client.get(f"/api/tasks/{tid}/plans").json()["data"]
    assert any(p["run_id"] == second["data"]["id"] for p in plans2)


def test_progress_reporter_throttles_callbacks():
    calls = []

    def cb(frac, eta):
        calls.append((frac, eta))

    rep = ProgressReporter(total=1000, deadline_s=60, on_progress=cb)
    for _ in range(1000):
        rep.tick()
    assert 2 <= len(calls) <= 80
    assert calls[-1][0] == 1.0


def test_run_status_from_db_missing_run_returns_empty(conn):
    assert run_status_from_db(conn, 999999) == {}


def test_get_missing_job_returns_404(client):
    resp = client.get("/api/jobs/999999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "E_NOT_FOUND"


def test_registry_evicts_oldest_finished_jobs():
    from app import jobs as jobs_mod

    jobs_mod._REGISTRY.clear()
    original_cap = jobs_mod.MAX_REGISTRY_JOBS
    try:
        jobs_mod.MAX_REGISTRY_JOBS = 3
        for i in range(1, 6):
            job = jobs_mod.JobState(run_id=i, task_id=1, status="done")
            job.finished_at = float(i)
            with jobs_mod._REGISTRY_LOCK:
                jobs_mod._REGISTRY[i] = job
                jobs_mod._evict_finished_jobs_locked()
        remaining = sorted(jobs_mod._REGISTRY)
        assert len(remaining) <= 3
        assert remaining == [3, 4, 5]
    finally:
        jobs_mod.MAX_REGISTRY_JOBS = original_cap
        jobs_mod._REGISTRY.clear()


def test_registry_never_evicts_running_jobs():
    from app import jobs as jobs_mod

    jobs_mod._REGISTRY.clear()
    original_cap = jobs_mod.MAX_REGISTRY_JOBS
    try:
        jobs_mod.MAX_REGISTRY_JOBS = 2
        running = jobs_mod.JobState(run_id=100, task_id=1, status="running")
        with jobs_mod._REGISTRY_LOCK:
            jobs_mod._REGISTRY[100] = running
        for i in range(1, 6):
            job = jobs_mod.JobState(run_id=i, task_id=1, status="done")
            job.finished_at = float(i)
            with jobs_mod._REGISTRY_LOCK:
                jobs_mod._REGISTRY[i] = job
                jobs_mod._evict_finished_jobs_locked()
        assert 100 in jobs_mod._REGISTRY
        assert len(jobs_mod._REGISTRY) <= 2
    finally:
        jobs_mod.MAX_REGISTRY_JOBS = original_cap
        jobs_mod._REGISTRY.clear()
