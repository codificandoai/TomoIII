"""UC-325 — MetaReasoningOrchestrator: metarrazonamiento operativo.

Responsabilidades:
1. Seleccionar una heurística de razonamiento según el contexto (dominio,
   complejidad, tiempo, confianza histórica).
2. Ajustar recursos computacionales: max_rounds, stall_threshold,
   hallucination_threshold, chunk budget, query expansion.
3. Monitorizar convergencia y rendimientos decrecientes, decidiendo
   si continuar, cambiar de heurística o detener.
4. Emitir métricas Prometheus con labels para Grafana:
   - uc325_reasoning_strategy_total
   - uc325_meta_resource_gauge
   - uc325_convergence_delta
   - uc325_stall_count
   - uc325_heuristic_switch_total
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from observability_325 import ObservabilityManager


class ReasoningHeuristic(str, Enum):
    """Heurísticas de razonamiento seleccionables."""
    CONSERVATIVE = "conservative"       # pocas rondas, bajo riesgo de alucinación
    BALANCED = "balanced"               # default
    EXPLORATORY = "exploratory"         # más rondas, más expansión
    ADAPTIVE = "adaptive"               # se ajusta por iteración
    DEPTH_FIRST = "depth_first"         # profundidad en retrieval
    BREADTH_FIRST = "breadth_first"     # varias queries paralelas
    EVIDENCE_FOCUSED = "evidence_focused"  # alta exigencia de evidencia


@dataclass
class HeuristicProfile:
    """Perfil de heurística con parámetros ajustables."""
    name: ReasoningHeuristic
    max_rounds: int = 5
    stall_threshold: int = 2
    hallucination_threshold: float = 0.5
    min_convergence_delta: float = 0.02
    max_chunks_per_round: int = 10
    max_hypotheses: int = 20
    query_expansion: bool = False
    divergence_strategy: bool = False
    evidence_weight: float = 0.4
    coherence_weight: float = 0.3
    confidence_weight: float = 0.3
    priority: int = 0  # menor = más conservador

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.value,
            "max_rounds": self.max_rounds,
            "stall_threshold": self.stall_threshold,
            "hallucination_threshold": self.hallucination_threshold,
            "min_convergence_delta": self.min_convergence_delta,
            "max_chunks_per_round": self.max_chunks_per_round,
            "max_hypotheses": self.max_hypotheses,
            "query_expansion": self.query_expansion,
            "divergence_strategy": self.divergence_strategy,
            "evidence_weight": self.evidence_weight,
            "coherence_weight": self.coherence_weight,
            "confidence_weight": self.confidence_weight,
            "priority": self.priority,
        }


@dataclass
class MetaReasoningPlan:
    """Plan de metarrazonamiento resultante."""
    trace_id: str
    heuristic: ReasoningHeuristic
    profile: HeuristicProfile
    context: Dict[str, Any] = field(default_factory=dict)
    adjusted_params: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "heuristic": self.heuristic.value,
            "profile": self.profile.to_dict(),
            "context": self.context,
            "adjusted_params": self.adjusted_params,
            "reasoning": self.reasoning,
        }


class MetaReasoningOrchestrator:
    """Orquestador de metarrazonamiento."""

    DEFAULT_PROFILES: Dict[ReasoningHeuristic, HeuristicProfile] = {
        ReasoningHeuristic.CONSERVATIVE: HeuristicProfile(
            name=ReasoningHeuristic.CONSERVATIVE,
            max_rounds=3,
            stall_threshold=1,
            hallucination_threshold=0.3,
            min_convergence_delta=0.03,
            max_chunks_per_round=5,
            max_hypotheses=10,
            query_expansion=False,
            divergence_strategy=False,
            priority=1,
        ),
        ReasoningHeuristic.BALANCED: HeuristicProfile(
            name=ReasoningHeuristic.BALANCED,
            max_rounds=5,
            stall_threshold=2,
            hallucination_threshold=0.5,
            min_convergence_delta=0.02,
            max_chunks_per_round=10,
            max_hypotheses=20,
            query_expansion=True,
            divergence_strategy=False,
            priority=2,
        ),
        ReasoningHeuristic.EXPLORATORY: HeuristicProfile(
            name=ReasoningHeuristic.EXPLORATORY,
            max_rounds=8,
            stall_threshold=3,
            hallucination_threshold=0.6,
            min_convergence_delta=0.01,
            max_chunks_per_round=15,
            max_hypotheses=30,
            query_expansion=True,
            divergence_strategy=True,
            priority=3,
        ),
        ReasoningHeuristic.ADAPTIVE: HeuristicProfile(
            name=ReasoningHeuristic.ADAPTIVE,
            max_rounds=6,
            stall_threshold=2,
            hallucination_threshold=0.5,
            min_convergence_delta=0.015,
            max_chunks_per_round=12,
            max_hypotheses=25,
            query_expansion=True,
            divergence_strategy=True,
            priority=4,
        ),
        ReasoningHeuristic.DEPTH_FIRST: HeuristicProfile(
            name=ReasoningHeuristic.DEPTH_FIRST,
            max_rounds=4,
            stall_threshold=2,
            hallucination_threshold=0.45,
            min_convergence_delta=0.02,
            max_chunks_per_round=8,
            max_hypotheses=15,
            query_expansion=False,
            divergence_strategy=False,
            evidence_weight=0.6,
            coherence_weight=0.2,
            confidence_weight=0.2,
            priority=2,
        ),
        ReasoningHeuristic.BREADTH_FIRST: HeuristicProfile(
            name=ReasoningHeuristic.BREADTH_FIRST,
            max_rounds=6,
            stall_threshold=2,
            hallucination_threshold=0.5,
            min_convergence_delta=0.018,
            max_chunks_per_round=20,
            max_hypotheses=25,
            query_expansion=True,
            divergence_strategy=True,
            evidence_weight=0.3,
            coherence_weight=0.3,
            confidence_weight=0.4,
            priority=2,
        ),
        ReasoningHeuristic.EVIDENCE_FOCUSED: HeuristicProfile(
            name=ReasoningHeuristic.EVIDENCE_FOCUSED,
            max_rounds=5,
            stall_threshold=2,
            hallucination_threshold=0.25,
            min_convergence_delta=0.025,
            max_chunks_per_round=12,
            max_hypotheses=20,
            query_expansion=True,
            divergence_strategy=False,
            evidence_weight=0.7,
            coherence_weight=0.15,
            confidence_weight=0.15,
            priority=2,
        ),
    }

    def __init__(
        self,
        observability: Optional[ObservabilityManager] = None,
        profiles: Optional[Dict[ReasoningHeuristic, HeuristicProfile]] = None,
    ) -> None:
        self.observability = observability or ObservabilityManager()
        self.profiles = profiles or dict(self.DEFAULT_PROFILES)
        self._history: List[Dict[str, Any]] = []
        self._current_trace_id: str = ""
        self._current_plan: Optional[MetaReasoningPlan] = None

    def _hash_context(self, query: str, domain: str, context: Dict[str, Any]) -> str:
        payload = f"{query}:{domain}:{str(sorted(context.items()))}"
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def _estimate_complexity(self, query: str, context: Dict[str, Any]) -> str:
        """Estima complejidad del query."""
        words = len(query.split())
        has_and = " and " in query.lower() or " y " in query.lower()
        has_or = " or " in query.lower() or " o " in query.lower()
        has_why = query.lower().startswith(("why", "how", "cuál", "cómo", "por qué"))
        gaps = context.get("known_gaps", 0)
        if words > 15 or has_and or has_or or gaps > 3 or has_why:
            return "high"
        if words > 8 or gaps > 1:
            return "medium"
        return "low"

    def _select_heuristic(
        self,
        query: str,
        domain: str,
        context: Dict[str, Any],
    ) -> ReasoningHeuristic:
        """Mapeo de contexto a heurística."""
        complexity = self._estimate_complexity(query, context)
        risk_level = context.get("risk_level", "medium")
        time_budget = context.get("time_budget_ms", 5000)
        confidence_prior = context.get("confidence_prior", 0.5)

        if risk_level == "critical" or complexity == "low" or time_budget < 2000:
            return ReasoningHeuristic.CONSERVATIVE

        if domain in ("medical", "legal", "compliance") or confidence_prior < 0.3:
            return ReasoningHeuristic.EVIDENCE_FOCUSED

        if complexity == "high" and time_budget > 8000:
            if domain in ("agi", "research"):
                return ReasoningHeuristic.EXPLORATORY
            return ReasoningHeuristic.BREADTH_FIRST

        if complexity == "medium" and domain in ("trading", "reservations"):
            return ReasoningHeuristic.BALANCED

        if "deep" in query.lower() or "detailed" in query.lower():
            return ReasoningHeuristic.DEPTH_FIRST

        # Fallback con historia: si una heurística tuvo éxito en este dominio,
        # preferirla.
        domain_success = {}
        for h in self._history:
            if h.get("domain") == domain and h.get("success"):
                heur = h.get("heuristic")
                domain_success[heur] = domain_success.get(heur, 0) + 1
        if domain_success:
            best = max(domain_success.items(), key=lambda x: x[1])[0]
            return ReasoningHeuristic(best)

        return ReasoningHeuristic.BALANCED

    def plan(
        self,
        query: str,
        domain: str = "general",
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> MetaReasoningPlan:
        """Crea un plan de metarrazonamiento."""
        context = context or {}
        trace_id = trace_id or f"mr-{int(time.time() * 1000)}-{self._hash_context(query, domain, context)}"

        heuristic = self._select_heuristic(query, domain, context)
        profile = self.profiles.get(heuristic, self.profiles[ReasoningHeuristic.BALANCED])

        # Ajuste de recursos según contexto.
        adjusted = self._adjust_resources(profile, context)

        # Métrica: selección de estrategia.
        self.observability.inc_counter(
            "uc325_reasoning_strategy_total",
            labels={
                "strategy": heuristic.value,
                "domain": domain,
                "heuristic": heuristic.value,
                "complexity": self._estimate_complexity(query, context),
            },
        )

        # Métrica: recursos asignados.
        for param, value in adjusted.items():
            if isinstance(value, (int, float)):
                self.observability.set_gauge(
                    "uc325_meta_resource_gauge",
                    float(value),
                    labels={
                        "trace_id": trace_id,
                        "strategy": heuristic.value,
                        "param": param,
                    },
                )

        plan = MetaReasoningPlan(
            trace_id=trace_id,
            heuristic=heuristic,
            profile=profile,
            context={
                "query": query,
                "domain": domain,
                "complexity": self._estimate_complexity(query, context),
                **context,
            },
            adjusted_params=adjusted,
            reasoning=(
                f"heuristic={heuristic.value} selected for domain={domain}, "
                f"complexity={self._estimate_complexity(query, context)}, "
                f"adjusted={adjusted}"
            ),
        )

        self._current_trace_id = trace_id
        self._current_plan = plan
        return plan

    def _adjust_resources(self, profile: HeuristicProfile, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ajusta recursos computacionales según presupuesto y complejidad."""
        time_budget = context.get("time_budget_ms", 5000)
        token_budget = context.get("token_budget", 0)
        requested_rounds = context.get("requested_max_rounds")

        max_rounds = requested_rounds or profile.max_rounds
        if time_budget < 2000:
            max_rounds = min(max_rounds, 3)
        elif time_budget > 10000:
            max_rounds = min(max_rounds + 2, 10)

        stall_threshold = profile.stall_threshold
        if context.get("allow_stall"):
            stall_threshold += 1

        hallucination_threshold = profile.hallucination_threshold
        if context.get("strict_evidence"):
            hallucination_threshold = max(0.1, hallucination_threshold - 0.15)

        max_chunks = profile.max_chunks_per_round
        if token_budget and token_budget < 2000:
            max_chunks = max(3, max_chunks // 2)
        elif token_budget and token_budget > 10000:
            max_chunks = min(30, max_chunks + 5)

        return {
            "max_rounds": max_rounds,
            "stall_threshold": stall_threshold,
            "hallucination_threshold": round(hallucination_threshold, 4),
            "min_convergence_delta": profile.min_convergence_delta,
            "max_chunks_per_round": max_chunks,
            "max_hypotheses": profile.max_hypotheses,
            "query_expansion": profile.query_expansion,
            "divergence_strategy": profile.divergence_strategy,
            "evidence_weight": profile.evidence_weight,
            "coherence_weight": profile.coherence_weight,
            "confidence_weight": profile.confidence_weight,
        }

    def monitor_step(
        self,
        round_number: int,
        convergence_delta: float,
        stall_count: int,
        confidence: float,
        quality_overall: float,
    ) -> Dict[str, Any]:
        """Monitorea una iteración y decide si continuar o cambiar heurística."""
        if self._current_plan is None:
            return {"action": "continue"}

        heuristic = self._current_plan.heuristic
        trace_id = self._current_plan.trace_id

        self.observability.set_gauge(
            "uc325_convergence_delta",
            convergence_delta,
            labels={"trace_id": trace_id, "strategy": heuristic.value, "round": str(round_number)},
        )
        self.observability.set_gauge(
            "uc325_stall_count",
            float(stall_count),
            labels={"trace_id": trace_id, "strategy": heuristic.value, "round": str(round_number)},
        )
        self.observability.set_gauge(
            "uc325_meta_confidence",
            confidence,
            labels={"trace_id": trace_id, "strategy": heuristic.value, "round": str(round_number)},
        )

        # Regla de cambio de heurística.
        if stall_count >= self._current_plan.adjusted_params["stall_threshold"] and confidence < 0.5:
            # Cambiar a una heurística más conservadora o enfocada en evidencia.
            new_heuristic = ReasoningHeuristic.CONSERVATIVE
            if heuristic == ReasoningHeuristic.EXPLORATORY:
                new_heuristic = ReasoningHeuristic.BALANCED

            self.observability.inc_counter(
                "uc325_heuristic_switch_total",
                labels={
                    "from": heuristic.value,
                    "to": new_heuristic.value,
                    "reason": "stall_and_low_confidence",
                },
            )

            self._current_plan.heuristic = new_heuristic
            self._current_plan.profile = self.profiles[new_heuristic]
            self._current_plan.adjusted_params = self._adjust_resources(
                self._current_plan.profile,
                self._current_plan.context,
            )
            self._current_plan.reasoning += (
                f"\nSwitched to {new_heuristic.value} at round {round_number} "
                f"due to stall_count={stall_count} and confidence={confidence:.3f}"
            )
            return {
                "action": "switch_heuristic",
                "new_heuristic": new_heuristic.value,
                "reason": "stall_and_low_confidence",
            }

        if convergence_delta < self._current_plan.adjusted_params["min_convergence_delta"] and confidence < 0.4:
            return {
                "action": "request_more_info",
                "reason": "converged_with_low_confidence",
            }

        if quality_overall < 0.2 and round_number > 2:
            return {
                "action": "escalate",
                "reason": "quality_too_low",
            }

        return {"action": "continue"}

    def record_outcome(
        self,
        trace_id: str,
        success: bool,
        final_verdict: str,
        rounds: int,
    ) -> None:
        """Registra el resultado para feedback de selección de heurísticas."""
        self._history.append({
            "trace_id": trace_id,
            "heuristic": self._current_plan.heuristic.value if self._current_plan else "unknown",
            "success": success,
            "final_verdict": final_verdict,
            "rounds": rounds,
            "timestamp": time.time(),
        })
        self.observability.inc_counter(
            "uc325_meta_outcome_total",
            labels={
                "success": str(success),
                "verdict": final_verdict,
                "heuristic": self._current_plan.heuristic.value if self._current_plan else "unknown",
            },
        )
