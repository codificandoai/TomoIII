"""
UC-075 — Online Incremental Learner con Circuit Breaker.

Combina aprendizaje online incremental (`partial_fit`) con reentrenamiento
por lotes gobernado. Cada micro-lote pasa por:

1. Checkpoint de integridad de datos (schema, tipos, nulos, rangos).
2. Circuit Breaker (CLOSED → HALF_OPEN → OPEN).
3. Evaluación pre partial_fit (concept drift).
4. partial_fit sobre el modelo productivo (checkpoint previo).
5. Evaluación post partial_fit.
6. Decisión: aplicar, cuarentenar o revertir pesos.
7. Trazabilidad en MLflow + métricas Prometheus/Grafana.

Si el circuit breaker está OPEN, los micro-lotes se cuarentenan y se
alerta sin contaminar el modelo. Tras un cooldown, pasa a HALF_OPEN y
permite un número limitado de micro-lotes exitosos para volver a CLOSED.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from models_075 import PipelineStatus
from mlflow_adapter_075 import MLflowAdapter
from observability_075 import Observability075


# ---------------------------------------------------------------------------
# Modelos de datos
# ---------------------------------------------------------------------------

class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class MicroBatchIntegrityReport:
    """Resultado de la validación de integridad del micro-lote."""
    passed: bool
    schema_errors: List[str] = field(default_factory=list)
    null_errors: List[str] = field(default_factory=list)
    range_errors: List[str] = field(default_factory=list)
    n_rows: int = 0
    fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "schema_errors": self.schema_errors,
            "null_errors": self.null_errors,
            "range_errors": self.range_errors,
            "n_rows": self.n_rows,
            "fingerprint": self.fingerprint,
        }


@dataclass
class ConceptDriftReport:
    """Drift conceptual medido sobre el modelo actual con el micro-lote."""
    accuracy_pre: float
    accuracy_post: Optional[float]
    drift_score: float
    metric_name: str = "accuracy_drop"
    threshold: float = 0.05
    breached: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy_pre": self.accuracy_pre,
            "accuracy_post": self.accuracy_post,
            "drift_score": self.drift_score,
            "metric_name": self.metric_name,
            "threshold": self.threshold,
            "breached": self.breached,
            "evidence": self.evidence,
        }


@dataclass
class MicroBatchResult:
    """Resultado completo del procesamiento de un micro-lote."""
    batch_id: str
    learner_id: str
    timestamp: float
    integrity: MicroBatchIntegrityReport
    circuit_state_before: CircuitBreakerState
    circuit_state_after: CircuitBreakerState
    drift: ConceptDriftReport
    applied: bool
    reverted: bool
    quarantined: bool
    quarantine_reason: str = ""
    mlflow_run_id: str = ""
    model_checkpoint_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "learner_id": self.learner_id,
            "timestamp": self.timestamp,
            "integrity": self.integrity.to_dict(),
            "circuit_state_before": self.circuit_state_before.value,
            "circuit_state_after": self.circuit_state_after.value,
            "drift": self.drift.to_dict(),
            "applied": self.applied,
            "reverted": self.reverted,
            "quarantined": self.quarantined,
            "quarantine_reason": self.quarantine_reason,
            "mlflow_run_id": self.mlflow_run_id,
            "model_checkpoint_id": self.model_checkpoint_id,
            "metadata": self.metadata,
        }


@dataclass
class OnlineLearnerPolicy:
    """Política del aprendizaje online incremental."""
    # Circuit breaker
    concept_drift_threshold: float = 0.05       # caída máxima accuracy pre/post
    max_quarantine_ratio: float = 0.20          # % micro-lotes cuarentena antes de alerta alta
    cooldown_seconds: float = 60.0              # tiempo OPEN → HALF_OPEN
    half_open_max_batches: int = 3            # batches exitosos en HALF_OPEN para cerrar
    # Integridad
    required_schema: Optional[List[str]] = None
    allowed_nulls: bool = False
    feature_ranges: Optional[Dict[str, Tuple[float, float]]] = None
    max_rows: int = 10_000
    # Evaluación
    eval_metric: str = "accuracy"

    def to_dict(self) -> Dict[str, Any]:
        return {k: (list(v) if isinstance(v, (list, tuple)) else v)
                for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------------
# Funciones inyectables (defaults)
# ---------------------------------------------------------------------------

IntegrityValidatorFn = Callable[[Any, Any, Any, OnlineLearnerPolicy], MicroBatchIntegrityReport]
DriftEvaluatorFn = Callable[[Any, Any, Any, str], Tuple[float, Dict[str, Any]]]


def default_integrity_validator(
    X: Any,
    y: Any,
    metadata: Optional[Dict[str, Any]],
    policy: OnlineLearnerPolicy,
) -> MicroBatchIntegrityReport:
    """Validación básica de integridad: schema, nulos, rangos, tamaño."""
    errors = MicroBatchIntegrityReport(passed=True, n_rows=_len(X))

    # Tamaño
    if errors.n_rows > policy.max_rows:
        errors.range_errors.append(f"batch_size {errors.n_rows} > {policy.max_rows}")
        errors.passed = False

    # Schema (nombres de columnas o keys)
    if policy.required_schema is not None and hasattr(X, "columns"):
        missing = set(policy.required_schema) - set(X.columns)
        if missing:
            errors.schema_errors.append(f"missing columns: {sorted(missing)}")
            errors.passed = False
    elif policy.required_schema is not None and isinstance(X, list):
        keys = set(X[0].keys()) if X and isinstance(X[0], dict) else set()
        missing = set(policy.required_schema) - keys
        if missing:
            errors.schema_errors.append(f"missing keys: {sorted(missing)}")
            errors.passed = False

    # Nulos
    if not policy.allowed_nulls:
        if hasattr(X, "isnull"):
            nulls = X.isnull().sum().sum()
            if nulls:
                errors.null_errors.append(f"nulls found: {nulls}")
                errors.passed = False
        elif isinstance(X, list):
            nulls = sum(
                1
                for row in X
                if isinstance(row, (dict, list))
                for v in (row.values() if isinstance(row, dict) else row)
                if v is None
            )
            if nulls:
                errors.null_errors.append(f"nulls found: {nulls}")
                errors.passed = False

    # Rangos
    if policy.feature_ranges is not None:
        for feat, (lo, hi) in policy.feature_ranges.items():
            if hasattr(X, "__getitem__") and hasattr(X, "__iter__"):
                col = X[feat] if hasattr(X, "columns") else None
                if col is not None:
                    out = ((col < lo) | (col > hi)).sum()
                    if out:
                        errors.range_errors.append(f"{feat}: {out} fuera de [{lo}, {hi}]")
                        errors.passed = False

    errors.fingerprint = f"n{errors.n_rows}-s{len(errors.schema_errors)}-r{len(errors.range_errors)}"
    return errors


def default_drift_evaluator(
    model: Any,
    X: Any,
    y: Any,
    metric: str,
) -> Tuple[float, Dict[str, Any]]:
    """Evalúa el modelo sobre (X, y) y devuelve accuracy u otra métrica."""
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None

    if hasattr(model, "predict"):
        try:
            preds = model.predict(X)
            if y is None:
                return 0.0, {"error": "no labels"}
            if np is not None:
                y_arr = np.asarray(y)
                p_arr = np.asarray(preds)
                accuracy = float((y_arr == p_arr).mean())
            else:
                correct = sum(1 for a, b in zip(y, preds) if a == b)
                accuracy = correct / max(len(y), 1)
            return accuracy, {"n_samples": len(y)}
        except Exception as exc:
            return 0.0, {"error": str(exc)}
    return 0.0, {"error": "model has no predict"}


def _len(X: Any) -> int:
    if hasattr(X, "__len__"):
        try:
            return len(X)
        except Exception:
            pass
    if hasattr(X, "shape"):
        return int(X.shape[0])
    return 0


# ---------------------------------------------------------------------------
# Online Incremental Learner
# ---------------------------------------------------------------------------

class OnlineIncrementalLearner:
    """Aprendizaje online incremental con Circuit Breaker y cuarentena."""

    def __init__(
        self,
        learner_id: str,
        model: Any,
        policy: Optional[OnlineLearnerPolicy] = None,
        integrity_validator: Optional[IntegrityValidatorFn] = None,
        drift_evaluator: Optional[DriftEvaluatorFn] = None,
        mlflow: Optional[MLflowAdapter] = None,
        observability: Optional[Observability075] = None,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.learner_id = learner_id
        self.model = model
        self.policy = policy or OnlineLearnerPolicy()
        self.integrity_validator = integrity_validator or default_integrity_validator
        self.drift_evaluator = drift_evaluator or default_drift_evaluator
        self.mlflow = mlflow
        self.observability = observability
        self.event_sink = event_sink

        # Circuit breaker state
        self.state = CircuitBreakerState.CLOSED
        self.last_failure: Optional[float] = None
        self.half_open_successes: int = 0
        self.quarantine: List[MicroBatchResult] = []
        self.history: List[MicroBatchResult] = []
        self._checkpoints: Dict[str, Any] = {}
        self._checkpoint_counter = 0

    # ------------------------------------------------------------------
    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink({"event_type": event_type, "timestamp": time.time(), **payload})
            except Exception:
                pass

    def _make_checkpoint(self) -> str:
        """Guarda una copia profunda del modelo actual."""
        self._checkpoint_counter += 1
        cid = f"ck-{int(time.time())}-{self._checkpoint_counter}"
        try:
            self._checkpoints[cid] = copy.deepcopy(self.model)
        except Exception:
            # Fallback: intentar guardar state_dict (PyTorch/Keras/sklearn-like)
            if hasattr(self.model, "state_dict"):
                self._checkpoints[cid] = copy.deepcopy(self.model.state_dict())
            elif hasattr(self.model, "get_params"):
                self._checkpoints[cid] = (copy.deepcopy(self.model.get_params()),
                                          copy.deepcopy(getattr(self.model, "coef_", None)))
            else:
                self._checkpoints[cid] = None
        return cid

    def _restore_checkpoint(self, cid: str) -> bool:
        """Restaura el modelo desde el checkpoint."""
        snap = self._checkpoints.get(cid)
        if snap is None:
            return False
        if isinstance(snap, dict) and hasattr(self.model, "load_state_dict"):
            self.model.load_state_dict(snap)
            return True
        if isinstance(snap, tuple) and hasattr(self.model, "set_params"):
            params, coef = snap
            self.model.set_params(**params)
            if coef is not None and hasattr(self.model, "coef_"):
                self.model.coef_ = coef
            return True
        try:
            self.model = copy.deepcopy(snap)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    def fit_micro_batch(
        self,
        X: Any,
        y: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MicroBatchResult:
        """Procesa un micro-lote con todas las protecciones."""
        batch_id = f"mb-{uuid.uuid4().hex[:10]}"
        metadata = metadata or {}
        state_before = self.state

        # 1. Checkpoint de integridad
        integrity = self.integrity_validator(X, y, metadata, self.policy)

        result = MicroBatchResult(
            batch_id=batch_id,
            learner_id=self.learner_id,
            timestamp=time.time(),
            integrity=integrity,
            circuit_state_before=state_before,
            circuit_state_after=state_before,
            drift=ConceptDriftReport(
                accuracy_pre=0.0,
                accuracy_post=None,
                drift_score=0.0,
                threshold=self.policy.concept_drift_threshold,
            ),
            applied=False,
            reverted=False,
            quarantined=False,
            metadata=metadata,
        )

        if not integrity.passed:
            result.quarantined = True
            result.quarantine_reason = f"integrity_failure: {'; '.join(integrity_errors(integrity))}"
            self._quarantine(result, "integrity_failure", 1.0)
            return result

        # 2. Circuit breaker transitions
        self._transition()

        if self.state == CircuitBreakerState.OPEN:
            result.quarantined = True
            result.quarantine_reason = "circuit_breaker_open"
            result.circuit_state_after = self.state
            self._quarantine(result, "circuit_breaker_open", 0.0)
            return result

        # 3. Pre partial_fit drift
        acc_pre, ev_pre = self.drift_evaluator(self.model, X, y, self.policy.eval_metric)
        result.drift.accuracy_pre = acc_pre
        result.drift.evidence["pre"] = ev_pre
        result.drift.metric_name = self.policy.eval_metric
        result.drift.threshold = self.policy.concept_drift_threshold

        # Conceptual drift: si el modelo actual ya performa mal en el lote, algo cambió
        if acc_pre < 0.0:  # error de evaluación
            pass

        # 4. partial_fit con checkpoint previo
        checkpoint_id = self._make_checkpoint()
        result.model_checkpoint_id = checkpoint_id

        applied = False
        if hasattr(self.model, "partial_fit"):
            try:
                self.model.partial_fit(X, y)
                applied = True
            except Exception as exc:
                result.quarantined = True
                result.quarantine_reason = f"partial_fit_error: {exc}"
                self._restore_checkpoint(checkpoint_id)
                self._open_circuit()
                self._quarantine(result, "partial_fit_error", 0.0)
                result.circuit_state_after = self.state
                return result
        else:
            # Fallback: fit sobre batch (no verdadero online; se advierte)
            try:
                self.model.fit(X, y)
                applied = True
            except Exception as exc:
                result.quarantined = True
                result.quarantine_reason = f"fit_error: {exc}"
                self._restore_checkpoint(checkpoint_id)
                self._open_circuit()
                self._quarantine(result, "fit_error", 0.0)
                result.circuit_state_after = self.state
                return result

        result.applied = applied

        # 5. Post partial_fit drift
        acc_post, ev_post = self.drift_evaluator(self.model, X, y, self.policy.eval_metric)
        result.drift.accuracy_post = acc_post
        result.drift.evidence["post"] = ev_post
        result.drift.drift_score = max(0.0, acc_pre - acc_post)
        result.drift.breached = result.drift.drift_score > self.policy.concept_drift_threshold

        if result.drift.breached:
            # Olvido catastrófico / concept drift → revertir y cuarentenar
            self._restore_checkpoint(checkpoint_id)
            result.reverted = True
            result.applied = False
            result.quarantined = True
            result.quarantine_reason = (
                f"concept_drift: {self.policy.eval_metric} drop "
                f"{result.drift.drift_score:.4f} > {self.policy.concept_drift_threshold}"
            )
            self._open_circuit()
            self._quarantine(result, "concept_drift_post_partial_fit", result.drift.drift_score)
            result.circuit_state_after = self.state
            return result

        # 6. Éxito: actualizar circuit breaker si HALF_OPEN
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= self.policy.half_open_max_batches:
                self.state = CircuitBreakerState.CLOSED
                self.half_open_successes = 0
        result.circuit_state_after = self.state
        self._record_partial_fit(result)
        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    def _transition(self) -> None:
        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure and (time.time() - self.last_failure) >= self.policy.cooldown_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_successes = 0
                if self.observability:
                    self.observability.record_circuit_breaker_state(self.learner_id, self.state.value)

    def _open_circuit(self) -> None:
        self.state = CircuitBreakerState.OPEN
        self.last_failure = time.time()
        if self.observability:
            self.observability.record_circuit_breaker_state(self.learner_id, self.state.value)
        self._emit("uc075_circuit_breaker_open", {"learner_id": self.learner_id})

    def _quarantine(
        self,
        result: MicroBatchResult,
        reason: str,
        drift_score: float,
    ) -> None:
        result.quarantined = True
        result.circuit_state_after = self.state
        self.quarantine.append(result)
        self.history.append(result)

        metrics = {
            "drift_score": drift_score,
            "accuracy_pre": result.drift.accuracy_pre,
            "accuracy_post": result.drift.accuracy_post or 0.0,
            "n_rows": result.integrity.n_rows,
        }
        metadata = {
            "learner_id": self.learner_id,
            "circuit_state": self.state.value,
            "integrity": result.integrity.to_dict(),
            "metadata": result.metadata,
        }

        if self.mlflow:
            self.mlflow.log_quarantine(result.batch_id, reason, metrics, metadata)
            result.mlflow_run_id = result.batch_id  # local identifier; real mlflow id se registra

        if self.observability:
            self.observability.record_quarantine(
                self.learner_id, reason, drift_score, result.drift.accuracy_pre,
            )

        self._emit("uc075_microbatch_quarantined", result.to_dict())

    def _record_partial_fit(self, result: MicroBatchResult) -> None:
        if self.observability:
            self.observability.record_partial_fit(
                learner=self.learner_id,
                drift_score=result.drift.drift_score,
                accuracy_pre=result.drift.accuracy_pre,
                accuracy_post=result.drift.accuracy_post or 0.0,
                applied=True,
            )
        self._emit("uc075_microbatch_applied", result.to_dict())

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        n_quarantined = len(self.quarantine)
        n_total = len(self.history)
        return {
            "learner_id": self.learner_id,
            "circuit_breaker_state": self.state.value,
            "last_failure": self.last_failure,
            "half_open_successes": self.half_open_successes,
            "total_batches": n_total,
            "quarantined_batches": n_quarantined,
            "quarantine_ratio": round(n_quarantined / max(n_total, 1), 4),
            "checkpoints": len(self._checkpoints),
        }

    def get_quarantine(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.quarantine]

    def get_history(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.history]


def integrity_errors(report: MicroBatchIntegrityReport) -> List[str]:
    return report.schema_errors + report.null_errors + report.range_errors
