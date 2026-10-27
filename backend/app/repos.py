import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.errors import ConflictError, InUseError, NotFoundError


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    return dict(r)


def _rows(cur: sqlite3.Cursor) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


class ContainerTypeRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_all(self, enabled_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM container_type"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id"
        return _rows(self.conn.execute(sql))

    def get(self, cid: int) -> dict:
        row = _row(self.conn.execute("SELECT * FROM container_type WHERE id = ?", (cid,)).fetchone())
        if not row:
            raise NotFoundError("container type not found")
        return row

    def get_by_code(self, code: str) -> dict | None:
        return _row(
            self.conn.execute("SELECT * FROM container_type WHERE code = ?", (code,)).fetchone()
        )

    def create(self, data: dict) -> dict:
        if self.get_by_code(data["code"]):
            raise ConflictError(f"container type code already exists: {data['code']}")
        cols = (
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
            "freight_price",
            "enabled",
            "remark",
        )
        values = [data.get(c) for c in cols]
        if values[cols.index("enabled")] is None:
            values[cols.index("enabled")] = 1
        if values[cols.index("volume")] is None:
            values[cols.index("volume")] = _volume_m3(
                data["inner_l"], data["inner_w"], data["inner_h"]
            )
        if values[cols.index("freight_price")] is None:
            values[cols.index("freight_price")] = 0.0
        cur = self.conn.execute(
            f"INSERT INTO container_type ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            values,
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def update(self, cid: int, data: dict) -> dict:
        existing = self.get(cid)
        if "code" in data and data["code"] != existing["code"]:
            other = self.get_by_code(data["code"])
            if other:
                raise ConflictError(f"container type code already exists: {data['code']}")
        fields = [
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
            "freight_price",
            "enabled",
            "remark",
        ]
        merged = {k: data[k] if k in data else existing[k] for k in fields}
        if "volume" not in data:
            merged["volume"] = _volume_m3(merged["inner_l"], merged["inner_w"], merged["inner_h"])
        self.conn.execute(
            """UPDATE container_type SET
               code=?, name=?, iso_code=?, inner_l=?, inner_w=?, inner_h=?,
               door_w=?, door_h=?, max_payload=?, tare_weight=?, volume=?,
               freight_price=?, enabled=?, remark=? WHERE id=?""",
            [merged[k] for k in fields] + [cid],
        )
        self.conn.commit()
        return self.get(cid)

    def is_referenced(self, code: str) -> bool:
        n = self.conn.execute(
            "SELECT COUNT(*) AS n FROM container_instance WHERE type_code = ?",
            (code,),
        ).fetchone()["n"]
        return n > 0

    def delete(self, cid: int) -> None:
        existing = self.get(cid)
        if self.is_referenced(existing["code"]):
            raise InUseError("container type is referenced; disable it instead")
        self.conn.execute("DELETE FROM container_type WHERE id = ?", (cid,))
        self.conn.commit()


class PackageMasterRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_all(self, enabled_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM package_master"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id"
        return _rows(self.conn.execute(sql))

    def get(self, pid: int) -> dict:
        row = _row(self.conn.execute("SELECT * FROM package_master WHERE id = ?", (pid,)).fetchone())
        if not row:
            raise NotFoundError("package not found")
        return row

    def get_by_pn(self, pn: str) -> dict | None:
        if not pn:
            return None
        return _row(self.conn.execute("SELECT * FROM package_master WHERE pn = ?", (pn,)).fetchone())

    def get_by_packmatls(self, packmatls: str, pn: str | None = None) -> dict | None:
        """Match by (package_type/name, pn). pn=None means dual-field match:
        only master records without PN qualify (a row lacking PN can only be
        filled by a packaging record that itself has no PN)."""
        if not packmatls:
            return None
        if pn:
            return _row(
                self.conn.execute(
                    """SELECT * FROM package_master
                       WHERE package_type = ? AND pn = ? ORDER BY id LIMIT 1""",
                    (packmatls, pn),
                ).fetchone()
            )
        return _row(
            self.conn.execute(
                """SELECT * FROM package_master
                   WHERE (package_type = ? OR name = ?)
                     AND (pn IS NULL OR pn = '')
                   ORDER BY id LIMIT 1""",
                (packmatls, packmatls),
            ).fetchone()
        )

    def create(self, data: dict) -> dict:
        pn = data.get("pn")
        if pn:
            if self.get_by_pn(pn):
                raise ConflictError(f"PN already exists: {pn}")
        cols = (
            "pn",
            "code",
            "name",
            "package_type",
            "cargo_type",
            "l",
            "w",
            "h",
            "tare",
            "net",
            "gross",
            "volume",
            "rotatable",
            "crush_sensitive",
            "same_type_stack",
            "default_loading",
            "max_stack",
            "enabled",
            "remark",
        )
        values = [data.get(c) for c in cols]
        if values[cols.index("enabled")] is None:
            values[cols.index("enabled")] = 1
        if values[cols.index("rotatable")] is None:
            values[cols.index("rotatable")] = 1
        cur = self.conn.execute(
            f"INSERT INTO package_master ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            values,
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def update(self, pid: int, data: dict) -> dict:
        existing = self.get(pid)
        if data.get("pn") and data["pn"] != existing["pn"]:
            other = self.get_by_pn(data["pn"])
            if other:
                raise ConflictError(f"PN already exists: {data['pn']}")
        fields = [
            "pn",
            "code",
            "name",
            "package_type",
            "cargo_type",
            "l",
            "w",
            "h",
            "tare",
            "net",
            "gross",
            "volume",
            "rotatable",
            "crush_sensitive",
            "same_type_stack",
            "default_loading",
            "max_stack",
            "enabled",
            "remark",
        ]
        merged = {k: data[k] if k in data else existing[k] for k in fields}
        self.conn.execute(
            f"UPDATE package_master SET {', '.join(k + '=?' for k in fields)} WHERE id=?",
            [merged[k] for k in fields] + [pid],
        )
        self.conn.commit()
        return self.get(pid)

    def upsert(self, data: dict) -> dict:
        existing = None
        if data.get("pn"):
            existing = self.get_by_pn(data["pn"])
        pack = data.get("name") or data.get("package_type")
        if existing is None and pack:
            existing = self.get_by_packmatls(pack, data.get("pn"))
        if existing:
            return self.update(existing["id"], data)
        return self.create(data)

    def delete(self, pid: int) -> None:
        self.get(pid)
        self.conn.execute("DELETE FROM package_master WHERE id = ?", (pid,))
        self.conn.commit()


class TaskRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_all(self) -> list[dict]:
        items = _rows(self.conn.execute("SELECT * FROM task ORDER BY id DESC"))
        for row in items:
            for k in ("params_json", "rules_json", "site_groups_json", "container_mode_json"):
                row[k] = _load(row.get(k))
        return items

    def get(self, tid: int) -> dict:
        row = _row(self.conn.execute("SELECT * FROM task WHERE id = ?", (tid,)).fetchone())
        if not row:
            raise NotFoundError("task not found")
        for k in ("params_json", "rules_json", "site_groups_json", "container_mode_json"):
            row[k] = _load(row.get(k))
        return row

    def create(self, data: dict) -> dict:
        now = data.get("created_at") or datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            """INSERT INTO task (name, created_at, params_json, rules_json,
               site_groups_json, container_mode_json, status, adopted_plan_id, last_ok_plan_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["name"],
                now,
                _dump(data.get("params_json")),
                _dump(data.get("rules_json")),
                _dump(data.get("site_groups_json")),
                _dump(data.get("container_mode_json")),
                data.get("status") or "draft",
                data.get("adopted_plan_id"),
                data.get("last_ok_plan_id"),
            ),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def update(self, tid: int, data: dict) -> dict:
        existing = self.get(tid)
        fields = [
            "name",
            "params_json",
            "rules_json",
            "site_groups_json",
            "container_mode_json",
            "status",
            "adopted_plan_id",
            "last_ok_plan_id",
        ]
        json_fields = {
            "params_json",
            "rules_json",
            "site_groups_json",
            "container_mode_json",
        }
        vals = []
        for f in fields:
            v = data[f] if f in data else existing[f]
            if f in json_fields:
                v = _dump(v) if not isinstance(v, str) and v is not None else v
            vals.append(v)
        self.conn.execute(
            f"UPDATE task SET {', '.join(k + '=?' for k in fields)} WHERE id=?",
            vals + [tid],
        )
        self.conn.commit()
        return self.get(tid)

    def delete(self, tid: int) -> None:
        self.get(tid)
        self.conn.execute("DELETE FROM task WHERE id = ?", (tid,))
        self.conn.commit()


class ImportRowRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_by_task(self, task_id: int) -> list[dict]:
        items = _rows(
            self.conn.execute(
                "SELECT * FROM import_row WHERE task_id = ? ORDER BY row_no",
                (task_id,),
            )
        )
        for row in items:
            row["filled_fields_json"] = _load(row.get("filled_fields_json")) or []
        return items

    def replace_for_task(self, task_id: int, rows: list[dict]) -> list[dict]:
        self.conn.execute("DELETE FROM import_row WHERE task_id = ?", (task_id,))
        cols = (
            "task_id",
            "row_no",
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
            "o_ref",
            "p_dn",
            "q_misc",
            "filled_fields_json",
            "source_flag",
        )
        for r in rows:
            vals = [task_id if c == "task_id" else r.get(c) for c in cols]
            if isinstance(r.get("filled_fields_json"), (list, dict)):
                vals[cols.index("filled_fields_json")] = json.dumps(
                    r["filled_fields_json"], ensure_ascii=False
                )
            self.conn.execute(
                f"INSERT INTO import_row ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                vals,
            )
        self.conn.commit()
        return self.list_by_task(task_id)


class ExportTemplateRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_all(self) -> list[dict]:
        return _rows(self.conn.execute("SELECT * FROM export_template ORDER BY id"))

    def get(self, tid: int) -> dict:
        row = _row(
            self.conn.execute("SELECT * FROM export_template WHERE id = ?", (tid,)).fetchone()
        )
        if not row:
            raise NotFoundError("export template not found")
        return row

    def create(self, data: dict) -> dict:
        cur = self.conn.execute(
            "INSERT INTO export_template (name, is_default, columns_json) VALUES (?, ?, ?)",
            (
                data["name"],
                1 if data.get("is_default") else 0,
                _dump(data.get("columns_json") or []),
            ),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def update(self, tid: int, data: dict) -> dict:
        existing = self.get(tid)
        if data.get("is_default"):
            current_default = self.conn.execute(
                "SELECT id FROM export_template WHERE is_default = 1 AND id != ?", (tid,)
            ).fetchone()
            if current_default:
                self.conn.execute("UPDATE export_template SET is_default = 0 WHERE id = ?", (current_default["id"],))
        fields = []
        vals = []
        if "name" in data:
            fields.append("name=?")
            vals.append(data["name"])
        if "is_default" in data:
            fields.append("is_default=?")
            vals.append(1 if data["is_default"] else 0)
        if "columns_json" in data:
            fields.append("columns_json=?")
            vals.append(_dump(data["columns_json"]))
        if not fields:
            return existing
        vals.append(tid)
        self.conn.execute(f"UPDATE export_template SET {', '.join(fields)} WHERE id = ?", vals)
        self.conn.commit()
        return self.get(tid)

    def delete(self, tid: int) -> None:
        existing = self.get(tid)
        if existing["is_default"]:
            raise InUseError("default export template cannot be deleted")
        self.conn.execute("DELETE FROM export_template WHERE id = ?", (tid,))
        self.conn.commit()


class SettingRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_all(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.conn.execute("SELECT key, value FROM app_setting")}

    def put(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO app_setting (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        self.conn.commit()


def _volume_m3(l_mm: int, w_mm: int, h_mm: int) -> float:
    return (l_mm * w_mm * h_mm) / 1_000_000_000


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _load(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value
