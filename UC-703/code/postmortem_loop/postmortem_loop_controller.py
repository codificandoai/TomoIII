"""Controller del bucle de post-mortem autónomo para LLMOps."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from postmortem_loop.anti_regression_synthesizer import AntiRegressionSynthesizer
from postmortem_loop.context_freezer import ContextFreezer
from postmortem_loop.corrective_agent import CorrectiveAgent
from postmortem_loop.documentation_agent import DocumentationAgent
from postmortem_loop.models_pm import (
    AntiRegressionCase,
    CorrectiveProposal,
    IncidentRecord,
    PostMortemReport,
    RootCauseHypothesis,
    RunbookUpdate,
    ValidationResult,
)
from postmortem_loop.risk_gate import RiskGate
from postmortem_loop.root_cause_agent import RootCauseAgent
from postmortem_loop.validation_gate import ValidationGate


class PostMortemLoopController:
    """
    Orquesta el pipeline de post-mortem autónomo:
    congelar contexto -> análisis de causa raíz -> gate de riesgo/HITL ->
    propuestas correctivas -> casos anti-regresión -> validación ->
    documentación/runbook.
    """

    def __init__(
        self,
        freezer: Optional[ContextFreezer] = None,
        root_cause_agent: Optional[RootCauseAgent] = None,
        risk_gate: Optional[RiskGate] = None,
        corrective_agent: Optional[CorrectiveAgent] = None,
        synthesizer: Optional[AntiRegressionSynthesizer] = None,
        validator: Optional[ValidationGate] = None,
        doc_agent: Optional[DocumentationAgent] = None,
    ) -> None:
        self.freezer = freezer or ContextFreezer()
        self.root_cause_agent = root_cause_agent or RootCauseAgent()
        self.risk_gate = risk_gate or RiskGate()
        self.corrective_agent = corrective_agent or CorrectiveAgent()
        self.synthesizer = synthesizer or AntiRegressionSynthesizer()
        self.validator = validator or ValidationGate()
        self.doc_agent = doc_agent or DocumentationAgent()
        self._proposals: Dict[str, CorrectiveProposal] = {}
        self._validations: List[ValidationResult] = []

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------
    def freeze_incident(self, data: Dict[str, Any]) -> IncidentRecord:
        return self.freezer.freeze(**data)

    def analyze(self, record_id: str) -> Optional[Dict[str, Any]]:
        record = self.freezer.get(record_id)
        if not record:
            return None
        hypotheses = self.root_cause_agent.analyze(record)
        return {
            "record": record.to_dict(),
            "hypotheses": [h.to_dict() for h in hypotheses],
        }

    def run_postmortem(
        self,
        record_id: str,
        approver: str = "",
        auto_approve_low_risk: bool = True,
    ) -> Optional[Dict[str, Any]]:
        record = self.freezer.get(record_id)
        if not record:
            return None

        hypotheses = self.root_cause_agent.analyze(record)
        if not hypotheses:
            return None
        top_hypothesis = hypotheses[0]

        gate_result = self.risk_gate.decision(record.severity, top_hypothesis, approver=approver)
        if not gate_result["approved"]:
            return {
                "record_id": record_id,
                "status": "awaiting_human_review",
                "hypothesis": top_hypothesis.to_dict(),
                "reason": gate_result["reason"],
            }

        proposals = self.corrective_agent.propose(record, top_hypothesis)
        for p in proposals:
            self._proposals[p.proposal_id] = p

        anti_regression_cases = self.synthesizer.synthesize(record, top_hypothesis, count=3)

        validations = []
        for p in proposals:
            validation = self.validator.validate(p, anti_regression_cases)
            self._validations.append(validation)
            validations.append(validation)

        report = self.doc_agent.generate_report(record, top_hypothesis, proposals)
        runbook_update = self.doc_agent.update_runbook(record, top_hypothesis)

        return {
            "record_id": record_id,
            "status": "completed",
            "human_approval": gate_result.get("human_approval", False),
            "hypothesis": top_hypothesis.to_dict(),
            "proposals": [p.to_dict() for p in proposals],
            "anti_regression_cases": [c.to_dict() for c in anti_regression_cases],
            "validations": [v.to_dict() for v in validations],
            "report": report.to_dict(),
            "runbook_update": runbook_update.to_dict(),
        }

    # ------------------------------------------------------------------
    # HITL helpers
    # ------------------------------------------------------------------
    def approve_hypothesis(self, hypothesis_id: str, approver: str, notes: str = "") -> Optional[RootCauseHypothesis]:
        # Find hypothesis across records (simplified: no stored dict of hypotheses, so search)
        for record in self.freezer.list_records().values():
            for h in self.root_cause_agent.analyze(record):
                if h.hypothesis_id == hypothesis_id:
                    h.approved = True
                    h.approver = approver
                    h.notes = notes
                    return h
        return None

    def approve_proposal(self, proposal_id: str, approver: str) -> Optional[CorrectiveProposal]:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        proposal.status = "approved"
        proposal.approver = approver
        return proposal

    def reject_proposal(self, proposal_id: str, approver: str) -> Optional[CorrectiveProposal]:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        proposal.status = "rejected"
        proposal.approver = approver
        return proposal

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    def dashboard(self) -> Dict[str, Any]:
        return {
            "incident_records": len(self.freezer.list_records()),
            "proposals": len(self._proposals),
            "validations": len(self._validations),
            "runbooks": self.doc_agent.list_runbook_versions(),
            "validated_proposals": sum(1 for v in self._validations if v.shadow_passed),
        }
