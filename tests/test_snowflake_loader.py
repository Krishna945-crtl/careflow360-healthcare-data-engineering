import pytest
from scripts.load_snowflake import DATABASE, TABLES, batch_merge_sql, connection_options


def test_sql_batched_and_parameterized():
    for table, columns in TABLES:
        sql = batch_merge_sql(table, columns, 2)
        assert f"MERGE INTO {DATABASE}.RAW.{table}" in sql
        assert sql.count("%s") == 2 * len(columns)
        assert "UNION ALL" in sql
        assert f"ON t.{columns[0]} = s.{columns[0]}" in sql


def test_date_and_timestamp_casts():
    table, cols = TABLES[2]
    sql = batch_merge_sql(table, cols, 1)
    assert "TRY_TO_DATE(%s)" in sql
    assert "TRY_TO_TIMESTAMP_TZ(%s)" in sql


def test_reject_bad_identifiers():
    with pytest.raises(ValueError):
        batch_merge_sql("INVENTED", ("ID",), 1)
    with pytest.raises(ValueError):
        batch_merge_sql("CLINICS", TABLES[0][1], 0)


def test_browser_auth_no_password(monkeypatch):
    for k, v in {
        "SNOWFLAKE_ACCOUNT": "testorg-testaccount", "SNOWFLAKE_USER": "testuser",
        "SNOWFLAKE_WAREHOUSE": "CAREFLOW_WH", "SNOWFLAKE_ROLE": "CAREFLOW_INGEST_ROLE",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("SNOWFLAKE_AUTHENTICATOR", raising=False)
    monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
    options = connection_options()
    assert options["authenticator"] == "externalbrowser"
    assert "password" not in options
    assert options["database"] == "CAREFLOW_DB"
