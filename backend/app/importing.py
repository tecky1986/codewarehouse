from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.encoding import EncodingError, decode_bytes
from app.errors import AppError
from app.repos import PackageMasterRepo

COL_MAP = [
    "a_no",
    "b_len",
    "c_wid",
    "d_hgt",
    "e_cbm",
    "f_outcase",
    "g_packmatls",
    "h_tare",
    "i_net",
    "j_gross",
    "k_pn",
    "l_note",
    "m_site",
    "_n_ignored",
    "o_ref",
    "p_dn",
    "q_misc",
]

DIM_FIELDS = ("b_len", "c_wid", "d_hgt")
FILLABLE = ("b_len", "c_wid", "d_hgt", "e_cbm", "h_tare", "i_net", "j_gross")
MASTER_DIM = {"b_len": "l", "c_wid": "w", "d_hgt": "h", "e_cbm": "volume", "h_tare": "tare", "i_net": "net", "j_gross": "gross"}


def parse_xlsx(content: bytes) -> list[list]:
    wb = load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def parse_csv(content: bytes) -> list[list]:
    try:
        text, _enc = decode_bytes(content)
    except EncodingError as e:
        raise AppError("E_ENCODING", str(e), 400) from e
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        rows.append([c.strip() for c in line.split(",")])
    return rows


def rows_from_file(filename: str, content: bytes) -> list[list]:
    name = (filename or "").lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        return parse_csv(content)
    try:
        return parse_xlsx(content)
    except Exception as e:
        raise AppError("E_ENCODING", f"无法解析文件: {e}", 400) from e


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def map_raw_rows(raw_rows: list[list]) -> list[dict]:
    if not raw_rows:
        return []
    data_rows = raw_rows[1:] if raw_rows else []
    out = []
    for i, raw in enumerate(data_rows, start=2):
        if raw is None or all(v is None or v == "" for v in raw):
            continue
        item = {"row_no": i, "source_flag": "table", "filled_fields_json": []}
        for idx, key in enumerate(COL_MAP):
            val = raw[idx] if idx < len(raw) else None
            if key == "_n_ignored":
                continue
            if key in FILLABLE or key in DIM_FIELDS:
                item[key] = _num(val)
            else:
                item[key] = _str(val)
        if item.get("b_len") is not None:
            item["b_len"] = item["b_len"] * 10
        if item.get("c_wid") is not None:
            item["c_wid"] = item["c_wid"] * 10
        if item.get("d_hgt") is not None:
            item["d_hgt"] = item["d_hgt"] * 10
        out.append(item)
    return out


def complete_rows(conn, rows: list[dict]) -> list[dict]:
    pkg = PackageMasterRepo(conn)
    completed = []
    for row in list(rows):
        filled = []
        source = "table"
        missing_dim = any(row.get(k) is None for k in DIM_FIELDS)
        master = None
        if missing_dim:
            pn = row.get("k_pn")
            if pn:
                master = pkg.get_by_pn(pn)
            if master is None and row.get("g_packmatls"):
                master = pkg.get_by_packmatls(row["g_packmatls"])
            if master and master.get("enabled", 1):
                source = "master"
                for field, mkey in MASTER_DIM.items():
                    if row.get(field) is None and master.get(mkey) is not None:
                        row[field] = master[mkey]
                        filled.append(field)
        row["filled_fields_json"] = filled
        row["source_flag"] = source
        row["complete"] = all(row.get(k) is not None for k in DIM_FIELDS)
        row["errors"] = []
        if not row["complete"]:
            row["errors"].append("missing_spec")
        completed.append(row)
    return completed


def missing_keys(rows: list[dict]) -> list[dict]:
    seen = []
    keys = set()
    for r in rows:
        if r.get("complete"):
            continue
        key = (r.get("k_pn") or "", r.get("g_packmatls") or "")
        if key in keys:
            continue
        keys.add(key)
        seen.append({"pn": r.get("k_pn"), "packmatls": r.get("g_packmatls"), "row_no": r.get("row_no")})
    return seen


def preview_payload(rows: list[dict]) -> dict:
    miss = missing_keys(rows)
    return {
        "rows": rows,
        "missing": miss,
        "can_compute": len(miss) == 0 and all(r.get("complete") for r in rows),
        "row_count": len(rows),
    }


def pending_fill_workbook(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "pending"
    ws.append(["PN", "PackMatls", "长cm", "宽cm", "高cm", "箱重kg", "净重kg", "毛重kg"])
    for m in missing_keys(rows):
        ws.append([m["pn"], m["packmatls"], None, None, None, None, None, None])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_maintain_xlsx(content: bytes) -> list[dict]:
    wb = load_workbook(BytesIO(content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    out = []
    for raw in rows[1:]:
        if raw is None or all(v is None or v == "" for v in raw):
            continue
        item = {}
        for i, h in enumerate(headers):
            if i < len(raw):
                item[h] = raw[i]
        pn = item.get("PN") or item.get("pn")
        pack = item.get("PackMatls") or item.get("packmatls")
        l_cm = _num(item.get("长cm") or item.get("l") or item.get("长"))
        w_cm = _num(item.get("宽cm") or item.get("w") or item.get("宽"))
        h_cm = _num(item.get("高cm") or item.get("h") or item.get("高"))
        out.append(
            {
                "pn": _str(pn),
                "name": _str(pack),
                "package_type": _str(pack),
                "l": int(l_cm * 10) if l_cm is not None else None,
                "w": int(w_cm * 10) if w_cm is not None else None,
                "h": int(h_cm * 10) if h_cm is not None else None,
                "tare": _num(item.get("箱重kg") or item.get("tare")),
                "net": _num(item.get("净重kg") or item.get("net")),
                "gross": _num(item.get("毛重kg") or item.get("gross")),
                "enabled": 1,
            }
        )
    return out
