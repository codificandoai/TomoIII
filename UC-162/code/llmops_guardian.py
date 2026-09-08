"""
UC-162 — Guardian LLMOps.

Orquestador principal que integra:
1. Modelado lógico de datos (esquema con constraints de sesgo).
2. Verificación de sesgo (demográfico, perspectiva, temporal, fuente, lenguaje).
3. Linaje semántico (grafo de transformaciones).
4. Detección de hallucination (coherencia de outputs del LLM).
5. Versionado de prompts (aprobación, evaluación).
6. Detección de drift conceptual (significado vs distribución).

Flujo:
  Diseño lógico (LLMOps) → UC-087 (integridad criptográfica) →
  Modelo entrenado → LLMOps evalúa sesgo y drift conceptual →
  Solo si ambas capas aprueban → UC-315 recibe conocimiento validado.
"""

import time
import uuid
from typing import Dict, List, Optional, Any

from models_162 import (
    LLMOpsConfig,
    CorpusDocument,
    DocumentMetadata,
    LLMOpsResult,
    LLMOpsDecision,
    BiasAction,
)
from logical_data_model import LogicalSchema, compute_hash
from bias_verifier import BiasVerifier
from lineage_tracker import LineageTracker
from hallucination_detector import HallucinationDetector
from prompt_versioning import PromptRegistry
from conceptual_drift_detector import ConceptualDriftDetector
from observability_162 import ObservabilityManager


