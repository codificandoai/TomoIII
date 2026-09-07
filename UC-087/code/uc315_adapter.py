"""
UC-087 — Adaptador opcional para modelos de UC-315.

Si UC-315 está disponible en el entorno, expone wrappers compatibles con
ModelSecurityGuardian para TradingWorldModel, NeuralTransitionModel y
GPTransitionModel.

Si no está disponible, el guardian usa los modelos sandbox de UC-087.
"""

from typing import Any, Optional, List, Callable

_uc315_available = False


def _try_import_uc315():
    global _uc315_available
    try:
        import _import_paths  # noqa: F401
        from world_model import TradingWorldModel
        from probabilistic_model import NeuralTransitionModel, GPTransitionModel
        _uc315_available = True
        return TradingWorldModel, NeuralTransitionModel, GPTransitionModel
    except Exception:
        return None, None, None


_TradingWorldModel, _NeuralTransitionModel, _GPTransitionModel = _try_import_uc315()


class UC315ModelProxy:
    """Envuelve un modelo de transición de UC-315 con interfaz predict_proba."""

    def __init__(self, model: Any, model_type: str = "neural"):
        self.model = model
        self.model_type = model_type

    def predict_proba(self, features: List[float]) -> float:
        """Retorna probabilidad positiva para un estado/acción representado por features."""
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(features)
            if isinstance(proba, (list, tuple)):
                return float(proba[1]) if len(proba) > 1 else float(proba[0])
            return float(proba)
        if hasattr(self.model, "predict"):
            pred = self.model.predict(features)
            if isinstance(pred, (list, tuple)):
                pred = pred[0]
            return 0.9 if pred else 0.1
        return 0.5

    def predict(self, features: List[float]) -> int:
        proba = self.predict_proba(features)
        return 1 if proba >= 0.5 else 0


class UC315Adapter:
    """Adaptador entre UC-315 y el guardian de seguridad ML de UC-087."""

    def __init__(self, world_model: Optional[Any] = None):
        self.world_model = world_model
        self.neural_proxy: Optional[UC315ModelProxy] = None
        self.gp_proxy: Optional[UC315ModelProxy] = None
        if self.world_model is not None:
            if hasattr(self.world_model, "probabilistic_model"):
                model = self.world_model.probabilistic_model
                model_type = getattr(self.world_model.config, "probabilistic", {}).get("model_type", "neural")
                self.neural_proxy = UC315ModelProxy(model, model_type=model_type)

    @staticmethod
    def is_available() -> bool:
        return _uc315_available

    def get_predict_fn(self) -> Callable[[List[float]], float]:
        if self.neural_proxy:
            return self.neural_proxy.predict_proba
        return lambda x: 0.5


def load_world_model(*args, **kwargs) -> Optional[Any]:
    """Carga un TradingWorldModel de UC-315 si está disponible."""
    if _TradingWorldModel is None:
        return None
    return _TradingWorldModel(*args, **kwargs)
