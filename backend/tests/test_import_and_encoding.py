from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.deps import get_conn, reset_conn_for_tests
from app.encoding import content_disposition, csv_bytes, decode_bytes
from app.main import app

SAMPLE = Path("/workspace/.monkeycode-tmp-files/d340e47a-Step3Output-1.xlsx")
_need_sample = pytest.mark.skipif(not SAMPLE.exists(), reason="SAMPLE xlsx not available")


@pytest.fixture
def client(tmp_path):
    conn = reset_conn_for_tests(tmp_path / "imp.db")
    app.dependency_overrides[get_conn] = lambda: conn
    with TestClient(app, raise_server_exceptions=False) as c:
        c.conn = conn
        yield c
    app.dependency_overrides.clear()


def _create_task(client, name="t"):
    return client.post("/api/tasks", json={"name": name}).json()["data"]["id"]


@_need_sample
def test_sample_ib1_uses_table_values(client):
    tid = _create_task(client)
    resp = client.post(
        f"/api/tasks/{tid}/import",
        files={
            "file": (
                "Step3Output-1.xlsx",
                SAMPLE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    ib1 = [r for r in body["rows"] if r["g_packmatls"] == "OUTCASE(IB-1)"]
    assert len(ib1) == 2
    assert ib1[0]["b_len"] == 1460
    assert ib1[0]["c_wid"] == 1150
    assert ib1[0]["d_hgt"] == 1100
    assert ib1[0]["j_gross"] == 392
    assert ib1[0]["source_flag"] == "table"
    ven = [r for r in body["rows"] if r["g_packmatls"] == "OUTCASE(VEN)"]
    assert all(not r["complete"] for r in ven)
    assert body["can_compute"] is False
    assert any(m["pn"] == "ACW1081490*80" for m in body["missing"])


@_need_sample
def test_ven_filled_by_pn(client):
    client.post(
        "/api/packages",
        json={
            "pn": "ACW1081490*80",
            "name": "OUTCASE(VEN)",
            "package_type": "OUTCASE(VEN)",
            "l": 1110,
            "w": 800,
            "h": 900,
            "tare": 10,
            "net": 20,
            "gross": 30,
            "enabled": 1,
        },
    )
    client.post(
        "/api/packages",
        json={
            "name": "OUTCASE(IB-1)",
            "package_type": "OUTCASE(IB-1)",
            "l": 1460,
            "w": 1150,
            "h": 1100,
            "tare": 5,
            "net": 50,
            "gross": 392,
            "enabled": 1,
        },
    )
    tid = _create_task(client)
    body = client.post(
        f"/api/tasks/{tid}/import",
        files={
            "file": (
                "Step3Output-1.xlsx",
                SAMPLE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()["data"]
    ven = [r for r in body["rows"] if r["k_pn"] == "ACW1081490*80"]
    assert all(r["complete"] for r in ven)
    assert ven[0]["b_len"] == 1110
    assert ven[0]["source_flag"] == "master"
    assert "b_len" in ven[0]["filled_fields_json"]
    ib1 = [r for r in body["rows"] if r["g_packmatls"] == "OUTCASE(IB-1)"]
    assert ib1[0]["b_len"] == 1460
    assert body["can_compute"] is True


def test_n_column_ignored(client):
    wb = Workbook()
    ws = wb.active
    ws.append(["箱号", "长", "宽", "高", "体积", "OUTCASE", "PackMatls", "箱重", "净重", "毛重", "PN", "备注", "Site", "集装箱号", "关单号", "DN", "尺寸"])
    ws.append([1, 10, 10, 10, 0.001, "A", "BOX", 1, 1, 2, None, None, "S1", "SHOULD-IGNORE", None, "DN1", None])
    buf = BytesIO()
    wb.save(buf)
    tid = _create_task(client)
    body = client.post(
        f"/api/tasks/{tid}/import",
        files={"file": ("n.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()["data"]
    assert body["rows"][0]["b_len"] == 100
    assert "SHOULD-IGNORE" not in str(body["rows"][0])


def test_matched_xlsx_exports_master_filled_table(client):
    client.post(
        "/api/packages",
        json={
            "pn": "PN-FILL",
            "name": "BOX-A",
            "package_type": "BOX-A",
            "l": 1200,
            "w": 800,
            "h": 600,
            "tare": 10,
            "net": 20,
            "gross": 30,
            "enabled": 1,
        },
    )
    client.post(
        "/api/packages",
        json={
            "name": "BOX-B",
            "package_type": "BOX-B",
            "l": 1460,
            "w": 1150,
            "h": 1100,
            "tare": 5,
            "net": 50,
            "gross": 392,
            "enabled": 1,
        },
    )
    wb = Workbook()
    ws = wb.active
    ws.append(["箱号", "长", "宽", "高", "体积", "OUTCASE", "PackMatls", "箱重", "净重", "毛重", "PN", "备注", "Site", "集装箱号", "关单号", "DN", "尺寸"])
    ws.append([1, None, None, None, None, "A", "BOX-A", None, None, None, "PN-FILL", None, "S1", None, None, "DN1", None])
    ws.append([2, 146, 115, 110, 1.85, "B", "BOX-B", 5, 50, 392, None, None, "S1", None, None, "DN2", None])
    ws.append([3, None, None, None, None, "C", "BOX-UNKNOWN", None, None, None, "NO-PN", None, "S1", None, None, "DN3", None])
    buf = BytesIO()
    wb.save(buf)
    tid = _create_task(client)
    client.post(
        f"/api/tasks/{tid}/import",
        files={"file": ("m.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    resp = client.get(f"/api/tasks/{tid}/import/matched.xlsx")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    assert "filename*=UTF-8''" in resp.headers["content-disposition"]
    out = load_workbook(BytesIO(resp.content), data_only=True)
    sheet = out.active
    header = [c.value for c in sheet[1]]
    assert header[:17] == [
        "箱号 No", "长 Length", "宽 width", "高 high", "体积 CBM",
        "OUTCASE NO.", "PackMatls", "箱重", "净重", "毛重",
        "PN", "备注", "Site", "集装箱号", "关单号", "DN", "尺寸",
    ]
    assert header[17] == "匹配来源"
    rows = [list(r) for r in sheet.iter_rows(min_row=2, values_only=True)]
    assert len(rows) == 3
    filled = rows[0]
    assert filled[1] == 120.0
    assert filled[2] == 80.0
    assert filled[3] == 60.0
    assert filled[10] == "PN-FILL"
    assert filled[17] == "主数据"
    table = rows[1]
    assert table[1] == 146.0
    assert table[2] == 115.0
    assert table[3] == 110.0
    assert table[17] == "原表"
    unmatched = rows[2]
    assert unmatched[1] is None
    assert unmatched[10] == "NO-PN"
    assert unmatched[17] == "未匹配"


def test_encoding_utf8_bom_gbk():
    text = "箱号,名称\n1,货物"
    utf8, enc = decode_bytes(text.encode("utf-8"))
    assert enc == "utf-8"
    assert "货物" in utf8
    bom, enc2 = decode_bytes(text.encode("utf-8-sig"))
    assert enc2 == "utf-8-sig"
    assert "货物" in bom
    gbk, enc3 = decode_bytes(text.encode("gbk"))
    assert enc3 == "gbk"
    assert "货物" in gbk
    csv = csv_bytes("箱号,名称")
    assert csv.startswith(b"\xef\xbb\xbf")
    disp = content_disposition("待填规格.xlsx")
    assert "filename*=UTF-8''" in disp
    assert "xlsx" in disp


@_need_sample
def test_chinese_header_roundtrip_and_pending_filename(client):
    tid = _create_task(client)
    client.post(
        f"/api/tasks/{tid}/import",
        files={
            "file": (
                "Step3Output-1.xlsx",
                SAMPLE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    pending = client.get(f"/api/tasks/{tid}/import/pending.xlsx")
    assert pending.status_code == 200
    assert "filename*=UTF-8''" in pending.headers["content-disposition"]
    wb = load_workbook(BytesIO(pending.content))
    headers = [c.value for c in next(wb.active.iter_rows(max_row=1))]
    assert "PN" in headers
    assert "PackMatls" in headers


def test_packmatls_match_requires_dual_fields(client):
    # a master record that owns a different PN must not fill a PN-less row,
    # even if the packing material matches (packmatls-only lookup)
    client.post(
        "/api/packages",
        json={
            "pn": "OTHER-PN",
            "name": "OUTCASE(VEN)",
            "package_type": "OUTCASE(VEN)",
            "l": 500,
            "w": 500,
            "h": 500,
            "tare": 1,
            "net": 2,
            "gross": 3,
            "enabled": 1,
        },
    )
    tid = _create_task(client)
    wb = Workbook()
    ws = wb.active
    ws.append(["箱号", "长", "宽", "高", "体积", "OUTCASE", "PackMatls", "箱重", "净重", "毛重", "PN", "备注", "Site"])
    ws.append([1, None, None, None, None, "A", "OUTCASE(VEN)", 1, 1, 2, None, None, "S1"])
    buf = BytesIO()
    wb.save(buf)
    body = client.post(
        f"/api/tasks/{tid}/import",
        files={"file": ("ven.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()["data"]
    row = body["rows"][0]
    # pn-less row + master with different PN -> no fill, still incomplete
    assert row["source_flag"] == "table"
    assert row["complete"] is False
    assert body["can_compute"] is False

    # now a master record without any PN: dual-field match allows the fill
    client.post(
        "/api/packages",
        json={
            "name": "OUTCASE(VEN)",
            "package_type": "OUTCASE(VEN)",
            "l": 600,
            "w": 600,
            "h": 600,
            "tare": 4,
            "net": 5,
            "gross": 6,
            "enabled": 1,
        },
    )
    rematch = client.post(f"/api/tasks/{tid}/import/re-match").json()["data"]
    row2 = rematch["rows"][0]
    assert row2["source_flag"] == "master"
    assert row2["complete"] is True
    assert row2["b_len"] == 600


@_need_sample
def test_packmatls_dual_field_match_when_pn_present(client):
    # a master record with the same PN and packmatls must fill the row
    client.post(
        "/api/packages",
        json={
            "pn": "ACW1081490*80",
            "name": "OUTCASE(VEN)",
            "package_type": "OUTCASE(VEN)",
            "l": 1110,
            "w": 800,
            "h": 900,
            "tare": 10,
            "net": 20,
            "gross": 30,
            "enabled": 1,
        },
    )
    tid = _create_task(client)
    body = client.post(
        f"/api/tasks/{tid}/import",
        files={
            "file": (
                "Step3Output-1.xlsx",
                SAMPLE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()["data"]
    ven = [r for r in body["rows"] if r["k_pn"] == "ACW1081490*80"]
    assert all(r["complete"] for r in ven)
    assert ven[0]["source_flag"] == "master"


@_need_sample
def test_batch_maintain_and_rematch(client):
    tid = _create_task(client)
    client.post(
        f"/api/tasks/{tid}/import",
        files={
            "file": (
                "Step3Output-1.xlsx",
                SAMPLE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    wb = Workbook()
    ws = wb.active
    ws.append(["PN", "PackMatls", "长cm", "宽cm", "高cm", "箱重kg", "净重kg", "毛重kg"])
    ws.append(["ACW1081490*80", "OUTCASE(VEN)", 120, 80, 90, 10, 20, 30])
    ws.append([None, "OUTCASE(IB-1)", 146, 115, 110, 5, 50, 392])
    buf = BytesIO()
    wb.save(buf)
    saved = client.post(
        f"/api/tasks/{tid}/import/batch-maintain",
        files={"file": ("m.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert saved.status_code == 200
    rematch = client.post(f"/api/tasks/{tid}/import/re-match").json()["data"]
    assert rematch["can_compute"] is True
    ven = [r for r in rematch["rows"] if r["k_pn"] == "ACW1081490*80"]
    assert ven[0]["b_len"] == 1200


@_need_sample
def test_site_groups_default_and_mutex(client):
    tid = _create_task(client)
    client.post(
        f"/api/tasks/{tid}/import",
        files={
            "file": (
                "Step3Output-1.xlsx",
                SAMPLE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    groups = client.get(f"/api/tasks/{tid}/site-groups").json()["data"]
    assert groups
    assert all(g["together"] is False and g["separate"] is False for g in groups)
    bad = client.put(
        f"/api/tasks/{tid}/site-groups",
        json=[{"site": "Canoas", "together": True, "separate": True}],
    )
    assert bad.status_code == 422
    ok = client.put(
        f"/api/tasks/{tid}/site-groups",
        json=[{"site": "Canoas", "together": True, "separate": False}],
    )
    assert ok.status_code == 200
    again = client.get(f"/api/tasks/{tid}/site-groups").json()["data"]
    canoas = next(g for g in again if g["site"] == "Canoas")
    assert canoas["together"] is True
    task = client.get(f"/api/tasks/{tid}").json()["data"]
    assert task["status"] == "configuring"


def _import_rows(client, tid, sites):
    wb = Workbook()
    ws = wb.active
    ws.append(["箱号", "长", "宽", "高", "体积", "OUTCASE", "PackMatls", "箱重", "净重", "毛重", "PN", "备注", "Site", "集装箱号", "关单号", "DN", "尺寸"])
    for idx, site in enumerate(sites, start=1):
        ws.append([idx, 10, 10, 10, 0.001, "A", "BOX", 1, 1, 2, None, None, site, None, None, "DN1", None])
    buf = BytesIO()
    wb.save(buf)
    return client.post(
        f"/api/tasks/{tid}/import",
        files={"file": ("sites.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()["data"]


def test_preview_payload_reports_site_auto_confirmation(client):
    tid = _create_task(client)
    body = _import_rows(client, tid, ["S1", "S1", ""])
    assert body["distinct_sites"] == ["S1"]
    assert body["site_auto_confirmed"] is True

    multi = _import_rows(client, tid, ["S1", "S2"])
    assert multi["distinct_sites"] == ["S1", "S2"]
    assert multi["site_auto_confirmed"] is False

    empty = _import_rows(client, tid, ["", ""])
    assert empty["distinct_sites"] == []
    assert empty["site_auto_confirmed"] is True
    groups = client.get(f"/api/tasks/{tid}/site-groups").json()["data"]
    assert len(groups) == 1
    assert groups[0]["site"] == ""
    assert len(groups[0]["items"]) == 2


def test_import_supplement_converts_cm_to_mm_and_matches(client):
    tid = _create_task(client)
    wb = Workbook()
    ws = wb.active
    ws.append(["箱号", "长", "宽", "高", "体积", "OUTCASE", "PackMatls", "箱重", "净重", "毛重", "PN", "备注", "Site"])
    ws.append([1, 146, 115, 110, 1.85, "A", "OUTCASE(TEST-SUP)", 136, 256, 392, "PN-SUP-1", None, "S1"])
    buf = BytesIO()
    wb.save(buf)
    preview = client.post(
        f"/api/tasks/{tid}/import",
        files={"file": ("sup.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()["data"]
    assert preview["can_compute"] is False
    assert preview["unmatched"]

    resp = client.post(
        f"/api/tasks/{tid}/import/supplement",
        json=[
            {
                "pn": "PN-SUP-1",
                "name": "OUTCASE(TEST-SUP)",
                "l": 146,
                "w": 115,
                "h": 110,
                "tare": 136,
                "net": 256,
                "gross": 392,
                "max_load": None,
            }
        ],
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["can_compute"] is True
    assert body["unmatched"] == []
    row = body["rows"][0]
    assert row["b_len"] == 1460
    assert row["c_wid"] == 1150
    assert row["d_hgt"] == 1100

    pkgs = client.get("/api/packages").json()["data"]
    rec = next(p for p in pkgs if p.get("pn") == "PN-SUP-1")
    assert rec["l"] == 1460
    assert rec["w"] == 1150
    assert rec["h"] == 1100
    assert rec["package_type"] == "OUTCASE(TEST-SUP)"
    assert rec["max_load"] is None


def test_settings_defaults(client):
    data = client.get("/api/settings").json()["data"]
    assert data["manual_limit_kg"] == "30"
    assert data["fork_tine_mm"] == "1220"
    assert data["time_limit_s"] == "60"
    assert data["gap_mm"] == "0"
    updated = client.put("/api/settings", json={"manual_limit_kg": "25"}).json()["data"]
    assert updated["manual_limit_kg"] == "25"
