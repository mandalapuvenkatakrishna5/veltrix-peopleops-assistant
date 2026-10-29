import sqlite3
from contextlib import contextmanager
from .config import DB_PATH

@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
    finally:
        conn.close()

def employee(employee_id):
    with connect() as c:
        row = c.execute("SELECT * FROM employees WHERE employee_id=?", (employee_id,)).fetchone()
        return dict(row) if row else None

def direct_reports(employee_id):
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM employees WHERE manager_id=? ORDER BY employee_id", (employee_id,))]
