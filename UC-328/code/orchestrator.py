"""
UC-328 — Motor ORQUESTA-R (Orquestador Resiliente con Gestión de Sobrecarga).

Orquesta búsquedas externas a gran escala para RAG empresarial, gestionando:
- Latencia y costo de búsquedas externas.
- Silos de datos y fragmentación.
- Alineación de esquemas heterogéneos.
- Conocimiento ambiguo/contradictorio.
- Contexto persistente y actualizado.
- Privacidad y cumplimiento normativo.
- Escalabilidad, recuperación ante fallos y equilibrio costo-fiabilidad.
"""

from typing import List, Dict, Any, Optional, Callable
import time

from orquesta_models import (
    OrquestaConfig, OrquestaResult, Subquery, Source, PartialResult,
    ResolvedFact, ExecutionMetrics, ExecutionVerdict, SubqueryStatus,
    PrivacyPolicy,
)
from source_registry import SourceRegistry
from schema_federation import SchemaFederation
from query_router import QueryRouter
from cache_manager import CacheManager
from cost_latency_manager import CostLatencyManager
from conflict_resolver import ConflictResolver
from privacy_compliance import PrivacyComplianceManager
from fault_tolerance import FaultToleranceManager
from load_balancer import LoadBalancer
from context_manager import ContextManager
from observability_328 import ObservabilityManager


