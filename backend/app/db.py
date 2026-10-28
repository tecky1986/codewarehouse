import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS container_type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    iso_code TEXT,
    inner_l INTEGER NOT NULL,
    inner_w INTEGER NOT NULL,
    inner_h INTEGER NOT NULL,
    door_w INTEGER,
    door_h INTEGER,
    max_payload REAL NOT NULL,
    tare_weight REAL,
    volume REAL,
    freight_price REAL NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS package_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pn TEXT UNIQUE,
    code TEXT,
    name TEXT,
    package_type TEXT,
    cargo_type TEXT,
    l INTEGER,
    w INTEGER,
    h INTEGER,
    tare REAL,
    net REAL,
    gross REAL,
    volume REAL,
    rotatable INTEGER DEFAULT 1,
    crush_sensitive INTEGER DEFAULT 0,
    same_type_stack INTEGER DEFAULT 0,
    default_loading TEXT,
    max_stack INTEGER,
    max_load REAL,
    enabled INTEGER NOT NULL DEFAULT 1,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    params_json TEXT,
    rules_json TEXT,
    site_groups_json TEXT,
    container_mode_json TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    adopted_plan_id INTEGER,
    last_ok_plan_id INTEGER
);

CREATE TABLE IF NOT EXISTS import_row (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    row_no INTEGER NOT NULL,
    a_no TEXT,
    b_len REAL,
    c_wid REAL,
    d_hgt REAL,
    e_cbm REAL,
    f_outcase TEXT,
    g_packmatls TEXT,
    h_tare REAL,
    i_net REAL,
    j_gross REAL,
    k_pn TEXT,
    l_note TEXT,
    m_site TEXT,
    o_ref TEXT,
    p_dn TEXT,
    q_misc TEXT,
    filled_fields_json TEXT,
    source_flag TEXT
);

CREATE TABLE IF NOT EXISTS packing_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    algorithms_json TEXT
);

CREATE TABLE IF NOT EXISTS packing_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES packing_run(id) ON DELETE CASCADE,
    algorithm TEXT NOT NULL,
    is_adopted INTEGER NOT NULL DEFAULT 0,
    kpi_json TEXT,
    created_ms INTEGER
);

CREATE TABLE IF NOT EXISTS container_instance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES packing_plan(id) ON DELETE CASCADE,
    type_code TEXT NOT NULL,
    seq_no INTEGER NOT NULL,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS placement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES packing_plan(id) ON DELETE CASCADE,
    container_id INTEGER REFERENCES container_instance(id),
    import_row_id INTEGER REFERENCES import_row(id),
    x REAL,
    y REAL,
    z REAL,
    dim_x REAL,
    dim_y REAL,
    dim_z REAL,
    rotation TEXT,
    load_seq INTEGER,
    unassigned_reason TEXT
);

CREATE TABLE IF NOT EXISTS export_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    columns_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_setting (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

def _resolve_db_path() -> Path:
    data_dir = os.environ.get("CP_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "data.db"
    return Path(__file__).resolve().parents[1] / "data.db"


_DEFAULT_DB = _resolve_db_path()
DEFAULT_DB = _DEFAULT_DB


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else _resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(container_type)").fetchall()}
    if "freight_price" not in cols:
        conn.execute("ALTER TABLE container_type ADD COLUMN freight_price REAL NOT NULL DEFAULT 0")
    pkg_cols = {row["name"] for row in conn.execute("PRAGMA table_info(package_master)").fetchall()}
    if "max_load" not in pkg_cols:
        conn.execute("ALTER TABLE package_master ADD COLUMN max_load REAL")
    conn.commit()
