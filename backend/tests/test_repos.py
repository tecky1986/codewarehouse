import pytest

from app.errors import ConflictError, InUseError, NotFoundError
from app.repos import ContainerTypeRepo, PackageMasterRepo, TaskRepo, pn_wildcard_match


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


# ---- PN wildcard matching -----------------------------------------------

def test_wildcard_match_fn():
    # ? = any number of any chars
    assert pn_wildcard_match("ACW?80", "ACW108149080")
    assert pn_wildcard_match("ACW?", "ACW")
    assert pn_wildcard_match("A?B", "AB")
    assert pn_wildcard_match("A?B", "A123B")
    assert not pn_wildcard_match("A?B", "A123C")
    # # = exactly one char per #
    assert pn_wildcard_match("AB#CD", "ABxCD")
    assert not pn_wildcard_match("AB#CD", "AB12CD")
    assert pn_wildcard_match("AB##CD", "AB12CD")
    assert not pn_wildcard_match("AB##CD", "AB1CD")
    assert pn_wildcard_match("A##B", "A12B")
    # no wildcards = exact only
    assert pn_wildcard_match("EXACT", "EXACT")
    assert not pn_wildcard_match("EXACT", "exact")
    assert not pn_wildcard_match("AB", "ABC")
    # combined
    assert pn_wildcard_match("A?##B", "AX12B")
    assert not pn_wildcard_match("A?##B", "AX1B4")


def test_get_by_pn_wildcard(conn):
    repo = PackageMasterRepo(conn)
    # exact PN wins over wildcard
    exact = repo.create({"pn": "ACW1081", "name": "exact-match", "l": 100, "w": 100, "h": 100})
    # ? wildcard: ACW?1 matches ACW101, ACW1081, ACW9991, etc.
    wild_q = repo.create({"pn": "ACW?1", "name": "q-match", "l": 200, "w": 200, "h": 200})
    # # wildcard: P#N## matches P1N23 (one # = one char, two ## = two chars)
    multi = repo.create({"pn": "P#N##", "name": "multi-hash", "l": 300, "w": 300, "h": 300})

    # exact match still works and takes priority
    r = repo.get_by_pn("ACW1081")
    assert r["id"] == exact["id"]

    # ? wildcard matches any-length fill
    r2 = repo.get_by_pn("ACW1091")
    assert r2["id"] == wild_q["id"]
    assert r2["name"] == "q-match"

    # # multi-char pattern
    r3 = repo.get_by_pn("P1N23")
    assert r3["id"] == multi["id"]
    assert r3["name"] == "multi-hash"

    # no match
    assert repo.get_by_pn("ZZZZZ") is None
    assert repo.get_by_pn("") is None


def test_upsert_does_not_match_wildcard(conn):
    repo = PackageMasterRepo(conn)
    # ? matches any chars: ABC?DEF matches ABC1DEF, ABCDEF, ABC123456DEF, etc.
    repo.create({"pn": "ABC?DEF", "name": "wild", "l": 1, "w": 1, "h": 1})
    # upserting an exact PN should create a NEW row, not update the wildcard
    created = repo.upsert({"pn": "ABC1DEF", "name": "new", "l": 2, "w": 2, "h": 2})
    rows = repo.list_all()
    assert len(rows) == 2
    assert any(r["pn"] == "ABC1DEF" for r in rows)
