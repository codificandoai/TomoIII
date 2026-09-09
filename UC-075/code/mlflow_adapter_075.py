"""
UC-075 — Adapter MLflow (opcional, degradación elegante).

Si mlflow está instalado, registra cada run con:
run_id, params (strategy_used, drift_score, business_trigger,
dataset_version, model_version, code_version), métricas y tags.

Si no está instalado/o no configurado, escribe un log JSONL local auditable
(mismo contrato de datos) en `.uc075_mlflow/`.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

try:
    import mlflow  # type: ignore
    MLFLOW_AVAILABLE = True
except Exception:
    MLFLOW_AVAILABLE = False


class MLflowAdapter:
    """Registro unificado de runs con MLflow real o fallback JSONL."""

    EXPERIMENT = "uc075-continuous-training"

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        fallback_dir: str = ".uc075_mlflow",
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self._use_mlflow = MLFLOW_AVAILABLE and enabled

        os.makedirs(fallback_dir, exist_ok=True)
        self.fallback_path = os.path.join(fallback_dir, "runs.jsonl")
        if self._use_mlflow:
            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(self.EXPERIMENT)

    # ------------------------------------------------------------------
    def start_run(self, run_name: str) -> str:
        """Abre contexto de run y devuelve run_id."""
        if not self.enabled:
            return f"local-{run_name}"
        if self._use_mlflow:
            active = mlflow.start_run(run_name=run_name)
            return active.info.run_id
        run_id = f"local-{run_name}-{int(time.time())}"
        return run_id

    # ------------------------------------------------------------------
    def log_run(self, run_id: str, run: Dict[str, Any]) -> None:
        """Registra params + métricas + tags del run."""
        if not self.enabled:
            return

        params = {
            "strategy_used": run.get("strategy_used", ""),
            "business_trigger": run.get("trigger", {}).get("business_trigger", ""),
            "dataset_version": (run.get("freeze") or {}).get("dataset_version", ""),
            "code_version": run.get("code_version", ""),
            "agent_id": run.get("agent_id", ""),
        }
        metrics = {
            "drift_score": float(run.get("drift_score", 0.0)),
            "duration_sec": float(run.get("finished_at", 0) or 0) - float(run.get("started_at", 0) or 0),
            "actual_cost_usd": float(run.get("actual_cost_usd", 0.0)),
            "n_gates_passed": sum(
                1 for g in run.get("gates", []) if g.get("verdict") == "pass"
            ),
        }
        tags = {
            "final_status": run.get("status", ""),
            "decision": run.get("decision", "") or "",
            "approver": (run.get("approval") or {}).get("approver", ""),
            "compliance": "nist_ai_rmf,iso_42001",
        }

        if self._use_mlflow:
            for k, v in params.items():
                mlflow.log_param(k, v)
            for k, v in metrics.items():
                mlflow.log_metric(k, v)
            for k, v in tags.items():
                mlflow.set_tag(k, v)
            mlflow.set_tag("mlflow.note.content", run.get("decision_reason", ""))
            return

        self._write_fallback({
            "run_id": run_id,
            "timestamp": time.time(),
            "params": params,
            "metrics": metrics,
            "tags": tags,
            "run": run,
        })

    # ------------------------------------------------------------------
    def log_quarantine(
        self,
        batch_id: str,
        reason: str,
        metrics: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registra un micro-lote cuarentenado con status QUARANTINED.

        Siempre escribe fallback JSONL (auditoría), y también intenta MLflow
        cuando está habilitado.
        """
        record = {
            "batch_id": batch_id,
            "update_status": "QUARANTINED",
            "reason": reason,
            "metrics": metrics,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        if self.enabled and self._use_mlflow:
            try:
                active = mlflow.start_run(run_name=f"quarantine-{batch_id}")
                mlflow.log_param("batch_id", batch_id)
                mlflow.log_param("update_status", "QUARANTINED")
                mlflow.log_param("reason", reason)
                for k, v in (metadata or {}).items():
                    mlflow.log_param(k, v)
                for k, v in metrics.items():
                    mlflow.log_metric(k, v)
                mlflow.set_tag("status", "QUARANTINED")
                mlflow.end_run()
                record["mlflow_run_id"] = active.info.run_id
            except Exception:
                pass
        # Fallback JSONL siempre escribe para garantizar evidencia de cuarentena.
        self._write_fallback({"type": "quarantine", **record})

    # ------------------------------------------------------------------
    def end_run(self, status: str = "FINISHED") -> None:
        if self._use_mlflow:
            mlflow.end_run(status=status)

    # ------------------------------------------------------------------
    def _write_fallback(self, record: Dict[str, Any]) -> None:
        if not self.fallback_path:
            return
        with open(self.fallback_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    # ------------------------------------------------------------------
    @property
    def backend(self) -> str:
        return "mlflow" if self._use_mlflow else "jsonl"

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "experiment": self.EXPERIMENT,
            "fallback_path": self.fallback_path,
        }
