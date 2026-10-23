import pytest

from app.errors import ConflictError, InUseError, NotFoundError
from app.repos import ContainerTypeRepo, PackageMasterRepo, TaskRepo


def test_container_type_unique_code(conn):
    repo = ContainerTypeRepo(conn)
    repo.create(
        {
            "code": "40GP",
            "name": "40GP",
            "inner_l": 12032,
            "inner_w": 2352,
            "inner_h": 2393,
            "max_payload": 26700,
        }
    )
    with pytest.raises(ConflictError):
        repo.create(
            {
                "code": "40GP",
                "name": "dup",
                "inner_l": 1,
                "inner_w": 1,
                "inner_h": 1,
                "max_payload": 1,
            }
        )


def test_container_type_volume_auto(conn):
    repo = ContainerTypeRepo(conn)
    row = repo.create(
        {
            "code": "20GP",
            "name": "20GP",
            "inner_l": 5898,
            "inner_w": 2352,
            "inner_h": 2393,
            "max_payload": 28200,
        }
    )
    expected = 5898 * 2352 * 2393 / 1_000_000_000
    assert abs(row["volume"] - expected) < 1e-9


def test_container_type_referenced_cannot_delete(conn):
    ct = ContainerTypeRepo(conn)
    created = ct.create(
        {
            "code": "40HQ",
            "name": "40HQ",
            "inner_l": 12032,
            "inner_w": 2352,
            "inner_h": 2698,
            "max_payload": 26700,
        }
    )
    task = TaskRepo(conn).create({"name": "ref-task"})
    conn.execute(
        """INSERT INTO packing_run (task_id, created_at, status, algorithms_json)
           VALUES (?, 't', 'done', '[]')""",
        (task["id"],),
    )
    conn.execute(
        "INSERT INTO packing_plan (run_id, algorithm, is_adopted, kpi_json, created_ms) VALUES (1, 'dblf', 0, '{}', 0)"
    )
    conn.execute(
        "INSERT INTO container_instance (plan_id, type_code, seq_no, label) VALUES (1, '40HQ', 1, '40HQ-1')"
    )
    conn.commit()
    with pytest.raises(InUseError):
        ct.delete(created["id"])
    ct.update(created["id"], {"enabled": 0})
    assert ct.get(created["id"])["enabled"] == 0


def test_task_round_trip(conn):
    repo = TaskRepo(conn)
    created = repo.create(
        {
            "name": "样表任务",
            "params_json": {"time_limit_s": 60},
            "rules_json": ["site_together", "pn_continuous"],
            "site_groups_json": [],
            "container_mode_json": {"mode": "fixed", "type": "40GP", "count": 1},
        }
    )
    loaded = repo.get(created["id"])
    assert loaded["name"] == "样表任务"
    assert loaded["status"] == "draft"
    assert "time_limit_s" in loaded["params_json"]
    updated = repo.update(created["id"], {"status": "ready", "name": "样表任务-2"})
    assert updated["status"] == "ready"
    assert updated["name"] == "样表任务-2"
    repo.delete(created["id"])
    with pytest.raises(NotFoundError):
        repo.get(created["id"])


def test_package_pn_unique_when_filled(conn):
    repo = PackageMasterRepo(conn)
    repo.create({"pn": "ACW1081490*80", "name": "VEN", "l": 1000, "w": 800, "h": 600})
    with pytest.raises(ConflictError):
        repo.create({"pn": "ACW1081490*80", "name": "dup"})
    blank1 = repo.create({"pn": None, "name": "tmp-a"})
    blank2 = repo.create({"pn": None, "name": "tmp-b"})
    assert blank1["id"] != blank2["id"]
