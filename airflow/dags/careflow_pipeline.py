"""Optional scheduled Snowflake ELT DAG. Requires the optional cloud dependencies and credentials."""
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
from airflow import DAG
from airflow.operators.python import PythonOperator
ROOT=Path(__file__).resolve().parents[2]

def run_ingestion():
    from pipeline.core import ingest
    return ingest(ROOT/'data'/'careflow.db')

def cloud_upload():
    from scripts.load_snowflake import upload
    upload()

def transform_and_test():
    subprocess.run(['dbt','build','--project-dir',str(ROOT/'dbt')],check=True,timeout=900)

with DAG('careflow360_daily',start_date=datetime(2026,1,1),schedule='@daily',catchup=False,
         default_args={'retries':2,'retry_delay':timedelta(minutes=5)},tags=['careflow','synthetic']) as dag:
    ingest=PythonOperator(task_id='generate_and_ingest_synthetic',python_callable=run_ingestion)
    load=PythonOperator(task_id='merge_snowflake_raw',python_callable=cloud_upload)
    build=PythonOperator(task_id='run_dbt_models_and_tests',python_callable=transform_and_test)
    ingest >> load >> build
