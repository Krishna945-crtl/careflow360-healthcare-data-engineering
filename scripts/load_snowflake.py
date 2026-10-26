"""CareFlow 360 synthetic RAW loader for Snowflake.

Uses browser authentication by default and batched, parameterized MERGE statements.
Run from project root: python -m scripts.load_snowflake
Only synthetic fixture data is uploaded. No real patient information.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.core import CLINICS, fixture_rows

DATABASE = "CAREFLOW_DB"
SCHEMA = "RAW"
BATCH_SIZE = 40

TABLES = (
    ("CLINICS", ("CLINIC_ID", "NAME", "REGION")),
    ("PATIENTS", ("PATIENT_ID", "NAME", "BIRTH_YEAR", "CLINIC_ID")),
    ("APPOINTMENTS", ("APPOINTMENT_ID", "PATIENT_ID", "CLINIC_ID", "SCHEDULED_DATE", "STATUS", "TYPE", "UPDATED_AT")),
    ("ENCOUNTERS", ("ENCOUNTER_ID", "APPOINTMENT_ID", "ENCOUNTERED_ON", "UPDATED_AT")),
)


def connection_options() -> dict:
    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_ROLE")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Set environment variables: " + ", ".join(missing))
    opts = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "database": DATABASE,
        "schema": SCHEMA,
        "login_timeout": 60,
    }
    # External browser authentication is preferred for interactive, local development.
    auth = os.getenv("SNOWFLAKE_AUTHENTICATOR", "OAUTH_AUTHORIZATION_CODE")
    if auth == "snowflake":
        if not os.getenv("SNOWFLAKE_PASSWORD"):
            raise RuntimeError("SNOWFLAKE_PASSWORD required if SNOWFLAKE_AUTHENTICATOR=snowflake")
        opts["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    else:
        opts["authenticator"] = auth
    return opts


def batch_merge_sql(table: str, columns: tuple[str, ...], count: int) -> str:
    """Generate one parameterized Snowflake MERGE for <=40 distinct source rows."""
    allowed = dict(TABLES)
    if table not in allowed or allowed[table] != columns:
        raise ValueError("Unexpected table/column identifiers")
    if not 1 <= count <= BATCH_SIZE:
        raise ValueError("Invalid batch size")
    def expr(column: str) -> str:
        if column in ("SCHEDULED_DATE", "ENCOUNTERED_ON"):
            return "TRY_TO_DATE(%s)"
        if column == "UPDATED_AT":
            return "TRY_TO_TIMESTAMP_TZ(%s)"
        return "%s"
    select_parts = []
    for n in range(count):
        fields = [f"{expr(c)} AS {c}" if n == 0 else expr(c) for c in columns]
        select_parts.append("SELECT " + ", ".join(fields))
    source = " UNION ALL ".join(select_parts)
    key = columns[0]
    update = ", ".join(f"t.{c} = s.{c}" for c in columns[1:])
    insert_cols = ", ".join(columns)
    insert_values = ", ".join(f"s.{c}" for c in columns)
    return (f"MERGE INTO {DATABASE}.{SCHEMA}.{table} t USING ({source}) s "
            f"ON t.{key} = s.{key} "
            f"WHEN MATCHED THEN UPDATE SET {update} "
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_values})")


def upload() -> None:
    import snowflake.connector

    patients, appointments, encounters = fixture_rows()
    sources = (CLINICS, patients, appointments, encounters)
    con = snowflake.connector.connect(**connection_options())
    try:
        cur = con.cursor()
        try:
            role, database, schema = cur.execute(
                "SELECT CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA()"
            ).fetchone()
            print(f"Connected: role={role}, database={database}, schema={schema}")
            if (str(database).upper(), str(schema).upper()) != (DATABASE, SCHEMA):
                raise RuntimeError("Connected to unexpected database/schema; refusing to write")
            cur.execute("BEGIN")
            for (table, columns), rows in zip(TABLES, sources):
                keys = [row[0] for row in rows]
                if len(keys) != len(set(keys)):
                    raise ValueError(f"Duplicate source identifiers in {table}")
                for start in range(0, len(rows), BATCH_SIZE):
                    batch = rows[start:start + BATCH_SIZE]
                    flat_params = tuple(value for row in batch for value in row)
                    cur.execute(batch_merge_sql(table, columns, len(batch)), flat_params)
                print(f"{table}: {len(rows)} synthetic source rows merged")
            cur.execute("COMMIT")
            print("Snowflake RAW load committed successfully.")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        finally:
            cur.close()
    finally:
        con.close()


if __name__ == "__main__":
    upload()
