"""UC-119 — LLM ROI Analyzer.

Calcula el retorno de inversión (ROI) de modelos LLM empresariales
alineando métricas técnicas con KPIs de negocio. Permite justificar
actualizaciones de modelo, realizar post-mortems de implementaciones
y comunicar valor a stakeholders.

Funcionalidades:
1. ROI por modelo/caso de uso (costo vs. valor generado).
2. KPIs de negocio alineados con actualizaciones de modelo.
3. Reportes para stakeholders con métricas claras.
4. Post-mortems de ROI por implementación.
5. Justificación de futuras inversiones o reajuste de iniciativas.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class InvestmentStatus(str, Enum):
    JUSTIFIED = "justified"
    MARGINAL = "marginal"
    NOT_JUSTIFIED = "not_justified"
    PENDING = "pending"


class BusinessKPI(str, Enum):
    USER_SATISFACTION = "user_satisfaction"
    RESOLUTION_TIME = "resolution_time"
    RESOLUTION_COST = "resolution_cost"
    AUTOMATION_RATE = "automation_rate"
    TASKS_AUTOMATED = "tasks_automated"
    ERROR_REDUCTION = "error_reduction"
    THROUGHPUT = "throughput"
    REVENUE_IMPACT = "revenue_impact"


@dataclass
class ModelUsageRecord:
    """Registro de uso de un modelo LLM con métricas de coste y valor."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    model_version: str = ""
    use_case: str = "default"
    provider: str = ""

    # Costos
    cost_usd: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0.0

    # Valor / KPIs de negocio
    user_satisfaction: float = 0.0       # 0-1
    resolution_time_sec: float = 0.0     # tiempo de resolución
    automated: bool = False              # tarea automatizada
    error_occurred: bool = False
    revenue_generated_usd: float = 0.0   # valor económico directo

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "model_version": self.model_version,
            "use_case": self.use_case,
            "provider": self.provider,
            "cost_usd": self.cost_usd,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "latency_ms": self.latency_ms,
            "user_satisfaction": self.user_satisfaction,
            "resolution_time_sec": self.resolution_time_sec,
            "automated": self.automated,
            "error_occurred": self.error_occurred,
            "revenue_generated_usd": self.revenue_generated_usd,
        }


@dataclass
class ROIResult:
    """Resultado del cálculo de ROI para un modelo/caso de uso."""
    model: str
    model_version: str
    use_case: str
    period_start: float
    period_end: float

    # Métricas financieras
    total_cost_usd: float = 0.0
    total_revenue_usd: float = 0.0
    net_value_usd: float = 0.0
    roi_percentage: float = 0.0
    cost_per_request: float = 0.0
    revenue_per_request: float = 0.0

    # KPIs de negocio
    avg_user_satisfaction: float = 0.0
    avg_resolution_time_sec: float = 0.0
    automation_rate: float = 0.0
    tasks_automated: int = 0
    error_rate: float = 0.0
    total_requests: int = 0

    # Evaluación
    status: InvestmentStatus = InvestmentStatus.PENDING
    justification: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "model_version": self.model_version,
            "use_case": self.use_case,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_revenue_usd": round(self.total_revenue_usd, 4),
            "net_value_usd": round(self.net_value_usd, 4),
            "roi_percentage": round(self.roi_percentage, 2),
            "cost_per_request": round(self.cost_per_request, 6),
            "revenue_per_request": round(self.revenue_per_request, 6),
            "avg_user_satisfaction": round(self.avg_user_satisfaction, 4),
            "avg_resolution_time_sec": round(self.avg_resolution_time_sec, 2),
            "automation_rate": round(self.automation_rate, 4),
            "tasks_automated": self.tasks_automated,
            "error_rate": round(self.error_rate, 4),
            "total_requests": self.total_requests,
            "status": self.status.value,
            "justification": self.justification,
        }


