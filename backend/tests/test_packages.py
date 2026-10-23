import pytest
from fastapi.testclient import TestClient

from app.deps import get_conn, reset_conn_for_tests
from app.main import app


@pytest.fixture
def client(tmp_path):
    conn = reset_conn_for_tests(tmp_path / "pkg.db")
    app.dependency_overrides[get_conn] = lambda: conn
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_package_crud_and_pn_unique(client):
    created = client.post(
        "/api/packages",
        json={
            "pn": "ACW1081490*80",
            "name": "OUTCASE(VEN)",
            "package_type": "OUTCASE(VEN)",
            "l": 1200,
            "w": 800,
            "h": 900,
            "tare": 40,
            "net": 200,
            "gross": 240,
            "rotatable": 1,
            "crush_sensitive": 0,
            "same_type_stack": 0,
            "default_loading": "forklift",
        },
    )
    assert created.status_code == 200
    pid = created.json()["data"]["id"]
    listed = client.get("/api/packages").json()["data"]
    assert any(p["pn"] == "ACW1081490*80" for p in listed)
    dup = client.post("/api/packages", json={"pn": "ACW1081490*80", "name": "x"})
    assert dup.status_code == 409
    updated = client.put(f"/api/packages/{pid}", json={"enabled": 0})
    assert updated.json()["data"]["enabled"] == 0
    deleted = client.delete(f"/api/packages/{pid}")
    assert deleted.status_code == 200
