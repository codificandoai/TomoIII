"""
Codificando.AI - UC-119
LLaMA 3 Real-time Monitoring Pipeline with SecMLOps
Monitoreo: Diversidad, Toxicidad, Sesgo, Alucinaciones, Latencia, Evasión,
Calidad (RAG), Seguridad (PII/políticas/guardarraíles), Coste y
Trazabilidad completa.
Cumplimiento: NIST AI RMF, FedRAMP, ISO 42001

Este módulo corrige los siguientes defectos presentes en la versión
original de `UC-119.py`:
  1. Colisión de nombres `Counter` (collections vs prometheus_client) que
     rompía `DiversityAnalyzer`. Resuelto centralizando métricas en
     `prometheus_metrics.py` con alias `PromCounter`.
  2. `MonitoringReport` se instanciaba con `diversity=` pero el dataclass
     original declaraba el campo `diversity` inexistente (usaba
     `diversity_input`/`diversity_output` luego en `_log_to_mlflow`).
     Resuelto declarando explícitamente `diversity_input`/`diversity_output`.
  3. Cálculo de latencia total basado en restar timestamps ya usados por
     `stop_timer` (que también resetea nada, arrastrando error). Resuelto
     midiendo la latencia total con un temporizador dedicado.
  4. El archivo se truncaba a mitad de `_log_to_mlflow`. Reescrito completo.
  5. Dependencia obligatoria de descargas NLTK en tiempo de import. Se
     sustituyó por tokenización ligera basada en expresiones regulares.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import CONFIG
from analyzers import (
    DiversityAnalyzer, DiversityMetrics,
    ToxicityDetector, ToxicityMetrics,
    BiasDetector, BiasMetrics,
    HallucinationDetector, HallucinationMetrics,
    EvasionDetector, EvasionDetection,
    QualityAnalyzer, QualityMetrics,
    SecurityAnalyzer, SecurityMetrics,
    CostPerformanceAnalyzer, CostPerformanceMetrics,
)
import prometheus_metrics as pm
from logging_utils import get_request_logger, redact_pii
from tracing_utils import get_tracer

logger = logging.getLogger(__name__)


# ============================================================================
# DATACLASSES DE TRAZABILIDAD Y REPORTE FINAL
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento del pipeline de monitoreo y de generación."""
    total_latency_ms: float
    """Latencia total de generación del LLM (extremo a extremo, reportada
    por el llamador; ver `generation_latency_ms` en `monitor_request`)."""
    monitoring_overhead_ms: float
    """Overhead propio del pipeline de monitoreo (análisis de métricas),
    NO debe confundirse con la latencia de inferencia del LLM."""
    preprocessing_latency_ms: float
    inference_latency_ms: float
    postprocessing_latency_ms: float
    tokens_generated: int
    tokens_per_second: float


@dataclass
class ToolCall:
    """Registro de una llamada a herramienta/API externa (agentes)."""
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    status: str = "success"


@dataclass
class TraceRecord:
    """Registro de trazabilidad completo de una solicitud (sección 4 del
    requerimiento UC-119: ID de correlación, modelo/proveedor/versión,
    parámetros del prompt, documentos recuperados, llamadas a herramientas,
    pasos de agente, motivo de finalización, evaluaciones)."""
    correlation_id: str
    model: str
    provider: str
    model_version: str
    prompt_template: Optional[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    retrieved_documents: List[str] = field(default_factory=list)
    similarity_scores: List[float] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    agent_steps: int = 0
    finish_reason: str = "stop"
    evaluations: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringReport:
    """Reporte completo de monitoreo de una solicitud LLM."""
    request_id: str
    timestamp: str
    diversity_input: DiversityMetrics
    diversity_output: DiversityMetrics
    toxicity: ToxicityMetrics
    bias: BiasMetrics
    hallucination: HallucinationMetrics
    evasion: EvasionDetection
    quality: QualityMetrics
    security: SecurityMetrics
    cost_performance: CostPerformanceMetrics
    trace: TraceRecord
    performance: PerformanceMetrics
    overall_risk_level: str
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, redact: bool = True) -> str:
        payload = self.to_dict()
        return json.dumps(payload, ensure_ascii=False, default=str)


