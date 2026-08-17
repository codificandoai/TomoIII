"""Fixtures compartidos para las pruebas de UC-179."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.data_collector import DataCollector
from core.deployment_manager import DeploymentManager
from core.knowledge_base import KnowledgeBase
from core.model_validator import ModelValidator
from models.trainer import ModelTrainer
from pipeline_service import ContinuousLearningPipeline


@pytest.fixture()
def kb(tmp_path) -> KnowledgeBase:
    return KnowledgeBase(tmp_path / "kb.db")


@pytest.fixture()
def collector(kb) -> DataCollector:
    return DataCollector(kb)


@pytest.fixture()
def trainer(kb, tmp_path) -> ModelTrainer:
    return ModelTrainer(kb, tmp_path / "models" / "versions")


@pytest.fixture()
def validator(kb) -> ModelValidator:
    return ModelValidator(kb)


@pytest.fixture()
def deployment(kb, tmp_path) -> DeploymentManager:
    return DeploymentManager(kb, tmp_path / "models" / "production")


@pytest.fixture()
def pipeline(tmp_path) -> ContinuousLearningPipeline:
    return ContinuousLearningPipeline(
        db_path=tmp_path / "kb.db",
        model_versions_dir=tmp_path / "models" / "versions",
        production_dir=tmp_path / "models" / "production",
    )


def make_dataset(n_per_class: int = 15):
    """Genera un dataset sintético balanceado de dos clases para pruebas
    de entrenamiento/validación."""
    data = []
    for i in range(n_per_class):
        data.append({"input": f"pregunta de soporte tecnico numero {i}", "output": "respuesta_soporte"})
    for i in range(n_per_class):
        data.append({"input": f"pregunta de facturacion numero {i}", "output": "respuesta_facturacion"})
    return data
