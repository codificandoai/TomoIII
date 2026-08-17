"""
Codificando.AI - UC-179
Configuración centralizada del sistema autónomo de reentrenamiento
continuo: rutas de almacenamiento (base de conocimiento, versiones de
modelo, despliegue de producción) y umbrales de negocio (cuándo
reentrenar, cuándo hacer fine-tuning, qué métricas mínimas exigir antes
de desplegar). Los umbrales se cargan desde `config/thresholds.yaml` y
pueden sobreescribirse con variables de entorno (mismo patrón usado en
`UC-129/code/config.py`).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_THRESHOLDS_PATH = BASE_DIR / "config" / "thresholds.yaml"


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _env_path(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default)))


@dataclass
class PathsConfig:
    data_dir: Path = field(default_factory=lambda: _env_path("UC179_DATA_DIR", BASE_DIR / "data"))
    db_path: Optional[Path] = None
    model_versions_dir: Optional[Path] = None
    production_dir: Optional[Path] = None

    def __post_init__(self):
        self.db_path = self.db_path or _env_path("UC179_DB_PATH", self.data_dir / "knowledge_base.db")
        self.model_versions_dir = self.model_versions_dir or _env_path(
            "UC179_MODEL_VERSIONS_DIR", self.data_dir / "models" / "versions")
        self.production_dir = self.production_dir or _env_path(
            "UC179_PRODUCTION_DIR", self.data_dir / "models" / "production")


@dataclass
class RetrainingThresholds:
    min_new_samples_since_last_training: int = 500
    performance_degradation: float = 0.05
    max_age_days: int = 30


@dataclass
class FineTuningThresholds:
    min_samples: int = 100
    confidence_threshold: float = 0.7
    max_cost_per_epoch: float = 50.0


@dataclass
class QualityMetricsThresholds:
    min_accuracy: float = 0.85
    min_f1_score: float = 0.80
    max_latency_ms: int = 500
    max_metric_regression_pct: float = 5.0


@dataclass
class DataQualityConfig:
    min_input_length: int = 10
    min_output_length: int = 3
    min_token_count: int = 3
    semantic_duplicate_threshold: float = 0.85


@dataclass
class Config:
    paths: PathsConfig
    retraining: RetrainingThresholds
    fine_tuning: FineTuningThresholds
    quality: QualityMetricsThresholds
    data_quality: DataQualityConfig


def _load_yaml_thresholds(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(thresholds_path: Optional[Path] = None) -> Config:
    raw = _load_yaml_thresholds(thresholds_path or DEFAULT_THRESHOLDS_PATH)
    retraining_raw = raw.get("retraining_thresholds", {})
    fine_tuning_raw = raw.get("fine_tuning_thresholds", {})
    quality_raw = raw.get("quality_metrics", {})
    data_quality_raw = raw.get("data_quality", {})

    retraining = RetrainingThresholds(
        min_new_samples_since_last_training=_env_int(
            "UC179_MIN_NEW_SAMPLES",
            retraining_raw.get("min_new_samples_since_last_training", 500)),
        performance_degradation=_env_float(
            "UC179_PERFORMANCE_DEGRADATION",
            retraining_raw.get("performance_degradation", 0.05)),
        max_age_days=_env_int("UC179_MAX_AGE_DAYS", retraining_raw.get("max_age_days", 30)),
    )
    fine_tuning = FineTuningThresholds(
        min_samples=_env_int("UC179_FINE_TUNING_MIN_SAMPLES", fine_tuning_raw.get("min_samples", 100)),
        confidence_threshold=_env_float(
            "UC179_FINE_TUNING_CONFIDENCE", fine_tuning_raw.get("confidence_threshold", 0.7)),
        max_cost_per_epoch=_env_float(
            "UC179_FINE_TUNING_MAX_COST", fine_tuning_raw.get("max_cost_per_epoch", 50.0)),
    )
    quality = QualityMetricsThresholds(
        min_accuracy=_env_float("UC179_MIN_ACCURACY", quality_raw.get("min_accuracy", 0.85)),
        min_f1_score=_env_float("UC179_MIN_F1", quality_raw.get("min_f1_score", 0.80)),
        max_latency_ms=_env_int("UC179_MAX_LATENCY_MS", quality_raw.get("max_latency_ms", 500)),
        max_metric_regression_pct=_env_float(
            "UC179_MAX_REGRESSION_PCT", quality_raw.get("max_metric_regression_pct", 5.0)),
    )
    data_quality = DataQualityConfig(
        min_input_length=_env_int("UC179_MIN_INPUT_LEN", data_quality_raw.get("min_input_length", 10)),
        min_output_length=_env_int("UC179_MIN_OUTPUT_LEN", data_quality_raw.get("min_output_length", 3)),
        min_token_count=_env_int("UC179_MIN_TOKEN_COUNT", data_quality_raw.get("min_token_count", 3)),
        semantic_duplicate_threshold=_env_float(
            "UC179_SEMANTIC_DUP_THRESHOLD", data_quality_raw.get("semantic_duplicate_threshold", 0.85)),
    )

    return Config(paths=PathsConfig(), retraining=retraining, fine_tuning=fine_tuning,
                  quality=quality, data_quality=data_quality)


CONFIG = load_config()
