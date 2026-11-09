from app.db import connect, init_schema
from app.seed import seed_if_empty

_CONN = None
_DB_PATH = None


def get_conn():
    global _CONN, _DB_PATH
    if _CONN is None:
        from app.db import _resolve_db_path

        _DB_PATH = _resolve_db_path()
        _CONN = connect(_DB_PATH)
        init_schema(_CONN)
        seed_if_empty(_CONN)
    return _CONN


def reset_conn_for_tests(path):
    global _CONN, _DB_PATH
    if _CONN is not None:
        _CONN.close()
    _DB_PATH = path
    _CONN = connect(path)
    init_schema(_CONN)
    seed_if_empty(_CONN, with_sample=False)
    return _CONN


def current_db_path():
    return _DB_PATH
