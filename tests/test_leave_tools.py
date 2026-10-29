import sqlite3
import pytest
import app.db as db
import app.tools as tools

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    path=str(tmp_path/"test.db")
    c=sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE employees(employee_id TEXT PRIMARY KEY,full_name TEXT,email TEXT,phone TEXT,region TEXT,join_date TEXT,level TEXT,role TEXT,manager_id TEXT);
    CREATE TABLE leave_balances(employee_id TEXT,leave_type TEXT,balance_days REAL,PRIMARY KEY(employee_id,leave_type));
    CREATE TABLE leave_requests(request_id TEXT PRIMARY KEY,employee_id TEXT,leave_type TEXT,start_date TEXT,end_date TEXT,working_days INTEGER,status TEXT,created_at TEXT);
    INSERT INTO employees VALUES('M1','Manager Name','m@example.com','123','IN','2020-01-01','L5','manager',NULL);
    INSERT INTO employees VALUES('E1','Employee Name','e@example.com','456','IN','2021-01-01','L2','employee','M1');
    INSERT INTO employees VALUES('E2','Other Name','o@example.com','789','IN','2021-01-01','L2','employee',NULL);
    INSERT INTO leave_balances VALUES('E1','annual',10);
    INSERT INTO leave_balances VALUES('E1','sick',5);
    INSERT INTO leave_balances VALUES('M1','annual',10);
    INSERT INTO leave_balances VALUES('M1','sick',5);
    """)
    c.commit(); c.close()
    monkeypatch.setattr(db,"DB_PATH",path)
    monkeypatch.setattr(tools,"APP_TODAY","2026-10-29")
    return path

def test_employee_cannot_view_other_leave(test_db):
    emp=db.employee("E1")
    with pytest.raises(PermissionError):
        tools.get_leave_balance(emp,"E2")

def test_manager_can_view_direct_report(test_db):
    manager=db.employee("M1")
    assert tools.get_leave_balance(manager,"E1")["employee_id"]=="E1"
    with pytest.raises(PermissionError):
        tools.get_leave_balance(manager,"E2")

def test_apply_leave_transaction_updates_balance(test_db):
    emp=db.employee("E1")
    result=tools.apply_leave(emp,"annual","2026-11-02","2026-11-03",{"2026-11-02"})
    assert result["working_days"]==1
    assert tools.get_leave_balance(emp,"E1","annual")["balances"][0]["balance_days"]==9

def test_apply_rejects_overlap_and_insufficient_balance(test_db):
    emp=db.employee("E1")
    tools.apply_leave(emp,"annual","2026-11-02","2026-11-03",set())
    with pytest.raises(ValueError,match="overlap"):
        tools.validate_apply(emp,"annual","2026-11-03","2026-11-04",set())
    with pytest.raises(ValueError,match="Insufficient"):
        tools.validate_apply(emp,"sick","2026-11-02","2026-11-10",set())

def test_cancel_only_future_own_request_and_restores_balance(test_db):
    emp=db.employee("E1")
    result=tools.apply_leave(emp,"annual","2026-11-02","2026-11-03",set())
    tools.cancel_leave(emp,result["request_id"])
    assert tools.get_leave_balance(emp,"E1","annual")["balances"][0]["balance_days"]==10
