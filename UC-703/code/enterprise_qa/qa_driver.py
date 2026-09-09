"""Enterprise QA Driver: valida KPIs por pilar y genera banderas de control.

Este módulo está diseñado para ejecutarse en un pipeline CI/CD y bloquear
promociones cuando se enciendan banderas RED. Es determinista y no requiere
LLMs externos para los evaluadores básicos.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from enterprise_qa.models_qa import ControlFlag, EscalationAction, KPIResult, Pillar, QAReport, TestCase


class EnterpriseQADriver:
    """
    Valora respuestas de LLM contra tres pilares empresariales:
    - Lógica de Negocio (Contexto)
    - Lenguaje Específico del Dominio
    - Lógica de Procesos Propios

    Más controles transversales de cumplimiento (PII/términos prohibidos).
    """

    PILLAR_KPI = {
        Pillar.BUSINESS_LOGIC: "KPI 1.1 Rule Adherence Rate",
        Pillar.DOMAIN_LANGUAGE: "KPI 2.1 Keyword Hit Rate",
        Pillar.PROCESS_LOGIC: "KPI 3.1 Step Sequence F1",
        Pillar.COMPLIANCE: "KPI 0.0 Compliance / Safety",
    }

    def __init__(
        self,
        tolerance_yellow: float = 0.10,
        tolerance_red: float = 0.0,
    ) -> None:
        self.tolerance_yellow = tolerance_yellow
        self.tolerance_red = tolerance_red
        self._results: List[KPIResult] = []
        self._escalations: List[EscalationAction] = []

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower())

    def _evaluate_keywords(self, text: str, keywords: Sequence[str]) -> float:
        if not keywords:
            return 1.0
        text_lower = self._normalize(text)
        found = sum(1 for kw in keywords if self._normalize(kw) in text_lower)
        return found / len(keywords)

    def _check_forbidden(self, text: str, forbidden: Sequence[str]) -> Optional[str]:
        text_lower = self._normalize(text)
        for fw in forbidden:
            if self._normalize(fw) in text_lower:
                return fw
        return None

    def _evaluate_process_sequence(self, text: str, required_sequence: Sequence[str]) -> float:
        if not required_sequence:
            return 1.0
        text_lower = self._normalize(text)
        last_index = -1
        for step in required_sequence:
            idx = text_lower.find(self._normalize(step))
            if idx == -1 or idx <= last_index:
                return 0.0
            last_index = idx
        return 1.0

    def run_test(self, test_case: TestCase) -> None:
        response = test_case.llm_response

        # 0. Hard compliance check (PII, forbidden terms, safety)
        forbidden_hit = self._check_forbidden(response, test_case.forbidden_keywords)
        if forbidden_hit is not None:
            self._results.append(KPIResult(
                test_id=test_case.id,
                pillar=Pillar.COMPLIANCE,
                kpi_name=self.PILLAR_KPI[Pillar.COMPLIANCE],
                score=0.0,
                flag=ControlFlag.RED.value,
                details=f"Forbidden/PII term detected: '{forbidden_hit}'",
            ))
            return

        # Pillar-specific evaluation
        pillar = Pillar(test_case.pillar) if test_case.pillar in {p.value for p in Pillar} else Pillar.BUSINESS_LOGIC
        if pillar == Pillar.BUSINESS_LOGIC:
            score = self._evaluate_keywords(response, test_case.expected_keywords)
            kpi_name = self.PILLAR_KPI[Pillar.BUSINESS_LOGIC]
            details = f"Rule keywords matched: {score*100:.1f}%"
        elif pillar == Pillar.DOMAIN_LANGUAGE:
            score = self._evaluate_keywords(response, test_case.expected_keywords)
            kpi_name = self.PILLAR_KPI[Pillar.DOMAIN_LANGUAGE]
            details = f"Domain terms matched: {score*100:.1f}%"
        elif pillar == Pillar.PROCESS_LOGIC:
            seq = test_case.required_sequence or test_case.expected_keywords
            score = self._evaluate_process_sequence(response, seq)
            kpi_name = self.PILLAR_KPI[Pillar.PROCESS_LOGIC]
            details = f"Process sequence followed: {score*100:.1f}%"
        else:
            score = 1.0
            kpi_name = self.PILLAR_KPI[pillar]
            details = "N/A"

        flag = self._flag_for_score(score)
        self._results.append(KPIResult(
            test_id=test_case.id,
            pillar=pillar.value,
            kpi_name=kpi_name,
            score=round(score, 4),
            flag=flag.value,
            details=details,
        ))

    def _flag_for_score(self, score: float) -> ControlFlag:
        if score <= self.tolerance_red:
            return ControlFlag.RED
        if score < (1.0 - self.tolerance_yellow):
            return ControlFlag.YELLOW
        return ControlFlag.GREEN

    def evaluate_global_gate(self) -> ControlFlag:
        if any(r.flag == ControlFlag.RED.value for r in self._results):
            return ControlFlag.RED
        if any(r.flag == ControlFlag.YELLOW.value for r in self._results):
            return ControlFlag.YELLOW
        return ControlFlag.GREEN

    def _escalation_for_flag(self, flag: ControlFlag) -> EscalationAction:
        if flag == ControlFlag.RED:
            return EscalationAction(
                flag=flag.value,
                action="BLOCK_DEPLOY_AND_TRIGGER_ROLLBACK",
                owner="QA / Security / DevOps",
                description=(
                    "Pipeline blocked. Immediate rollback to last stable version. "
                    "Manual review required before re-deployment."
                ),
            )
        if flag == ControlFlag.YELLOW:
            return EscalationAction(
                flag=flag.value,
                action="ALLOW_DEPLOY_AND_LOG_MLOPS_TICKET",
                owner="MLOps / Data",
                description=(
                    "Deployment allowed with warnings. Create follow-up ticket to "
                    "collect targeted examples and address drift in next cycle."
                ),
            )
        return EscalationAction(
            flag=flag.value,
            action="PROCEED_TO_CANARY_DEPLOYMENT",
            owner="Release / DevOps",
            description="All KPIs within thresholds. Proceed to canary rollout.",
        )

    def generate_report(self) -> QAReport:
        global_flag = self.evaluate_global_gate()
        action = self._escalation_for_flag(global_flag)
        self._escalations = [action]
        return QAReport(
            global_status=global_flag.value,
            action=action.action,
            total_tests=len(self._results),
            red_flags=sum(1 for r in self._results if r.flag == ControlFlag.RED.value),
            yellow_flags=sum(1 for r in self._results if r.flag == ControlFlag.YELLOW.value),
            green_flags=sum(1 for r in self._results if r.flag == ControlFlag.GREEN.value),
            results=list(self._results),
            escalations=list(self._escalations),
        )

    def run_batch(self, cases: Sequence[TestCase]) -> QAReport:
        for case in cases:
            self.run_test(case)
        return self.generate_report()

    def reset(self) -> None:
        self._results.clear()
        self._escalations.clear()


def load_test_cases(path: str) -> List[TestCase]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TestCase(**item) for item in data]


def save_report(report: QAReport, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Enterprise QA Gate for LLMOps")
    parser.add_argument("--input", required=True, help="JSON file with test cases")
    parser.add_argument("--output", default="qa_report.json", help="Output report path")
    parser.add_argument(
        "--tolerance-yellow",
        type=float,
        default=0.10,
        help="Score drop allowed before YELLOW flag (default 0.10)",
    )
    parser.add_argument(
        "--tolerance-red",
        type=float,
        default=0.0,
        help="Score threshold for RED flag (default 0.0)",
    )
    args = parser.parse_args(argv)

    cases = load_test_cases(args.input)
    driver = EnterpriseQADriver(
        tolerance_yellow=args.tolerance_yellow,
        tolerance_red=args.tolerance_red,
    )
    report = driver.run_batch(cases)
    save_report(report, args.output)

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    if report.global_status == ControlFlag.RED.value:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
