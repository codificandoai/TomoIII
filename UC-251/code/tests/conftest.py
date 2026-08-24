"""Configuración de tests: forzar componentes stub para ejecución offline."""
import os
import tempfile

import pytest

os.environ.setdefault("UC251_EMBEDDER_MODEL", "stub")
os.environ.setdefault("UC251_VECTOR_BACKEND", "brute")
os.environ.setdefault("UC251_GENERATOR_PROVIDER", "stub")
os.environ.setdefault("UC251_RERANKER_MODEL", "stub")
os.environ.setdefault("UC251_JUDGE_PROVIDER", "heuristic")
os.environ.setdefault("UC251_MIN_CHUNK_LENGTH", "10")

_workdir = tempfile.mkdtemp(prefix="uc251_test_")
os.environ.setdefault("UC251_WORK_DIR", _workdir)


@pytest.fixture
def pipeline():
    from rag_pipeline import RAGPipeline

    return RAGPipeline()


@pytest.fixture
def sample_doc():
    return (
        "Política de vacaciones. "
        "Los empleados tienen derecho a 22 días laborables de vacaciones al año. "
        "El periodo de solicitud mínima es de 15 días naturales antes del inicio. "
        "El departamento de RRHH debe aprobar todas las peticiones."
    )
