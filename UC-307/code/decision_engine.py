"""Motor de decisiones del orquestador central para UC-307.

A partir del fitness y de las métricas de tres niveles decide si un agente:
- Persiste en la población.
- Debe ajustar sus parámetros.
- Necesita reentrenamiento.
- Debe ser mutado.
- Debe ser eliminado.
- Debe generar descendencia (crecimiento/cruce).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from config import THRESHOLDS
from models import AgentDNA, DecisionAction


class DecisionEngine:
    """Reglas de gobernanza del orquestador sobre los agentes."""

    def __init__(self, thresholds=THRESHOLDS):
        self.cfg = thresholds

    def decide(
        self,
        success_rate: float,
        normalized_quality: float,
        efficiency_score: float,
        fitness: float,
        dna: Optional[AgentDNA] = None,
        mate_dna: Optional[AgentDNA] = None,
        population_size: Optional[int] = None,
    ) -> Tuple[DecisionAction, List[DecisionAction], str]:
        """Devuelve (veredicto_principal, acciones_recomendadas, razonamiento)."""

        actions: List[DecisionAction] = []

        # Regla de seguridad: eliminar si el agente es claramente perjudicial
        if success_rate < self.cfg.success_low and fitness < self.cfg.fitness_eliminate:
            reason = (
                f"Tasa de éxito {success_rate:.2%} y fitness {fitness:.2f} están por "
                "debajo de los umbrales críticos. El agente se considera no viable."
            )
            actions.append(DecisionAction.ELIMINATE)
            # Si la población quedaría muy pequeña, ordenar crecimiento
            if population_size is not None and population_size <= self.cfg.min_population_size:
                if mate_dna is not None:
                    actions.append(DecisionAction.GROW_CROSSOVER)
                    reason += " Se ordena descendencia por cruce para mantener diversidad."
                else:
                    actions.append(DecisionAction.GROW_RANDOM)
                    reason += " Se ordena la creación de un agente aleatorio para mantener el mínimo de población."
            return DecisionAction.ELIMINATE, actions, reason

        # El agente es un élite: persistir y eventualmente reproducirse
        if fitness >= self.cfg.fitness_elite and efficiency_score >= 0.7:
            reason = (
                f"Fitness {fitness:.2f} >= elite {self.cfg.fitness_elite} y eficiencia "
                f"{efficiency_score:.2f} >= 0.70. El agente se conserva como referente."
            )
            actions.append(DecisionAction.PERSIST)
            # Si existe un compañero de cruza, el élite puede generar descendencia
            if mate_dna is not None:
                actions.append(DecisionAction.GROW_CROSSOVER)
                reason += " Cruza con otro agente para producir descendencia mejorada."
            return DecisionAction.PERSIST, actions, reason

        # Calidad insuficiente pero eficiencia aceptable -> ajuste fino de parámetros
        if normalized_quality < self.cfg.quality_min:
            reason = (
                f"Calidad normalizada {normalized_quality:.2f} < {self.cfg.quality_min}. "
                "Se ajustan hiperparámetros (temperature, learning_rate, etc.) antes de reentrenar."
            )
            actions.append(DecisionAction.ADJUST_PARAMS)
            return DecisionAction.ADJUST_PARAMS, actions, reason

        # Eficiencia deficiente -> ajuste de parámetros para reducir tokens/latencia/herramientas
        if efficiency_score < 0.5:
            reason = (
                f"Eficiencia {efficiency_score:.2f} < 0.50 (tokens, latencia o llamadas excesivas). "
                "Se ajustan parámetros para reducir consumo."
            )
            actions.append(DecisionAction.ADJUST_PARAMS)
            return DecisionAction.ADJUST_PARAMS, actions, reason

        # Fitness bajo -> reentrenar o mutar según qué tan bajo esté
        if fitness < self.cfg.fitness_mutation:
            reason = (
                f"Fitness {fitness:.2f} < {self.cfg.fitness_mutation}. "
                "Se aplica mutación para explorar nueva configuración de ADN."
            )
            actions.append(DecisionAction.MUTATE)
            return DecisionAction.MUTATE, actions, reason

        if fitness < self.cfg.fitness_retrain:
            reason = (
                f"Fitness {fitness:.2f} < {self.cfg.fitness_retrain}. "
                "Se recomienda reentrenamiento con datos y configuración actualizados."
            )
            actions.append(DecisionAction.RETRAIN)
            return DecisionAction.RETRAIN, actions, reason

        # Caso intermedio: persistir pero ajustar suavemente
        reason = (
            f"Fitness {fitness:.2f} en rango aceptable. "
            "Se mantiene en la población con ajustes menores."
        )
        actions.append(DecisionAction.PERSIST)
        actions.append(DecisionAction.ADJUST_PARAMS)
        return DecisionAction.PERSIST, actions, reason

    def should_spawn_random(self, population_size: int) -> bool:
        """Verifica si la población necesita nuevos agentes aleatorios."""
        return population_size < self.cfg.min_population_size
