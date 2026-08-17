"""
Codificando.AI - UC-179
Utilidades de métricas reutilizables: resumen del historial de
versiones de modelo (para el endpoint `/api/v1/models/history` y el
panel de tendencias de accuracy/f1) y cálculo de deriva (drift) simple
entre dos snapshots de métricas.
"""

from typing import Dict, List, Optional


def summarize_history(history: List[Dict]) -> Dict:
    """Resume el historial de entrenamientos: total de versiones,
    versión activa/desplegada, y tendencia de accuracy entre la primera
    y la última versión registrada."""
    if not history:
        return {"total_versions": 0, "active_version": None, "deployed_version": None,
                "accuracy_trend": None}

    active = next((h for h in history if h["is_active"]), None)
    deployed = next((h for h in history if h["is_deployed"]), None)

    ordered = sorted(history, key=lambda h: h["timestamp"])
    first_acc = ordered[0]["metrics"].get("accuracy_mean") or ordered[0]["metrics"].get("accuracy")
    last_acc = ordered[-1]["metrics"].get("accuracy_mean") or ordered[-1]["metrics"].get("accuracy")

    trend = None
    if first_acc is not None and last_acc is not None:
        trend = {
            "first_accuracy": first_acc,
            "last_accuracy": last_acc,
            "delta": last_acc - first_acc,
        }

    return {
        "total_versions": len(history),
        "active_version": active["model_version"] if active else None,
        "deployed_version": deployed["model_version"] if deployed else None,
        "accuracy_trend": trend,
    }


def compute_drift(baseline_metrics: Optional[Dict], current_metrics: Optional[Dict],
                   metric_keys: Optional[List[str]] = None) -> Dict:
    """Calcula la variación porcentual de un conjunto de métricas entre
    un baseline (p.ej. modelo en producción) y un snapshot actual (p.ej.
    métricas recientes de uso en `usage_tracking`)."""
    metric_keys = metric_keys or ["accuracy", "f1_score", "precision", "recall"]
    if not baseline_metrics or not current_metrics:
        return {}

    drift = {}
    for key in metric_keys:
        base_val = baseline_metrics.get(key)
        curr_val = current_metrics.get(key)
        if base_val is None or curr_val is None:
            continue
        diff = curr_val - base_val
        drift[key] = {
            "baseline": base_val,
            "current": curr_val,
            "delta": diff,
            "delta_pct": (diff / base_val) * 100 if base_val else 0.0,
        }
    return drift
