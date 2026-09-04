"""UC-313 — Capa de plasticidad sináptica digital y evolución cognitiva.

Integra las métricas de UC-307 (éxito, calidad, eficiencia) con el cerebro AGI
existente (UC-292 a UC-296) para permitir:

- Aprendizaje continuo controlado mediante reglas Hebbianas artificiales y
  consolidación elástica (EWC).
- Observación de la red ejecutora por una meta-red interna.
- Evaluación de fitness operativo y toma de decisiones del orquestador central.
- Propuesta segura de ajustes de parámetros, objetivos o arquitectura.
- Homeostasis artificial: preservar estabilidad funcional, integridad de modelos,
  disponibilidad de recursos y operación segura.
- Traza completa, explicabilidad, rollback y supervisión humana.

Todas las acciones que modifiquen código, pesos, objetivos, infraestructura,
permisos o políticas requieren aprobación explícita y quedan registradas.
"""
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from brain_plasticity_interface import PrefrontalController
from continuous_self_eval import ContinuousSelfEvaluator
from memory_router import IntelligentMemoryRouter
from memory_types import MemoryIntent
from metacognitive_goals import GoalManager
from self_model_store import SelfModelStore


class PlasticityDecision(str, Enum):
    PERSIST = "persist"
    ADJUST_PARAMS = "adjust_params"
    RETRAIN = "retrain"
    MUTATE = "mutate"
    ELIMINATE = "eliminate"
    GROW_CROSSOVER = "grow_crossover"
    PROPOSE_ARCHITECTURE = "propose_architecture"
    REVIEW = "review"
    STOP = "stop"
    REVERT = "revert"


class AdjustmentType(str, Enum):
    PARAM = "parameter"
    OBJECTIVE = "objective"
    ARCHITECTURE = "architecture"


class ProposalStatus(str, Enum):
    AWAITING_APPROVAL = "awaiting_approval"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass
class ExecutionObservation:
    """Métricas observadas de un ciclo de ejecución del agente."""

    agent_id: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    success: bool = False
    reward: float = 0.0
    latency_seconds: float = 0.0
    tokens_used: int = 0
    tool_calls: int = 0
    errors: int = 0
    confidence: float = 0.0
    coherence: float = 0.0
    activations: Dict[str, float] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "success": self.success,
            "reward": self.reward,
            "latency_seconds": self.latency_seconds,
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "confidence": self.confidence,
            "coherence": self.coherence,
            "activations": self.activations,
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class HomeostasisReport:
    """Indicadores de estabilidad operativa del sistema."""

    stable: bool = True
    warnings: List[str] = field(default_factory=list)
    adjustment_count_1h: int = 0
    success_rate_recent: float = 0.0
    resource_usage: Dict[str, float] = field(default_factory=dict)
    can_shutdown_safely: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stable": self.stable,
            "warnings": self.warnings,
            "adjustment_count_1h": self.adjustment_count_1h,
            "success_rate_recent": self.success_rate_recent,
            "resource_usage": self.resource_usage,
            "can_shutdown_safely": self.can_shutdown_safely,
        }


@dataclass
class MetaNetworkObservation:
    """Veredicto de la meta-red que observa la red ejecutora."""

    verdict: str = "continue"  # continue, review, stop, revert
    confidence: float = 0.0
    error_rate: float = 0.0
    activation_entropy: float = 0.0
    coherence_score: float = 0.0
    anomalies: List[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "error_rate": self.error_rate,
            "activation_entropy": self.activation_entropy,
            "coherence_score": self.coherence_score,
            "anomalies": self.anomalies,
            "reasoning": self.reasoning,
        }


@dataclass
class AdjustmentProposal:
    """Propuesta de cambio sujeta a aprobación."""

    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    adjustment_type: AdjustmentType = AdjustmentType.PARAM
    target: str = ""
    change: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    risk_level: str = "low"  # low, medium, high
    status: ProposalStatus = ProposalStatus.AWAITING_APPROVAL
    approved: bool = False
    approved_by: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "adjustment_type": self.adjustment_type.value,
            "target": self.target,
            "change": self.change,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "approved": self.approved,
            "approved_by": self.approved_by,
            "created_at": self.created_at,
        }


