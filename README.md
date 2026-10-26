> **Snowflake setup update:** See [SNOWFLAKE_NEXT_STEPS.md](SNOWFLAKE_NEXT_STEPS.md) for secure local loading. Database references use `CAREFLOW_DB`. The Snowflake/dbt/Airflow cloud workflow is not validated until you run it against your account.

# CareFlow 360
### Multi-Clinic Care Continuity & Data Reliability Platform

A privacy-safe, portfolio-grade healthcare operations application featuring a responsive dashboard, deterministic synthetic data, reliable local ETL, quarantined invalid records, and optional Snowflake/dbt/Airflow cloud ELT.

> **This is a synthetic demonstration, not a clinical system.** It contains no real patient information. Care gaps are operational data-quality flags, not clinical assessments.

## Features

- **Responsive dashboard:** four KPIs, weekly appointment trends, completion mix, per-clinic performance, exception queue and audit information
- **Interactive filtering:** five clinics and 7/30/90-day windows, with CSV export of the currently filtered exception sample
- **Deterministic ingestion:** reproducible 700 synthetic patients and 2,100 appointments, UPSERT rather than duplicate inserts, repeatable validation and intentionally quarantined bad source rows
- **Auditability:** ingestion history, rejected-record reasons and unique source identifiers
- **Cloud ELT reference:** Snowflake RAW schemas and MERGE loader, dbt staging/marts/tests, optional Airflow DAG with retry policy
- **CI:** pytest quality checks on pull requests and pushes

## Quick start — working demo, no cloud account required

Requires Python 3.10+.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. Data is generated on the first launch and stored in `data/careflow.db`.

Run tests:

```bash
pytest -q
```

Or launch with Docker:

```bash
docker compose up --build
```

## Architecture

```text
Synthetic source generator (Python)
       |
       +--> SQLite: idempotent upserts + quarantine + run audit
       |       |
       |       +--> FastAPI -> responsive operations dashboard
       |
       +--> [optional Snowflake MERGE loader]
                   |
                   v
                RAW tables
                   |
                   v
          dbt staging -> care continuity fact -> clinic performance mart
                   ^
                   |
          [optional Airflow DAG: ingest -> load -> dbt build/tests]
```

**Important:** The local dashboard reads SQLite. Snowflake/dbt/Airflow are real project components but are **optional and not automatically provisioned, configured, or exercised by the local demo**. The project does not claim those cloud paths were run during local testing.

## Metrics definitions

| Metric | Definition |
| --- | --- |
| Appointments | Number of appointments scheduled in the selected period |
| Completion rate | Appointments marked `completed` / all appointments |
| No-show rate | Appointments marked `no_show` / all appointments |
| Care gaps | Completed **follow-up** appointments without a matching encounter record |
| Unmatched encounter evidence | All completed appointments without a matching encounter |
| Quarantined rows | Known bad source events rejected by the demonstration ingestion validator |

This is deliberately an **operational** definition. A missing encounter can mean delayed ingestion rather than missed medical care. It should be investigated, not treated as a medical conclusion.

## Cloud ELT setup (optional, requires your account)

1. Create a Snowflake trial/account, warehouse and a least-privilege role. Never commit credentials.
2. Run `warehouse/snowflake_setup.sql` in the Snowflake SQL worksheet with authorized permissions.
3. Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, and `SNOWFLAKE_ROLE` as environment variables.
4. Install optional dependencies: `pip install snowflake-connector-python dbt-snowflake`.
5. Execute `python -m scripts.load_snowflake` to merge generated rows into RAW tables.
6. Copy `dbt/profiles.example.yml` into `~/.dbt/profiles.yml` and run `dbt build --project-dir dbt`.
7. To schedule, install/configure compatible Apache Airflow in a **separate environment**, make the project importable from its worker, register `airflow/dags/careflow_pipeline.py`, and ensure dbt/Snowflake credentials exist in the worker. The optional DAG runs ingest -> Snowflake RAW merge -> dbt build/tests.

**Production improvement:** Snowflake `COPY INTO` with stages and task-specific least-privilege service accounts, Airflow Secrets Backend, a reliable watermark/CDC process, and backfill monitoring. The supplied per-row MERGE loader is for this small portfolio dataset, not bulk production throughput.

## Quality, privacy & limitations

- The local FastAPI `/api/pipeline/run` endpoint is intentionally unauthenticated for localhost demos; **do not publicly deploy this endpoint** without auth, rate limiting and authorization.
- The CSV export includes anonymized appointment IDs and hashed pseudonymous patient references; no names or DOBs are exported.
- Patient identities are synthetic. Cross-clinic visit history is linked by deterministic ID, **not** probabilistic real-person matching.
- Quarantine is an illustrative validation path for three deliberately malformed source events. Broader automated source-level validation would be required for production.
- The `exceptions.csv` endpoint exports the **top 12 displayed exceptions**, not the entire source table.
- Appointment status and encounter presence may disagree due to synthetic missing events; the dashboard treats this as an audit task.
- Current snapshots are synthetic and relative to the day the demo runs; not longitudinal regulated patient datasets.
- SQLite is intentionally single-node and is not presented as a scalable production data warehouse.
- The example cloud schemas support deduplication, but do not yet implement full SCD Type 2 or guaranteed exactly-once external CDC.

## Interview demo route

1. Open overview and change period from 90 to 7 days.
2. Filter to one clinic and compare its completion/no-show rates.
3. Open care exceptions, explain why missing encounter data warrants investigation.
4. Show quarantine reasons and discuss fail-open vs fail-closed decisions.
5. Click **Run pipeline** twice: demonstrate idempotent appointment counts despite two audit runs.
6. Show Snowflake schema, dbt models/tests and optional Airflow DAG, and explain which components need external configuration.

## Structure

```text
app/                 FastAPI + polished responsive dashboard
pipeline/            deterministic synthetic generator, local ingestion, KPI definitions
tests/               ingestion integrity and filter tests
warehouse/           Snowflake RAW schema
scripts/             optional Snowflake MERGE loader
dbt/                 staging, marts and schema tests
airflow/dags/        optional ELT orchestration
.github/workflows/   CI test job
```

## Attribution

Original demonstration implementation. All records and clinic names are fictitious; no identifiable health information is used.
