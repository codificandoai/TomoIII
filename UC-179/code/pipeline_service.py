"""
Codificando.AI - UC-179
`ContinuousLearningPipeline`: orquestador reutilizable del sistema
autónomo de reentrenamiento continuo. Es el único punto de entrada que
combina `core.knowledge_base.KnowledgeBase`, `core.data_collector.DataCollector`,
`models.trainer.ModelTrainer`, `core.model_validator.ModelValidator` y
`core.deployment_manager.DeploymentManager` en un pipeline lineal:

    ingesta -> filtrado -> almacenamiento -> disparo de reentrenamiento
    -> entrenamiento (completo o fine-tuning) -> validación -> despliegue
    -> predicción en producción (con retroalimentación a la base de
    conocimiento vía `track_usage`)

Tanto `app.py` (API Flask) como `UC-179.py` (CLI) y las DAGs de Airflow en
`workflows/` reutilizan esta misma clase, evitando duplicar lógica de
negocio entre las distintas interfaces de entrada.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union

from config import CONFIG, Config
from core.data_collector import DataCollector
from core.deployment_manager import DeploymentManager
from core.knowledge_base import KnowledgeBase
from core.model_validator import ModelValidator
from models.metrics import summarize_history
from models.trainer import ModelTrainer

logger = logging.getLogger(__name__)


def _parse_timestamp(ts: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Formato de timestamp no reconocido: {ts!r}")


class ContinuousLearningPipeline:
    def __init__(self, config: Optional[Config] = None,
                 db_path: Optional[Union[str, Path]] = None,
                 model_versions_dir: Optional[Union[str, Path]] = None,
                 production_dir: Optional[Union[str, Path]] = None):
        self.config = config or CONFIG
        self.kb = KnowledgeBase(db_path or self.config.paths.db_path)
        self.collector = DataCollector(self.kb, self.config.data_quality)
        self.trainer = ModelTrainer(self.kb, model_versions_dir or self.config.paths.model_versions_dir)
        self.validator = ModelValidator(self.kb, self.config.quality)
        self.deployment = DeploymentManager(self.kb, production_dir or self.config.paths.production_dir)

    # ------------------------------------------------------------------
    # Ingesta
    # ------------------------------------------------------------------
    def ingest(self, sources: List[Dict]) -> Dict:
        collected = self.collector.collect_from_sources(sources)
        filtered = self.collector.filter_data(collected)

        stored_ids = []
        for item in filtered:
            row_id = self.kb.add_training_data(
                item["input"], item["output"], source=item["source"],
                quality_score=item["quality_score"])
            if row_id:
                stored_ids.append(row_id)

        logger.info(f"Ingesta: {len(collected)} recolectados, {len(filtered)} filtrados, "
                    f"{len(stored_ids)} almacenados")
        return {"collected": len(collected), "filtered": len(filtered),
                "stored": len(stored_ids), "stored_ids": stored_ids}

    def approve_samples(self, sample_ids: Optional[List[int]] = None) -> Dict:
        """Aprueba muestras ingeridas para que sean elegibles en el
        próximo entrenamiento. Si no se especifican IDs, aprueba todas
        las pendientes (`validated=0`)."""
        if sample_ids is None:
            sample_ids = self.kb.get_pending_sample_ids()
        self.kb.validate_samples(sample_ids)
        return {"validated_count": len(sample_ids), "sample_ids": sample_ids}

    # ------------------------------------------------------------------
    # Disparo y ejecución de reentrenamiento
    # ------------------------------------------------------------------
    def check_retraining_trigger(self) -> str:
        last_training = self.kb.get_last_training_timestamp()
        new_samples = self.kb.get_new_samples_count(since_timestamp=last_training)

        if new_samples >= self.config.retraining.min_new_samples_since_last_training:
            return "full_retraining"

        if last_training:
            days_since = (datetime.now(timezone.utc) - _parse_timestamp(last_training)).days
            if days_since >= self.config.retraining.max_age_days:
                return "full_retraining"

        if new_samples >= self.config.fine_tuning.min_samples:
            return "fine_tuning"

        return "no_training"

    def train(self, training_type: Optional[str] = None, validate_after: bool = True) -> Dict:
        training_type = training_type or self.check_retraining_trigger()
        if training_type not in ("full_retraining", "fine_tuning"):
            return {"status": "skipped", "reason": "umbrales de reentrenamiento no alcanzados",
                    "trigger": training_type}

        version_prefix = "ft" if training_type == "fine_tuning" else "v"
        version = f"{version_prefix}{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

        if training_type == "full_retraining":
            data = self.kb.get_training_data(validated_only=True)
            if len(data) < 2 or len({d["output"] for d in data}) < 2:
                return {"status": "skipped", "reason": "datos validados insuficientes o de una sola clase"}
            model_path = self.trainer.train_full(data, version)
        else:
            new_data = self.kb.get_training_data(validated_only=False, limit=500)
            if len(new_data) < 2 or len({d["output"] for d in new_data}) < 2:
                return {"status": "skipped", "reason": "datos nuevos insuficientes o de una sola clase"}
            model_path = self.trainer.fine_tune(new_data, version)

        logger.info(f"Modelo entrenado: {version} ({training_type}) -> {model_path}")
        result = {"status": "trained", "training_type": training_type,
                  "model_version": version, "model_path": model_path}

        if validate_after:
            result["validation"] = self.validate(version)

        return result

    # ------------------------------------------------------------------
    # Validación y despliegue
    # ------------------------------------------------------------------
    def validate(self, model_version: Optional[str] = None,
                 test_data: Optional[List[Dict]] = None) -> Dict:
        entry = self._find_model_entry(model_version, require_active=True)

        model = self.trainer.load_model(entry["model_path"])
        test_data = test_data if test_data is not None else self.kb.get_training_data(
            validated_only=True, limit=200)
        if len(test_data) < 1:
            return {"status": "skipped", "reason": "no hay datos de prueba disponibles",
                    "model_version": entry["model_version"]}

        deployed = self.kb.get_deployed_model()
        baseline_metrics = deployed["metrics"] if deployed else None

        metrics = self.validator.validate_model(model, test_data, baseline_metrics)
        should_deploy = self.validator.should_deploy(metrics)

        return {"status": "validated", "model_version": entry["model_version"],
                "model_path": entry["model_path"], "metrics": metrics, "should_deploy": should_deploy}

    def deploy(self, model_version: str, force: bool = False) -> Dict:
        entry = self._find_model_entry(model_version, require_active=False)

        if not force:
            validation = self.validate(model_version)
            if not validation.get("should_deploy", False):
                return {"status": "rejected", "reason": "métricas por debajo del umbral",
                        "validation": validation}

        metadata = self.deployment.deploy_model(entry["model_path"], model_version, entry["metrics"])
        logger.info(f"Modelo desplegado a producción: {model_version}")
        return {"status": "deployed", "metadata": metadata}

    def rollback(self, backup_model_path: Optional[str] = None) -> Dict:
        metadata = self.deployment.rollback(backup_model_path)
        logger.info(f"Rollback ejecutado. Versión restaurada: {metadata.get('version')}")
        return {"status": "rolled_back", "metadata": metadata}

    def _find_model_entry(self, model_version: Optional[str], require_active: bool) -> Dict:
        history = self.kb.get_model_history(limit=100)
        if model_version:
            entry = next((h for h in history if h["model_version"] == model_version), None)
        elif require_active:
            entry = next((h for h in history if h["is_active"]), None)
        else:
            entry = history[0] if history else None

        if entry is None:
            raise KeyError(f"Modelo no encontrado: {model_version!r}")
        return entry

    # ------------------------------------------------------------------
    # Inferencia en producción (retroalimenta la base de conocimiento)
    # ------------------------------------------------------------------
    def predict(self, text: str, user_feedback: Optional[str] = None) -> Dict:
        model_path = self.deployment.current_model_path
        if not model_path.exists():
            raise RuntimeError("No hay ningún modelo desplegado en producción")

        model = self.trainer.load_model(model_path)

        start = time.perf_counter()
        prediction = model.predict([text])[0]
        confidence: Optional[float] = None
        try:
            confidence = float(max(model.predict_proba([text])[0]))
        except AttributeError:
            pass
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        self.kb.track_usage(text, str(prediction), confidence or 0.0, elapsed_ms, user_feedback)

        return {"input": text, "prediction": prediction, "confidence": confidence,
                "processing_time_ms": elapsed_ms}

    # ------------------------------------------------------------------
    # Estado general del pipeline
    # ------------------------------------------------------------------
    def status(self) -> Dict:
        last_training = self.kb.get_last_training_timestamp()
        new_samples = self.kb.get_new_samples_count(since_timestamp=last_training)
        history = self.kb.get_model_history()

        return {
            "last_training_timestamp": last_training,
            "new_samples_since_last_training": new_samples,
            "next_trigger": self.check_retraining_trigger(),
            "deployed_model": self.kb.get_deployed_model(),
            "active_model_metrics": self.kb.get_active_model_metrics(),
            "history_summary": summarize_history(history),
        }