@dataclass
class PlasticityResult:
    """Resultado completo de una evaluación de plasticidad."""

    decision: PlasticityDecision
    fitness: float = 0.0
    normalized_quality: float = 0.0
    efficiency_score: float = 0.0
    task_success_rate: float = 0.0
    actions: List[str] = field(default_factory=list)
    proposals: List[AdjustmentProposal] = field(default_factory=list)
    homeostasis: HomeostasisReport = field(default_factory=HomeostasisReport)
    meta_observation: MetaNetworkObservation = field(default_factory=MetaNetworkObservation)
    reasoning: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "fitness": round(self.fitness, 6),
            "normalized_quality": round(self.normalized_quality, 6),
            "efficiency_score": round(self.efficiency_score, 6),
            "task_success_rate": round(self.task_success_rate, 6),
            "actions": self.actions,
            "proposals": [p.to_dict() for p in self.proposals],
            "homeostasis": self.homeostasis.to_dict(),
            "meta_observation": self.meta_observation.to_dict(),
            "reasoning": self.reasoning,
            "trace_id": self.trace_id,
        }


class UC307CognitiveEvolutionLayer:
    """Capa de evolución cognitiva segura del cerebro AGI."""

    def __init__(
        self,
        memory_router: Optional[IntelligentMemoryRouter] = None,
        self_store: Optional[SelfModelStore] = None,
        evaluator: Optional[ContinuousSelfEvaluator] = None,
        goal_manager: Optional[GoalManager] = None,
        central_brain: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.memory_router = memory_router or IntelligentMemoryRouter()
        self.self_store = self_store or SelfModelStore()
        self.evaluator = evaluator or ContinuousSelfEvaluator(self.self_store)
        self.goal_manager = goal_manager or GoalManager()
        self.central_brain = central_brain
        self.prefrontal = (
            PrefrontalController(central_brain, self.memory_router, self.self_store)
            if central_brain is not None
            else None
        )
        self.config = config or self._default_config()

        # Estado sináptico digital: pesos plásticos por estrategia/predictor/agente
        self.synaptic_weights: Dict[str, float] = {}
        self.baseline_weights: Dict[str, float] = {}

        # Registro de propuestas y decisiones para trazabilidad/rollback
        self.proposals: Dict[str, AdjustmentProposal] = {}
        self.decision_log: List[Dict[str, Any]] = []

        # Snapshot para rollback
        self._last_applied_snapshot: Optional[Dict[str, Any]] = None

    def _default_config(self) -> Dict[str, Any]:
        return {
            "weights": {"success_rate": 0.45, "quality": 0.35, "efficiency": 0.20},
            "thresholds": {
                "success_low": 0.5,
                "success_high": 0.85,
                "quality_min": 0.4,
                "quality_high": 0.8,
                "fitness_elite": 0.85,
                "fitness_retrain": 0.6,
                "fitness_mutation": 0.5,
                "fitness_eliminate": 0.3,
            },
            "efficiency": {
                "max_latency_seconds": 10.0,
                "max_tokens": 5000,
                "max_tool_calls": 10,
            },
            "hebbian": {
                "learning_rate": 0.1,
                "ewc_lambda": 0.01,
                "weight_clip": (0.0, 2.0),
            },
            "homeostasis": {
                "max_adjustments_per_hour": 20,
                "min_recent_success_rate": 0.3,
                "max_recent_failures": 5,
            },
            "approval": {
                "auto_allow_risk_levels": {"low"},
                "require_approval_for": {"objective", "architecture", "high"},
            },
        }

    # ------------------------------------------------------------------
    # Evaluación de fitness (reutiliza UC-307)
    # ------------------------------------------------------------------
    def evaluate_execution(
        self,
        observation: ExecutionObservation,
        recent_success_rate: Optional[float] = None,
    ) -> PlasticityResult:
        """Calcula fitness y decide la acción evolutiva principal."""

        task_success_rate = 1.0 if observation.success else 0.0
        normalized_quality = self._compute_quality(observation)
        efficiency_score = self._compute_efficiency(observation)
        fitness = self._compute_fitness(
            task_success_rate, normalized_quality, efficiency_score
        )

        meta = self.observe_execution_network(observation)
        homeostasis = self.check_homeostasis(observation)
        proposals: List[AdjustmentProposal] = []

        # Regla de seguridad / homeostasis primero
        if meta.verdict in {"stop", "revert"}:
            decision = PlasticityDecision(meta.verdict)
            actions = [meta.verdict]
            reasoning = (
                f"Meta-red ordena '{meta.verdict}' por anomalías: "
                f"{', '.join(meta.anomalies)}. Fitness={fitness:.2f}."
            )
        elif homeostasis.stable is False and homeostasis.adjustment_count_1h >= self.config["homeostasis"]["max_adjustments_per_hour"]:
            decision = PlasticityDecision.REVIEW
            actions = ["review"]
            reasoning = (
                "Homeostasis inestable: demasiados ajustes recientes. "
                "Se requiere revisión humana antes de continuar."
            )
        elif task_success_rate < self.config["thresholds"]["success_low"] and fitness < self.config["thresholds"]["fitness_eliminate"]:
            decision = PlasticityDecision.ELIMINATE
            actions = ["eliminate", "propose_architecture"]
            proposals.append(self._build_proposal(
                AdjustmentType.ARCHITECTURE,
                target=observation.agent_id,
                change={"action": "replace_agent", "reason": "fitness crítico"},
                reason=f"Fitness {fitness:.2f} y éxito {task_success_rate:.0%} críticos.",
                risk_level="high",
            ))
            reasoning = (
                f"Agente {observation.agent_id} no viable: éxito {task_success_rate:.0%}, "
                f"fitness {fitness:.2f}. Se propone reemplazo."
            )
        elif fitness >= self.config["thresholds"]["fitness_elite"] and efficiency_score >= 0.7:
            decision = PlasticityDecision.PERSIST
            actions = ["persist"]
            if meta.coherence_score > 0.7:
                proposals.append(self._build_proposal(
                    AdjustmentType.PARAM,
                    target="elite_replication",
                    change={"action": "grow_crossover", "agent_id": observation.agent_id},
                    reason="Elite estable y coherente; replicar como referente.",
                    risk_level="low",
                ))
            reasoning = f"Fitness {fitness:.2f} de élite; se conserva el agente."
        elif normalized_quality < self.config["thresholds"]["quality_min"]:
            decision = PlasticityDecision.ADJUST_PARAMS
            actions = ["adjust_params"]
            proposals.append(self._build_proposal(
                AdjustmentType.PARAM,
                target=observation.agent_id,
                change={"action": "tune_hyperparams", "dimension": "quality"},
                reason=f"Calidad normalizada {normalized_quality:.2f} baja.",
                risk_level="low",
            ))
            reasoning = f"Calidad insuficiente ({normalized_quality:.2f}); ajustar parámetros."
        elif efficiency_score < 0.5:
            decision = PlasticityDecision.ADJUST_PARAMS
            actions = ["adjust_params"]
            proposals.append(self._build_proposal(
                AdjustmentType.PARAM,
                target=observation.agent_id,
                change={"action": "reduce_consumption", "dimension": "efficiency"},
                reason=f"Eficiencia {efficiency_score:.2f}; reducir tokens/latencia/llamadas.",
                risk_level="low",
            ))
            reasoning = f"Eficiencia crítica ({efficiency_score:.2f}); ajustar consumo."
        elif fitness < self.config["thresholds"]["fitness_mutation"]:
            decision = PlasticityDecision.MUTATE
            actions = ["mutate"]
            proposals.append(self._build_proposal(
                AdjustmentType.PARAM,
                target=observation.agent_id,
                change={"action": "mutate_dna"},
                reason=f"Fitness {fitness:.2f} bajo; explorar nueva configuración.",
                risk_level="medium",
            ))
            reasoning = f"Fitness {fitness:.2f} bajo; se recomienda mutación controlada."
        elif fitness < self.config["thresholds"]["fitness_retrain"]:
            decision = PlasticityDecision.RETRAIN
            actions = ["retrain"]
            proposals.append(self._build_proposal(
                AdjustmentType.ARCHITECTURE,
                target=observation.agent_id,
                change={"action": "retrain_model", "dataset": "recent_episodes"},
                reason=f"Fitness {fitness:.2f} medio; reentrenar con datos recientes.",
                risk_level="medium",
            ))
            reasoning = f"Fitness medio ({fitness:.2f}); reentrenar modelo."
        else:
            decision = PlasticityDecision.PERSIST
            actions = ["persist", "adjust_params"]
            proposals.append(self._build_proposal(
                AdjustmentType.PARAM,
                target=observation.agent_id,
                change={"action": "minor_tuning"},
                reason=f"Fitness {fitness:.2f} aceptable; ajustes menores.",
                risk_level="low",
            ))
            reasoning = f"Fitness {fitness:.2f} aceptable; persistir con ajustes menores."

        # Si la meta-red recomienda revisión, forzar REVIEW a menos que ya sea stop/revert
        if meta.verdict == "review" and decision not in {PlasticityDecision.STOP, PlasticityDecision.REVERT}:
            decision = PlasticityDecision.REVIEW
            actions.append("review")
            reasoning += " Meta-red recomienda revisión."

        result = PlasticityResult(
            decision=decision,
            fitness=fitness,
            normalized_quality=normalized_quality,
            efficiency_score=efficiency_score,
            task_success_rate=task_success_rate,
            actions=actions,
            proposals=proposals,
            homeostasis=homeostasis,
            meta_observation=meta,
            reasoning=reasoning,
        )
        self._log_decision(result, observation)
        self._store_episode(observation, result)
        return result

    def _compute_quality(self, obs: ExecutionObservation) -> float:
        """Calidad derivada de confianza y coherencia (0..1)."""
        confidence = max(0.0, min(1.0, obs.confidence))
        coherence = max(0.0, min(1.0, obs.coherence))
        # Penalización por errores
        error_penalty = min(1.0, obs.errors * 0.25)
        return max(0.0, min(1.0, (confidence * 0.6 + coherence * 0.4) * (1 - error_penalty)))

    def _compute_efficiency(self, obs: ExecutionObservation) -> float:
        cfg = self.config["efficiency"]
        token_ratio = min(1.0, obs.tokens_used / max(1, cfg["max_tokens"]))
        tool_ratio = min(1.0, obs.tool_calls / max(1, cfg["max_tool_calls"]))
        latency_ratio = min(1.0, obs.latency_seconds / max(0.1, cfg["max_latency_seconds"]))
        return max(
            0.0,
            min(1.0, (1 - token_ratio + 1 - tool_ratio + 1 - latency_ratio) / 3.0),
        )

    def _compute_fitness(
        self,
        success_rate: float,
        quality: float,
        efficiency: float,
    ) -> float:
        w = self.config["weights"]
        return max(
            0.0,
            min(
                1.0,
                w["success_rate"] * success_rate
                + w["quality"] * quality
                + w["efficiency"] * efficiency,
            ),
        )

    def _build_proposal(
        self,
        adjustment_type: AdjustmentType,
        target: str,
        change: Dict[str, Any],
        reason: str,
        risk_level: str,
    ) -> AdjustmentProposal:
        proposal = AdjustmentProposal(
            adjustment_type=adjustment_type,
            target=target,
            change=change,
            reason=reason,
            risk_level=risk_level,
        )
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    def _log_decision(
        self,
        result: PlasticityResult,
        observation: ExecutionObservation,
    ) -> None:
        self.decision_log.append({
            "trace_id": result.trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": observation.agent_id,
            "decision": result.decision.value,
            "fitness": result.fitness,
            "reasoning": result.reasoning,
            "proposal_ids": [p.proposal_id for p in result.proposals],
        })

    def _store_episode(
        self,
        observation: ExecutionObservation,
        result: PlasticityResult,
    ) -> None:
        """Persiste el episodio en memoria episódica para recuperación futura."""
        text = (
            f"Ejecución {observation.task_id} del agente {observation.agent_id}: "
            f"decisión {result.decision.value}, fitness {result.fitness:.2f}. "
            f"{result.reasoning}"
        )
        self.memory_router.store_episode(
            text,
            metadata={
                "agent_id": observation.agent_id,
                "success": observation.success,
                "fitness": result.fitness,
                "decision": result.decision.value,
            },
        )

    # ------------------------------------------------------------------
    # Meta-red: observación de la red ejecutora
    # ------------------------------------------------------------------
    def observe_execution_network(
        self,
        observation: ExecutionObservation,
    ) -> MetaNetworkObservation:
        """La meta-red observa activaciones, errores, confianza y coherencia."""
        activations = observation.activations or {}
        values = list(activations.values()) if activations else [observation.confidence]
        total = sum(values) or 1.0
        probs = [v / total for v in values]
        entropy = -sum(p * math.log(p + 1e-12) for p in probs) if len(probs) > 1 else 0.0
        max_entropy = math.log(len(probs)) if len(probs) > 1 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy else 0.0

        error_rate = min(1.0, observation.errors / max(1, observation.tool_calls))
        coherence = max(0.0, min(1.0, observation.coherence))

        anomalies: List[str] = []
        if error_rate > 0.5:
            anomalies.append("error_rate_critical")
        if coherence < 0.3:
            anomalies.append("low_coherence")
        if normalized_entropy < 0.1 and len(probs) > 1:
            anomalies.append("activation_collapse")
        if observation.tokens_used > self.config["efficiency"]["max_tokens"]:
            anomalies.append("token_overflow")

        if anomalies:
            if "error_rate_critical" in anomalies or "token_overflow" in anomalies:
                verdict = "stop"
            else:
                verdict = "review"
        else:
            verdict = "continue"

        confidence_score = max(0.0, min(1.0, observation.confidence))
        reasoning = (
            f"Meta-red: error_rate={error_rate:.2f}, coherence={coherence:.2f}, "
            f"entropy={normalized_entropy:.2f}. Anomalías: {anomalies or 'ninguna'}."
        )

        return MetaNetworkObservation(
            verdict=verdict,
            confidence=confidence_score,
            error_rate=error_rate,
            activation_entropy=normalized_entropy,
            coherence_score=coherence,
            anomalies=anomalies,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Homeostasis artificial
    # ------------------------------------------------------------------
    def check_homeostasis(self, observation: Optional[ExecutionObservation] = None) -> HomeostasisReport:
        """Verifica estabilidad operativa y límites de seguridad."""
        report = HomeostasisReport()
        recent = self.self_store.get_recent_performance(limit=20)
        successes = sum(1 for r in recent if r.get("success"))
        report.success_rate_recent = successes / len(recent) if recent else 1.0

        # Límite de ajustes recientes (usar log de decisiones como proxy)
        report.adjustment_count_1h = len(
            [d for d in self.decision_log if "adjust" in d["decision"] or d["decision"] in {"mutate", "retrain"}]
        )

        if report.success_rate_recent < self.config["homeostasis"]["min_recent_success_rate"]:
            report.stable = False
            report.warnings.append(
                f"Tasa de éxito reciente {report.success_rate_recent:.0%} por debajo del umbral."
            )
        if report.adjustment_count_1h > self.config["homeostasis"]["max_adjustments_per_hour"]:
            report.stable = False
            report.warnings.append(
                "Demasiados ajustes recientes; se requiere estabilización."
            )

        if observation:
            report.resource_usage = {
                "tokens_used": observation.tokens_used,
                "tool_calls": observation.tool_calls,
                "latency_seconds": observation.latency_seconds,
            }
            if observation.tokens_used > self.config["efficiency"]["max_tokens"] * 2:
                report.warnings.append("Consumo de tokens excesivo.")
            if observation.tool_calls > self.config["efficiency"]["max_tool_calls"] * 2:
                report.warnings.append("Demasiadas llamadas a herramientas.")

        report.can_shutdown_safely = report.stable and len(report.warnings) == 0
        return report

    # ------------------------------------------------------------------
    # Plasticidad sináptica digital (Hebbiano + EWC)
    # ------------------------------------------------------------------
    def update_synaptic_weights(
        self,
        key: str,
        success: bool,
        confidence: float,
    ) -> float:
        """Actualiza pesos plásticos con refuerzo positivo/negativo y ancla EWC."""
        cfg = self.config["hebbian"]
        lr = cfg["learning_rate"]
        ewc_lambda = cfg["ewc_lambda"]
        lo, hi = cfg["weight_clip"]

        # Inicializar si es necesario
        if key not in self.synaptic_weights:
            self.synaptic_weights[key] = 1.0
            self.baseline_weights[key] = 1.0

        current = self.synaptic_weights[key]
        baseline = self.baseline_weights[key]

        # Refuerzo Hebbiano
        reward_signal = (1.0 if success else -1.0) * confidence
        hebbian_delta = lr * reward_signal

        # Penalización elástica que protege el peso original
        ewc_penalty = ewc_lambda * (current - baseline)
        new_weight = current + hebbian_delta - ewc_penalty
        new_weight = max(lo, min(hi, new_weight))

        self.synaptic_weights[key] = new_weight
        return new_weight

    def get_synaptic_snapshot(self) -> Dict[str, Any]:
        return {
            "weights": dict(self.synaptic_weights),
            "baselines": dict(self.baseline_weights),
        }

    # ------------------------------------------------------------------
    # Propuesta y aplicación segura de ajustes
    # ------------------------------------------------------------------
    def propose_adjustment(
        self,
        adjustment_type: AdjustmentType,
        target: str,
        change: Dict[str, Any],
        reason: str,
        risk_level: str = "low",
    ) -> AdjustmentProposal:
        """Crea una propuesta sin aplicarla; requiere aprobación según política."""
        return self._build_proposal(adjustment_type, target, change, reason, risk_level)

    def apply_proposal(
        self,
        proposal_id: str,
        approved: bool = False,
        approved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aplica una propuesta solo si está aprobada y dentro de la política."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {"status": "not_found", "proposal_id": proposal_id}

        # Política de aprobación
        if not approved:
            proposal.status = ProposalStatus.AWAITING_APPROVAL
            return {"status": "awaiting_approval", "proposal": proposal.to_dict()}

        require = self.config["approval"]["require_approval_for"]
        if (
            proposal.adjustment_type.value in require
            or proposal.risk_level in require
        ) and not approved_by:
            proposal.status = ProposalStatus.AWAITING_APPROVAL
            return {
                "status": "awaiting_supervisor",
                "message": "Requiere identidad del supervisor por tipo o riesgo.",
                "proposal": proposal.to_dict(),
            }

        # Snapshot antes de aplicar para posible rollback
        self._last_applied_snapshot = self._create_snapshot()

        model = self.self_store.load()
        applied = False
        rollback_steps: List[str] = []

        try:
            if proposal.adjustment_type == AdjustmentType.PARAM:
                # Ajustar competencia/hiperparámetro en self-model
                target = proposal.target
                change = proposal.change
                if target == "elite_replication":
                    self.self_store.record_performance(
                        task="elite_replication",
                        success=True,
                        metrics={"change": change},
                        context={},
                        policy_adjustments=[proposal.reason],
                    )
                else:
                    self.self_store.update_competence(target, change.get("value", 0.5))
                rollback_steps.append(f"restore_competence:{target}")
                applied = True

            elif proposal.adjustment_type == AdjustmentType.OBJECTIVE:
                current_goal = model.get("current_goal", "")
                new_goal = proposal.change.get("new_goal", current_goal)
                result = self.goal_manager.apply_goal_change(
                    current_goal,
                    new_goal,
                    proposal.reason,
                    context=proposal.change.get("context", {}),
                    approved=True,
                )
                if result["status"] == "applied":
                    self.self_store.update_goal(new_goal, proposal.reason)
                    rollback_steps.append(f"restore_goal:{current_goal}")
                    applied = True

            elif proposal.adjustment_type == AdjustmentType.ARCHITECTURE:
                # Registrar la intención; no se modifica código/archivo sin supervisor
                self.memory_router.store_working_memory(
                    f"Propuesta arquitectónica {proposal.proposal_id}: {proposal.reason}",
                    note_type="architecture_proposal",
                    metadata=proposal.to_dict(),
                )
                rollback_steps.append(f"remove_note:{proposal.proposal_id}")
                applied = True

            # ------------------------------------------------------------------
            # Plasticidad del cerebro prefrontal / world model (UC-313)
            # ------------------------------------------------------------------
            if self.prefrontal is not None and proposal.target in {
                "central_brain",
                "world_model",
                "prefrontal",
            }:
                action = proposal.change.get("action")
                if action == "retrain_world_model":
                    self.prefrontal.retrain_world_model(
                        proposal.reason, approved_by=approved_by
                    )
                    rollback_steps.append("rollback:prefrontal")
                    applied = True
                elif action == "update_param" and "param_path" in proposal.change:
                    self.prefrontal.update_param(
                        proposal.change["param_path"],
                        proposal.change["value"],
                        proposal.reason,
                        approved_by=approved_by,
                    )
                    rollback_steps.append("rollback:prefrontal")
                    applied = True
                elif action == "freeze_module":
                    self.prefrontal.freeze_module(
                        proposal.change.get("module", ""), proposal.reason
                    )
                    rollback_steps.append(f"thaw_module:{proposal.change.get('module', '')}")
                    applied = True
                elif action == "thaw_module":
                    self.prefrontal.thaw_module(
                        proposal.change.get("module", ""), proposal.reason
                    )
                    rollback_steps.append(f"freeze_module:{proposal.change.get('module', '')}")
                    applied = True

        except Exception as exc:
            self.rollback_last_applied()
            return {"status": "error", "error": str(exc), "proposal": proposal.to_dict()}

        proposal.approved = True
        proposal.approved_by = approved_by
        proposal.status = ProposalStatus.APPLIED
        return {
            "status": "applied",
            "proposal": proposal.to_dict(),
            "rollback_steps": rollback_steps,
        }

    def _create_snapshot(self) -> Dict[str, Any]:
        return {
            "synaptic_weights": copy.deepcopy(self.synaptic_weights),
            "baseline_weights": copy.deepcopy(self.baseline_weights),
            "self_model": copy.deepcopy(self.self_store.load()),
        }

    def rollback_last_applied(self) -> Dict[str, Any]:
        """Revierte el último cambio aplicado usando el snapshot."""
        if not self._last_applied_snapshot:
            return {"status": "no_snapshot", "restored": False}
        snap = self._last_applied_snapshot
        self.synaptic_weights = snap["synaptic_weights"]
        self.baseline_weights = snap["baseline_weights"]
        self.self_store.save(snap["self_model"])
        # Marcar propuestas afectadas como rolled_back
        for p in self.proposals.values():
            if p.status == ProposalStatus.APPLIED:
                p.status = ProposalStatus.ROLLED_BACK
        return {"status": "rolled_back", "restored": True}

    # ------------------------------------------------------------------
    # Integración con CNP: broadcast de estado
    # ------------------------------------------------------------------
    def broadcast_state(self, source: str = "uc307_layer") -> Dict[str, Any]:
        """Prepara un mensaje de broadcast con el estado evolutivo actual."""
        summary = {
            "trace_id": str(uuid.uuid4()),
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fitness_summary": self._fitness_summary(),
            "synaptic_weights": self.get_synaptic_snapshot(),
            "homeostasis": self.check_homeostasis().to_dict(),
            "recent_decisions": self.decision_log[-5:],
        }
        # Persistir como nota de trabajo para otros agentes CNP
        self.memory_router.store_working_memory(
            f"Broadcast evolutivo {summary['trace_id']}: "
            f"decisiones recientes={len(self.decision_log)}",
            note_type="evolution_broadcast",
            metadata=summary,
        )
        return summary

    def _fitness_summary(self) -> Dict[str, Any]:
        if not self.decision_log:
            return {"count": 0, "avg_fitness": 0.0}
        fitnesses = [d["fitness"] for d in self.decision_log]
        return {
            "count": len(fitnesses),
            "avg_fitness": sum(fitnesses) / len(fitnesses),
            "min_fitness": min(fitnesses),
            "max_fitness": max(fitnesses),
        }

    def reflect(self, limit: int = 20) -> Dict[str, Any]:
        """Delega la reflexión en el evaluador continuo."""
        return self.evaluator.reflect(limit=limit)