@dataclass
class ModelUpdateJustification:
    """Justificación de una actualización de modelo basada en ROI."""
    justification_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    from_version: str = ""
    to_version: str = ""
    use_case: str = ""

    # Comparación
    roi_before: float = 0.0
    roi_after: float = 0.0
    roi_delta: float = 0.0

    # KPIs
    satisfaction_delta: float = 0.0
    resolution_time_delta: float = 0.0
    cost_delta: float = 0.0
    automation_delta: float = 0.0

    # Evaluación
    status: InvestmentStatus = InvestmentStatus.PENDING
    reasoning: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "justification_id": self.justification_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "use_case": self.use_case,
            "roi_before": round(self.roi_before, 2),
            "roi_after": round(self.roi_after, 2),
            "roi_delta": round(self.roi_delta, 2),
            "satisfaction_delta": round(self.satisfaction_delta, 4),
            "resolution_time_delta": round(self.resolution_time_delta, 2),
            "cost_delta": round(self.cost_delta, 6),
            "automation_delta": round(self.automation_delta, 4),
            "status": self.status.value,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
        }


@dataclass
class ImplementationPostMortem:
    """Post-mortem de ROI de una implementación de modelo."""
    postmortem_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    model_version: str = ""
    use_case: str = ""

    # Resultados
    roi_result: Optional[Dict[str, Any]] = None
    expected_roi: float = 0.0
    actual_roi: float = 0.0
    roi_gap: float = 0.0

    # Análisis
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Decisión
    continue_investment: bool = False
    adjust_initiative: bool = False
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "postmortem_id": self.postmortem_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "model_version": self.model_version,
            "use_case": self.use_case,
            "roi_result": self.roi_result,
            "expected_roi": round(self.expected_roi, 2),
            "actual_roi": round(self.actual_roi, 2),
            "roi_gap": round(self.roi_gap, 2),
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "lessons_learned": self.lessons_learned,
            "recommendations": self.recommendations,
            "continue_investment": self.continue_investment,
            "adjust_initiative": self.adjust_initiative,
            "reasoning": self.reasoning,
        }


