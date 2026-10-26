from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health_envelope():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["status"] == "ok"
    assert set(body.keys()) == {"code", "message", "data"}


def test_spa_fallback_serves_index_for_frontend_routes(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    monkeypatch.setattr("app.main._STATIC", static)
    from app.main import SPAStaticFiles, app as spa_app

    spa_app.router.routes = [r for r in spa_app.router.routes if getattr(r, "name", None) != "static"]
    spa_app.mount("/", SPAStaticFiles(directory=str(static), html=True), name="static")
    c = TestClient(spa_app, raise_server_exceptions=False)
    resp = c.get("/tasks/1/import")
    assert resp.status_code == 200
    assert b"spa" in resp.content
    api = c.get("/api/health")
    assert api.status_code == 200
    assert api.json()["code"] == 0
