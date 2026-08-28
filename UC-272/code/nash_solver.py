"""Solvers de equilibrio cooperativo para UC-272.

Implementa:
- Nash Bargaining Solution: maximiza producto (u_i - d_i).
- Pareto Frontier: opciones no dominadas.
- Kalai-Smorodinsky: equitativo + eficiente (proporcional a ideal points).
- Weighted Utilitarian: maximiza suma ponderada de utilidades.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from models import AgentUtilityProfile, EquilibriumCriterion, EquilibriumResult


def _option_utilities(profiles: List[AgentUtilityProfile], option: str) -> Dict[str, float]:
    return {p.agent_id: p.option_utilities.get(option, p.disagreement_point) for p in profiles}


def _all_options(profiles: List[AgentUtilityProfile]) -> set[str]:
    opts: set[str] = set()
    for p in profiles:
        opts.update(p.option_utilities.keys())
    return opts


class NashBargainingSolver:
    """Resuelve negociación multi-agente usando Nash Bargaining Solution."""

    def __init__(self, profiles: List[AgentUtilityProfile]) -> None:
        self.profiles = profiles
        self.options = _all_options(profiles)

    def solve(self) -> Tuple[Optional[str], Dict[str, float], float]:
        """Retorna (best_option, utilities, nash_product)."""
        best_option = None
        best_product = -1.0
        best_utils: Dict[str, float] = {}

        for option in self.options:
            utils = _option_utilities(self.profiles, option)
            product = 1.0
            feasible = True
            for p in self.profiles:
                u = utils[p.agent_id]
                if u < p.disagreement_point:
                    feasible = False
                    break
                product *= (u - p.disagreement_point)
            if feasible and product > best_product:
                best_product = product
                best_option = option
                best_utils = utils

        return best_option, best_utils, best_product

    def pareto_frontier(self) -> List[Tuple[str, Dict[str, float]]]:
        """Calcula el frente de Pareto de opciones no dominadas."""
        pareto: List[Tuple[str, Dict[str, float]]] = []
        for option in self.options:
            utils = _option_utilities(self.profiles, option)
            dominated = False
            for other in self.options:
                if other == option:
                    continue
                other_utils = _option_utilities(self.profiles, other)
                all_geq = all(other_utils[a] >= utils[a] for a in utils)
                any_gt = any(other_utils[a] > utils[a] for a in utils)
                if all_geq and any_gt:
                    dominated = True
                    break
            if not dominated:
                pareto.append((option, utils))
        return pareto

    def kalai_smorodinsky(self) -> Tuple[Optional[str], Dict[str, float]]:
        """Solución Kalai-Smorodinsky: proporcional a los puntos ideales.

        Encuentra la opción que mantiene las utilidades más proporcionales
        a lo que cada agente podría obtener en su mejor caso.
        """
        # Ideal points: máxima utilidad alcanzable por cada agente
        ideal: Dict[str, float] = {}
        for p in self.profiles:
            ideal[p.agent_id] = max(p.option_utilities.values()) if p.option_utilities else p.disagreement_point

        # Rango normalizado
        ranges: Dict[str, float] = {}
        for p in self.profiles:
            ranges[p.agent_id] = max(ideal[p.agent_id] - p.disagreement_point, 1e-9)

        best_option = None
        best_min_ratio = -1.0
        best_utils: Dict[str, float] = {}

        for option in self.options:
            utils = _option_utilities(self.profiles, option)
            feasible = all(utils[p.agent_id] >= p.disagreement_point for p in self.profiles)
            if not feasible:
                continue
            # Ratio mínimo de "cuánto obtiene respecto a su ideal"
            min_ratio = min(
                (utils[p.agent_id] - p.disagreement_point) / ranges[p.agent_id]
                for p in self.profiles
            )
            if min_ratio > best_min_ratio:
                best_min_ratio = min_ratio
                best_option = option
                best_utils = utils

        return best_option, best_utils

    def weighted_utilitarian(self) -> Tuple[Optional[str], Dict[str, float], float]:
        """Maximiza la suma ponderada de utilidades."""
        best_option = None
        best_sum = -math.inf
        best_utils: Dict[str, float] = {}

        for option in self.options:
            utils = _option_utilities(self.profiles, option)
            weighted = sum(utils[p.agent_id] * p.weight for p in self.profiles)
            if weighted > best_sum:
                best_sum = weighted
                best_option = option
                best_utils = utils

        return best_option, best_utils, best_sum

    def solve_all(self) -> EquilibriumResult:
        """Ejecuta Nash y agrega Pareto frontier."""
        best_opt, utils, product = self.solve()
        pareto = self.pareto_frontier()
        return EquilibriumResult(
            criterion=EquilibriumCriterion.nash,
            best_option=best_opt,
            utilities=utils,
            nash_product=product,
            pareto_frontier=[{"option": o, "utilities": u} for o, u in pareto],
            rationale=f"Nash bargaining: option={best_opt}, product={product:.4f}, pareto_size={len(pareto)}",
        )
