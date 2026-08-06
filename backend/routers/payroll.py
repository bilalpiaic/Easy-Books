"""Payroll module — employees, salary components, structures, and payroll runs."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, func, select

from models import (
    Account, AttendanceRecord, Employee, EmployeeSalaryStructure, PayrollLine,
    PayrollLineDetail, PayrollRun, SalaryComponent,
)
from routers.common import CurrentUserDep, SessionDep, next_number
from services.events import emit
from services.permissions import perm_dep
from services.posting import EntryInput, post_transaction

# ── Routers ───────────────────────────────────────────────────────────────────

employees_router = APIRouter(
    prefix="/api/employees",
    tags=["payroll"],
    dependencies=[perm_dep("employees")],
)

payroll_router = APIRouter(
    prefix="/api/payroll",
    tags=["payroll"],
    dependencies=[perm_dep("payroll")],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    employee_code: Optional[str] = None
    name: str
    department: Optional[str] = None
    designation: Optional[str] = None
    join_date: Optional[str] = None
    cnic: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    is_active: bool = True


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    join_date: Optional[str] = None
    cnic: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    is_active: Optional[bool] = None


class ComponentCreate(BaseModel):
    name: str
    code: str
    component_type: str      # earnings | deductions | statutory
    is_taxable: bool = False
    is_fixed: bool = True
    gl_account_id: Optional[int] = None
    is_active: bool = True


class ComponentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    component_type: Optional[str] = None
    is_taxable: Optional[bool] = None
    is_fixed: Optional[bool] = None
    gl_account_id: Optional[int] = None
    is_active: Optional[bool] = None


class StructureRow(BaseModel):
    component_id: int
    amount: float = 0.0
    pct_of_basic: Optional[float] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class PayrollRunCreate(BaseModel):
    period_start: str
    period_end: str
    pay_date: str
    notes: Optional[str] = None


class PayrollRunUpdate(BaseModel):
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    pay_date: Optional[str] = None
    notes: Optional[str] = None


class LineUpdate(BaseModel):
    employee_id: int
    gross_earnings: float
    total_deductions: float
    net_pay: float


class RunLinesUpdate(BaseModel):
    lines: List[LineUpdate]


# ── Helper ────────────────────────────────────────────────────────────────────

def _find_salary_expense_account(session: Session, tenant_id: int) -> Optional[Account]:
    """Find best-match salary expense account for the tenant."""
    # 5100 = Salary Expense in _COA_COMMON (seeded for every tenant)
    for code in ("5100", "5200", "5000"):
        acct = session.exec(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.code == code,
                Account.is_group == False,  # noqa: E712
            )
        ).first()
        if acct:
            return acct
    # Fall back: any active non-group expense account with salary/payroll in name
    acct = session.exec(
        select(Account).where(
            Account.tenant_id == tenant_id,
            Account.type == "expense",
            Account.is_active == True,  # noqa: E712
            Account.is_group == False,  # noqa: E712
        )
    ).first()
    return acct


def _find_salaries_payable_account(session: Session, tenant_id: int) -> Optional[Account]:
    """Find best-match salaries payable liability account for the tenant."""
    # 2250 = Salaries Payable in _COA_COMMON (seeded for every tenant)
    for code in ("2250", "2000"):
        acct = session.exec(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.code == code,
                Account.is_group == False,  # noqa: E712
            )
        ).first()
        if acct:
            return acct
    # Fall back: first active non-group liability account
    acct = session.exec(
        select(Account).where(
            Account.tenant_id == tenant_id,
            Account.type == "liability",
            Account.is_active == True,  # noqa: E712
            Account.is_group == False,  # noqa: E712
        )
    ).first()
    return acct


def _compute_lines(
    session: Session, tenant_id: int, run_id: int
) -> List[PayrollLine]:
    """Compute PayrollLine + PayrollLineDetail rows for all active employees."""
    from datetime import date as DateType
    from routers.leave import unpaid_leave_days

    run = session.get(PayrollRun, run_id)
    if not run:
        return []

    employees = session.exec(
        select(Employee).where(
            Employee.tenant_id == tenant_id,
            Employee.is_active == True,  # noqa: E712
        )
    ).all()

    # Ensure LOP salary component exists for unpaid-leave deductions (#303)
    lop = session.exec(
        select(SalaryComponent).where(
            SalaryComponent.tenant_id == tenant_id,
            SalaryComponent.code == "LOP",
        )
    ).first()
    if not lop:
        lop = SalaryComponent(
            tenant_id=tenant_id,
            name="Loss of Pay",
            code="LOP",
            component_type="deductions",
            is_taxable=False,
            is_fixed=True,
            is_active=True,
        )
        session.add(lop)
        session.flush()

    # Calendar days in pay period for daily-rate LOP (simple /30-style if needed)
    try:
        ps = DateType.fromisoformat(run.period_start)
        pe = DateType.fromisoformat(run.period_end)
        period_days = max(1, (pe - ps).days + 1)
    except ValueError:
        period_days = 30

    lines: List[PayrollLine] = []
    for emp in employees:
        structures = session.exec(
            select(EmployeeSalaryStructure).where(
                EmployeeSalaryStructure.employee_id == emp.id
            )
        ).all()

        # Find basic salary for pct calculations
        basic_amount = 0.0
        for s in structures:
            comp = session.get(SalaryComponent, s.component_id)
            if comp and comp.code.upper() == "BASIC":
                basic_amount = s.amount
                break

        gross = 0.0
        deductions = 0.0
        detail_rows = []
        for s in structures:
            comp = session.get(SalaryComponent, s.component_id)
            if not comp or not comp.is_active:
                continue
            # Resolve amount
            if not comp.is_fixed and s.pct_of_basic is not None:
                amt = basic_amount * s.pct_of_basic / 100.0
            else:
                amt = s.amount

            detail_rows.append((s.component_id, amt, comp.component_type))
            if comp.component_type == "earnings":
                gross += amt
            elif comp.component_type in ("deductions", "statutory"):
                deductions += amt

        # Unpaid leave → LOP deduction (#303)
        unpaid_days = unpaid_leave_days(
            session, tenant_id, emp.id, run.period_start, run.period_end
        )
        if unpaid_days > 0 and basic_amount > 0:
            daily = basic_amount / float(period_days)
            lop_amt = round(daily * unpaid_days, 2)
            if lop_amt > 0:
                detail_rows.append((lop.id, lop_amt, "deductions"))
                deductions += lop_amt

        net = gross - deductions

        line = PayrollLine(
            payroll_run_id=run_id,
            employee_id=emp.id,
            gross_earnings=gross,
            total_deductions=deductions,
            net_pay=net,
        )
        session.add(line)
        session.flush()  # get line.id

        for comp_id, amt, _ in detail_rows:
            session.add(PayrollLineDetail(
                payroll_line_id=line.id,
                component_id=comp_id,
                amount=amt,
                is_override=False,
            ))

        lines.append(line)
    return lines


def _serialize_run(run: PayrollRun, session: Session) -> dict:
    """Serialize a PayrollRun with aggregate line stats."""
    lines = session.exec(
        select(PayrollLine).where(PayrollLine.payroll_run_id == run.id)
    ).all()
    total_net = sum(l.net_pay for l in lines)
    return {
        "id": run.id,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "pay_date": run.pay_date,
        "status": run.status,
        "notes": run.notes,
        "jv_number": run.jv_number,
        "transaction_id": run.transaction_id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "total_lines": len(lines),
        "total_net_pay": total_net,
    }


# ── Employees ─────────────────────────────────────────────────────────────────

@employees_router.get("")
def list_employees(
    user: CurrentUserDep,
    session: SessionDep,
    active_only: bool = False,
    search: Optional[str] = None,
):
    q = select(Employee).where(Employee.tenant_id == user.tenant_id)
    if active_only:
        q = q.where(Employee.is_active == True)  # noqa: E712
    if search:
        s = f"%{search}%"
        q = q.where(
            (Employee.name.ilike(s)) | (Employee.employee_code.ilike(s))  # type: ignore[attr-defined]
        )
    emps = session.exec(q.order_by(Employee.name)).all()
    return [
        {
            "id": e.id,
            "employee_code": e.employee_code,
            "name": e.name,
            "department": e.department,
            "designation": e.designation,
            "join_date": e.join_date,
            "cnic": e.cnic,
            "bank_account": e.bank_account,
            "bank_name": e.bank_name,
            "is_active": e.is_active,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in emps
    ]


@employees_router.post("", dependencies=[perm_dep("employees", "edit")])
def create_employee(body: EmployeeCreate, user: CurrentUserDep, session: SessionDep):
    # Auto-generate employee_code if not provided
    if not body.employee_code:
        code = next_number(
            session, user.tenant_id,
            name="employee",
            prefix="EMP",
            width=4,
            fmt="{prefix}-{seq:04d}",
        )
    else:
        code = body.employee_code

    emp = Employee(
        tenant_id=user.tenant_id,
        employee_code=code,
        name=body.name,
        department=body.department,
        designation=body.designation,
        join_date=body.join_date,
        cnic=body.cnic,
        bank_account=body.bank_account,
        bank_name=body.bank_name,
        is_active=body.is_active,
        created_by_id=user.id,
    )
    session.add(emp)
    session.flush()
    emit(session, user.tenant_id, "employee.created", {
        "employee_id": emp.id, "employee_code": emp.employee_code,
        "name": emp.name, "department": emp.department,
    })
    session.commit()
    session.refresh(emp)
    return {"id": emp.id, "employee_code": emp.employee_code}


@employees_router.get("/{emp_id}")
def get_employee(emp_id: int, user: CurrentUserDep, session: SessionDep):
    emp = session.get(Employee, emp_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")
    structures = session.exec(
        select(EmployeeSalaryStructure, SalaryComponent)
        .join(SalaryComponent, EmployeeSalaryStructure.component_id == SalaryComponent.id)  # type: ignore[arg-type]
        .where(EmployeeSalaryStructure.employee_id == emp_id)
    ).all()
    return {
        "id": emp.id,
        "employee_code": emp.employee_code,
        "name": emp.name,
        "department": emp.department,
        "designation": emp.designation,
        "join_date": emp.join_date,
        "cnic": emp.cnic,
        "bank_account": emp.bank_account,
        "bank_name": emp.bank_name,
        "is_active": emp.is_active,
        "created_at": emp.created_at.isoformat() if emp.created_at else None,
        "salary_structure": [
            {
                "id": s.id,
                "component_id": s.component_id,
                "component_name": c.name,
                "component_code": c.code,
                "component_type": c.component_type,
                "is_fixed": c.is_fixed,
                "amount": s.amount,
                "pct_of_basic": s.pct_of_basic,
                "effective_from": s.effective_from,
                "effective_to": s.effective_to,
            }
            for s, c in structures
        ],
    }


@employees_router.put("/{emp_id}", dependencies=[perm_dep("employees", "edit")])
def update_employee(emp_id: int, body: EmployeeUpdate, user: CurrentUserDep, session: SessionDep):
    emp = session.get(Employee, emp_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(emp, k, v)
    session.add(emp)
    session.commit()
    return {"ok": True}


@employees_router.delete("/{emp_id}", dependencies=[perm_dep("employees", "edit")])
def deactivate_employee(emp_id: int, user: CurrentUserDep, session: SessionDep):
    emp = session.get(Employee, emp_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")
    emp.is_active = False
    session.add(emp)
    session.commit()
    return {"ok": True}


# ── Salary Structure ──────────────────────────────────────────────────────────

@employees_router.get("/{emp_id}/structure")
def get_structure(emp_id: int, user: CurrentUserDep, session: SessionDep):
    emp = session.get(Employee, emp_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")
    rows = session.exec(
        select(EmployeeSalaryStructure).where(
            EmployeeSalaryStructure.employee_id == emp_id
        )
    ).all()
    return [
        {
            "id": r.id,
            "component_id": r.component_id,
            "amount": r.amount,
            "pct_of_basic": r.pct_of_basic,
            "effective_from": r.effective_from,
            "effective_to": r.effective_to,
        }
        for r in rows
    ]


@employees_router.put("/{emp_id}/structure", dependencies=[perm_dep("employees", "edit")])
def replace_structure(
    emp_id: int, body: List[StructureRow], user: CurrentUserDep, session: SessionDep
):
    emp = session.get(Employee, emp_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")
    # Validate components belong to tenant
    for row in body:
        comp = session.get(SalaryComponent, row.component_id)
        if not comp or comp.tenant_id != user.tenant_id:
            raise HTTPException(404, f"Component {row.component_id} not found")
    # Delete existing
    existing = session.exec(
        select(EmployeeSalaryStructure).where(
            EmployeeSalaryStructure.employee_id == emp_id
        )
    ).all()
    for e in existing:
        session.delete(e)
    session.flush()
    # Insert new
    for row in body:
        session.add(EmployeeSalaryStructure(
            employee_id=emp_id,
            component_id=row.component_id,
            amount=row.amount,
            pct_of_basic=row.pct_of_basic,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        ))
    session.commit()
    return {"ok": True}


# ── Salary Components ─────────────────────────────────────────────────────────

@payroll_router.get("/components")
def list_components(user: CurrentUserDep, session: SessionDep):
    comps = session.exec(
        select(SalaryComponent).where(
            SalaryComponent.tenant_id == user.tenant_id
        ).order_by(SalaryComponent.component_type, SalaryComponent.name)  # type: ignore[arg-type]
    ).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "component_type": c.component_type,
            "is_taxable": c.is_taxable,
            "is_fixed": c.is_fixed,
            "gl_account_id": c.gl_account_id,
            "is_active": c.is_active,
        }
        for c in comps
    ]


@payroll_router.post("/components", dependencies=[perm_dep("payroll.components", "edit")])
def create_component(body: ComponentCreate, user: CurrentUserDep, session: SessionDep):
    comp = SalaryComponent(
        tenant_id=user.tenant_id,
        name=body.name,
        code=body.code,
        component_type=body.component_type,
        is_taxable=body.is_taxable,
        is_fixed=body.is_fixed,
        gl_account_id=body.gl_account_id,
        is_active=body.is_active,
    )
    session.add(comp)
    session.commit()
    session.refresh(comp)
    return {"id": comp.id}


@payroll_router.put("/components/{comp_id}", dependencies=[perm_dep("payroll.components", "edit")])
def update_component(comp_id: int, body: ComponentUpdate, user: CurrentUserDep, session: SessionDep):
    comp = session.get(SalaryComponent, comp_id)
    if not comp or comp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Component not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(comp, k, v)
    session.add(comp)
    session.commit()
    return {"ok": True}


@payroll_router.delete("/components/{comp_id}", dependencies=[perm_dep("payroll.components", "edit")])
def delete_component(comp_id: int, user: CurrentUserDep, session: SessionDep):
    comp = session.get(SalaryComponent, comp_id)
    if not comp or comp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Component not found")
    # Block if referenced by any structure rows
    refs = session.exec(
        select(EmployeeSalaryStructure).where(
            EmployeeSalaryStructure.component_id == comp_id
        )
    ).first()
    if refs:
        raise HTTPException(400, "Component is used in employee salary structures and cannot be deleted")
    session.delete(comp)
    session.commit()
    return {"ok": True}


# ── HRM Summary (hub overview) ────────────────────────────────────────────────

@payroll_router.get("/summary")
def hrm_summary(user: CurrentUserDep, session: SessionDep):
    tid = user.tenant_id
    today = date.today()
    month_start = today.replace(day=1)

    active_employees = session.exec(
        select(func.count(Employee.id)).where(  # type: ignore[arg-type]
            Employee.tenant_id == tid, Employee.is_active == True  # noqa: E712
        )
    ).one() or 0

    last_posted = session.exec(
        select(PayrollRun)
        .where(PayrollRun.tenant_id == tid, PayrollRun.status == "posted")
        .order_by(PayrollRun.pay_date.desc())  # type: ignore[attr-defined]
        .limit(1)
    ).first()

    pending_runs = session.exec(
        select(func.count(PayrollRun.id)).where(  # type: ignore[arg-type]
            PayrollRun.tenant_id == tid,
            PayrollRun.status.in_(["draft", "approved"]),  # type: ignore[attr-defined]
        )
    ).one() or 0

    att_recs = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.tenant_id == tid,
            AttendanceRecord.date >= month_start.isoformat(),
            AttendanceRecord.date <= today.isoformat(),
        )
    ).all()

    present_count = sum(1 for r in att_recs if r.status in ("present", "half_day"))
    days_so_far = max((today - month_start).days + 1, 1)
    max_possible = (active_employees or 1) * days_so_far
    avg_attendance_pct = round(present_count / max_possible * 100, 1) if att_recs else 0.0

    recent_runs = session.exec(
        select(PayrollRun)
        .where(PayrollRun.tenant_id == tid)
        .order_by(PayrollRun.pay_date.desc())  # type: ignore[attr-defined]
        .limit(5)
    ).all()

    # _serialize_run computes total_net_pay and total_lines from PayrollLine rows
    serialized_runs = [_serialize_run(r, session) for r in recent_runs]
    last_posted_net = 0.0
    if last_posted:
        last_lines = session.exec(
            select(PayrollLine).where(PayrollLine.payroll_run_id == last_posted.id)
        ).all()
        last_posted_net = sum(l.net_pay for l in last_lines)

    return {
        "active_employees": active_employees,
        "last_payroll_net": last_posted_net,
        "pending_runs": pending_runs,
        "avg_attendance_pct": avg_attendance_pct,
        "recent_runs": serialized_runs,
    }


# ── Payroll Runs ──────────────────────────────────────────────────────────────

@payroll_router.get("/runs")
def list_runs(user: CurrentUserDep, session: SessionDep):
    runs = session.exec(
        select(PayrollRun).where(
            PayrollRun.tenant_id == user.tenant_id
        ).order_by(PayrollRun.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    return [_serialize_run(r, session) for r in runs]


@payroll_router.post("/runs", dependencies=[perm_dep("payroll", "edit")])
def create_run(body: PayrollRunCreate, user: CurrentUserDep, session: SessionDep):
    run = PayrollRun(
        tenant_id=user.tenant_id,
        period_start=body.period_start,
        period_end=body.period_end,
        pay_date=body.pay_date,
        notes=body.notes,
        status="draft",
        created_by_id=user.id,
    )
    session.add(run)
    session.flush()  # get run.id

    _compute_lines(session, user.tenant_id, run.id)

    session.commit()
    session.refresh(run)
    return _serialize_run(run, session)


@payroll_router.get("/runs/{run_id}")
def get_run(run_id: int, user: CurrentUserDep, session: SessionDep):
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")

    lines = session.exec(
        select(PayrollLine).where(PayrollLine.payroll_run_id == run_id)
    ).all()

    lines_out = []
    for line in lines:
        emp = session.get(Employee, line.employee_id)
        details = session.exec(
            select(PayrollLineDetail, SalaryComponent)
            .join(SalaryComponent, PayrollLineDetail.component_id == SalaryComponent.id)  # type: ignore[arg-type]
            .where(PayrollLineDetail.payroll_line_id == line.id)
        ).all()
        lines_out.append({
            "id": line.id,
            "employee_id": line.employee_id,
            "employee_name": emp.name if emp else f"#{line.employee_id}",
            "employee_code": emp.employee_code if emp else "",
            "gross_earnings": line.gross_earnings,
            "total_deductions": line.total_deductions,
            "net_pay": line.net_pay,
            "details": [
                {
                    "id": d.id,
                    "component_id": d.component_id,
                    "component_name": c.name,
                    "component_type": c.component_type,
                    "amount": d.amount,
                    "is_override": d.is_override,
                }
                for d, c in details
            ],
        })

    return {
        "id": run.id,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "pay_date": run.pay_date,
        "status": run.status,
        "notes": run.notes,
        "jv_number": run.jv_number,
        "transaction_id": run.transaction_id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "lines": lines_out,
        "total_gross": sum(l["gross_earnings"] for l in lines_out),
        "total_deductions": sum(l["total_deductions"] for l in lines_out),
        "total_net": sum(l["net_pay"] for l in lines_out),
    }


@payroll_router.put("/runs/{run_id}", dependencies=[perm_dep("payroll", "edit")])
def update_run(run_id: int, body: PayrollRunUpdate, user: CurrentUserDep, session: SessionDep):
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "draft":
        raise HTTPException(400, "Only draft runs can be edited")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(run, k, v)
    session.add(run)
    session.commit()
    return {"ok": True}


@payroll_router.put("/runs/{run_id}/lines", dependencies=[perm_dep("payroll", "edit")])
def update_run_lines(run_id: int, body: RunLinesUpdate, user: CurrentUserDep, session: SessionDep):
    """Update individual payroll line amounts (override mode)."""
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "draft":
        raise HTTPException(400, "Only draft runs can be edited")
    for lu in body.lines:
        line = session.exec(
            select(PayrollLine).where(
                PayrollLine.payroll_run_id == run_id,
                PayrollLine.employee_id == lu.employee_id,
            )
        ).first()
        if line:
            line.gross_earnings = lu.gross_earnings
            line.total_deductions = lu.total_deductions
            line.net_pay = lu.net_pay
            session.add(line)
    session.commit()
    return {"ok": True}


@payroll_router.post("/runs/{run_id}/approve", dependencies=[perm_dep("payroll", "edit")])
def approve_run(run_id: int, user: CurrentUserDep, session: SessionDep):
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "draft":
        raise HTTPException(400, f"Run is already {run.status}")
    run.status = "approved"
    session.add(run)
    session.commit()
    return {"ok": True}


@payroll_router.post("/runs/{run_id}/post", dependencies=[perm_dep("payroll", "edit")])
def post_run(run_id: int, user: CurrentUserDep, session: SessionDep):
    """Post approved payroll run to the GL.

    Aggregates all line amounts by GL account:
    - Earnings → Dr expense accounts (or fallback salary expense)
    - Net pay → Cr salaries payable (or fallback liability)
    - Deductions → Cr their respective accounts (or fallback liability)
    """
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "approved":
        raise HTTPException(400, "Run must be approved before posting")
    if run.transaction_id:
        raise HTTPException(400, "Run is already posted")

    lines = session.exec(
        select(PayrollLine).where(PayrollLine.payroll_run_id == run_id)
    ).all()

    if not lines:
        raise HTTPException(400, "No payroll lines — nothing to post")

    total_net = sum(l.net_pay for l in lines)
    if total_net <= 0:
        raise HTTPException(400, "Total net pay is zero — nothing to post")

    # Find fallback accounts
    expense_acct = _find_salary_expense_account(session, user.tenant_id)
    payable_acct = _find_salaries_payable_account(session, user.tenant_id)

    if not expense_acct:
        raise HTTPException(400, "No expense account found. Please configure a salary expense GL account.")
    if not payable_acct:
        raise HTTPException(400, "No liability account found. Please configure a salaries payable GL account.")

    # Aggregate debits (earnings) by GL account
    dr_by_account: dict[int, float] = {}
    # Aggregate credits (deductions) by GL account
    cr_by_account: dict[int, float] = {}

    # Collect all line details
    for line in lines:
        details = session.exec(
            select(PayrollLineDetail, SalaryComponent)
            .join(SalaryComponent, PayrollLineDetail.component_id == SalaryComponent.id)  # type: ignore[arg-type]
            .where(PayrollLineDetail.payroll_line_id == line.id)
        ).all()
        for detail, comp in details:
            gl_id = comp.gl_account_id if comp.gl_account_id else (
                expense_acct.id if comp.component_type == "earnings" else payable_acct.id
            )
            if comp.component_type == "earnings":
                dr_by_account[gl_id] = dr_by_account.get(gl_id, 0.0) + detail.amount
            elif comp.component_type in ("deductions", "statutory"):
                cr_by_account[gl_id] = cr_by_account.get(gl_id, 0.0) + detail.amount

    # If no component details at all, use totals directly
    if not dr_by_account:
        total_gross = sum(l.gross_earnings for l in lines)
        dr_by_account[expense_acct.id] = total_gross

    # Build entry list
    # Double-entry: Dr gross (earnings) = Cr net pay (payable) + Cr deductions (each account)
    entries: list[EntryInput] = []
    for acct_id, amt in dr_by_account.items():
        if amt > 0:
            entries.append(EntryInput(account_id=acct_id, debit=amt, credit=0))

    # Credit: net pay → salaries payable
    entries.append(EntryInput(account_id=payable_acct.id, debit=0, credit=float(total_net)))

    # Credit: each deduction to its account (separate from net pay line)
    for acct_id, amt in cr_by_account.items():
        if amt > 0:
            entries.append(EntryInput(account_id=acct_id, debit=0, credit=amt))

    # Post the transaction
    txn = post_transaction(
        session,
        user,
        date=run.pay_date,
        description=f"Payroll — {run.period_start} to {run.period_end}",
        voucher_type="JV",
        entries=entries,
        audit_detail={"payroll_run_id": run_id, "period_start": run.period_start, "period_end": run.period_end},
    )

    run.transaction_id = txn.id
    run.jv_number = txn.jv_number
    run.status = "posted"
    session.add(run)
    session.commit()
    return {"ok": True, "jv_number": txn.jv_number, "transaction_id": txn.id}


@payroll_router.post("/runs/{run_id}/void", dependencies=[perm_dep("payroll", "edit")])
def void_run(run_id: int, user: CurrentUserDep, session: SessionDep):
    """Void a posted payroll run by creating a reversing GL entry."""
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")
    if run.status != "posted":
        raise HTTPException(400, "Only posted runs can be voided")

    # Get original transaction entries
    from models import JournalEntry
    orig_entries = session.exec(
        select(JournalEntry).where(JournalEntry.transaction_id == run.transaction_id)
    ).all()

    if not orig_entries:
        raise HTTPException(400, "Original journal entries not found")

    # Build reversing entries (swap Dr/Cr)
    reversing: list[EntryInput] = [
        EntryInput(account_id=e.account_id, debit=float(e.credit), credit=float(e.debit))
        for e in orig_entries
        if float(e.debit) > 0 or float(e.credit) > 0
    ]

    rev_txn = post_transaction(
        session,
        user,
        date=run.pay_date,
        description=f"VOID Payroll — {run.period_start} to {run.period_end}",
        voucher_type="JV",
        entries=reversing,
        audit_detail={"void_payroll_run_id": run_id},
    )

    run.status = "void"
    session.add(run)
    session.commit()
    return {"ok": True, "reversing_jv": rev_txn.jv_number}


# ── Payslip ───────────────────────────────────────────────────────────────────

@payroll_router.get("/runs/{run_id}/payslip/{emp_id}")
def get_payslip(run_id: int, emp_id: int, user: CurrentUserDep, session: SessionDep):
    run = session.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id:
        raise HTTPException(404, "Payroll run not found")
    emp = session.get(Employee, emp_id)
    if not emp or emp.tenant_id != user.tenant_id:
        raise HTTPException(404, "Employee not found")

    line = session.exec(
        select(PayrollLine).where(
            PayrollLine.payroll_run_id == run_id,
            PayrollLine.employee_id == emp_id,
        )
    ).first()
    if not line:
        raise HTTPException(404, "Payroll line not found for this employee in this run")

    details = session.exec(
        select(PayrollLineDetail, SalaryComponent)
        .join(SalaryComponent, PayrollLineDetail.component_id == SalaryComponent.id)  # type: ignore[arg-type]
        .where(PayrollLineDetail.payroll_line_id == line.id)
    ).all()

    earnings = [
        {"name": c.name, "code": c.code, "amount": d.amount}
        for d, c in details if c.component_type == "earnings"
    ]
    deductions = [
        {"name": c.name, "code": c.code, "amount": d.amount}
        for d, c in details if c.component_type in ("deductions", "statutory")
    ]

    from routers.leave import unpaid_leave_days
    from models import LeaveRequest, LeaveType
    leave_rows = session.exec(
        select(LeaveRequest, LeaveType)
        .join(LeaveType, LeaveRequest.leave_type_id == LeaveType.id)  # type: ignore[arg-type]
        .where(
            LeaveRequest.tenant_id == user.tenant_id,
            LeaveRequest.employee_id == emp_id,
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= run.period_end,
            LeaveRequest.to_date >= run.period_start,
        )
    ).all()
    leave_summary = [
        {
            "leave_type": lt.name,
            "code": lt.code,
            "is_paid": lt.is_paid,
            "from_date": req.from_date,
            "to_date": req.to_date,
            "days": req.days,
        }
        for req, lt in leave_rows
    ]
    unpaid_days = unpaid_leave_days(
        session, user.tenant_id, emp_id, run.period_start, run.period_end
    )

    return {
        "run": {
            "id": run.id,
            "period_start": run.period_start,
            "period_end": run.period_end,
            "pay_date": run.pay_date,
            "jv_number": run.jv_number,
            "status": run.status,
        },
        "employee": {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "name": emp.name,
            "department": emp.department,
            "designation": emp.designation,
            "bank_account": emp.bank_account,
            "bank_name": emp.bank_name,
        },
        "earnings": earnings,
        "deductions": deductions,
        "leave": leave_summary,
        "unpaid_leave_days": unpaid_days,
        "gross_earnings": line.gross_earnings,
        "total_deductions": line.total_deductions,
        "net_pay": line.net_pay,
    }


# ── Combine into a single router for main.py ──────────────────────────────────

router = APIRouter()
router.include_router(employees_router)
router.include_router(payroll_router)
