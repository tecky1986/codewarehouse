from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.deps import get_conn, reset_conn_for_tests
from app.main import app
from app.repos import ContainerTypeRepo, TaskRepo


@pytest.fixture
def client(tmp_path):
    conn = reset_conn_for_tests(tmp_path / "api.db")
    app.dependency_overrides[get_conn] = lambda: conn
    with TestClient(app, raise_server_exceptions=False) as c:
        c.conn = conn
        yield c
    app.dependency_overrides.clear()


def test_preset_three_types(client):
    body = client.get("/api/container-types").json()
    assert body["code"] == 0
    codes = {r["code"] for r in body["data"]}
    assert {"20GP", "40GP", "40HQ"} <= codes
    gp20 = next(r for r in body["data"] if r["code"] == "20GP")
    assert gp20["inner_l"] == 5898
    assert gp20["inner_w"] == 2352
    assert gp20["inner_h"] == 2393
    assert gp20["max_payload"] == 28200
    assert gp20["enabled"] == 1


def test_code_conflict(client):
    resp = client.post(
        "/api/container-types",
        json={
            "code": "40GP",
            "name": "dup",
            "inner_l": 1,
            "inner_w": 1,
            "inner_h": 1,
            "max_payload": 1,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "E_CONFLICT"


def test_positive_validation(client):
    resp = client.post(
        "/api/container-types",
        json={
            "code": "BAD",
            "name": "bad",
            "inner_l": 0,
            "inner_w": 1,
            "inner_h": 1,
            "max_payload": 1,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "E_VALIDATION"


def test_volume_override(client):
    created = client.post(
        "/api/container-types",
        json={
            "code": "OT",
            "name": "other",
            "inner_l": 1000,
            "inner_w": 1000,
            "inner_h": 1000,
            "max_payload": 1000,
            "volume": 9.9,
        },
    ).json()["data"]
    assert created["volume"] == 9.9
    auto = client.post(
        "/api/container-types",
        json={
            "code": "OT2",
            "name": "other2",
            "inner_l": 1000,
            "inner_w": 1000,
            "inner_h": 1000,
            "max_payload": 1000,
        },
    ).json()["data"]
    assert abs(auto["volume"] - 1.0) < 1e-9


def test_referenced_cannot_delete(client):
    repo = ContainerTypeRepo(client.conn)
    row = repo.get_by_code("40HQ")
    task = TaskRepo(client.conn).create({"name": "ref"})
    client.conn.execute(
        "INSERT INTO packing_run (task_id, created_at, status, algorithms_json) VALUES (?, 't', 'done', '[]')",
        (task["id"],),
    )
    client.conn.execute(
        "INSERT INTO packing_plan (run_id, algorithm, is_adopted, kpi_json, created_ms) VALUES (1, 'dblf', 0, '{}', 0)"
    )
    client.conn.execute(
        "INSERT INTO container_instance (plan_id, type_code, seq_no, label) VALUES (1, '40HQ', 1, '40HQ-1')"
    )
    client.conn.commit()
    resp = client.delete(f"/api/container-types/{row['id']}")
    assert resp.status_code == 409
    assert resp.json()["code"] == "E_IN_USE"


def test_excel_import_export(client):
    exported = client.get("/api/container-types/export")
    assert exported.status_code == 200
    assert "spreadsheetml" in exported.headers["content-type"]

    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "code",
            "name",
            "iso_code",
            "inner_l",
            "inner_w",
            "inner_h",
            "door_w",
            "door_h",
            "max_payload",
            "tare_weight",
            "volume",
            "enabled",
            "remark",
        ]
    )
    ws.append(["45HQ", "45HQ", "L5G1", 13556, 2352, 2698, 2340, 2585, 25800, 4800, None, 1, "imp"])
    buf = BytesIO()
    wb.save(buf)
    resp = client.post(
        "/api/container-types/import",
        files={
            "file": (
                "t.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    codes = {r["code"] for r in client.get("/api/container-types").json()["data"]}
    assert "45HQ" in codes
