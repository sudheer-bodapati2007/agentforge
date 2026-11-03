"""AgentForge database test runner (baked into the sandbox image; trusted code).

Used when a project has a PostgreSQL database. Inside the sandbox container it:
  1. applies /workspace/db/migrations/*.sql in name order, each in its own transaction,
     stopping at the first failure;
  2. reads the resulting schema back from the database (tables, columns, keys, indexes);
  3. writes both to /out/database.json;
  4. runs pytest with the same fixed arguments as every other test run, and exits with
     pytest's exit code.

Nothing here comes from model output except the SQL files, which run inside the
throwaway database as a non-superuser role.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg
from sqlalchemy import create_engine, inspect

MIGRATIONS = Path("/workspace/db/migrations")
OUT = Path("/out/database.json")
PYTEST = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--timeout=30", "--junitxml=/out/junit.xml"]
MAX_SQL_BYTES = 200_000


def connect(url: str, attempts: int = 20) -> psycopg.Connection:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return psycopg.connect(url, connect_timeout=3)
        except psycopg.OperationalError as exc:  # the server may still be starting
            last = exc
            time.sleep(0.5)
    raise RuntimeError(f"could not connect to the test database: {last}")


def apply_migrations(url: str) -> list[dict]:
    results: list[dict] = []
    files = sorted(MIGRATIONS.glob("*.sql")) if MIGRATIONS.is_dir() else []
    with connect(url) as conn:
        for path in files:
            sql = path.read_text(encoding="utf-8", errors="replace")
            if len(sql.encode("utf-8")) > MAX_SQL_BYTES:
                results.append({"file": path.name, "ok": False, "error": "migration file is too large"})
                break
            try:
                with conn.transaction():
                    conn.execute(sql)
                results.append({"file": path.name, "ok": True, "error": None})
            except psycopg.Error as exc:
                results.append({"file": path.name, "ok": False, "error": str(exc).strip()[:1000]})
                break
    return results


def describe_schema(sqlalchemy_url: str) -> list[dict]:
    engine = create_engine(sqlalchemy_url)
    try:
        inspector = inspect(engine)
        tables = []
        for name in sorted(inspector.get_table_names()):
            pk = inspector.get_pk_constraint(name).get("constrained_columns") or []
            tables.append(
                {
                    "name": name,
                    "columns": [
                        {
                            "name": c["name"],
                            "type": str(c["type"]),
                            "nullable": bool(c["nullable"]),
                            "default": None if c.get("default") is None else str(c["default"])[:200],
                            "primary_key": c["name"] in pk,
                        }
                        for c in inspector.get_columns(name)
                    ],
                    "foreign_keys": [
                        {
                            "columns": fk["constrained_columns"],
                            "references": f"{fk['referred_table']}({', '.join(fk['referred_columns'])})",
                        }
                        for fk in inspector.get_foreign_keys(name)
                    ],
                    "unique": [u["column_names"] for u in inspector.get_unique_constraints(name)],
                    "indexes": [{"name": i["name"], "columns": i["column_names"], "unique": bool(i["unique"])} for i in inspector.get_indexes(name)],
                }
            )
        return tables
    finally:
        engine.dispose()


def main() -> int:
    sqlalchemy_url = os.environ["DATABASE_URL"]  # postgresql+psycopg://... for the generated app
    plain_url = sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)
    report: dict = {"migrations": [], "schema": [], "error": None}
    try:
        report["migrations"] = apply_migrations(plain_url)
        report["schema"] = describe_schema(sqlalchemy_url)
    except Exception as exc:  # reported, never hidden: the tests still run and show the effect
        report["error"] = f"{exc.__class__.__name__}: {str(exc)[:1000]}"
    OUT.write_text(json.dumps(report), encoding="utf-8")
    return subprocess.call(PYTEST, cwd="/workspace")


if __name__ == "__main__":
    sys.exit(main())
