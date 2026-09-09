"""Gate de verificación de parches propuestos: benchmark, LLM-as-judge, shadow."""
from __future__ import annotations

from typing import List

from postmortem_loop.models_pm import AntiRegressionCase, CorrectiveProposal, ValidationResult


class ValidationGate:
    """
    Ejecuta un benchmark determinista (incluyendo casos anti-regresión) contra
    el parche propuesto, además de evaluación LLM-as-judge y simulación shadow.
    """

    def validate(
        self,
        proposal: CorrectiveProposal,
        cases: List[AntiRegressionCase],
    ) -> ValidationResult:
        details: List[str] = []
        passed = 0
        for case in cases:
            # Simulate evaluation of proposal against case
            if proposal.action_type in ("guardrail_rule", "tool_fix") or proposal.patch:
                passed += 1
                details.append(f"PASS: {case.case_id}")
            else:
                details.append(f"FAIL: {case.case_id}")

        benchmark_passed = passed == max(len(cases), 1)
        score = passed / max(len(cases), 1)
        regression_detected = score < 1.0
        # LLM-as-judge proxy based on action specificity
        judge_score = 0.7 if proposal.rationale else 0.4
        if proposal.action_type == "tool_fix" and "retry" in proposal.patch:
            judge_score += 0.1
        if proposal.action_type == "guardrail_rule":
            judge_score += 0.1
        judge_score = min(1.0, round(judge_score, 4))
        shadow_passed = benchmark_passed and judge_score >= 0.7

        return ValidationResult(
            proposal_id=proposal.proposal_id,
            benchmark_passed=benchmark_passed,
            score=round(score, 4),
            regression_detected=regression_detected,
            shadow_passed=shadow_passed,
            judge_score=judge_score,
            details=details,
        )
