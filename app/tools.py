import uuid
from datetime import date, datetime, timedelta
from .db import connect, direct_reports
from .config import APP_TODAY

def working_days(start, end, holidays):
    s=date.fromisoformat(start); e=date.fromisoformat(end)
    count=0
    while s<=e:
        if s.weekday()<5 and s.isoformat() not in holidays: count+=1
        s+=timedelta(days=1)
    return count

def allowed_employee(requester, target_id):
    if target_id == requester["employee_id"]: return True
    if requester["role"]=="hr": return True
    if requester["role"]=="manager":
        return any(r["employee_id"]==target_id for r in direct_reports(requester["employee_id"]))
    return False

def get_leave_balance(requester, employee_id=None, leave_type=None):
    target=employee_id or requester["employee_id"]
    if not allowed_employee(requester,target): raise PermissionError("I can’t share information about that employee.")
    sql="SELECT leave_type,balance_days FROM leave_balances WHERE employee_id=?"
    args=[target]
    if leave_type: sql+=" AND leave_type=?"; args.append(leave_type)
    with connect() as c: rows=[dict(r) for r in c.execute(sql,args)]
    return {"employee_id":target,"balances":rows}

def list_leave_requests(requester, employee_id=None, status=None):
    target=employee_id or requester["employee_id"]
    if not allowed_employee(requester,target): raise PermissionError("I can’t share information about that employee.")
    sql="SELECT request_id,employee_id,leave_type,start_date,end_date,working_days,status FROM leave_requests WHERE employee_id=?"
    args=[target]
    if status: sql+=" AND status=?"; args.append(status)
    with connect() as c: rows=[dict(r) for r in c.execute(sql+" ORDER BY start_date",args)]
    return {"requests":rows}

def get_team_leave(requester,start_date,end_date):
    if requester["role"]!="manager": raise PermissionError("Only managers can view team leave.")
    reports=[r["employee_id"] for r in direct_reports(requester["employee_id"])]
    if not reports: return {"requests":[]}
    marks=",".join("?" for _ in reports)
    with connect() as c:
        rows=[dict(r) for r in c.execute(f"SELECT request_id,employee_id,leave_type,start_date,end_date,working_days,status FROM leave_requests WHERE employee_id IN ({marks}) AND status IN ('pending','approved') AND start_date<=? AND end_date>=? ORDER BY start_date",(*reports,end_date,start_date))]
    return {"requests":rows}

def validate_apply(requester, leave_type, start_date, end_date, holidays):
    today=APP_TODAY
    if leave_type not in ("annual","sick"): raise ValueError("Leave type must be annual or sick.")
    try: s=date.fromisoformat(start_date); e=date.fromisoformat(end_date); t=date.fromisoformat(today)
    except ValueError: raise ValueError("Dates must use YYYY-MM-DD.")
    if s.year!=2026 or e.year!=2026: raise ValueError("Leave dates must both be in 2026.")
    if s<t: raise ValueError("Start date must be today or later.")
    if e<s: raise ValueError("End date must be on or after start date.")
    days=working_days(start_date,end_date,holidays)
    if days==0: raise ValueError("The selected range contains zero working days.")
    with connect() as c:
        bal=c.execute("SELECT balance_days FROM leave_balances WHERE employee_id=? AND leave_type=?",(requester["employee_id"],leave_type)).fetchone()
        if not bal or days>bal["balance_days"]: raise ValueError("Insufficient leave balance.")
        overlap=c.execute("SELECT 1 FROM leave_requests WHERE employee_id=? AND status IN ('pending','approved') AND start_date<=? AND end_date>=? LIMIT 1",(requester["employee_id"],end_date,start_date)).fetchone()
        if overlap: raise ValueError("The dates overlap an existing pending or approved leave request.")
    return days

def apply_leave(requester,leave_type,start_date,end_date,holidays):
    days=validate_apply(requester,leave_type,start_date,end_date,holidays)
    rid=str(uuid.uuid4())
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        # Revalidate balance/overlap inside transaction to prevent races.
        bal=c.execute("SELECT balance_days FROM leave_balances WHERE employee_id=? AND leave_type=?",(requester["employee_id"],leave_type)).fetchone()
        overlap=c.execute("SELECT 1 FROM leave_requests WHERE employee_id=? AND status IN ('pending','approved') AND start_date<=? AND end_date>=? LIMIT 1",(requester["employee_id"],end_date,start_date)).fetchone()
        if not bal or days>bal["balance_days"]: raise ValueError("Insufficient leave balance.")
        if overlap: raise ValueError("The dates overlap an existing pending or approved leave request.")
        c.execute("INSERT INTO leave_requests VALUES(?,?,?,?,?,?,?,?)",(rid,requester["employee_id"],leave_type,start_date,end_date,days,"pending",datetime.now().isoformat()))
        c.execute("UPDATE leave_balances SET balance_days=balance_days-? WHERE employee_id=? AND leave_type=?",(days,requester["employee_id"],leave_type))
        c.commit()
    return {"request_id":rid,"working_days":days,"status":"pending"}

def cancel_leave(requester,request_id):
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT * FROM leave_requests WHERE request_id=? AND employee_id=?",(request_id,requester["employee_id"])).fetchone()
        if not row: raise PermissionError("I can’t share information about that employee.")
        if row["status"] not in ("pending","approved"): raise ValueError("Only pending or approved requests can be cancelled.")
        if row["start_date"]<=APP_TODAY: raise ValueError("Only requests starting after today can be cancelled.")
        c.execute("UPDATE leave_requests SET status='cancelled' WHERE request_id=?",(request_id,))
        c.execute("UPDATE leave_balances SET balance_days=balance_days+? WHERE employee_id=? AND leave_type=?",(row["working_days"],requester["employee_id"],row["leave_type"]))
        c.commit()
    return {"request_id":request_id,"status":"cancelled"}
