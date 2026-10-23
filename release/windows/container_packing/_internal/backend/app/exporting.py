"""Export: plan write-back to the original 17-column table (R4/R27/R30).

Sheet layout (R4 AC2, PRD §7.4):
  1. "装箱结果": original A–Q columns (N overridden by container label,
     import-ignored N value dropped) + new "装箱顺序" column after Q.
     When a custom template (R5) is given, its column fields/order/widths
     /alignments/number formats are applied to this sheet.
  2. "未分配明细": unassigned rows with reason.
  3. "用箱摘要": per-container KPI rows + overall KPI block.

CSV fallback (R28): utf-8-sig, sheet 1 only.
Chinese filenames via RFC 5987 (content_disposition).

Unit notes: import_rows store dimensions in mm (cm ×10 on import); the
export mirrors the original table, so B/C/D are rendered back in cm
(R28/P10: cells equal the original table except N and the new column).
"""

import json
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

from app.encoding import csv_bytes
from app.errors import AppError, NotFoundError

ORIG_HEADERS = [
    "箱号 No",
    "长 Length",
    "宽 width",
    "高 high",
    "体积 CBM",
    "OUTCASE NO.",
    "PackMatls",
    "箱重",
    "净重",
    "毛重",
    "PN",
    "备注",
    "Site",
    "集装箱号",
    "关单号",
    "DN",
    "尺寸",
]
ORIG_KEYS = [
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
N_COL_INDEX = ORIG_KEYS.index("_n_ignored")
# fields stored in mm that the original table carries in cm
_CM_FIELDS = {"b_len", "c_wid", "d_hgt"}


def _row_values(row: dict) -> list:
    vals = []
    for k in ORIG_KEYS:
        if k == "_n_ignored":
            vals.append(None)
            continue
        v = row.get(k)
        if k in _CM_FIELDS and v is not None:
            v = v / 10.0
        vals.append(v)
    return vals


class ExportService:
    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _plan(self, plan_id: int) -> dict:
        row = self.conn.execute(
            "SELECT p.*, r.task_id FROM packing_plan p JOIN packing_run r ON r.id = p.run_id WHERE p.id = ?",
            (plan_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("plan not found")
        d = dict(row)
        d["kpi"] = json.loads(d.pop("kpi_json") or "{}")
        return d

    def _placements(self, plan_id: int) -> list[dict]:
        rows = self.conn.execute(
            """SELECT pl.container_id, ci.label, pl.import_row_id,
                      pl.x, pl.y, pl.z, pl.dim_x, pl.dim_y, pl.dim_z,
                      pl.load_seq, pl.unassigned_reason
               FROM placement pl LEFT JOIN container_instance ci ON ci.id = pl.container_id
               WHERE pl.plan_id = ?
               ORDER BY pl.load_seq, pl.id""",
            (plan_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _task_rows(self, task_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM import_row WHERE task_id = ? ORDER BY row_no",
            (task_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            filled = d.get("filled_fields_json")
            if isinstance(filled, str):
                try:
                    d["filled_fields_json"] = json.loads(filled)
                except json.JSONDecodeError:
                    d["filled_fields_json"] = []
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # build workbook
    # ------------------------------------------------------------------

    def build_workbook(self, plan_id: int, template: dict | None = None) -> Workbook:
        plan = self._plan(plan_id)
        placements = self._placements(plan_id)
        task_rows = self._task_rows(plan["task_id"])

        # import_row_id -> placement info
        placed: dict[int, dict] = {}
        unassigned: dict[int, dict] = {}
        for p in placements:
            if p["import_row_id"] is None:
                continue
            if p["container_id"] is not None:
                placed[p["import_row_id"]] = p
            else:
                unassigned[p["import_row_id"]] = p

        wb = Workbook()

        # ---- sheet 1: 装箱结果 (P10: A-Q preserved, N overridden, + new column)
        ws = wb.active
        ws.title = "装箱结果"
        if template:
            cols = template.get("columns_json") or []
            if isinstance(cols, str):
                cols = json.loads(cols or "[]")
            if cols:
                header = [c.get("header") or c.get("field") for c in cols]
                ws.append(header)
                for row in task_rows:
                    vals = _row_values(row)
                    rid = row["id"]
                    p = placed.get(rid)
                    out = []
                    for c in cols:
                        f = c.get("field")
                        if f == "container_label":
                            out.append(p["label"] if p else None)
                        elif f == "load_seq":
                            out.append(p["load_seq"] if p else None)
                        else:
                            out.append(row.get(f))
                    ws.append(out)
                for i, c in enumerate(cols, start=1):
                    ws.column_dimensions[get_column_letter(i)].width = c.get("width") or 12
                    fmt = c.get("number_format")
                    align = c.get("align")
                    if not fmt and not align:
                        continue
                    for r in range(2, ws.max_row + 1):
                        cell = ws.cell(row=r, column=i)
                        if fmt:
                            cell.number_format = fmt
                        if align in ("left", "right", "center", "justify"):
                            cell.alignment = Alignment(horizontal=align)
            else:
                self._write_default_sheet1(ws, task_rows, placed)
        else:
            self._write_default_sheet1(ws, task_rows, placed)

        # ---- sheet 2: 未分配明细
        ws2 = wb.create_sheet("未分配明细")
        ws2.append(["集装箱号", "装箱顺序", "原因", "箱号 No", "OUTCASE NO.", "PackMatls", "PN"])
        for row in task_rows:
            p = unassigned.get(row["id"])
            if p is None:
                continue
            ws2.append(
                [
                    p["label"] or "",
                    p["load_seq"],
                    p["unassigned_reason"] or "未分配",
                    row.get("a_no"),
                    row.get("f_outcase"),
                    row.get("g_packmatls"),
                    row.get("k_pn"),
                ]
            )

        # ---- sheet 3: 用箱摘要 (per-container + overall KPI, R30)
        ws3 = wb.create_sheet("用箱摘要")
        ws3.append(["箱号", "箱型", "件数", "已用体积m3", "容积m3", "体积利用率%", "已载kg", "载重kg", "载重利用率%"])
        kpi = plan["kpi"]
        for c in (kpi.get("per_container") or []):
            ws3.append(
                [
                    c.get("label"),
                    c.get("type_code"),
                    c.get("item_count"),
                    c.get("volume_used_m3"),
                    c.get("volume_capacity_m3"),
                    round((c.get("vol_util") or 0) * 100, 1),
                    c.get("payload_used_kg"),
                    c.get("payload_capacity_kg"),
                    round((c.get("pay_util") or 0) * 100, 1),
                ]
            )
        overall = kpi.get("overall") or {}
        ws3.append([])
        ws3.append(["整体", "用箱数", overall.get("containers_used")])
        ws3.append(["体积利用率%", round((overall.get("vol_util") or 0) * 100, 1), "载重利用率%", round((overall.get("pay_util") or 0) * 100, 1)])
        ws3.append(["未分配件数", overall.get("unassigned_count"), "未分配体积m3", overall.get("unassigned_volume_m3")])
        ws3.append(["未分配重量kg", overall.get("unassigned_weight_kg"), "耗时s", overall.get("elapsed_s")])
        return wb

    def _write_default_sheet1(self, ws, task_rows, placed):
        header = ORIG_HEADERS + ["装箱顺序"]
        ws.append(header)
        for row in task_rows:
            vals = _row_values(row)
            rid = row["id"]
            if rid in placed:
                p = placed[rid]
                vals[N_COL_INDEX] = p["label"]
                vals.append(p["load_seq"])
            else:
                vals.append(None)
            ws.append(vals)

    def to_xlsx(self, plan_id: int, template: dict | None = None) -> bytes:
        from app.excel_io import workbook_to_bytes

        return workbook_to_bytes(self.build_workbook(plan_id, template=template))

    def to_csv(self, plan_id: int) -> bytes:
        plan = self._plan(plan_id)
        placements = self._placements(plan_id)
        task_rows = self._task_rows(plan["task_id"])
        placed: dict[int, dict] = {}
        for p in placements:
            if p["import_row_id"] and p["container_id"] is not None:
                placed[p["import_row_id"]] = p
        lines = [",".join(ORIG_HEADERS + ["装箱顺序"])]
        for row in task_rows:
            vals = _row_values(row)
            rid = row["id"]
            p = placed.get(rid)
            if p:
                vals[N_COL_INDEX] = p["label"]
                vals.append(p["load_seq"])
            else:
                vals.append(None)
            cells = []
            for v in vals:
                if v is None:
                    cells.append("")
                elif isinstance(v, float):
                    cells.append(str(v))
                else:
                    s = str(v)
                    if "," in s or '"' in s:
                        s = '"' + s.replace('"', '""') + '"'
                    cells.append(s)
            lines.append(",".join(cells))
        return csv_bytes("\n".join(lines))


def default_template_columns() -> list[dict]:
    """Default export template: A–Q order (N overridden) + new 装箱顺序 column."""
    cols = []
    for i, (key, header) in enumerate(zip(ORIG_KEYS, ORIG_HEADERS), start=1):
        col = {
            "field": key,
            "header": header,
            "width": 12,
            "align": "left" if key in ("f_outcase", "g_packmatls", "k_pn", "l_note", "m_site", "q_misc") else "right",
            "number_format": None,
        }
        if key == "_n_ignored":
            col["field"] = "container_label"
            col["header"] = "集装箱号"
            col["overridden"] = True
        cols.append(col)
    cols.append({"field": "load_seq", "header": "装箱顺序", "width": 10, "align": "right", "number_format": None})
    return cols
