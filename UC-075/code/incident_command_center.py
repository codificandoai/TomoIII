"""
UC-075 — Incident Command Center: StackStorm + Wiki.js para LLMOps.

Unifica incidentes, acciones y contexto en una plataforma de colaboración:
- StackStorm como motor de ejecución subordinado a UC-317.
- Wiki.js como single pane of glass para runbooks, postmortems y estado.
- Integración con Grafana/Loki/Tempo para observabilidad.

Diseño de autoridad:
- UC-315 decide, UC-317 ejecuta.
- StackStorm NO decide; solo ejecuta acciones previamente autorizadas.
- Cada acción requiere un approval_ref auditable y debe estar en allowlist.
- Acciones destructivas/financieras/regulatorias exigen HITL (UC-290).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Enums y utilidades
# ---------------------------------------------------------------------------


class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class IncidentPageType(str, Enum):
    INCIDENT = "incident"
    RUNBOOK = "runbook"
    POSTMORTEM = "postmortem"
    STATUS_BOARD = "status_board"


class ApprovalScope(str, Enum):
    AUTO = "auto"  # bajo riesgo, aprobada por política
    HITL = "hitl"  # aprobación humana explícita
    DENIED = "denied"


# ---------------------------------------------------------------------------
# StackStorm adapter (ejecución subordinada)
# ---------------------------------------------------------------------------


@dataclass
class StackStormAction:
    action_id: str = field(default_factory=lambda: f"st2-action-{uuid.uuid4().hex[:8]}")
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    incident_id: str = ""
    approval_ref: str = ""  # referencia a aprobación UC-290/UC-315
    scope: ApprovalScope = ApprovalScope.AUTO
    requested_by: str = "uc075-icc"
    status: ActionStatus = ActionStatus.PENDING
    result: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None
    rolled_back_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action": self.action,
            "params": self.params,
            "incident_id": self.incident_id,
            "approval_ref": self.approval_ref,
            "scope": self.scope.value,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "result": self.result,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "rolled_back_at": self.rolled_back_at,
        }


class StackStormAdapter:
    """
    Adaptador de StackStorm para UC-075.

    - Mantiene una cola de acciones.
    - Ejecuta solo si hay approval_ref y la acción está en allowlist.
    - Registra webhook callbacks para notificar a otros sistemas.
    - Simula ejecución para no depender de un servidor real.
    """

    def __init__(
        self,
        auto_allowlist: Optional[Set[str]] = None,
        hitl_allowlist: Optional[Set[str]] = None,
    ) -> None:
        # Acciones de bajo riesgo que pueden ejecutarse con aprobación por política
        self.auto_allowlist = auto_allowlist or {
            "notify_team", "log_forensics", "isolate_readonly",
            "increase_monitoring", "dump_trace", "scan_sbom",
        }
        # Acciones de alto riesgo que requieren HITL explícito
        self.hitl_allowlist = hitl_allowlist or {
            "revoke_credentials", "disable_tool", "delete_resource",
            "modify_firewall", "rollback_model", "failover_region",
            "rotate_secrets", "terminate_agent", "block_component",
        }
        self._actions: Dict[str, StackStormAction] = {}
        self._webhooks: Dict[str, List[Callable[[StackStormAction], None]]] = {}
        self._executors: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_executors()

    def _register_default_executors(self) -> None:
        for action in list(self.auto_allowlist) + list(self.hitl_allowlist):
            self._executors[action] = lambda params, a=action: {"simulated": True, "action": a, "params": params}

    def register_executor(
        self,
        action: str,
        fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        self._executors[action] = fn

    def register_webhook(
        self,
        event: str,
        callback: Callable[[StackStormAction], None],
    ) -> None:
        self._webhooks.setdefault(event, []).append(callback)

    def _emit(self, event: str, action: StackStormAction) -> None:
        for cb in self._webhooks.get(event, []):
            try:
                cb(action)
            except Exception:
                pass

    def submit(
        self,
        action: str,
        params: Dict[str, Any],
        incident_id: str,
        approval_ref: str,
        scope: str = ApprovalScope.AUTO.value,
        requested_by: str = "uc075-icc",
    ) -> StackStormAction:
        st2_action = StackStormAction(
            action=action,
            params=params,
            incident_id=incident_id,
            approval_ref=approval_ref,
            scope=ApprovalScope(scope),
            requested_by=requested_by,
        )
        self._actions[st2_action.action_id] = st2_action
        self._emit("submitted", st2_action)
        return st2_action

    def _requires_hitl(self, action: str) -> bool:
        return action in self.hitl_allowlist

    def execute(self, action_id: str) -> StackStormAction:
        """Ejecuta una acción solo si está apropiadamente autorizada."""
        st2 = self._actions.get(action_id)
        if not st2:
            raise ValueError(f"Action {action_id} not found")

        # Fall-closed: sin approval_ref no se ejecuta nada de alto riesgo.
        if not st2.approval_ref:
            st2.status = ActionStatus.REJECTED
            st2.result = {"error": "Missing approval_ref"}
            self._emit("rejected", st2)
            return st2

        if self._requires_hitl(st2.action) and st2.scope != ApprovalScope.HITL:
            st2.status = ActionStatus.REJECTED
            st2.result = {"error": f"Action {st2.action} requires explicit HITL approval"}
            self._emit("rejected", st2)
            return st2

        if st2.action not in self.auto_allowlist and st2.action not in self.hitl_allowlist:
            st2.status = ActionStatus.REJECTED
            st2.result = {"error": f"Action {st2.action} not in allowlist"}
            self._emit("rejected", st2)
            return st2

        fn = self._executors.get(st2.action)
        try:
            result = fn(st2.params) if fn else {"simulated": True}
            st2.status = ActionStatus.EXECUTED
            st2.result = result
            st2.executed_at = time.time()
        except Exception as exc:
            st2.status = ActionStatus.FAILED
            st2.result = {"error": str(exc)}
        self._emit("executed", st2)
        return st2

    def rollback(self, action_id: str) -> StackStormAction:
        st2 = self._actions.get(action_id)
        if not st2:
            raise ValueError(f"Action {action_id} not found")
        st2.status = ActionStatus.ROLLED_BACK
        st2.rolled_back_at = time.time()
        st2.result = {"rolled_back": True}
        self._emit("rolled_back", st2)
        return st2

    def list_actions(
        self,
        incident_id: Optional[str] = None,
        status: Optional[ActionStatus] = None,
    ) -> List[StackStormAction]:
        actions = list(self._actions.values())
        if incident_id:
            actions = [a for a in actions if a.incident_id == incident_id]
        if status:
            actions = [a for a in actions if a.status == status]
        return actions


# ---------------------------------------------------------------------------
# Wiki.js adapter (single pane of glass)
# ---------------------------------------------------------------------------


@dataclass
class WikiPage:
    page_id: str = field(default_factory=lambda: f"wiki-{uuid.uuid4().hex[:8]}")
    page_type: IncidentPageType = IncidentPageType.INCIDENT
    title: str = ""
    content: str = ""
    tags: List[str] = field(default_factory=list)
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_git_commit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_type": self.page_type.value,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_git_commit": self.source_git_commit,
        }


class WikiJsAdapter:
    """Adaptador de Wiki.js para documentación colaborativa de incidentes."""

    def __init__(self) -> None:
        self._pages: Dict[str, WikiPage] = {}
        self._by_incident: Dict[str, List[str]] = {}

    def create_page(
        self,
        page_type: IncidentPageType,
        title: str,
        content: str,
        incident_id: str = "",
        tags: Optional[List[str]] = None,
        source_git_commit: str = "",
    ) -> WikiPage:
        page = WikiPage(
            page_type=page_type,
            title=title,
            content=content,
            tags=tags or [],
            source_git_commit=source_git_commit,
        )
        self._pages[page.page_id] = page
        if incident_id:
            self._by_incident.setdefault(incident_id, []).append(page.page_id)
        return page

    def update_page(self, page_id: str, content: str, source_git_commit: str = "") -> Optional[WikiPage]:
        page = self._pages.get(page_id)
        if not page:
            return None
        page.content += f"\n\n---\n\n{content}"
        page.version += 1
        page.updated_at = time.time()
        if source_git_commit:
            page.source_git_commit = source_git_commit
        return page

    def create_postmortem(
        self,
        incident_id: str,
        title: str,
        findings: List[str],
        action_items: List[str],
        participants: List[str],
    ) -> WikiPage:
        content = f"""# {title}

