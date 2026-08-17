"""
Codificando.AI - UC-179
DAG de Airflow para el disparo y ejecución del reentrenamiento
(completo o fine-tuning), delegando toda la lógica en
`pipeline_service.ContinuousLearningPipeline`.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

from pipeline_service import ContinuousLearningPipeline

default_args = {
    "owner": "ml_system",
    "start_date": datetime(2024, 1, 1),
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


def check_retraining_trigger(**kwargs) -> str:
    pipeline = ContinuousLearningPipeline()
    trigger = pipeline.check_retraining_trigger()
    return {"full_retraining": "full_retraining", "fine_tuning": "fine_tuning"}.get(trigger, "no_training")


def execute_full_retraining(**kwargs) -> dict:
    pipeline = ContinuousLearningPipeline()
    return pipeline.train(training_type="full_retraining", validate_after=False)


def execute_fine_tuning(**kwargs) -> dict:
    pipeline = ContinuousLearningPipeline()
    return pipeline.train(training_type="fine_tuning", validate_after=False)


with DAG(
    "model_training_pipeline",
    default_args=default_args,
    description="Automated model training pipeline (UC-179)",
    schedule_interval="0 2 * * 0",
    catchup=False,
    tags=["ml", "training", "uc-179"],
) as dag:

    check_trigger = BranchPythonOperator(task_id="check_retraining_trigger",
                                          python_callable=check_retraining_trigger)
    full_training = PythonOperator(task_id="full_retraining", python_callable=execute_full_retraining)
    fine_tune = PythonOperator(task_id="fine_tuning", python_callable=execute_fine_tuning)
    no_training = DummyOperator(task_id="no_training")

    check_trigger >> [full_training, fine_tune, no_training]
