"""
Codificando.AI - UC-179
DAG de Airflow para validar y desplegar (si corresponde) el modelo
entrenado por `training_dag.py`, delegando en
`pipeline_service.ContinuousLearningPipeline`.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from pipeline_service import ContinuousLearningPipeline

default_args = {
    "owner": "ml_system",
    "start_date": datetime(2024, 1, 1),
    "retries": 2,
}


def validate_new_model(**kwargs) -> dict:
    ti = kwargs["ti"]
    training_info = ti.xcom_pull(dag_id="model_training_pipeline", task_ids="full_retraining") or \
        ti.xcom_pull(dag_id="model_training_pipeline", task_ids="fine_tuning")

    if not training_info or training_info.get("status") != "trained":
        return {"status": "skip", "reason": "No model to validate"}

    pipeline = ContinuousLearningPipeline()
    validation_results = pipeline.validate(model_version=training_info["model_version"])

    ti.xcom_push(key="validation_results", value=validation_results)
    ti.xcom_push(key="model_version", value=training_info["model_version"])
    return validation_results


def deploy_if_better(**kwargs) -> dict:
    ti = kwargs["ti"]
    validation_results = ti.xcom_pull(key="validation_results")
    model_version = ti.xcom_pull(key="model_version")

    if not validation_results or not model_version:
        return {"status": "skip"}

    pipeline = ContinuousLearningPipeline()
    return pipeline.deploy(model_version, force=False)


with DAG(
    "model_validation_pipeline",
    default_args=default_args,
    description="Model validation and deployment (UC-179)",
    schedule_interval=None,
    catchup=False,
    tags=["ml", "validation", "uc-179"],
) as dag:

    validate_task = PythonOperator(task_id="validate_model", python_callable=validate_new_model)
    deploy_task = PythonOperator(task_id="deploy_if_better", python_callable=deploy_if_better)

    validate_task >> deploy_task