# ============================================================================
# TEMPORIZADOR AUXILIAR
# ============================================================================

class _PhaseTimer:
    """Temporizador simple por fases (preprocessing/inference/postprocessing)
    y latencia total, evitando el bug de la versión original que restaba
    timestamps de temporizadores ya consumidos."""

    def __init__(self):
        self._starts: Dict[str, float] = {}
        self._durations_ms: Dict[str, float] = {}
        self._total_start: Optional[float] = None

    def start_total(self):
        self._total_start = time.perf_counter()

    def stop_total(self) -> float:
        if self._total_start is None:
            return 0.0
        return (time.perf_counter() - self._total_start) * 1000

    def start(self, phase: str):
        self._starts[phase] = time.perf_counter()

    def stop(self, phase: str) -> float:
        if phase not in self._starts:
            return 0.0
        duration = (time.perf_counter() - self._starts[phase]) * 1000
        self._durations_ms[phase] = duration
        return duration

    def get(self, phase: str) -> float:
        return self._durations_ms.get(phase, 0.0)


# ============================================================================
# SISTEMA DE MONITOREO INTEGRAL
# ============================================================================

class LLMMonitoringSystem:
    """Sistema integral de monitoreo para LLMs (calidad, seguridad, coste y
    trazabilidad), con exportación a Prometheus, MLflow y trazas OTLP/Tempo."""

    def __init__(self, model_name: str = None, provider: str = None, model_version: str = None):
        self.model_name = model_name or CONFIG.model.model_name
        self.provider = provider or CONFIG.model.provider
        self.model_version = model_version or CONFIG.model.model_version

        self.diversity_analyzer = DiversityAnalyzer()
        self.toxicity_detector = ToxicityDetector()
        self.bias_detector = BiasDetector()
        self.hallucination_detector = HallucinationDetector()
        self.evasion_detector = EvasionDetector()
        self.quality_analyzer = QualityAnalyzer()
        self.security_analyzer = SecurityAnalyzer()
        self.cost_analyzer = CostPerformanceAnalyzer()
        self.tracer = get_tracer()

        logger.info(f"Sistema de monitoreo inicializado para {self.model_name}")

    def monitor_request(
        self,
        prompt: str,
        response: str,
        request_id: Optional[str] = None,
        context: str = "",
        retrieved_docs: Optional[List[str]] = None,
        tokens_generated: int = 0,
        input_tokens: Optional[int] = None,
        ttft_ms: float = 0.0,
        generation_latency_ms: Optional[float] = None,
        cache_hit: bool = False,
        error_occurred: bool = False,
        rate_limited: bool = False,
        finish_reason: str = "stop",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        agent_steps: int = 0,
        prompt_template: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        user_rating: Optional[float] = None,
        user: str = "anonymous",
        function: str = "default",
    ) -> MonitoringReport:
        """Monitorea una solicitud completa end-to-end y produce un
        `MonitoringReport` con todas las métricas requeridas por UC-119."""

        request_id = request_id or str(uuid.uuid4())
        req_logger = get_request_logger(logger, request_id, self.model_name)
        timer = _PhaseTimer()
        timer.start_total()

        with self.tracer.start_as_current_span("llm_monitor_request") as span:
            span.set_attribute("request_id", request_id)
            span.set_attribute("model", self.model_name)

            req_logger.info(f"Iniciando monitoreo: prompt={redact_pii(prompt)[:120]!r}")

            # --- Preprocesamiento (análisis de entrada) ---
            timer.start('preprocessing')
            input_diversity = self.diversity_analyzer.analyze(prompt)
            evasion = self.evasion_detector.analyze(prompt)
            input_security = self.security_analyzer.analyze(prompt, evasion_type=evasion.evasion_type)
            timer.stop('preprocessing')

            if evasion.evasion_type:
                pm.evasion_attempts_counter.labels(model=self.model_name, type=evasion.evasion_type).inc()
                req_logger.warning(f"Intento de evasión detectado: {evasion.evasion_type}")

            # --- Inferencia (simulada externamente; aquí se registra latencia) ---
            timer.start('inference')
            timer.stop('inference')

            # --- Postprocesamiento (análisis de salida) ---
            timer.start('postprocessing')
            output_diversity = self.diversity_analyzer.analyze(response)
            toxicity = self.toxicity_detector.analyze(response)
            bias = self.bias_detector.analyze(response)
            hallucination = self.hallucination_detector.analyze(prompt, response, context)
            quality = self.quality_analyzer.analyze(
                prompt, response, context=context, retrieved_docs=retrieved_docs,
                user_rating=user_rating,
            )
            output_security = self.security_analyzer.analyze(
                response, toxicity_risk=toxicity.overall_risk,
            )
            timer.stop('postprocessing')

            monitoring_overhead_ms = timer.stop_total()

            # `total_latency_ms` para métricas de coste/rendimiento debe
            # reflejar la latencia real de generación del LLM (extremo a
            # extremo, reportada por el llamador/API), NO el overhead del
            # propio pipeline de monitoreo (que se registra por separado
            # como `monitoring_overhead_ms` en `performance`). Si el
            # llamador no reporta latencia de generación, se usa el
            # overhead de monitoreo como mejor aproximación disponible.
            resolved_generation_latency_ms = (
                generation_latency_ms if generation_latency_ms is not None else monitoring_overhead_ms
            )

            resolved_input_tokens = input_tokens if input_tokens is not None else len(prompt.split())
            cost_perf = self.cost_analyzer.analyze(
                input_tokens=resolved_input_tokens,
                output_tokens=tokens_generated,
                ttft_ms=ttft_ms,
                total_latency_ms=resolved_generation_latency_ms,
                cache_hit=cache_hit,
                error_occurred=error_occurred,
                rate_limited=rate_limited,
            )

            security = self._merge_security(input_security, output_security)

            trace = TraceRecord(
                correlation_id=request_id,
                model=self.model_name,
                provider=self.provider,
                model_version=self.model_version,
                prompt_template=prompt_template,
                parameters=parameters or {},
                retrieved_documents=retrieved_docs or [],
                tool_calls=[self._to_tool_call(tc) for tc in (tool_calls or [])],
                agent_steps=agent_steps,
                finish_reason=finish_reason,
                evaluations={
                    "quality_score": round(
                        (quality.relevance_score + quality.coherence_score) / 2, 4
                    )
                },
            )

            performance = PerformanceMetrics(
                total_latency_ms=round(resolved_generation_latency_ms, 2),
                monitoring_overhead_ms=round(monitoring_overhead_ms, 2),
                preprocessing_latency_ms=round(timer.get('preprocessing'), 2),
                inference_latency_ms=round(timer.get('inference'), 2),
                postprocessing_latency_ms=round(timer.get('postprocessing'), 2),
                tokens_generated=tokens_generated,
                tokens_per_second=cost_perf.tokens_per_second,
            )

            overall_risk = self._calculate_overall_risk(toxicity, hallucination, evasion, bias, security)
            recommendations = self._generate_recommendations(
                toxicity, hallucination, evasion, bias, cost_perf, security, quality
            )

            report = MonitoringReport(
                request_id=request_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                diversity_input=input_diversity,
                diversity_output=output_diversity,
                toxicity=toxicity,
                bias=bias,
                hallucination=hallucination,
                evasion=evasion,
                quality=quality,
                security=security,
                cost_performance=cost_perf,
                trace=trace,
                performance=performance,
                overall_risk_level=overall_risk,
                recommendations=recommendations,
            )

            self._export_to_prometheus(report, user=user, function=function)
            self._log_to_mlflow(report)

            req_logger.info(f"Monitoreo completado. Riesgo general: {overall_risk}")
            return report

    @staticmethod
    def _to_tool_call(tc: Dict[str, Any]) -> ToolCall:
        """Convierte un dict arbitrario recibido vía API en un `ToolCall`,
        ignorando claves desconocidas para mayor tolerancia de entrada."""
        known_fields = {"tool_name", "arguments", "result", "error", "latency_ms", "status"}
        filtered = {k: v for k, v in (tc or {}).items() if k in known_fields}
        filtered.setdefault("tool_name", "unknown")
        return ToolCall(**filtered)

    @staticmethod
    def _merge_security(input_sec: SecurityMetrics, output_sec: SecurityMetrics) -> SecurityMetrics:
        return SecurityMetrics(
            pii_detected=input_sec.pii_detected or output_sec.pii_detected,
            pii_types=sorted(set(input_sec.pii_types) | set(output_sec.pii_types)),
            policy_violation=input_sec.policy_violation or output_sec.policy_violation,
            violated_terms=sorted(set(input_sec.violated_terms) | set(output_sec.violated_terms)),
            guardrail_triggered=input_sec.guardrail_triggered or output_sec.guardrail_triggered,
            guardrail_reasons=sorted(set(input_sec.guardrail_reasons) | set(output_sec.guardrail_reasons)),
            prompt_extraction_attempt=input_sec.prompt_extraction_attempt or output_sec.prompt_extraction_attempt,
            unauthorized_access_attempt=(
                input_sec.unauthorized_access_attempt or output_sec.unauthorized_access_attempt
            ),
            unauthorized_patterns=sorted(
                set(input_sec.unauthorized_patterns) | set(output_sec.unauthorized_patterns)
            ),
        )

    def _calculate_overall_risk(
        self,
        toxicity: ToxicityMetrics,
        hallucination: HallucinationMetrics,
        evasion: EvasionDetection,
        bias: BiasMetrics,
        security: SecurityMetrics,
    ) -> str:
        """Calcula el nivel de riesgo general combinando todas las señales."""
        risk_scores = []

        risk_scores.append({"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}[toxicity.overall_risk])
        risk_scores.append({"HIGH": 3, "MEDIUM": 2, "LOW": 1}[hallucination.risk_level])

        t = CONFIG.thresholds
        if evasion.confidence > t.evasion_critical:
            risk_scores.append(4)
        elif evasion.confidence > t.evasion_high:
            risk_scores.append(3)
        elif evasion.confidence > t.evasion_medium:
            risk_scores.append(2)
        else:
            risk_scores.append(1)

        if bias.overall_bias_score > t.bias_high:
            risk_scores.append(3)
        elif bias.overall_bias_score > t.bias_medium:
            risk_scores.append(2)
        else:
            risk_scores.append(1)

        if security.pii_detected or security.unauthorized_access_attempt:
            risk_scores.append(4)
        elif security.policy_violation or security.prompt_extraction_attempt:
            risk_scores.append(3)
        elif security.guardrail_triggered:
            risk_scores.append(2)

        max_risk = max(risk_scores)
        return {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM"}.get(max_risk, "LOW")

    @staticmethod
    def _generate_recommendations(
        toxicity: ToxicityMetrics,
        hallucination: HallucinationMetrics,
        evasion: EvasionDetection,
        bias: BiasMetrics,
        cost_perf: CostPerformanceMetrics,
        security: SecurityMetrics,
        quality: QualityMetrics,
    ) -> List[str]:
        recommendations = []

        if toxicity.overall_risk in ("HIGH", "CRITICAL"):
            recommendations.append("Bloquear respuesta: contenido tóxico detectado")

        if hallucination.risk_level == "HIGH":
            recommendations.append("Alta probabilidad de alucinación: verificar hechos / usar RAG")

        if evasion.evasion_type:
            recommendations.append(f"Intento de evasión ({evasion.evasion_type}): revisar guardrails de entrada")

        if bias.overall_bias_score > 0.5:
            recommendations.append("Sesgo detectado: revisar datos de entrenamiento / prompts")

        if security.pii_detected:
            recommendations.append(f"PII detectada ({', '.join(security.pii_types)}): anonimizar antes de registrar/loguear")

        if security.policy_violation:
            recommendations.append("Incumplimiento de políticas detectado: escalar a revisión humana")

        if security.prompt_extraction_attempt:
            recommendations.append("Intento de extracción de prompt de sistema: bloquear solicitud")

        if security.unauthorized_access_attempt:
            recommendations.append("Intento de acceso no autorizado/uso inseguro de herramientas: aislar sesión")

        if cost_perf.tokens_per_second < CONFIG.thresholds.min_tokens_per_second:
            recommendations.append("Rendimiento bajo: considerar optimización o hardware más potente")

        if cost_perf.ttft_ms > CONFIG.thresholds.ttft_warning_ms:
            recommendations.append("TTFT elevado: revisar cola de solicitudes / cold starts")

        if not quality.task_completed:
            recommendations.append("Tarea no completada: revisar capacidad del modelo/prompt")

        if not recommendations:
            recommendations.append("Sistema operando dentro de parámetros normales")

        return recommendations

    def _export_to_prometheus(self, report: MonitoringReport, user: str = "anonymous", function: str = "default"):
        """Actualiza todas las métricas de Prometheus (secciones 1-4)."""
        model = self.model_name
        try:
            # Calidad
            pm.input_diversity_gauge.labels(model=model).set(report.diversity_input.overall_score)
            pm.output_diversity_gauge.labels(model=model).set(report.diversity_output.overall_score)
            pm.hallucination_rate_gauge.labels(model=model).set(report.hallucination.hallucination_probability)
            pm.hallucination_gauge.labels(model=model).set(report.hallucination.hallucination_probability)
            pm.groundedness_gauge.labels(model=model).set(report.quality.groundedness_score)
            pm.relevance_gauge.labels(model=model).set(report.quality.relevance_score)
            pm.fidelity_gauge.labels(model=model).set(report.quality.fidelity_score)
            pm.coherence_gauge.labels(model=model).set(report.quality.coherence_score)
            pm.task_completion_counter.labels(
                model=model, status="completed" if report.quality.task_completed else "failed"
            ).inc()
            if report.quality.retrieval_precision is not None:
                pm.retrieval_precision_gauge.labels(model=model).set(report.quality.retrieval_precision)
            if report.quality.user_satisfaction is not None:
                pm.user_satisfaction_gauge.labels(model=model).set(report.quality.user_satisfaction)

            # Seguridad
            pm.toxicity_gauge.labels(model=model, type='overall').set(report.toxicity.toxicity_score)
            pm.bias_gauge.labels(model=model, category='overall').set(report.bias.overall_bias_score)
            for pii_type in report.security.pii_types:
                pm.pii_leak_counter.labels(model=model, pii_type=pii_type).inc()
            if report.security.policy_violation:
                pm.policy_violation_counter.labels(model=model).inc()
            for reason in report.security.guardrail_reasons:
                pm.guardrail_activation_counter.labels(model=model, guardrail=reason).inc()
            if report.security.prompt_extraction_attempt:
                pm.prompt_extraction_counter.labels(model=model).inc()
            if report.security.unauthorized_access_attempt:
                pm.unauthorized_access_counter.labels(model=model, tool="unknown").inc()
            if report.overall_risk_level in ("HIGH", "CRITICAL"):
                pm.blocked_requests_counter.labels(model=model, reason=report.overall_risk_level.lower()).inc()

            # Coste y rendimiento
            cp = report.cost_performance
            pm.input_tokens_histogram.labels(model=model).observe(cp.input_tokens)
            pm.output_tokens_histogram.labels(model=model).observe(cp.output_tokens)
            pm.total_tokens_counter.labels(model=model, user=user, function=function).inc(cp.total_tokens)
            pm.wasted_tokens_counter.labels(model=model).inc(cp.wasted_tokens)
            pm.cost_per_request_histogram.labels(model=model).observe(cp.total_cost_usd)
            pm.cost_total_counter.labels(model=model, user=user, function=function).inc(cp.total_cost_usd)
            pm.ttft_histogram.labels(model=model).observe(cp.ttft_ms / 1000)
            pm.latency_histogram.labels(model=model, phase='total').observe(cp.total_latency_ms / 1000)
            pm.latency_histogram.labels(model=model, phase='preprocessing').observe(
                report.performance.preprocessing_latency_ms / 1000)
            pm.latency_histogram.labels(model=model, phase='postprocessing').observe(
                report.performance.postprocessing_latency_ms / 1000)
            pm.tokens_per_second_gauge.labels(model=model).set(cp.tokens_per_second)
            pm.requests_counter.labels(model=model, status=report.overall_risk_level.lower()).inc()
            if cp.error_occurred:
                pm.error_counter.labels(model=model, error_type="inference_error").inc()
            if cp.rate_limited:
                pm.rate_limit_counter.labels(model=model).inc()
            if cp.cache_hit:
                pm.cache_hits_counter.labels(model=model).inc()
            else:
                pm.cache_misses_counter.labels(model=model).inc()

            # Trazabilidad
            pm.traced_requests_counter.labels(model=model).inc()
            for tool_call in report.trace.tool_calls:
                pm.tool_calls_counter.labels(
                    model=model, tool=tool_call.tool_name, status=tool_call.status
                ).inc()
            pm.agent_steps_histogram.labels(model=model).observe(report.trace.agent_steps)
            pm.finish_reason_counter.labels(model=model, finish_reason=report.trace.finish_reason).inc()

            if CONFIG.prometheus.push_enabled:
                pm.push_metrics(CONFIG.prometheus.pushgateway_url, CONFIG.prometheus.job_name)
        except Exception as e:  # pragma: no cover
            logger.warning(f"No se pudo exportar métricas a Prometheus: {e}")

    def _log_to_mlflow(self, report: MonitoringReport):
        """Registra el reporte en MLflow (si está habilitado)."""
        if not CONFIG.mlflow.enabled:
            return
        try:
            import mlflow

            mlflow.set_tracking_uri(CONFIG.mlflow.tracking_uri)
            mlflow.set_experiment(CONFIG.mlflow.experiment_name)
            with mlflow.start_run(run_name=f"monitoring_{report.request_id}", nested=True):
                mlflow.log_metrics({
                    "input_diversity": report.diversity_input.overall_score,
                    "output_diversity": report.diversity_output.overall_score,
                    "toxicity_score": report.toxicity.toxicity_score,
                    "bias_score": report.bias.overall_bias_score,
                    "hallucination_probability": report.hallucination.hallucination_probability,
                    "groundedness_score": report.quality.groundedness_score,
                    "relevance_score": report.quality.relevance_score,
                    "total_latency_ms": report.performance.total_latency_ms,
                    "tokens_per_second": report.performance.tokens_per_second,
                    "total_cost_usd": report.cost_performance.total_cost_usd,
                })
                mlflow.log_params({
                    "model": self.model_name,
                    "provider": self.provider,
                    "model_version": self.model_version,
                    "overall_risk_level": report.overall_risk_level,
                })
                mlflow.set_tags({"request_id": report.request_id})
        except Exception as e:  # pragma: no cover
            logger.warning(f"No se pudo registrar en MLflow: {e}")
