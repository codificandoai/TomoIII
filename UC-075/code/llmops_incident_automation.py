"""
UC-075 — Automatización de incidentes LLMOps con Human-in-the-Loop.

Gestiona incidentes comunes de forma automatizada y escala a humanos los casos
ambiguos, complejos o con implicaciones regulatorias. Integra simulacros,
postmortem y aprendizaje de políticas, exportando métricas a Prometheus y
Grafana.

Diseñado para complementar (no reemplazar) el juicio humano:
- Automatización de alta confianza en incidentes claros y repetibles.
- Escalación obligatoria a HITL en ambigüedad, riesgo regulatorio o patrones
  nunca vistos.
- Simulacros periódicos (drills) para mantener la preparación.
- Postmortem con aprendizaje que alimenta el RiskRegister y las políticas.

Depende de:
- risk_management_framework.py (RiskRegister, RiskCategory, runbooks).
- observability_075.py (métricas Prometheus/Grafana).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from risk_management_framework import RiskCategory, RiskRegister, risk_from_agent_tool_abuse


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IncidentCategory(str, Enum):
    DATA_DRIFT = "data_drift"
    DATA_POISONING = "data_poisoning"
    PII_LEAK = "pii_leak"
    MODEL_DEGRADATION = "model_degradation"
    BIAS_VIOLATION = "bias_violation"
    ADVERSARIAL_ATTACK = "adversarial_attack"
    PROMPT_INJECTION = "prompt_injection"
    TOOL_ABUSE = "tool_abuse"
    AGENT_LOOP = "agent_loop"
    INFRASTRUCTURE_OUTAGE = "infrastructure_outage"
    SUPPLY_CHAIN = "supply_chain"
    REGULATORY_ALERT = "regulatory_alert"
    UNKNOWN = "unknown"


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"
    HUMAN_RESOLVED = "human_resolved"
    CLOSED_WITHOUT_ACTION = "closed_without_action"


class EscalationReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_CONTEXT = "ambiguous_context"
    REGULATORY_CONTEXT = "regulatory_context"
    NO_PLAYBOOK = "no_playbook"
    HIGH_SEVERITY = "high_severity"
    DESTRUCTIVE_ACTION = "destructive_action"
    NOVEL_PATTERN = "novel_pattern"
    HUMAN_REQUIRED = "human_required"


# ---------------------------------------------------------------------------
# Incidente
# ---------------------------------------------------------------------------


@dataclass
class Incident:
    incident_id: str = field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:10]}")
    category: IncidentCategory = IncidentCategory.UNKNOWN
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    title: str = ""
    description: str = ""
    source: str = ""  # detector / agent / monitoring
    detected_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    status: IncidentStatus = IncidentStatus.DETECTED
    confidence: float = 0.0  # 0..1
    impact_score: float = 0.0  # 0..1
    affected_artifacts: List[str] = field(default_factory=list)
    affected_agents: List[str] = field(default_factory=list)
    affected_runs: List[str] = field(default_factory=list)
    escalation_reasons: List[str] = field(default_factory=list)
    assigned_human: str = ""
    playbook_id: str = ""
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    resolution_notes: str = ""
    policy_learnings: List[str] = field(default_factory=list)
    drill_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "detected_at": self.detected_at,
            "resolved_at": self.resolved_at,
            "status": self.status.value,
            "confidence": round(self.confidence, 4),
            "impact_score": round(self.impact_score, 4),
            "affected_artifacts": self.affected_artifacts,
            "affected_agents": self.affected_agents,
            "affected_runs": self.affected_runs,
            "escalation_reasons": self.escalation_reasons,
            "assigned_human": self.assigned_human,
            "playbook_id": self.playbook_id,
            "actions_taken": self.actions_taken,
            "resolution_notes": self.resolution_notes,
            "policy_learnings": self.policy_learnings,
            "drill_id": self.drill_id,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Playbooks de respuesta automatizada
# ---------------------------------------------------------------------------


ActionExecutor = Callable[["Incident", "LLMOpsIncidentManager"], bool]


class PlaybookRegistry:
    """Registro de playbooks con acciones ejecutables y reglas de escalación."""

    DEFAULT_PLAYBOOKS: Dict[IncidentCategory, Dict[str, Any]] = {
        IncidentCategory.DATA_DRIFT: {
            "id": "pb-data-drift",
            "name": "Data drift response",
            "auto_actions": ["freeze_dataset", "trigger_retrain", "notify_owner"],
            "escalate_if_confidence_below": 0.6,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [],
        },
        IncidentCategory.DATA_POISONING: {
            "id": "pb-data-poisoning",
            "name": "Data poisoning containment",
            "auto_actions": ["quarantine_batch", "open_circuit_breaker", "notify_security"],
            "escalate_if_confidence_below": 0.7,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [EscalationReason.DESTRUCTIVE_ACTION],
        },
        IncidentCategory.PII_LEAK: {
            "id": "pb-pii-leak",
            "name": "PII leak response",
            "auto_actions": ["revoke_access", "mask_logs", "notify_dpo"],
            "escalate_if_confidence_below": 0.5,
            "max_auto_severity": IncidentSeverity.MEDIUM,
            "requires_human_for": [EscalationReason.REGULATORY_CONTEXT],
        },
        IncidentCategory.MODEL_DEGRADATION: {
            "id": "pb-model-degradation",
            "name": "Model degradation rollback",
            "auto_actions": ["rollback_model", "shadow_canary", "trigger_retrain"],
            "escalate_if_confidence_below": 0.6,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [],
        },
        IncidentCategory.BIAS_VIOLATION: {
            "id": "pb-bias-violation",
            "name": "Bias / fairness violation",
            "auto_actions": ["disable_auto_promote", "notify_fairness_team"],
            "escalate_if_confidence_below": 0.6,
            "max_auto_severity": IncidentSeverity.MEDIUM,
            "requires_human_for": [EscalationReason.REGULATORY_CONTEXT],
        },
        IncidentCategory.ADVERSARIAL_ATTACK: {
            "id": "pb-adversarial",
            "name": "Adversarial attack response",
            "auto_actions": ["isolate_model", "increase_monitoring", "notify_security"],
            "escalate_if_confidence_below": 0.7,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [EscalationReason.HIGH_SEVERITY],
        },
        IncidentCategory.PROMPT_INJECTION: {
            "id": "pb-prompt-injection",
            "name": "Prompt injection response",
            "auto_actions": ["block_input", "log_forensics", "rotate_guardrails"],
            "escalate_if_confidence_below": 0.5,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [],
        },
        IncidentCategory.TOOL_ABUSE: {
            "id": "pb-tool-abuse",
            "name": "Agent tool abuse",
            "auto_actions": ["revoke_credentials", "disable_tool", "require_hitl"],
            "escalate_if_confidence_below": 0.6,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [EscalationReason.DESTRUCTIVE_ACTION],
        },
        IncidentCategory.AGENT_LOOP: {
            "id": "pb-agent-loop",
            "name": "Agent execution loop",
            "auto_actions": ["terminate_agent", "dump_trace", "notify_operator"],
            "escalate_if_confidence_below": 0.5,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [],
        },
        IncidentCategory.INFRASTRUCTURE_OUTAGE: {
            "id": "pb-infra-outage",
            "name": "Infrastructure outage / misconfiguration",
            "auto_actions": ["failover_region", "page_sre", "rotate_secrets"],
            "escalate_if_confidence_below": 0.6,
            "max_auto_severity": IncidentSeverity.CRITICAL,
            "requires_human_for": [EscalationReason.HIGH_SEVERITY],
        },
        IncidentCategory.SUPPLY_CHAIN: {
            "id": "pb-supply-chain",
            "name": "Supply chain compromise",
            "auto_actions": ["block_component", "scan_sbom", "rebuild_image"],
            "escalate_if_confidence_below": 0.7,
            "max_auto_severity": IncidentSeverity.HIGH,
            "requires_human_for": [EscalationReason.NOVEL_PATTERN],
        },
        IncidentCategory.REGULATORY_ALERT: {
            "id": "pb-regulatory",
            "name": "Regulatory alert",
            "auto_actions": ["preserve_evidence", "legal_hold", "notify_legal"],
            "escalate_if_confidence_below": 0.4,
            "max_auto_severity": IncidentSeverity.LOW,
            "requires_human_for": [EscalationReason.REGULATORY_CONTEXT],
        },
        IncidentCategory.UNKNOWN: {
            "id": "pb-unknown",
            "name": "Unknown / novel pattern",
            "auto_actions": ["log_forensics", "notify_soc"],
            "escalate_if_confidence_below": 1.0,  # siempre escala
            "max_auto_severity": IncidentSeverity.LOW,
            "requires_human_for": [EscalationReason.NOVEL_PATTERN],
        },
    }

    def __init__(self, playbooks: Optional[Dict[IncidentCategory, Dict[str, Any]]] = None) -> None:
        self._playbooks = playbooks or dict(self.DEFAULT_PLAYBOOKS)
        self._executors: Dict[str, ActionExecutor] = {}
        self._register_default_executors()

    def _register_default_executors(self) -> None:
        self._executors["freeze_dataset"] = lambda inc, mgr: mgr._act("freeze_dataset", inc)
        self._executors["trigger_retrain"] = lambda inc, mgr: mgr._act("trigger_retrain", inc)
        self._executors["notify_owner"] = lambda inc, mgr: mgr._act("notify_owner", inc)
        self._executors["quarantine_batch"] = lambda inc, mgr: mgr._act("quarantine_batch", inc)
        self._executors["open_circuit_breaker"] = lambda inc, mgr: mgr._act("open_circuit_breaker", inc)
        self._executors["notify_security"] = lambda inc, mgr: mgr._act("notify_security", inc)
        self._executors["revoke_access"] = lambda inc, mgr: mgr._act("revoke_access", inc)
        self._executors["mask_logs"] = lambda inc, mgr: mgr._act("mask_logs", inc)
        self._executors["notify_dpo"] = lambda inc, mgr: mgr._act("notify_dpo", inc)
        self._executors["rollback_model"] = lambda inc, mgr: mgr._act("rollback_model", inc)
        self._executors["shadow_canary"] = lambda inc, mgr: mgr._act("shadow_canary", inc)
        self._executors["disable_auto_promote"] = lambda inc, mgr: mgr._act("disable_auto_promote", inc)
        self._executors["notify_fairness_team"] = lambda inc, mgr: mgr._act("notify_fairness_team", inc)
        self._executors["isolate_model"] = lambda inc, mgr: mgr._act("isolate_model", inc)
        self._executors["increase_monitoring"] = lambda inc, mgr: mgr._act("increase_monitoring", inc)
        self._executors["block_input"] = lambda inc, mgr: mgr._act("block_input", inc)
        self._executors["log_forensics"] = lambda inc, mgr: mgr._act("log_forensics", inc)
        self._executors["rotate_guardrails"] = lambda inc, mgr: mgr._act("rotate_guardrails", inc)
        self._executors["revoke_credentials"] = lambda inc, mgr: mgr._act("revoke_credentials", inc)
        self._executors["disable_tool"] = lambda inc, mgr: mgr._act("disable_tool", inc)
        self._executors["require_hitl"] = lambda inc, mgr: mgr._act("require_hitl", inc)
        self._executors["terminate_agent"] = lambda inc, mgr: mgr._act("terminate_agent", inc)
        self._executors["dump_trace"] = lambda inc, mgr: mgr._act("dump_trace", inc)
        self._executors["notify_operator"] = lambda inc, mgr: mgr._act("notify_operator", inc)
        self._executors["failover_region"] = lambda inc, mgr: mgr._act("failover_region", inc)
        self._executors["page_sre"] = lambda inc, mgr: mgr._act("page_sre", inc)
        self._executors["rotate_secrets"] = lambda inc, mgr: mgr._act("rotate_secrets", inc)
        self._executors["block_component"] = lambda inc, mgr: mgr._act("block_component", inc)
        self._executors["scan_sbom"] = lambda inc, mgr: mgr._act("scan_sbom", inc)
        self._executors["rebuild_image"] = lambda inc, mgr: mgr._act("rebuild_image", inc)
        self._executors["preserve_evidence"] = lambda inc, mgr: mgr._act("preserve_evidence", inc)
        self._executors["legal_hold"] = lambda inc, mgr: mgr._act("legal_hold", inc)
        self._executors["notify_legal"] = lambda inc, mgr: mgr._act("notify_legal", inc)
        self._executors["notify_soc"] = lambda inc, mgr: mgr._act("notify_soc", inc)

    def get(self, category: IncidentCategory) -> Dict[str, Any]:
        return self._playbooks.get(category, self._playbooks[IncidentCategory.UNKNOWN])

    def register_executor(self, action: str, fn: ActionExecutor) -> None:
        self._executors[action] = fn

    def execute(self, action: str, incident: "Incident", manager: "LLMOpsIncidentManager") -> bool:
        fn = self._executors.get(action)
        if fn is None:
            return False
        return fn(incident, manager)


# ---------------------------------------------------------------------------
# Clasificador y confianza
# ---------------------------------------------------------------------------


class IncidentClassifier:
    """Clasificación determinista basada en categoría y señales."""

    SEVERITY_ORDER = {
        IncidentSeverity.CRITICAL: 3,
        IncidentSeverity.HIGH: 2,
        IncidentSeverity.MEDIUM: 1,
        IncidentSeverity.LOW: 0,
    }

    def classify(
        self,
        category: IncidentCategory,
        title: str,
        description: str,
        impact_score: float,
    ) -> tuple[IncidentSeverity, float]:
        """Devuelve severidad y confianza estimada."""
        confidence = 0.7
        if category in (IncidentCategory.TOOL_ABUSE, IncidentCategory.AGENT_LOOP):
            confidence += 0.15
        if "regulatory" in title.lower() or "gdpr" in description.lower():
            confidence -= 0.1
        confidence = max(0.0, min(1.0, confidence))

        if impact_score >= 0.8:
            severity = IncidentSeverity.CRITICAL
        elif impact_score >= 0.6:
            severity = IncidentSeverity.HIGH
        elif impact_score >= 0.3:
            severity = IncidentSeverity.MEDIUM
        else:
            severity = IncidentSeverity.LOW
        return severity, confidence


# ---------------------------------------------------------------------------
# Cola de escalación humana
# ---------------------------------------------------------------------------


class HumanEscalationQueue:
    """Cola de incidentes que requieren atención humana."""

    def __init__(self) -> None:
        self._queue: List[Incident] = []

    def push(self, incident: Incident) -> None:
        self._queue.append(incident)

    def list_open(self) -> List[Incident]:
        return [i for i in self._queue if i.status == IncidentStatus.ESCALATED]

    def assign(self, incident_id: str, human: str) -> Optional[Incident]:
        for inc in self._queue:
            if inc.incident_id == incident_id:
                inc.assigned_human = human
                return inc
        return None

    def resolve(
        self,
        incident_id: str,
        resolution_notes: str,
        policy_learnings: Optional[List[str]] = None,
    ) -> Optional[Incident]:
        for inc in self._queue:
            if inc.incident_id == incident_id:
                inc.status = IncidentStatus.HUMAN_RESOLVED
                inc.resolved_at = time.time()
                inc.resolution_notes = resolution_notes
                if policy_learnings:
                    inc.policy_learnings.extend(policy_learnings)
                return inc
        return None


# ---------------------------------------------------------------------------
# Simulacros y aprendizaje
# ---------------------------------------------------------------------------


@dataclass
class DrillReport:
    drill_id: str
    scenario: str
    started_at: float
    finished_at: Optional[float]
    incidents_injected: int
    auto_resolved: int
    escalated: int
    mean_time_to_triage_seconds: float
    findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "scenario": self.scenario,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "incidents_injected": self.incidents_injected,
            "auto_resolved": self.auto_resolved,
            "escalated": self.escalated,
            "mean_time_to_triage_seconds": round(self.mean_time_to_triage_seconds, 4),
            "findings": self.findings,
        }


class DrillSimulator:
    """Ejecuta simulacros de incidentes sin afectar sistemas reales."""

    def __init__(self, manager: "LLMOpsIncidentManager") -> None:
        self.manager = manager
        self._drills: Dict[str, DrillReport] = {}

    def run_drill(
        self,
        scenario: str,
        incidents: List[Dict[str, Any]],
        dry_run: bool = True,
    ) -> DrillReport:
        drill_id = f"drill-{uuid.uuid4().hex[:10]}"
        report = DrillReport(
            drill_id=drill_id,
            scenario=scenario,
            started_at=time.time(),
            finished_at=None,
            incidents_injected=len(incidents),
            auto_resolved=0,
            escalated=0,
            mean_time_to_triage_seconds=0.0,
        )
        self._drills[drill_id] = report
        triage_times: List[float] = []

        for raw in incidents:
            start = time.time()
            inc = self.manager.detect(
                category=raw.get("category", IncidentCategory.UNKNOWN),
                title=raw.get("title", "drill incident"),
                description=raw.get("description", ""),
                source=raw.get("source", "drill"),
                impact_score=raw.get("impact_score", 0.5),
                affected_artifacts=raw.get("affected_artifacts", []),
                affected_agents=raw.get("affected_agents", []),
                tags={"drill": drill_id},
                dry_run=dry_run,
            )
            triage_times.append(time.time() - start)
            if inc.status == IncidentStatus.AUTO_RESOLVED:
                report.auto_resolved += 1
            elif inc.status == IncidentStatus.ESCALATED:
                report.escalated += 1

        report.finished_at = time.time()
        report.mean_time_to_triage_seconds = sum(triage_times) / max(len(triage_times), 1)
        if dry_run:
            report.findings.append("Dry-run: no actions executed on production systems.")
        return report

    def get(self, drill_id: str) -> Optional[DrillReport]:
        return self._drills.get(drill_id)

    def list(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._drills.values()]


class PolicyLearningEngine:
    """Extrae aprendizajes de incidentes resueltos para sugerir cambios de política."""

    def analyze(self, incidents: List[Incident]) -> List[Dict[str, Any]]:
        suggestions = []
        for inc in incidents:
            if inc.category == IncidentCategory.PROMPT_INJECTION and inc.confidence < 0.8:
                suggestions.append({
                    "target": "guardrails",
                    "suggestion": "Aumentar validación de inputs y actualizar deny-list de patrones.",
                    "incident_ids": [inc.incident_id],
                })
            if inc.category == IncidentCategory.TOOL_ABUSE and EscalationReason.DESTRUCTIVE_ACTION.value in inc.escalation_reasons:
                suggestions.append({
                    "target": "tool_policy",
                    "suggestion": "Requerir doble aprobación para herramientas destructivas.",
                    "incident_ids": [inc.incident_id],
                })
            if inc.category == IncidentCategory.DATA_POISONING and inc.impact_score > 0.7:
                suggestions.append({
                    "target": "data_validation",
                    "suggestion": "Añadir validación de provenance antes de indexar en RAG.",
                    "incident_ids": [inc.incident_id],
                })
            if inc.category == IncidentCategory.UNKNOWN:
                suggestions.append({
                    "target": "playbook",
                    "suggestion": f"Crear playbook para patrones similares a {inc.title}.",
                    "incident_ids": [inc.incident_id],
                })
        return suggestions


# ---------------------------------------------------------------------------
# Manager principal
# ---------------------------------------------------------------------------


class LLMOpsIncidentManager:
    """Orquesta detección, triage, respuesta, escalación y aprendizaje."""

    def __init__(
        self,
        risk_register: Optional[RiskRegister] = None,
        playbook_registry: Optional[PlaybookRegistry] = None,
        classifier: Optional[IncidentClassifier] = None,
        human_queue: Optional[HumanEscalationQueue] = None,
        observability: Optional[Any] = None,
    ) -> None:
        self.risk_register = risk_register
        self.playbooks = playbook_registry or PlaybookRegistry()
        self.classifier = classifier or IncidentClassifier()
        self.human_queue = human_queue or HumanEscalationQueue()
        self.observability = observability
        self._incidents: Dict[str, Incident] = {}
        self._drill_simulator = DrillSimulator(self)
        self._policy_learning = PolicyLearningEngine()
        self._action_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Detección y triage
    # ------------------------------------------------------------------
    def detect(
        self,
        category: IncidentCategory,
        title: str,
        description: str,
        source: str,
        impact_score: float = 0.5,
        confidence: Optional[float] = None,
        affected_artifacts: Optional[List[str]] = None,
        affected_agents: Optional[List[str]] = None,
        affected_runs: Optional[List[str]] = None,
        tags: Optional[Dict[str, str]] = None,
        dry_run: bool = False,
    ) -> Incident:
        if isinstance(category, str):
            category = IncidentCategory(category)
        severity, estimated_confidence = self.classifier.classify(
            category, title, description, impact_score
        )
        inc = Incident(
            category=category,
            severity=severity,
            title=title,
            description=description,
            source=source,
            impact_score=impact_score,
            confidence=confidence if confidence is not None else estimated_confidence,
            affected_artifacts=affected_artifacts or [],
            affected_agents=affected_agents or [],
            affected_runs=affected_runs or [],
            tags=tags or {},
        )
        self._incidents[inc.incident_id] = inc

        if self.observability:
            self.observability.record_incident(
                category=inc.category.value,
                severity=inc.severity.value,
                status=inc.status.value,
                confidence=inc.confidence,
                escalated=False,
            )

        self._triage(inc, dry_run=dry_run)
        return inc

    def _triage(self, incident: Incident, dry_run: bool = False) -> None:
        playbook = self.playbooks.get(incident.category)
        reasons: List[str] = []

        # Reglas de escalación
        if incident.confidence < playbook.get("escalate_if_confidence_below", 0.5):
            reasons.append(EscalationReason.LOW_CONFIDENCE.value)
        if IncidentClassifier.SEVERITY_ORDER[incident.severity] > IncidentClassifier.SEVERITY_ORDER[playbook.get("max_auto_severity", IncidentSeverity.HIGH)]:
            reasons.append(EscalationReason.HIGH_SEVERITY.value)
        if incident.category == IncidentCategory.REGULATORY_ALERT:
            reasons.append(EscalationReason.REGULATORY_CONTEXT.value)
        if incident.category == IncidentCategory.UNKNOWN:
            reasons.append(EscalationReason.NOVEL_PATTERN.value)
        if "destructive" in incident.description.lower():
            reasons.append(EscalationReason.DESTRUCTIVE_ACTION.value)
        if "ambiguous" in incident.description.lower() or "unclear" in incident.description.lower():
            reasons.append(EscalationReason.AMBIGUOUS_CONTEXT.value)

        if reasons:
            self._escalate(incident, reasons)
            return

        # Auto-resolución
        actions = playbook.get("auto_actions", [])
        success = True
        for action in actions:
            if dry_run:
                incident.actions_taken.append({"action": action, "status": "dry_run", "success": True})
            else:
                ok = self.playbooks.execute(action, incident, self)
                incident.actions_taken.append({"action": action, "status": "executed", "success": ok})
                success = success and ok

        if success:
            incident.status = IncidentStatus.AUTO_RESOLVED
            incident.resolved_at = time.time()
            incident.playbook_id = playbook.get("id", "")
        else:
            self._escalate(incident, [EscalationReason.HUMAN_REQUIRED.value])

    def _escalate(self, incident: Incident, reasons: List[str]) -> None:
        incident.status = IncidentStatus.ESCALATED
        incident.escalation_reasons = reasons
        self.human_queue.push(incident)
        if self.risk_register:
            if incident.category == IncidentCategory.TOOL_ABUSE and incident.affected_agents:
                risk = risk_from_agent_tool_abuse(
                    incident.affected_agents[0], "unknown", incident.description,
                    probability=incident.confidence, impact=incident.impact_score,
                )
                self.risk_register.register(risk)
            else:
                from risk_management_framework import Risk, RiskCategory
                risk = Risk(
                    category=RiskCategory(incident.category.value)
                    if incident.category.value in {c.value for c in RiskCategory}
                    else RiskCategory.SECURITY,
                    subcategory=incident.category.value,
                    description=incident.description,
                    probability=incident.confidence,
                    impact=incident.impact_score,
                    exposure=1.0,
                    trigger_event="incident_escalated",
                    trigger_details={"incident_id": incident.incident_id, "reasons": reasons},
                    linked_artifact_ids=incident.affected_artifacts,
                    linked_agent_ids=incident.affected_agents,
                    requires_hitl=True,
                )
                self.risk_register.register(risk)
        if self.observability:
            self.observability.record_incident_escalation(
                category=incident.category.value,
                reasons=reasons,
            )

    def _act(self, action: str, incident: Incident) -> bool:
        """Acción simulada: registra en log y devuelve éxito."""
        self._action_log.append({
            "timestamp": time.time(),
            "action": action,
            "incident_id": incident.incident_id,
        })
        return True

    # ------------------------------------------------------------------
    # Escalación humana
    # ------------------------------------------------------------------
    def assign_human(self, incident_id: str, human: str) -> Optional[Incident]:
        inc = self.human_queue.assign(incident_id, human)
        if inc:
            inc.assigned_human = human
            return inc
        return None

    def resolve_human(
        self,
        incident_id: str,
        resolution_notes: str,
        policy_learnings: Optional[List[str]] = None,
    ) -> Optional[Incident]:
        inc = self.human_queue.resolve(incident_id, resolution_notes, policy_learnings)
        if inc is None:
            inc = self._incidents.get(incident_id)
            if inc:
                inc.status = IncidentStatus.HUMAN_RESOLVED
                inc.resolved_at = time.time()
                inc.resolution_notes = resolution_notes
                if policy_learnings:
                    inc.policy_learnings.extend(policy_learnings)
        if inc and self.observability:
            self.observability.record_incident_resolution(
                category=inc.category.value,
                resolution="human",
                duration_seconds=(inc.resolved_at or time.time()) - inc.detected_at,
            )
        return inc

    # ------------------------------------------------------------------
    # Consultas y reportes
    # ------------------------------------------------------------------
    def get(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def list(
        self,
        category: Optional[IncidentCategory] = None,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
    ) -> List[Incident]:
        result = list(self._incidents.values())
        if category:
            result = [i for i in result if i.category == category]
        if status:
            result = [i for i in result if i.status == status]
        if severity:
            result = [i for i in result if i.severity == severity]
        return result

    def summary(self) -> Dict[str, Any]:
        total = len(self._incidents)
        auto = len([i for i in self._incidents.values() if i.status == IncidentStatus.AUTO_RESOLVED])
        escalated = len([i for i in self._incidents.values() if i.status == IncidentStatus.ESCALATED])
        human_resolved = len([i for i in self._incidents.values() if i.status == IncidentStatus.HUMAN_RESOLVED])
        mttr = 0.0
        resolved = [i for i in self._incidents.values() if i.resolved_at]
        if resolved:
            mttr = sum(i.resolved_at - i.detected_at for i in resolved) / len(resolved)  # type: ignore
        return {
            "total_incidents": total,
            "auto_resolved": auto,
            "escalated": escalated,
            "human_resolved": human_resolved,
            "pending_human": len(self.human_queue.list_open()),
            "mean_time_to_resolution_seconds": round(mttr, 4),
        }

    # ------------------------------------------------------------------
    # Simulacros y aprendizaje
    # ------------------------------------------------------------------
    @property
    def drills(self) -> DrillSimulator:
        return self._drill_simulator

    def run_drill(self, scenario: str, incidents: List[Dict[str, Any]]) -> DrillReport:
        return self._drill_simulator.run_drill(scenario, incidents, dry_run=True)

    def policy_learnings(self) -> List[Dict[str, Any]]:
        resolved = [i for i in self._incidents.values() if i.status in (
            IncidentStatus.AUTO_RESOLVED, IncidentStatus.HUMAN_RESOLVED
        )]
        return self._policy_learning.analyze(resolved)
