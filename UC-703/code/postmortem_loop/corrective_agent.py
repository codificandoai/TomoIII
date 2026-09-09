"""Agente de propuesta de acciones correctivas (sin autoridad de ejecución)."""
from __future__ import annotations

from typing import List

from postmortem_loop.models_pm import CorrectiveProposal, IncidentRecord, RootCauseHypothesis


class CorrectiveAgent:
    """
    Genera propuestas de código/guardrails como evidencia para revisión humana.
    No aplica cambios directamente.
    """

    def propose(
        self,
        record: IncidentRecord,
        hypothesis: RootCauseHypothesis,
    ) -> List[CorrectiveProposal]:
        proposals: List[CorrectiveProposal] = []

        if hypothesis.taxonomy == "prompt_injection":
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="guardrail_rule",
                target="input_filter",
                patch='{"rule": "reject if prompt contains ignore/jailbreak override patterns"}',
                rationale="Block prompt injection attempts before LLM call",
            ))
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="prompt_patch",
                target="system_prompt",
                patch="Add explicit instruction that retrieved documents are evidence, not instructions.",
                rationale="Reduce susceptibility to embedded instructions",
            ))
        elif hypothesis.taxonomy == "hallucination":
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="prompt_patch",
                target="system_prompt",
                patch="Require citations to retrieved documents; abstain if no source.",
                rationale="Reduce unsupported factual claims",
            ))
        elif hypothesis.taxonomy == "bad_rag":
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="tool_fix",
                target="retriever",
                patch="Increase top-k retrieval and add reranker filter.",
                rationale="Improve source relevance",
            ))
        elif hypothesis.taxonomy == "tool_bug":
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="tool_fix",
                target="external_tool",
                patch="Add retry with exponential backoff and schema validation.",
                rationale="Reduce transient tool failures",
            ))
        elif hypothesis.taxonomy == "model_regression":
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="prompt_patch",
                target="model_selection",
                patch="Rollback to previous model version until retrained LoRA is validated.",
                rationale="Stabilize quality while fix is validated",
            ))
        else:
            proposals.append(CorrectiveProposal(
                record_id=record.record_id,
                hypothesis_id=hypothesis.hypothesis_id,
                action_type="prompt_patch",
                target="system_prompt",
                patch="Add logging and HITL escalation for this taxonomy.",
                rationale="Generic containment until root cause confirmed",
            ))

        return proposals
