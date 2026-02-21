import os
from typing import Optional

import httpx
import uvicorn
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

EMPLOYEE_API_URL = os.environ.get("EMPLOYEE_API_URL", "http://localhost:8001")

mcp = FastMCP("Employee Directory")


def _api(method: str, path: str, **kwargs):
    url = f"{EMPLOYEE_API_URL}{path}"
    resp = httpx.request(method, url, **kwargs)
    if resp.status_code in (400, 404):
        raise ValueError(resp.json().get("detail", resp.text))
    resp.raise_for_status()
    return resp.json()


# ── Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_employees(active_only: bool = True) -> list[dict]:
    """Return all employees, optionally filtered to active ones only."""
    return _api("GET", "/employees", params={"active_only": active_only})


@mcp.tool()
def get_employee(employee_id: int) -> dict:
    """Return a single employee record by ID."""
    return _api("GET", f"/employees/{employee_id}")


@mcp.tool()
def search_employees(query: str) -> list[dict]:
    """Search employees by first name, last name, email, or job title (case-insensitive)."""
    return _api("GET", "/employees/search", params={"q": query})


@mcp.tool()
def list_departments() -> list[dict]:
    """Return all departments with employee headcount."""
    return _api("GET", "/departments")


@mcp.tool()
def get_employees_by_department(department_name: str, active_only: bool = True) -> list[dict]:
    """Return all employees in a given department (case-insensitive name match)."""
    return _api("GET", f"/departments/{department_name}/employees", params={"active_only": active_only})


@mcp.tool()
def get_salary_stats(department_name: Optional[str] = None) -> dict:
    """Return min / max / average salary, optionally scoped to a department."""
    params = {}
    if department_name:
        params["department"] = department_name
    return _api("GET", "/salary-stats", params=params)


@mcp.tool()
def get_schema() -> dict:
    """Return the database schema: every table with its column names and types.

    Returns:
        A dict keyed by table name, each value being a list of
        { name, type, notnull, pk } dicts.
    """
    return _api("GET", "/schema")


@mcp.tool()
def execute_query(sql: str, params: list | None = None) -> dict:
    """Execute a custom read-only SELECT query against the employee database.

    Only SELECT statements are permitted. Any attempt to run INSERT, UPDATE,
    DELETE, DROP, ALTER, CREATE, or other write/DDL statements will be rejected.

    Args:
        sql:    A valid SQLite SELECT statement.
        params: Optional list of positional parameters (? placeholders).

    Returns:
        A dict with keys:
          - columns: list of column names
          - rows:    list of row dicts
          - count:   number of rows returned

    Available tables:
      employees  (id, first_name, last_name, email, phone, department_id,
                  job_title, salary, hire_date, is_active)
      departments (id, name)
    """
    return _api("POST", "/query", json={"sql": sql, "params": params})


# ── Resources ──────────────────────────────────────────────────────────────

@mcp.resource("policy://leave")
def get_leave_policy() -> str:
    """Company leave policy document."""
    return """# Employee Leave Policy

## 1. Annual Leave
- Full-time employees accrue 15 days of paid annual leave per calendar year (pro-rated for part-time).
- Leave must be approved by the employee's direct manager at least 5 business days in advance.
- Unused leave of up to 5 days may be carried over to the following year; the remainder is forfeited.

## 2. Sick Leave
- Employees are entitled to 10 days of paid sick leave per year.
- A medical certificate is required for absences exceeding 3 consecutive days.
- Sick leave does not carry over to the next year.

## 3. Public Holidays
- Employees are entitled to all gazetted public holidays.
- Where an employee is required to work on a public holiday, a substitute day off will be granted.

## 4. Parental Leave
- **Maternity leave:** 16 weeks paid leave, commencing up to 4 weeks before the expected due date.
- **Paternity leave:** 2 weeks paid leave, to be taken within 4 weeks of the child's birth.
- **Adoption leave:** Same entitlements as maternity/paternity leave apply.

## 5. Compassionate Leave
- Up to 5 days of paid compassionate leave may be taken on the death of an immediate family member (spouse, child, parent, sibling).
- Up to 2 days for extended family members (grandparents, in-laws).

## 6. Unpaid Leave
- Employees may apply for unpaid leave for personal reasons after exhausting paid entitlements.
- Approval is at the discretion of the department head and HR.

## 7. Leave Application Process
1. Submit a leave request via the HR portal at least 5 business days in advance (except for emergencies).
2. Await written approval from your manager before confirming any travel or personal arrangements.
3. Ensure handover notes are completed before commencing leave.

## 8. Contact
For questions regarding this policy, contact **hr@company.com** or visit the HR portal.
"""


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cors = Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app = mcp.http_app(middleware=[cors], stateless_http=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
