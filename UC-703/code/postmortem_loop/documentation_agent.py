"""Agente de documentación: genera informe post-mortem y actualiza runbooks."""
from __future__ import annotations

from typing import List

from postmortem_loop.models_pm import (
    CorrectiveProposal,
    IncidentRecord,
    PostMortemReport,
    RootCauseHypothesis,
    RunbookUpdate,
)


class DocumentationAgent:
    """
    Produce informe post-mortem estructurado y propone actualizaciones al
    runbook correspondiente.
    """

    def __init__(self) -> None:
        self._runbooks: dict = {}

    def generate_report(
        self,
        record: IncidentRecord,
        hypothesis: RootCauseHypothesis,
        proposals: List[CorrectiveProposal],
    ) -> PostMortemReport:
        timeline = [
            f"Incident detected at {record.timestamp}",
            f"Root cause hypothesis: {hypothesis.taxonomy} (confidence {hypothesis.confidence})",
            f"Corrective proposals generated: {len(proposals)}",
        ]
        return PostMortemReport(
            record_id=record.record_id,
            timeline=timeline,
            root_cause=hypothesis.summary,
            impact=f"Affected domain: {record.metadata.get('business_domain', 'unknown')}; severity: {record.severity}",
            lessons=f"Strengthen {hypothesis.taxonomy} controls and add anti-regression cases.",
            corrective_proposals=[p.proposal_id for p in proposals],
        )

    def update_runbook(
        self,
        record: IncidentRecord,
        hypothesis: RootCauseHypothesis,
    ) -> RunbookUpdate:
        runbook_id = f"rb-{hypothesis.taxonomy}"
        changes = (
            f"Updated {hypothesis.taxonomy} runbook with incident {record.record_id}. "
            f"Added detection rule for {record.category}."
        )
        update = RunbookUpdate(
            record_id=record.record_id,
            runbook_id=runbook_id,
            changes=changes,
            version=self._bump_version(runbook_id),
        )
        self._runbooks[runbook_id] = update.version
        return update

    def _bump_version(self, runbook_id: str) -> str:
        current = self._runbooks.get(runbook_id, "1.0.0")
        major, minor, patch = current.split(".")
        return f"{major}.{minor}.{int(patch) + 1}"

    def list_runbook_versions(self) -> dict:
        return dict(self._runbooks)
