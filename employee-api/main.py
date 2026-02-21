import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from init_db import DB_PATH, init_db

if not os.path.exists(DB_PATH):
    init_db()

app = FastAPI(title="Employee API")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


@app.get("/employees")
def list_employees(active_only: bool = True) -> list[dict]:
    with get_db() as conn:
        query = """
            SELECT e.id, e.first_name, e.last_name, e.email, e.phone,
                   d.name AS department, e.job_title, e.salary,
                   e.hire_date, e.is_active
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
        """
        if active_only:
            query += " WHERE e.is_active = 1"
        query += " ORDER BY e.last_name, e.first_name"
        rows = conn.execute(query).fetchall()
        return [row_to_dict(r) for r in rows]


@app.get("/employees/search")
def search_employees(q: str) -> list[dict]:
    pattern = f"%{q}%"
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.first_name, e.last_name, e.email, e.phone,
                   d.name AS department, e.job_title, e.salary,
                   e.hire_date, e.is_active
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
            WHERE e.first_name  LIKE ?
               OR e.last_name   LIKE ?
               OR e.email       LIKE ?
               OR e.job_title   LIKE ?
            ORDER BY e.last_name, e.first_name
            """,
            (pattern, pattern, pattern, pattern),
        ).fetchall()
    return [row_to_dict(r) for r in rows]


@app.get("/employees/{employee_id}")
def get_employee(employee_id: int) -> dict:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT e.id, e.first_name, e.last_name, e.email, e.phone,
                   d.name AS department, e.job_title, e.salary,
                   e.hire_date, e.is_active
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
            WHERE e.id = ?
            """,
            (employee_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No employee found with id={employee_id}")
    return row_to_dict(row)


@app.get("/departments")
def list_departments() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.name,
                   COUNT(e.id)                                       AS total_employees,
                   SUM(CASE WHEN e.is_active = 1 THEN 1 ELSE 0 END) AS active_employees
            FROM departments d
            LEFT JOIN employees e ON e.department_id = d.id
            GROUP BY d.id, d.name
            ORDER BY d.name
            """
        ).fetchall()
    return [row_to_dict(r) for r in rows]


@app.get("/departments/{department_name}/employees")
def get_employees_by_department(department_name: str, active_only: bool = True) -> list[dict]:
    with get_db() as conn:
        query = """
            SELECT e.id, e.first_name, e.last_name, e.email, e.phone,
                   d.name AS department, e.job_title, e.salary,
                   e.hire_date, e.is_active
            FROM employees e
            JOIN departments d ON d.id = e.department_id
            WHERE LOWER(d.name) = LOWER(?)
        """
        params: list = [department_name]
        if active_only:
            query += " AND e.is_active = 1"
        query += " ORDER BY e.last_name, e.first_name"
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]


@app.get("/salary-stats")
def get_salary_stats(department: Optional[str] = None) -> dict:
    with get_db() as conn:
        if department:
            row = conn.execute(
                """
                SELECT MIN(e.salary) AS min_salary,
                       MAX(e.salary) AS max_salary,
                       ROUND(AVG(e.salary), 2) AS avg_salary,
                       COUNT(*) AS employee_count
                FROM employees e
                JOIN departments d ON d.id = e.department_id
                WHERE LOWER(d.name) = LOWER(?) AND e.is_active = 1
                """,
                (department,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT MIN(salary) AS min_salary,
                       MAX(salary) AS max_salary,
                       ROUND(AVG(salary), 2) AS avg_salary,
                       COUNT(*) AS employee_count
                FROM employees
                WHERE is_active = 1
                """
            ).fetchone()
    return row_to_dict(row)


@app.get("/schema")
def get_schema() -> dict:
    with get_db() as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        schema: dict = {}
        for table in tables:
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            schema[table] = [
                {
                    "name":    col[1],
                    "type":    col[2],
                    "notnull": bool(col[3]),
                    "pk":      bool(col[5]),
                }
                for col in cols
            ]
    return schema


class QueryRequest(BaseModel):
    sql: str
    params: Optional[list] = None


@app.post("/query")
def execute_query(request: QueryRequest) -> dict:
    _BLOCKED = {"insert", "update", "delete", "drop", "alter",
                "create", "replace", "truncate", "pragma", "attach", "detach"}

    normalised = request.sql.strip().lower()
    if not normalised.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed.")

    first_token = normalised.split()[0]
    if first_token in _BLOCKED:
        raise HTTPException(status_code=400, detail=f"Statement type '{first_token}' is not permitted.")

    tokens = set(normalised.replace("(", " ").replace(")", " ").split())
    blocked_found = tokens & _BLOCKED
    if blocked_found:
        raise HTTPException(status_code=400, detail=f"Query contains forbidden keyword(s): {blocked_found}")

    with get_db() as conn:
        cursor = conn.execute(request.sql, request.params or [])
        columns = [d[0] for d in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return {"columns": columns, "rows": rows, "count": len(rows)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
