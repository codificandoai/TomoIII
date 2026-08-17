"""
Codificando.AI - UC-179
DAG de Airflow para la etapa de recolección/ETL. Es un envoltorio fino
sobre `pipeline_service.ContinuousLearningPipeline.ingest`; toda la
lógica de negocio vive en el pipeline reutilizable, no en la DAG.

Requiere `apache-airflow` (no incluido en `requirements.txt` del
pipeline; ver la sección opcional de dependencias). Este archivo no se
importa desde `app.py`/`UC-179.py`/pruebas — solo lo carga el scheduler
de Airflow cuando este módulo se registra en su `DAGS_FOLDER`.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from pipeline_service import ContinuousLearningPipeline

default_args = {
    "owner": "ml_system",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": True,
    "email": ["ml-team@company.com"],
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def collect_data(**kwargs) -> dict:
    pipeline = ContinuousLearningPipeline()
    sources = [
        {"type": "user_feedback", "data": kwargs.get("dag_run").conf.get("feedback_data", [])},
        {"type": "annotations", "data": kwargs.get("dag_run").conf.get("annotations", [])},
    ]
    return pipeline.ingest(sources)


def validate_data_quality(**kwargs) -> dict:
    pipeline = ContinuousLearningPipeline()
    new_count = pipeline.kb.get_new_samples_count()
    if new_count < 100:
        return {"status": "skip", "reason": "Insufficient new data"}
    return {"status": "success", "new_samples": new_count}


with DAG(
    "data_etl_pipeline",
    default_args=default_args,
    description="ETL pipeline for continuous learning training data (UC-179)",
    schedule_interval="0 0 * * *",
    catchup=False,
    tags=["ml", "etl", "uc-179"],
) as dag:

    collect_task = PythonOperator(task_id="collect_data", python_callable=collect_data)
    validate_task = PythonOperator(task_id="validate_data_quality", python_callable=validate_data_quality)

    collect_task >> validate_task
