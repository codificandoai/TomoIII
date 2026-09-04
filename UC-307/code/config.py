"""Configuración del motor de evaluación y evolución de UC-307."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class EvalThresholds:
    """Umbrales que usa el orquestador central para decidir el destino de un agente."""

    # Nivel 1: tasa de éxito
    success_low: float = 0.50
    success_high: float = 0.85

    # Nivel 2: calidad normalizada (0..1)
    quality_min: float = 0.40
    quality_high: float = 0.80

    # Nivel 3: eficiencia (límites máximos aceptables)
    max_latency_seconds: float = 10.0
    max_tokens: int = 5_000
    max_tool_calls: int = 10
    max_cost_usd: float = 1.0

    # Fitness combinado
    fitness_elite: float = 0.85
    fitness_retrain: float = 0.60
    fitness_mutation: float = 0.50
    fitness_eliminate: float = 0.30

    # Pesos para el cálculo de fitness
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "success_rate": 0.45,
            "quality": 0.35,
            "efficiency": 0.20,
        }
    )

    # Límites de población
    min_population_size: int = 3
    max_population_size: int = 20


@dataclass
class EvolutionConfig:
    """Hiperparámetros por defecto y reglas de mutación/cruce."""

    default_hyperparams: Dict[str, float] = field(
        default_factory=lambda: {
            "learning_rate": 0.001,
            "temperature": 0.7,
            "max_iterations": 5,
            "top_p": 0.9,
            "exploration_factor": 0.2,
            "weight_decay": 0.01,
        }
    )

    # Rangos permitidos para mutar hiperparámetros
    param_bounds: Dict[str, tuple] = field(
        default_factory=lambda: {
            "learning_rate": (1e-5, 1e-1),
            "temperature": (0.0, 1.5),
            "max_iterations": (1.0, 20.0),
            "top_p": (0.1, 1.0),
            "exploration_factor": (0.0, 1.0),
            "weight_decay": (0.0, 0.5),
        }
    )

    mutation_strength: float = 0.15  # 15 % de variación respecto al valor actual
    mutation_probability: float = 0.30
    crossover_blend: float = 0.5  # promedio ponderado entre padres


# Instancias globales por convención
THRESHOLDS = EvalThresholds()
EVOLUTION = EvolutionConfig()
