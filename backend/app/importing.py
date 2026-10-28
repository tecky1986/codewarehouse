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
    """Fill missing dims/weights from master data and validate that every
    row matches a package master record.

    A row is *computable* only when:
      1. All dimensional fields (b_len / c_wid / d_hgt) are present
         (either from the row itself or filled from master).
      2. The row matches an enabled package master record (by PN or by
         PackMatls).  Unmatched rows are marked ``master_match=False``
         and excluded from computation.
    """
    pkg = PackageMasterRepo(conn)
    completed = []
    for row in list(rows):
        filled = []
        source = "table"
        missing_dim = any(row.get(k) is None for k in DIM_FIELDS)
        pn = _str(row.get("k_pn"))
        pack = _str(row.get("g_packmatls"))
        master = None
        if pn:
            master = pkg.get_by_pn(pn)
        if master is None and pack:
            master = pkg.get_by_packmatls(pack, pn)
        if master and master.get("enabled", 1):
            if missing_dim:
                source = "master"
                for field, mkey in MASTER_DIM.items():
                    if row.get(field) is None and master.get(mkey) is not None:
                        row[field] = master[mkey]
                        filled.append(field)
            row["master_match"] = True
        else:
            row["master_match"] = bool(master)
            if master is None:
                row["errors"] = row.get("errors", [])
                row["errors"].append("no_master_match")
        row["filled_fields_json"] = filled
        row["source_flag"] = source
        row["complete"] = all(row.get(k) is not None for k in DIM_FIELDS)
        if not row["complete"]:
            row.setdefault("errors", []).append("missing_spec")
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


def _distinct_sites(rows: list[dict]) -> list[str]:
    sites: list[str] = []
    seen: set[str] = set()
    has_rows = False
    for r in rows:
        has_rows = True
        site = str(r.get("m_site") or "").strip()
        if site and site not in seen:
            seen.add(site)
            sites.append(site)
    return sites, has_rows


def preview_payload(rows: list[dict]) -> dict:
    miss = missing_keys(rows)
    unmatched = [
        {"pn": r.get("k_pn"), "packmatls": r.get("g_packmatls"), "row_no": r.get("row_no")}
        for r in rows
        if not r.get("master_match", True)
    ]
    distinct_sites, has_rows = _distinct_sites(rows)
    return {
        "rows": rows,
        "missing": miss,
        "unmatched": unmatched,
        "can_compute": len(miss) == 0 and len(unmatched) == 0
        and all(r.get("complete") and r.get("master_match", True) for r in rows),
        "row_count": len(rows),
        "distinct_sites": distinct_sites,
        "site_auto_confirmed": has_rows and len(distinct_sites) <= 1,
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
    from app.excel_io import import_packages

    return import_packages(content)