class OrquestaREngine:
    """
    Motor principal de ORQUESTA-R.

    Recibe una consulta empresarial, la descompone, enruta a fuentes
    externas controlando costo/latencia, normaliza esquemas, resuelve
    conflictos, filtra por privacidad, actualiza contexto y entrega
    respuesta trazable.
    """

    def __init__(self, config: Optional[OrquestaConfig] = None):
        self.config = config or OrquestaConfig()

        self.sources = SourceRegistry()
        self.schema_federation = SchemaFederation()
        self.router = QueryRouter()
        self.cache = CacheManager(default_ttl_seconds=self.config.cache_ttl_seconds)
        self.cost_latency = CostLatencyManager(budget=self.config.budget)
        self.conflict_resolver = ConflictResolver(
            variance_threshold=self.config.conflict_variance_threshold,
        )
        self.privacy = PrivacyComplianceManager(active_policies=self.config.privacy_policies)
        self.fault_tolerance = FaultToleranceManager(max_retries=self.config.budget.max_retries)
        self.load_balancer = LoadBalancer()
        self.context = ContextManager(window_size=self.config.context_window_size)
        self.observability = ObservabilityManager()

    def execute(
        self,
        query: str,
        context: str = "",
        user_region: str = "global",
        external_connectors: Optional[Dict[str, Callable[[str, Dict[str, Any]], Any]]] = None,
    ) -> OrquestaResult:
        """
        Ejecuta el flujo completo ORQUESTA-R.

        Args:
            query: consulta empresarial original.
            context: contexto adicional.
            user_region: región del usuario para cumplimiento normativo.
            external_connectors: dict {source_id: callable(query, metadata) -> result}

        Returns:
            OrquestaResult con respuesta, métricas y trazabilidad.
        """
        start_time = time.time()
        result = OrquestaResult(query=query)
        root_span = self.observability.start_span(
            operation="orquesta_r_execute",
            trace_id=result.trace_id,
            attributes={"query": query, "context": context, "user_region": user_region},
        )

        self.observability.log(
            "INFO", f"ORQUESTA-R execute: {query[:120]}",
            trace_id=result.trace_id,
        )

        try:
            # FASE 0: Cargar contexto persistente
            global_context = self.context.load()

            # FASE 1: Descomposición y planificación
            subqueries = self.router.decompose(query, context)
            result.subqueries = subqueries
            self.observability.inc_counter("orquesta_subqueries_total", value=len(subqueries))

            # FASE 2: Selección de fuentes por política y capacidad
            all_sources = self.sources.list_sources(enabled_only=True)
            allowed_sources = self.privacy.filter_sources_by_policy(all_sources, user_region)

            # FASE 3: Ejecución por lotes
            for subquery in subqueries:
                self._execute_subquery(
                    subquery=subquery,
                    allowed_sources=allowed_sources,
                    global_context=global_context,
                    external_connectors=external_connectors or {},
                    result=result,
                )

            # FASE 4: Resolución de conflictos
            grouped = self._group_partials_by_key(result.partial_results)
            for key, partials in grouped.items():
                resolved = self.conflict_resolver.resolve(
                    key=key, partials=partials, global_context=global_context
                )
                result.resolved_facts.append(resolved)
                if resolved.warnings:
                    result.warnings.extend(resolved.warnings)

            # FASE 5: Síntesis final
            answer = self._synthesize_answer(query, result.resolved_facts)
            result.answer = answer
            result.confidence = self._compute_global_confidence(result.resolved_facts)

            # FASE 6: Actualización de contexto persistente
            delta = {
                "last_query": query,
                "last_answer_summary": str(answer)[:200],
                "resolved_facts_count": len(result.resolved_facts),
            }
            version = self.context.update(delta, dependencies=[s.subquery_id for s in subqueries])
            result.context_version_id = version.version_id

            # FASE 7: Veredicto y métricas
            self._determine_verdict(result)
            result.metrics = self._build_metrics(result)
            result.duration_ms = (time.time() - start_time) * 1000

            # Recomendaciones
            result.recommendations = self._generate_recommendations(result)

            self.observability.observe_histogram(
                "orquesta_total_duration_ms", result.duration_ms
            )
            self.observability.observe_histogram(
                "orquesta_confidence", result.confidence
            )
            self.observability.inc_counter("orquesta_executions_total")

            self.observability.log(
                "INFO",
                f"ORQUESTA-R completed: verdict={result.verdict.value}, "
                f"confidence={result.confidence:.3f}, cost={result.metrics.total_cost:.4f}",
                trace_id=result.trace_id,
            )

        except Exception as e:
            self.observability.log(
                "ERROR", f"ORQUESTA-R execution failed: {str(e)}",
                trace_id=result.trace_id,
            )
            result.verdict = ExecutionVerdict.FAILED
            result.warnings.append(str(e))
            result.duration_ms = (time.time() - start_time) * 1000

        self.observability.end_span(root_span.span_id, status="ERROR" if result.verdict == ExecutionVerdict.FAILED else "OK")
        return result

    def _execute_subquery(
        self,
        subquery: Subquery,
        allowed_sources: List[Source],
        global_context: Dict[str, Any],
        external_connectors: Dict[str, Callable[[str, Dict[str, Any]], Any]],
        result: OrquestaResult,
    ) -> None:
        """Ejecuta una subconsulta a través de fuentes seleccionadas."""
        subquery.status = SubqueryStatus.RUNNING
        sub_start = time.time()

        # Seleccionar fuentes candidatas
        candidates = self.router.select_sources(
            subquery=subquery,
            candidates=allowed_sources,
        )

        if not candidates:
            subquery.status = SubqueryStatus.FAILED
            result.warnings.append(f"No sources for subquery: {subquery.text}")
            return

        # Intentar con top-N fuentes según redundancia configurada
        redundancy = self.config.default_redundancy + 1
        selected = candidates[:redundancy]

        for source in selected:
            # Circuit breaker check
            if not self.fault_tolerance.is_available(source.source_id):
                continue

            # Caché
            cached = self.cache.get(subquery.text, source.source_id)
            if cached:
                partial = PartialResult(
                    subquery_id=subquery.subquery_id,
                    source_id=source.source_id,
                    data=cached.get("data"),
                    confidence=cached.get("confidence", 0.7),
                    method="cached",
                    lineage={"cache": True},
                )
                result.partial_results.append(partial)
                subquery.status = SubqueryStatus.CACHE_HIT
                result.metrics.cache_hits += 1
                self.observability.inc_counter("orquesta_cache_hits_total")
                continue

            # Estimación y presupuesto
            estimate = self.cost_latency.estimate(source, subquery)
            if not self.cost_latency.can_afford(
                estimate["estimated_cost"], estimate["estimated_latency_ms"]
            ):
                result.warnings.append(
                    f"Budget exceeded for source {source.name} on subquery {subquery.text}"
                )
                continue

            # Balanceo de carga
            if self.config.enable_load_balancing:
                alternative = self.load_balancer.rebalance_tasks(
                    source.source_id, selected, threshold=10
                )
                if alternative:
                    source = alternative

            # Ejecutar con tolerancia a fallos
            connector = external_connectors.get(source.source_id) or self.sources.get_connector(source.source_id)
            if not connector:
                continue

            self.load_balancer.assign(source.source_id)
            self.cost_latency.start_call()
            operation = lambda s=subquery, c=connector, src=source: self._call_connector(s, c, src)
            fallback = lambda: self._fallback_result(subquery, source)

            data, success, attempts = self.fault_tolerance.execute_with_retry(
                source_id=source.source_id,
                operation=operation,
                fallback=fallback,
            )
            self.cost_latency.end_call()
            self.load_balancer.release(source.source_id)

            result.metrics.retries += max(0, attempts - 1)
            latency_ms = (time.time() - sub_start) * 1000

            if success and data is not None:
                # Normalizar esquema
                normalized = self.schema_federation.normalize(source, data)
                # Aplicar privacidad
                if self.config.enable_privacy_filter:
                    for policy in self.config.privacy_policies:
                        if policy != PrivacyPolicy.NONE:
                            normalized = self.privacy.anonymize_record(normalized, policy)

                cost = estimate["estimated_cost"]
                self.cost_latency.record_actual(source.source_id, cost, latency_ms, success=True)
                self.fault_tolerance.record_success(source.source_id, latency_ms)

                confidence = self._extract_confidence(normalized)
                partial = PartialResult(
                    subquery_id=subquery.subquery_id,
                    source_id=source.source_id,
                    data=normalized,
                    raw_score=confidence,
                    normalized_score=confidence,
                    confidence=confidence,
                    method="direct",
                    lineage={"attempts": attempts, "latency_ms": latency_ms, "cost": cost},
                )
                result.partial_results.append(partial)

                # Guardar en caché
                if self.config.cache_enabled:
                    self.cache.set(
                        subquery_text=subquery.text,
                        source_id=source.source_id,
                        value={"data": normalized, "confidence": confidence},
                    )

                subquery.status = SubqueryStatus.COMPLETED
                subquery.source_id = source.source_id
                subquery.cost = cost
                subquery.latency_ms = latency_ms
                subquery.confidence = confidence
                result.metrics.subqueries_successful += 1
                break
            else:
                self.cost_latency.record_actual(source.source_id, estimate["estimated_cost"], latency_ms, success=False)

        if subquery.status not in (SubqueryStatus.COMPLETED, SubqueryStatus.CACHE_HIT):
            subquery.status = SubqueryStatus.PARTIAL_FAILURE
            result.metrics.subqueries_failed += 1
            result.warnings.append(f"Subquery failed after retries: {subquery.text}")

    def _call_connector(
        self,
        subquery: Subquery,
        connector: Callable[[str, Dict[str, Any]], Any],
        source: Source,
    ) -> Any:
        """Llama al conector de una fuente externa."""
        return connector(subquery.text, {"source": source.to_dict(), "metadata": {}})

    def _fallback_result(
        self,
        subquery: Subquery,
        source: Source,
    ) -> Any:
        """Resultado fallback cuando fallan todos los reintentos."""
        return {
            "content": f"Fallback: no data available for '{subquery.text}' from {source.name}",
            "source": source.name,
            "confidence": 0.3,
        }

    def _group_partials_by_key(self, partials: List[PartialResult]) -> Dict[str, List[PartialResult]]:
        """Agrupa resultados parciales por subconsulta."""
        grouped: Dict[str, List[PartialResult]] = {}
        for p in partials:
            grouped.setdefault(p.subquery_id, []).append(p)
        return grouped

    def _extract_confidence(self, data: Any) -> float:
        """Extrae confianza de datos normalizados."""
        if isinstance(data, dict):
            conf = data.get("confidence", data.get("score", 0.7))
            try:
                return float(conf)
            except (ValueError, TypeError):
                return 0.7
        return 0.7

    def _synthesize_answer(self, query: str, facts: List[ResolvedFact]) -> str:
        """Sintetiza respuesta final a partir de hechos resueltos."""
        if not facts:
            return "No se encontraron datos suficientes para responder."
        lines = [f"Respuesta a '{query}':"]
        for fact in facts:
            lines.append(f"- {fact.key}: {fact.value} (confianza: {fact.confidence:.2f})")
        return "\n".join(lines)

    def _compute_global_confidence(self, facts: List[ResolvedFact]) -> float:
        """Calcula confianza global promedio."""
        if not facts:
            return 0.0
        return sum(f.confidence for f in facts) / len(facts)

    def _determine_verdict(self, result: OrquestaResult) -> None:
        """Determina veredicto final."""
        total = len(result.subqueries)
        failed = result.metrics.subqueries_failed
        if failed == 0:
            result.verdict = ExecutionVerdict.SUCCESS
        elif failed < total:
            result.verdict = ExecutionVerdict.PARTIAL_SUCCESS
        else:
            result.verdict = ExecutionVerdict.FAILED

        # Presupuesto/latencia
        remaining = self.cost_latency.get_remaining_budget()
        if remaining["remaining_cost"] <= 0:
            result.verdict = ExecutionVerdict.BUDGET_EXCEEDED
        if remaining["remaining_latency_ms"] <= 0:
            result.verdict = ExecutionVerdict.LATENCY_EXCEEDED
        if any(p.method == "fallback" for p in result.partial_results):
            if result.verdict != ExecutionVerdict.FAILED:
                result.verdict = ExecutionVerdict.FALLBACK_USED

    def _build_metrics(self, result: OrquestaResult) -> ExecutionMetrics:
        """Construye métricas finales."""
        stats = self.cost_latency.get_statistics()
        result.metrics.total_cost = stats["spent_cost"]
        result.metrics.total_latency_ms = result.duration_ms
        result.metrics.subqueries_total = len(result.subqueries)
        result.metrics.circuit_breaker_opens = self.fault_tolerance.get_statistics()["circuit_open"]
        result.metrics.privacy_violations_blocked = self.privacy.get_statistics()["violations_blocked"]
        result.metrics.sources_used = list({p.source_id for p in result.partial_results if p.source_id})
        return result.metrics

    def _generate_recommendations(self, result: OrquestaResult) -> List[str]:
        """Genera recomendaciones post-ejecución."""
        recs = []
        if result.metrics.subqueries_failed > 0:
            recs.append("Considerar agregar fuentes alternativas o aumentar presupuesto.")
        if result.metrics.cache_hits == 0 and len(result.subqueries) > 2:
            recs.append("Aumentar TTL de caché para subconsultas frecuentes.")
        if result.confidence < self.config.min_confidence:
            recs.append("Baja confianza global: revisar fuentes o aumentar redundancia.")
        if result.metrics.privacy_violations_blocked > 0:
            recs.append("Revisar políticas de privacidad y consentimientos de fuentes.")
        return recs

    def register_source(
        self,
        data: Dict[str, Any],
        connector: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> Source:
        """Registra una fuente externa."""
        return self.sources.register_from_dict(data, connector)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas consolidadas del orquestador."""
        return {
            "sources": self.sources.get_statistics(),
            "cache": self.cache.get_statistics(),
            "cost_latency": self.cost_latency.get_statistics(),
            "fault_tolerance": self.fault_tolerance.get_statistics(),
            "load_balancer": self.load_balancer.get_statistics(),
            "context": self.context.get_statistics(),
            "privacy": self.privacy.get_statistics(),
            "schema_federation": self.schema_federation.get_statistics(),
            "observability": self.observability.get_summary(),
        }

    def reset(self) -> None:
        """Resetea todo el estado del orquestador."""
        self.sources.reset()
        self.schema_federation.reset()
        self.cache.reset()
        self.cost_latency.reset()
        self.fault_tolerance.reset()
        self.load_balancer.reset()
        self.context.reset()
        self.privacy.reset()
        self.observability.reset()
