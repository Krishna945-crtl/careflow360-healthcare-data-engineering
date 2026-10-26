# CareFlow 360 — Snowflake RAW loading on Windows

This update replaces `scripts/load_snowflake.py`. It does **not** overwrite your existing local SQLite database, dashboard, or Snowflake data.

## 1. Set up a least-privilege role once

In a Snowflake worksheet with an administrative role, execute `warehouse/ingestion_role_setup.sql`. Run `SELECT CURRENT_USER();` and then the final commented `GRANT ROLE` statement with your own Snowflake username. The role needs permission to `SELECT`, `INSERT`, and `UPDATE` the four already-created RAW tables, not permission to drop them.

## 2. Set Windows environment variables

In the *same Command Prompt* where you plan to run the loader, from the `careflow360` folder with `.venv` active:

```cmd
set "SNOWFLAKE_ACCOUNT=YOUR_ORG-YOUR_ACCOUNT"
set "SNOWFLAKE_USER=YOUR_USER"
set "SNOWFLAKE_WAREHOUSE=CAREFLOW_WH"
set "SNOWFLAKE_ROLE=CAREFLOW_INGEST_ROLE"
```

You can find your organization and account name from `SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME();`. Replace the placeholders. Do not paste authentication secrets into chats or GitHub. The script defaults to `authenticator='externalbrowser'`; Snowflake account configuration determines whether it is supported.

## 3. Check your environment and tests

```cmd
python -m pip install snowflake-connector-python
python -m pytest tests -v
```

## 4. Run ingestion

```cmd
python -m scripts.load_snowflake
```

A browser sign-in may appear. If your account does not support external-browser login, stop and configure a supported Snowflake authentication method rather than putting passwords into source code. The script supports `SNOWFLAKE_AUTHENTICATOR=snowflake` plus `SNOWFLAKE_PASSWORD` as an *optional* environment-based fallback, but avoid printing or committing secrets.

## 5. Verify counts

```sql
SELECT 'CLINICS' TABLE_NAME, COUNT(*) N FROM CAREFLOW_DB.RAW.CLINICS
UNION ALL SELECT 'PATIENTS', COUNT(*) FROM CAREFLOW_DB.RAW.PATIENTS
UNION ALL SELECT 'APPOINTMENTS', COUNT(*) FROM CAREFLOW_DB.RAW.APPOINTMENTS
UNION ALL SELECT 'ENCOUNTERS', COUNT(*) FROM CAREFLOW_DB.RAW.ENCOUNTERS;
```

The generated fixture currently includes five clinics, 700 patients and 2,100 appointments. The number of encounter records depends on the deterministic fixture generation. Re-running the loader on the same day should preserve counts because MERGEs match on source identifiers.

### Technical notes

- This is a batched parameterized MERGE implementation (40 rows per MERGE), not an industrial bulk COPY INTO loader.
- Snowflake can't be reached or authenticated from the delivered project in this environment; successful cloud ingestion must be verified on your account.
- Before production use, add dedicated batch audit logs, source record versioning, full error-quarantine and warehouse cost controls.
