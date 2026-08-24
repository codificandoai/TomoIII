"""Selección de estrategia de decisión según las propiedades del entorno."""
from __future__ import annotations

from models import EnvironmentProperties, StrategyKind


class StrategySelector:
    """Mapea propiedades ontológicas a una estrategia de agente."""

    @staticmethod
    def select(props: EnvironmentProperties) -> StrategyKind:
        if props.is_deterministic and props.is_fully_observable and props.is_discrete:
            return StrategyKind.EXACT_SEARCH
        if (
            not props.is_deterministic
            and not props.is_fully_observable
            and not props.is_discrete
        ):
            return StrategyKind.PROBABILISTIC_RISK
        if not props.is_deterministic and not props.is_fully_observable:
            # Entornos dinámicos y parcialmente observables con objetivos múltiples
            return StrategyKind.CONSTRAINT_PLANNING
        return StrategyKind.DECISION_TREE

    @staticmethod
    def explain(props: EnvironmentProperties, strategy: StrategyKind) -> str:
        reasons = {
            StrategyKind.EXACT_SEARCH: (
                "Entorno determinista, totalmente observable y discreto. "
                "Se puede usar búsqueda exhaustiva o cálculo exacto (ej. Minimax)."
            ),
            StrategyKind.CONSTRAINT_PLANNING: (
                "Entorno dinámico, parcialmente observable y multiobjetivo. "
                "Se requiere planificación restringida, uso de herramientas y gestión de incertidumbre."
            ),
            StrategyKind.PROBABILISTIC_RISK: (
                "Entorno estocástico, continuo y parcialmente observable. "
                "Se requiere inferencia bayesiana, análisis de riesgo y actualización de creencias."
            ),
            StrategyKind.DECISION_TREE: (
                "Entorno híbrido. Se usa un árbol de decisión con umbrales de confianza."
            ),
        }
        return reasons[strategy]