class LLMROIAnalyzer:
    """Analizador de ROI para modelos LLM empresariales."""

    def __init__(
        self,
        roi_justified_threshold: float = 50.0,
        roi_marginal_threshold: float = 0.0,
        satisfaction_weight: float = 0.3,
        automation_weight: float = 0.3,
        resolution_time_weight: float = 0.2,
        error_reduction_weight: float = 0.2,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.roi_justified_threshold = roi_justified_threshold
        self.roi_marginal_threshold = roi_marginal_threshold
        self.weights = {
            BusinessKPI.USER_SATISFACTION: satisfaction_weight,
            BusinessKPI.AUTOMATION_RATE: automation_weight,
            BusinessKPI.RESOLUTION_TIME: resolution_time_weight,
            BusinessKPI.ERROR_REDUCTION: error_reduction_weight,
        }
        self.event_sink = event_sink
        self._records: List[ModelUsageRecord] = []
        self._justifications: List[ModelUpdateJustification] = []
        self._postmortems: List[ImplementationPostMortem] = []

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink({"event_type": event_type, "timestamp": time.time(), **payload})
            except Exception:
                pass

    def record_usage(self, record: ModelUsageRecord) -> None:
        """Registra un evento de uso de modelo."""
        self._records.append(record)
        self._emit("roi_usage_recorded", record.to_dict())

    def calculate_roi(
        self,
        model: str,
        use_case: str = "default",
        model_version: str = "",
        period_start: Optional[float] = None,
        period_end: Optional[float] = None,
    ) -> ROIResult:
        """Calcula ROI para un modelo/caso de uso en un período."""
        records = [
            r for r in self._records
            if r.model == model
            and r.use_case == use_case
            and (not model_version or r.model_version == model_version)
            and (period_start is None or r.timestamp >= period_start)
            and (period_end is None or r.timestamp <= period_end)
        ]

        if not records:
            return ROIResult(
                model=model,
                model_version=model_version,
                use_case=use_case,
                period_start=period_start or 0.0,
                period_end=period_end or time.time(),
                status=InvestmentStatus.PENDING,
                justification="No data available for this model/use_case/period.",
            )

        total_cost = sum(r.cost_usd for r in records)
        total_revenue = sum(r.revenue_generated_usd for r in records)
        net_value = total_revenue - total_cost
        roi_pct = (net_value / total_cost * 100.0) if total_cost > 0 else 0.0

        total_requests = len(records)
        avg_satisfaction = sum(r.user_satisfaction for r in records) / total_requests
        avg_resolution = sum(r.resolution_time_sec for r in records) / total_requests
        automated_count = sum(1 for r in records if r.automated)
        automation_rate = automated_count / total_requests
        error_count = sum(1 for r in records if r.error_occurred)
        error_rate = error_count / total_requests

        # Determinar status
        if roi_pct >= self.roi_justified_threshold:
            status = InvestmentStatus.JUSTIFIED
            justification = (
                f"ROI {roi_pct:.1f}% supera el umbral {self.roi_justified_threshold}%. "
                f"Valor neto ${net_value:.2f}. Satisfacción {avg_satisfaction:.2f}. "
                f"Automatización {automation_rate:.1%}."
            )
        elif roi_pct >= self.roi_marginal_threshold:
            status = InvestmentStatus.MARGINAL
            justification = (
                f"ROI {roi_pct:.1f}% es marginal (umbral {self.roi_marginal_threshold}%-{self.roi_justified_threshold}%). "
                f"Revisar KPIs antes de continuar invirtiendo."
            )
        else:
            status = InvestmentStatus.NOT_JUSTIFIED
            justification = (
                f"ROI {roi_pct:.1f}% por debajo del umbral mínimo {self.roi_marginal_threshold}%. "
                f"Reajustar iniciativa o descontinuar."
            )

        result = ROIResult(
            model=model,
            model_version=model_version or records[0].model_version,
            use_case=use_case,
            period_start=period_start or records[0].timestamp,
            period_end=period_end or records[-1].timestamp,
            total_cost_usd=total_cost,
            total_revenue_usd=total_revenue,
            net_value_usd=net_value,
            roi_percentage=roi_pct,
            cost_per_request=total_cost / total_requests,
            revenue_per_request=total_revenue / total_requests,
            avg_user_satisfaction=avg_satisfaction,
            avg_resolution_time_sec=avg_resolution,
            automation_rate=automation_rate,
            tasks_automated=automated_count,
            error_rate=error_rate,
            total_requests=total_requests,
            status=status,
            justification=justification,
        )

        self._emit("roi_calculated", result.to_dict())
        return result

    def justify_update(
        self,
        model: str,
        from_version: str,
        to_version: str,
        use_case: str,
        roi_before: ROIResult,
        roi_after: ROIResult,
    ) -> ModelUpdateJustification:
        """Justifica una actualización de modelo comparando ROI antes/después."""
        delta = roi_after.roi_percentage - roi_before.roi_percentage

        justification = ModelUpdateJustification(
            model=model,
            from_version=from_version,
            to_version=to_version,
            use_case=use_case,
            roi_before=roi_before.roi_percentage,
            roi_after=roi_after.roi_percentage,
            roi_delta=delta,
            satisfaction_delta=roi_after.avg_user_satisfaction - roi_before.avg_user_satisfaction,
            resolution_time_delta=roi_after.avg_resolution_time_sec - roi_before.avg_resolution_time_sec,
            cost_delta=roi_after.cost_per_request - roi_before.cost_per_request,
            automation_delta=roi_after.automation_rate - roi_before.automation_rate,
            evidence={
                "before": roi_before.to_dict(),
                "after": roi_after.to_dict(),
            },
        )

        # Evaluar si la actualización está justificada
        improvements = []
        if delta > 0:
            improvements.append(f"ROI mejoró {delta:.1f}%")
        if justification.satisfaction_delta > 0:
            improvements.append(f"satisfacción +{justification.satisfaction_delta:.2f}")
        if justification.resolution_time_delta < 0:
            improvements.append(f"resolución {-justification.resolution_time_delta:.1f}s más rápida")
        if justification.automation_delta > 0:
            improvements.append(f"automatización +{justification.automation_delta:.1%}")
        if justification.cost_delta < 0:
            improvements.append(f"costo {-justification.cost_delta:.4f} menor por request")

        if delta >= self.roi_justified_threshold * 0.2 or len(improvements) >= 2:
            justification.status = InvestmentStatus.JUSTIFIED
            justification.reasoning = (
                f"Actualización justificada: {'; '.join(improvements)}. "
                f"ROI {roi_before.roi_percentage:.1f}% → {roi_after.roi_percentage:.1f}%."
            )
        elif delta >= 0:
            justification.status = InvestmentStatus.MARGINAL
            justification.reasoning = (
                f"Actualización marginal: {'; '.join(improvements) or 'sin mejoras significativas'}. "
                f"Revisar antes de continuar."
            )
        else:
            justification.status = InvestmentStatus.NOT_JUSTIFIED
            justification.reasoning = (
                f"Actualización no justificada: ROI disminuyó {abs(delta):.1f}%. "
                f"Revertir o reajustar."
            )

        self._justifications.append(justification)
        self._emit("roi_update_justified", justification.to_dict())
        return justification

    def postmortem(
        self,
        model: str,
        model_version: str,
        use_case: str,
        expected_roi: float,
        roi_result: ROIResult,
        what_worked: Optional[List[str]] = None,
        what_failed: Optional[List[str]] = None,
        lessons_learned: Optional[List[str]] = None,
    ) -> ImplementationPostMortem:
        """Realiza un post-mortem de ROI de una implementación."""
        actual_roi = roi_result.roi_percentage
        gap = actual_roi - expected_roi

        pm = ImplementationPostMortem(
            model=model,
            model_version=model_version,
            use_case=use_case,
            roi_result=roi_result.to_dict(),
            expected_roi=expected_roi,
            actual_roi=actual_roi,
            roi_gap=gap,
            what_worked=what_worked or [],
            what_failed=what_failed or [],
            lessons_learned=lessons_learned or [],
        )

        # Generar recomendaciones automáticas
        if gap >= 0:
            pm.continue_investment = True
            pm.recommendations.append(
                f"ROI superó expectativas ({actual_roi:.1f}% vs {expected_roi:.1f}%). "
                f"Continuar invirtiendo en esta iniciativa."
            )
        elif gap >= -10:
            pm.continue_investment = True
            pm.adjust_initiative = True
            pm.recommendations.append(
                f"ROI cercano a expectativas (gap {gap:.1f}%). Ajustar parámetros "
                f"y reevaluar en próximo ciclo."
            )
        else:
            pm.continue_investment = False
            pm.adjust_initiative = True
            pm.recommendations.append(
                f"ROI muy por debajo de expectativas (gap {gap:.1f}%). "
                f"Reconsiderar o descontinuar la iniciativa."
            )

        if roi_result.error_rate > 0.1:
            pm.recommendations.append(
                f"Tasa de error alta ({roi_result.error_rate:.1%}). "
                f"Priorizar estabilidad antes de escalar."
            )

        if roi_result.avg_user_satisfaction < 0.6:
            pm.recommendations.append(
                f"Satisfacción baja ({roi_result.avg_user_satisfaction:.2f}). "
                f"Mejorar calidad del modelo o prompt engineering."
            )

        pm.reasoning = "; ".join(pm.recommendations)

        self._postmortems.append(pm)
        self._emit("roi_postmortem_completed", pm.to_dict())
        return pm

    def stakeholder_report(
        self,
        model: str,
        use_case: str = "default",
        model_version: str = "",
    ) -> Dict[str, Any]:
        """Genera un reporte ejecutivo para stakeholders."""
        roi = self.calculate_roi(model, use_case, model_version)

        # KPIs técnicos
        technical_kpis = {
            "total_requests": roi.total_requests,
            "cost_per_request_usd": round(roi.cost_per_request, 6),
            "avg_latency_ms": 0.0,  # se llena si hay records
            "error_rate": round(roi.error_rate, 4),
        }

        records = [r for r in self._records if r.model == model and r.use_case == use_case]
        if records:
            technical_kpis["avg_latency_ms"] = round(
                sum(r.latency_ms for r in records) / len(records), 2
            )
            technical_kpis["avg_tokens_per_request"] = round(
                sum(r.tokens_input + r.tokens_output for r in records) / len(records), 1
            )

        # KPIs de negocio
        business_kpis = {
            "roi_percentage": round(roi.roi_percentage, 2),
            "net_value_usd": round(roi.net_value_usd, 2),
            "total_cost_usd": round(roi.total_cost_usd, 2),
            "total_revenue_usd": round(roi.total_revenue_usd, 2),
            "avg_user_satisfaction": round(roi.avg_user_satisfaction, 4),
            "avg_resolution_time_sec": round(roi.avg_resolution_time_sec, 2),
            "automation_rate": round(roi.automation_rate, 4),
            "tasks_automated": roi.tasks_automated,
        }

        # Resumen ejecutivo
        if roi.status == InvestmentStatus.JUSTIFIED:
            summary = (
                f"El modelo {model} ({use_case}) genera ROI positivo de "
                f"{roi.roi_percentage:.1f}%. La inversión está justificada."
            )
        elif roi.status == InvestmentStatus.MARGINAL:
            summary = (
                f"El modelo {model} ({use_case}) tiene ROI marginal de "
                f"{roi.roi_percentage:.1f}%. Revisar antes de continuar."
            )
        elif roi.status == InvestmentStatus.NOT_JUSTIFIED:
            summary = (
                f"El modelo {model} ({use_case}) no genera ROI suficiente "
                f"({roi.roi_percentage:.1f}%). Reajustar o descontinuar."
            )
        else:
            summary = f"Datos insuficientes para evaluar ROI de {model} ({use_case})."

        return {
            "report_id": str(uuid.uuid4())[:12],
            "timestamp": time.time(),
            "model": model,
            "model_version": model_version,
            "use_case": use_case,
            "executive_summary": summary,
            "investment_status": roi.status.value,
            "justification": roi.justification,
            "business_kpis": business_kpis,
            "technical_kpis": technical_kpis,
            "recommendations": self._generate_recommendations(roi),
        }

    def _generate_recommendations(self, roi: ROIResult) -> List[str]:
        """Genera recomendaciones automáticas basadas en ROI."""
        recs = []
        if roi.roi_percentage >= self.roi_justified_threshold:
            recs.append("Continuar invirtiendo: ROI supera el umbral de justificación.")
        if roi.avg_user_satisfaction < 0.6:
            recs.append("Mejorar satisfacción del usuario mediante prompt engineering o fine-tuning.")
        if roi.error_rate > 0.1:
            recs.append("Reducir tasa de errores: revisar estabilidad del modelo.")
        if roi.automation_rate < 0.3:
            recs.append("Aumentar automatización de tareas para escalar valor.")
        if roi.cost_per_request > 0.05:
            recs.append("Optimizar costos: considerar cuantización o modelo más eficiente.")
        if roi.avg_resolution_time_sec > 30:
            recs.append("Reducir tiempo de resolución: optimizar latencia de inferencia.")
        return recs

    def get_justifications(self) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._justifications]

    def get_postmortems(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._postmortems]

    def get_records(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records]

    def export_prometheus_metrics(self) -> str:
        """Exporta métricas de ROI en formato Prometheus text."""
        lines = []
        for model_use in set((r.model, r.use_case) for r in self._records):
            model, use_case = model_use
            roi = self.calculate_roi(model, use_case)
            labels = f'model="{model}",use_case="{use_case}"'
            lines.append(f'llm_roi_percentage{{{labels}}} {roi.roi_percentage}')
            lines.append(f'llm_roi_net_value_usd{{{labels}}} {roi.net_value_usd}')
            lines.append(f'llm_roi_total_cost_usd{{{labels}}} {roi.total_cost_usd}')
            lines.append(f'llm_roi_total_revenue_usd{{{labels}}} {roi.total_revenue_usd}')
            lines.append(f'llm_roi_avg_satisfaction{{{labels}}} {roi.avg_user_satisfaction}')
            lines.append(f'llm_roi_automation_rate{{{labels}}} {roi.automation_rate}')
            lines.append(f'llm_roi_error_rate{{{labels}}} {roi.error_rate}')
            lines.append(f'llm_roi_total_requests{{{labels}}} {roi.total_requests}')
        return "\n".join(lines) + "\n"