## Hallazgos
"""
        for f in findings:
            content += f"- {f}\n"
        content += "\n## Acciones\n"
        for a in action_items:
            content += f"- {a}\n"
        content += f"\n## Participantes\n{', '.join(participants)}"
        return self.create_page(
            IncidentPageType.POSTMORTEM,
            title,
            content,
            incident_id=incident_id,
            tags=["postmortem", incident_id],
        )

    def create_runbook_page(
        self,
        category: str,
        actions: List[str],
        version: str,
        source_git_commit: str = "",
    ) -> WikiPage:
        content = f"# Runbook: {category}\n\nVersión: `{version}`\n\n## Acciones\n"
        for a in actions:
            content += f"- {a}\n"
        return self.create_page(
            IncidentPageType.RUNBOOK,
            f"Runbook: {category}",
            content,
            tags=["runbook", category],
            source_git_commit=source_git_commit,
        )

    def get_pages_for_incident(self, incident_id: str) -> List[WikiPage]:
        return [self._pages[pid] for pid in self._by_incident.get(incident_id, []) if pid in self._pages]

    def search(self, query: str) -> List[WikiPage]:
        q = query.lower()
        return [p for p in self._pages.values() if q in p.title.lower() or q in p.content.lower()]


# ---------------------------------------------------------------------------
# Incident Command Center
# ---------------------------------------------------------------------------


@dataclass
class ICCIncident:
    icc_id: str = field(default_factory=lambda: f"icc-{uuid.uuid4().hex[:8]}")
    incident_id: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    severity: str = ""
    status: str = "open"
    owner: str = ""
    stakeholders: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    related_risk_ids: List[str] = field(default_factory=list)
    related_run_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "icc_id": self.icc_id,
            "incident_id": self.incident_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "owner": self.owner,
            "stakeholders": self.stakeholders,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "related_risk_ids": self.related_risk_ids,
            "related_run_ids": self.related_run_ids,
        }


class IncidentCommandCenter:
    """
    Centro de comando unificado que coordina StackStorm, Wiki.js y UC-075.
    """

    def __init__(
        self,
        stackstorm: Optional[StackStormAdapter] = None,
        wikijs: Optional[WikiJsAdapter] = None,
        observability: Optional[Any] = None,
    ) -> None:
        self.stackstorm = stackstorm or StackStormAdapter()
        self.wikijs = wikijs or WikiJsAdapter()
        self.observability = observability
        self._incidents: Dict[str, ICCIncident] = {}

    def report_incident(
        self,
        incident_id: str,
        title: str,
        description: str,
        category: str,
        severity: str,
        owner: str = "",
        stakeholders: Optional[List[str]] = None,
        related_risk_ids: Optional[List[str]] = None,
        related_run_ids: Optional[List[str]] = None,
    ) -> ICCIncident:
        inc = ICCIncident(
            incident_id=incident_id,
            title=title,
            description=description,
            category=category,
            severity=severity,
            owner=owner,
            stakeholders=stakeholders or [],
            related_risk_ids=related_risk_ids or [],
            related_run_ids=related_run_ids or [],
        )
        self._incidents[inc.icc_id] = inc
        self.wikijs.create_page(
            page_type=IncidentPageType.INCIDENT,
            title=f"Incidente {incident_id}: {title}",
            content=f"{description}\n\nCategoría: {category}\nSeveridad: {severity}\nOwner: {owner}",
            incident_id=incident_id,
            tags=["incident", category, severity],
        )
        if self.observability:
            self.observability.record_icc_incident_reported(
                category=category, severity=severity
            )
        return inc

    def update_status(self, icc_id: str, status: str) -> Optional[ICCIncident]:
        inc = self._incidents.get(icc_id)
        if not inc:
            return None
        inc.status = status
        inc.updated_at = time.time()
        return inc

    def submit_action(
        self,
        incident_id: str,
        action: str,
        params: Dict[str, Any],
        approval_ref: str,
        scope: str = ApprovalScope.AUTO.value,
        requested_by: str = "uc075-icc",
    ) -> StackStormAction:
        """Somete una acción a StackStorm. Ejecuta inmediatamente si está autorizada."""
        st2_action = self.stackstorm.submit(
            action=action,
            params=params,
            incident_id=incident_id,
            approval_ref=approval_ref,
            scope=scope,
            requested_by=requested_by,
        )
        # Auto-ejecutar acciones de bajo riesgo con approval_ref válido.
        if action in self.stackstorm.auto_allowlist:
            self.stackstorm.execute(st2_action.action_id)
        return st2_action

    def execute_approved_action(self, action_id: str) -> StackStormAction:
        return self.stackstorm.execute(action_id)

    def rollback_action(self, action_id: str) -> StackStormAction:
        return self.stackstorm.rollback(action_id)

    def create_postmortem(
        self,
        incident_id: str,
        title: str,
        findings: List[str],
        action_items: List[str],
        participants: List[str],
    ) -> WikiPage:
        page = self.wikijs.create_postmortem(
            incident_id, title, findings, action_items, participants
        )
        if self.observability:
            self.observability.record_icc_postmortem_created(incident_id)
        return page

    def sync_runbook(
        self,
        category: str,
        actions: List[str],
        version: str,
        source_git_commit: str = "",
    ) -> WikiPage:
        page = self.wikijs.create_runbook_page(category, actions, version, source_git_commit)
        if self.observability:
            self.observability.record_icc_runbook_sync(category, version)
        return page

    def unified_view(self, incident_id: str) -> Dict[str, Any]:
        """Vista unificada: incidente + acciones + wiki + riesgos + runs."""
        incidents = [inc for inc in self._incidents.values() if inc.incident_id == incident_id]
        incident = incidents[0].to_dict() if incidents else None
        actions = [a.to_dict() for a in self.stackstorm.list_actions(incident_id=incident_id)]
        wiki_pages = [p.to_dict() for p in self.wikijs.get_pages_for_incident(incident_id)]
        return {
            "incident": incident,
            "actions": actions,
            "wiki_pages": wiki_pages,
            "source": "uc075-incident-command-center",
            "generated_at": time.time(),
        }

    def status_board(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for inc in self._incidents.values():
            by_status[inc.status] = by_status.get(inc.status, 0) + 1
            by_severity[inc.severity] = by_severity.get(inc.severity, 0) + 1
        return {
            "total_incidents": len(self._incidents),
            "by_status": by_status,
            "by_severity": by_severity,
            "pending_actions": len([
                a for a in self.stackstorm._actions.values()
                if a.status == ActionStatus.PENDING
            ]),
            "executed_actions": len([
                a for a in self.stackstorm._actions.values()
                if a.status == ActionStatus.EXECUTED
            ]),
            "wiki_pages": len(self.wikijs._pages),
        }