class LLMOpsGuardian:
    """
    Guardian LLMOps: valida que los datos están conceptualmente bien
    estructurados y son libres de sesgo antes de alimentar UC-315.
    """

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.config = config or LLMOpsConfig()
        self.schema = LogicalSchema(config=self.config)
        self.bias_verifier = BiasVerifier(config=self.config)
        self.lineage_tracker = LineageTracker()
        self.hallucination_detector = HallucinationDetector(config=self.config)
        self.prompt_registry = PromptRegistry(config=self.config)
        self.drift_detector = ConceptualDriftDetector(config=self.config)
        self.observability = ObservabilityManager(
            component=self.config.component,
            pipeline=self.config.pipeline,
        )
        self._init_metrics()

    def _init_metrics(self):
        """Inicializa métricas Prometheus."""
        self.observability.gauge("llmops_bias_checks_total", 0)
        self.observability.gauge("llmops_bias_rejections_total", 0)
        self.observability.gauge("llmops_hallucination_detected_total", 0)
        self.observability.gauge("llmops_drift_detected_total", 0)
        self.observability.gauge("llmops_lineage_nodes_total", 0)
        self.observability.gauge("llmops_prompts_approved_total", 0)
        self.observability.gauge("llmops_guardian_duration_ms", 0)
        self.observability.gauge("llmops_last_coverage_score", 0)
        self.observability.gauge("llmops_last_drift_score", 0)

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    def process_corpus(
        self,
        documents: List[CorpusDocument],
        source: str = "unknown",
    ) -> LLMOpsResult:
        """
        Procesa un corpus completo: verifica sesgo, registra linaje,
        y emite una decisión LLMOps.
        """
        start = time.time()
        result = LLMOpsResult()
        trace_id = result.trace_id

        span = self.observability.start_span("process_corpus", trace_id)

        # 1. Validar estructura lógica
        structure_issues = []
        for doc in documents:
            issues = self.schema.validate_structure(doc)
            structure_issues.extend(issues)
        if structure_issues:
            result.issues.extend(structure_issues[:5])
            self.observability.log(
                "WARN",
                f"Estructura lógica inválida: {len(structure_issues)} issues",
                trace_id,
            )

        # 2. Verificar sesgo
        bias_span = self.observability.start_span("bias_verification", trace_id)
        bias_report = self.bias_verifier.verify(documents)
        self.observability.end_span(bias_span)
        result.bias_report = bias_report.to_dict()
        self.observability.increment("llmops_bias_checks_total")
        if not bias_report.all_passed:
            self.observability.increment("llmops_bias_rejections_total")
            for action in bias_report.actions:
                if action == BiasAction.REJECT.value:
                    result.issues.append("Sesgo crítico: lote rechazado")
                elif action == BiasAction.FLAG.value:
                    result.issues.append("Sesgo detectado: requiere revisión")
                elif action == BiasAction.ENRICH.value:
                    result.issues.append(
                        "Sesgo por falta de representación: enriquecer corpus"
                    )
        self.observability.log(
            "INFO" if bias_report.all_passed else "WARN",
            f"Verificación de sesgo: {'PASS' if bias_report.all_passed else 'FAIL'}",
            trace_id,
            {"actions": bias_report.actions, "metrics": bias_report.metrics},
        )

        # 3. Registrar linaje de ingesta
        for doc in documents:
            self.lineage_tracker.register_ingest(
                document_id=doc.id,
                text=doc.text,
                source=source,
            )
        result.lineage_graph = self.lineage_tracker.get_full_lineage()
        self.observability.gauge(
            "llmops_lineage_nodes_total", len(self.lineage_tracker.graph.nodes)
        )

        # 4. Decisión
        if not bias_report.all_passed and BiasAction.REJECT.value in bias_report.actions:
            result.decision = LLMOpsDecision.REJECT.value
        elif not bias_report.all_passed:
            result.decision = LLMOpsDecision.FLAG.value
        elif structure_issues:
            result.decision = LLMOpsDecision.FLAG.value
        else:
            result.decision = LLMOpsDecision.APPROVE.value

        # 5. Duración
        result.duration_ms = round((time.time() - start) * 1000, 2)
        self.observability.gauge("llmops_guardian_duration_ms", result.duration_ms)
        self.observability.end_span(span)

        self.observability.log(
            "INFO",
            f"Corpus procesado: decision={result.decision}",
            trace_id,
            {"duration_ms": result.duration_ms, "doc_count": len(documents)},
        )

        return result

    def evaluate_response(
        self,
        response: str,
        retrieved_chunks: List[str],
        prompt_version: str = "",
        model: str = "",
        trace_id: str = "",
    ) -> LLMOpsResult:
        """
        Evalúa una respuesta del LLM: detecta hallucination y
        registra linaje de generación.
        """
        start = time.time()
        result = LLMOpsResult()
        if trace_id:
            result.trace_id = trace_id

        span = self.observability.start_span("evaluate_response", result.trace_id)

        # 1. Detectar hallucination
        halluc_report = self.hallucination_detector.detect(
            response=response,
            retrieved_chunks=retrieved_chunks,
            trace_id=result.trace_id,
        )
        result.hallucination_report = halluc_report.to_dict()
        self.observability.gauge(
            "llmops_last_coverage_score", halluc_report.coverage_score
        )
        if halluc_report.is_hallucination:
            self.observability.increment("llmops_hallucination_detected_total")
            result.issues.append(
                f"Hallucination detectada: severidad={halluc_report.severity}"
            )

        # 2. Registrar linaje de generación
        if retrieved_chunks:
            parent_hash = compute_hash({"chunks": retrieved_chunks})
            self.lineage_tracker.register_generation(
                response=response,
                parent_hash=parent_hash,
                prompt_version=prompt_version,
                model=model,
            )
            result.lineage_graph = self.lineage_tracker.get_full_lineage()

        # 3. Decisión
        if halluc_report.is_hallucination and halluc_report.severity in (
            "high", "critical",
        ):
            result.decision = LLMOpsDecision.REJECT.value
        elif halluc_report.is_hallucination:
            result.decision = LLMOpsDecision.FLAG.value
        else:
            result.decision = LLMOpsDecision.APPROVE.value

        result.duration_ms = round((time.time() - start) * 1000, 2)
        self.observability.gauge("llmops_guardian_duration_ms", result.duration_ms)
        self.observability.end_span(span)

        self.observability.log(
            "INFO" if result.decision == "approve" else "WARN",
            f"Respuesta evaluada: decision={result.decision}, severity={halluc_report.severity}",
            result.trace_id,
            {"coverage": halluc_report.coverage_score},
        )

        return result

    def check_drift(
        self,
        concept_name: str,
        current_contexts: List[str],
        current_co_occurrences: List[List[str]] = None,
        trace_id: str = "",
    ) -> LLMOpsResult:
        """
        Verifica drift conceptual para un concepto.
        """
        start = time.time()
        result = LLMOpsResult()
        if trace_id:
            result.trace_id = trace_id

        drift_report = self.drift_detector.detect(
            concept_name=concept_name,
            current_contexts=current_contexts,
            current_co_occurrences=current_co_occurrences,
            trace_id=result.trace_id,
        )
        result.drift_report = drift_report.to_dict()
        self.observability.gauge(
            "llmops_last_drift_score", drift_report.drift_score
        )
        if drift_report.is_drift:
            self.observability.increment("llmops_drift_detected_total")
            result.issues.append(
                f"Drift conceptual detectado: tipo={drift_report.drift_type}, "
                f"score={drift_report.drift_score}"
            )
            result.decision = LLMOpsDecision.ESCALATE.value
        else:
            result.decision = LLMOpsDecision.APPROVE.value

        result.duration_ms = round((time.time() - start) * 1000, 2)
        self.observability.log(
            "INFO" if not drift_report.is_drift else "WARN",
            f"Drift check: {concept_name} → {result.decision}",
            result.trace_id,
            {"drift_score": drift_report.drift_score},
        )
        return result

    def set_baseline(
        self,
        concept_name: str,
        contexts: List[str],
        co_occurrences: List[List[str]] = None,
    ):
        """Establece un baseline conceptual para drift detection."""
        self.drift_detector.set_baseline(
            concept_name, contexts, co_occurrences
        )
        self.observability.log(
            "INFO",
            f"Baseline conceptual establecido: {concept_name}",
            "",
            {"sample_count": len(contexts)},
        )

    # ------------------------------------------------------------------
    # Prompt versioning
    # ------------------------------------------------------------------

    def register_prompt(
        self,
        template: str,
        version: str = "",
        tags: List[str] = None,
    ) -> Dict[str, Any]:
        prompt = self.prompt_registry.register(template, version, tags)
        self.observability.log(
            "INFO",
            f"Prompt registrado: {prompt.version}",
            "",
            {"prompt_id": prompt.id},
        )
        return prompt.to_dict()

    def approve_prompt(
        self,
        prompt_id: str,
        approved_by: str = "compliance_officer",
    ) -> Optional[Dict[str, Any]]:
        prompt = self.prompt_registry.approve(prompt_id, approved_by)
        if prompt:
            self.observability.increment("llmops_prompts_approved_total")
            self.observability.log(
                "INFO",
                f"Prompt aprobado: {prompt.version} por {approved_by}",
                "",
            )
            return prompt.to_dict()
        return None

    def evaluate_prompt(
        self,
        prompt_id: str,
        score: float,
    ) -> Optional[Dict[str, Any]]:
        prompt = self.prompt_registry.evaluate(prompt_id, score)
        if prompt:
            return prompt.to_dict()
        return None

    # ------------------------------------------------------------------
    # Estado y métricas
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "schema": self.schema.to_dict(),
            "lineage_nodes": len(self.lineage_tracker.graph.nodes),
            "prompts_registered": len(self.prompt_registry.prompts),
            "prompts_approved": len(self.prompt_registry.get_approved()),
            "baselines": list(self.drift_detector.baselines.keys()),
            "observability": self.observability.get_summary(),
        }

    def get_metrics(self) -> str:
        return self.observability.export_prometheus()

    def reset(self, config: Optional[LLMOpsConfig] = None):
        if config:
            self.config = config
        self.schema = LogicalSchema(config=self.config)
        self.bias_verifier = BiasVerifier(config=self.config)
        self.lineage_tracker = LineageTracker()
        self.hallucination_detector = HallucinationDetector(config=self.config)
        self.prompt_registry = PromptRegistry(config=self.config)
        self.drift_detector = ConceptualDriftDetector(config=self.config)
        self.observability.reset()
        self._init_metrics()
