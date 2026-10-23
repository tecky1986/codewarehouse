from fastapi import Request

from app.db import connect, init_schema
from app.seed import seed_if_empty

_CONN = None


def get_conn():
    global _CONN
    if _CONN is None:
        _CONN = connect()
        init_schema(_CONN)
        seed_if_empty(_CONN)
    return _CONN


def reset_conn_for_tests(path):
    global _CONN
    if _CONN is not None:
        _CONN.close()
    _CONN = connect(path)
    init_schema(_CONN)
    seed_if_empty(_CONN)
    return _CONN


def conn_from_request(request: Request):
    return request.app.state.conn
