"""Validación de los 4 procesos de resolución de conflictos UC-322.

Este script ejecuta escenarios específicos para verificar:
1. Memoria persistente (reputación se actualiza con cada episodio).
2. Orquestación con 4 niveles de escalación.
3. Manejo maduro de errores (escalación por severidad + circuit breaker).
4. Trazas y depuración (logs, spans, métricas Prometheus).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conflict_models import (
    AgentBelief,
    Conflict,
    ConflictSeverity,
    EscalationVerdict,
    ResolutionLevel,
)
from escalation_protocol import EscalationProtocol, EscalationConfig
from uc322 import ConflictResolutionLayer


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check(condition, message):
    status = "OK" if condition else "FAIL"
    symbol = "[OK]" if condition else "[FAIL]"
    print(f"  {symbol} {message}")
    return condition


def main():
    all_ok = True

    # ─────────────────────────────────────────────────────────────
    # 1. FALTA DE MEMORIA PERSISTENTE
    # ─────────────────────────────────────────────────────────────
    section("1. Falta de Memoria Persistente")

    layer = ConflictResolutionLayer()

    # Registrar varios episodios para el mismo agente
    layer.reputation.record_episode(
        agent_id="tech_1", task_id="t1", success=True, quality=0.9, efficiency=0.8, domain="trading"
    )
    rep_after_good = layer.reputation.get_reputation("tech_1", "trading")
    check(0.5 < rep_after_good <= 1.0, f"Reputación sube tras éxito: {rep_after_good:.4f}")

    layer.reputation.record_episode(
        agent_id="tech_1", task_id="t2", success=False, quality=0.1, efficiency=0.2, domain="trading"
    )
    rep_after_bad = layer.reputation.get_reputation("tech_1", "trading")
    check(rep_after_bad < rep_after_good, f"Reputación baja tras fallo: {rep_after_good:.4f} -> {rep_after_bad:.4f}")

    # Verificar historial de episodios
    entry = layer.reputation.get_entry("tech_1", "trading")
    check(len(entry.history) == 2, f"Historial de episodios persistido: {len(entry.history)} episodios")
    check(entry.total_episodes == 2, f"Total de episodios: {entry.total_episodes}")
    check(entry.success_count == 1, f"Éxitos contados: {entry.success_count}")
    check(entry.failure_count == 1, f"Fallos contados: {entry.failure_count}")

    # Aislamiento de dominios
    layer.reputation.record_episode(
        agent_id="tech_1", task_id="t3", success=False, quality=0.1, domain="reservations"
    )
    rep_trading = layer.reputation.get_reputation("tech_1", "trading")
    rep_reservations = layer.reputation.get_reputation("tech_1", "reservations")
    check(rep_trading != rep_reservations,
          f"Reputación aislada por dominio: trading={rep_trading:.4f}, reservations={rep_reservations:.4f}")

    # Peso de creencias afectado por reputación
    belief = AgentBelief(agent_id="tech_1", proposition="BUY", confidence=0.8)
    weight_trading = layer.reputation.weight_belief(belief, domain="trading")
    weight_reservations = layer.reputation.weight_belief(belief, domain="reservations")
    check(weight_trading != weight_reservations,
          f"Peso de creencia afectado por reputación: trading={weight_trading:.4f}, reservations={weight_reservations:.4f}")

    all_ok &= (0.5 < rep_after_good and rep_after_bad < rep_after_good and len(entry.history) == 2
               and rep_trading != rep_reservations and weight_trading != weight_reservations)

    # ─────────────────────────────────────────────────────────────
    # 2. SOPORTE LIMITADO DE ORQUESTACIÓN
    # ─────────────────────────────────────────────────────────────
    section("2. Soporte Limitado de Orquestación (4 Niveles)")

    # Escenario A: Negociación resuelve (brecha pequeña)
    layer2 = ConflictResolutionLayer()
    layer2.reputation.record_episode("a1", "init", True, 0.8, 0.8, "trading")
    layer2.reputation.record_episode("a2", "init", True, 0.8, 0.8, "trading")

    beliefs_negotiation = [
        AgentBelief(agent_id="a1", proposition="BUY", confidence=0.62),
        AgentBelief(agent_id="a2", proposition="BUY", confidence=0.55),
    ]
    result = layer2.resolve(beliefs=beliefs_negotiation, domain="trading")
    check(result.success, "Nivel 1 puede resolver conflictos pequeños")
    check(result.level_reached == ResolutionLevel.NEGOTIATION,
          f"Nivel alcanzado: {result.level_reached.name}")

    # Escenario B: Negociación falla, Votación resuelve
    layer3 = ConflictResolutionLayer()
    for a in ["b1", "b2", "b3"]:
        layer3.reputation.record_episode(a, "init", True, 0.8, 0.8, "trading")

    beliefs_voting = [
        AgentBelief(agent_id="b1", proposition="BUY", confidence=0.95),
        AgentBelief(agent_id="b2", proposition="BUY", confidence=0.20),
        AgentBelief(agent_id="b3", proposition="BUY", confidence=0.85),
    ]
    result = layer3.resolve(
        beliefs=beliefs_voting,
        domain="trading",
        options=["BUY", "SELL", "HOLD"],
    )
    check(result.success, "Nivel 2/3 puede resolver cuando Nivel 1 falla")
    check(result.level_reached.value >= ResolutionLevel.VOTING.value,
          f"Nivel alcanzado: {result.level_reached.name}")
    check(result.negotiation_result is not None, "Negociación se ejecutó")
    check(result.voting_result is not None, "Votación se ejecutó")
    check(result.voting_result is not None and len(result.voting_result.votes) > 0, "Votación registró votos")

    # Escenario C: Escalación completa Nivel 1→2→3→4
    # Configurar threshold de consenso muy alto para forzar que Nivel 2 falle,
    # y pujas CNP débiles para forzar que Nivel 3 falle.
    from voting_system import VotingConfig
    from cnp_dynamic import CNPConfig

    layer4 = ConflictResolutionLayer(
        voting_config=VotingConfig(consensus_threshold=0.99),
        cnp_config=CNPConfig(min_composite_score=0.99),
    )
    for a in ["c1", "c2", "c3"]:
        layer4.reputation.record_episode(a, "init", True, 0.8, 0.8, "trading")

    beliefs_escalation = [
        AgentBelief(agent_id="c1", proposition="A", confidence=0.9),
        AgentBelief(agent_id="c2", proposition="B", confidence=0.5),
        AgentBelief(agent_id="c3", proposition="C", confidence=0.1),
    ]
    result = layer4.resolve(
        beliefs=beliefs_escalation,
        domain="trading",
        options=["A", "B", "C"],
        agent_preferences={"c1": "A", "c2": "B", "c3": "C"},
        agent_bids=[
            {"agent_id": "c1", "bid_score": 0.2, "confidence": 0.2, "estimated_cost": 0.8, "estimated_latency_ms": 5000},
            {"agent_id": "c2", "bid_score": 0.2, "confidence": 0.2, "estimated_cost": 0.8, "estimated_latency_ms": 5000},
            {"agent_id": "c3", "bid_score": 0.2, "confidence": 0.2, "estimated_cost": 0.8, "estimated_latency_ms": 5000},
        ],
    )
    check(result.level_reached.value >= ResolutionLevel.ESCALATION.value,
          f"Nivel 4 alcanzado tras fallar 1, 2 y 3: {result.level_reached.name}")
    check(result.negotiation_result is not None, "Nivel 1 ejecutado")
    check(result.voting_result is not None, "Nivel 2 ejecutado")
    check(result.cnp_result is not None, "Nivel 3 ejecutado")
    check(result.escalation_result is not None, "Nivel 4 ejecutado")
    check(result.escalation_result.verdict in (
        EscalationVerdict.PROCEED, EscalationVerdict.REVIEW, EscalationVerdict.STOP, EscalationVerdict.REASSIGN
    ), f"Veredicto emitido: {result.escalation_result.verdict.value}")

    all_ok &= (result.level_reached == ResolutionLevel.ESCALATION
               and result.negotiation_result is not None
               and result.voting_result is not None
               and result.cnp_result is not None
               and result.escalation_result is not None)

    # ─────────────────────────────────────────────────────────────
    # 3. MANEJO INMADURO DE ERRORES
    # ─────────────────────────────────────────────────────────────
    section("3. Manejo Maduro de Errores (Escalación por Severidad)")

    from escalation_protocol import EscalationProtocol

    ep = EscalationProtocol()

    # Severidad baja → PROCEED o REASSIGN
    low = Conflict(agents_involved=["x"], severity=ConflictSeverity.LOW)
    r = ep.escalate(low)
    check(r.verdict in (EscalationVerdict.PROCEED, EscalationVerdict.REVIEW),
          f"Severidad LOW produce veredicto apropiado: {r.verdict.value}")

    # Severidad alta → REVIEW
    high = Conflict(agents_involved=["y"], severity=ConflictSeverity.HIGH)
    r = ep.escalate(high)
    check(r.verdict == EscalationVerdict.REVIEW, f"Severidad HIGH produce REVIEW: {r.verdict.value}")
    check(r.requires_human_review, "HIGH requiere revisión humana")

    # Severidad crítica → STOP
    critical = Conflict(agents_involved=["z"], severity=ConflictSeverity.CRITICAL)
    r = ep.escalate(critical)
    check(r.verdict == EscalationVerdict.STOP, f"Severidad CRITICAL produce STOP: {r.verdict.value}")

    # Circuit breaker: 3 conflictos consecutivos
    ep2 = EscalationProtocol(EscalationConfig())  # default threshold=3
    for i in range(3):
        c = Conflict(agents_involved=["z"], severity=ConflictSeverity.LOW)
        ep2.escalate(c)
    check(ep2.circuit_breaker_open, "Circuit breaker se abre tras 3 conflictos consecutivos")

    # Reasignación cuando CNP tiene ganador (usar EscalationProtocol fresco)
    ep3 = EscalationProtocol()
    from conflict_models import CNPResult
    med = Conflict(agents_involved=["z"], severity=ConflictSeverity.MEDIUM)
    cnp_result = CNPResult(conflict_id=med.conflict_id, task_id="t1", winner="agente_a", winner_score=0.8)
    r = ep3.escalate(med, cnp_result=cnp_result)
    check(r.verdict == EscalationVerdict.REASSIGN, f"CNP con ganador produce REASSIGN: {r.verdict.value}")

    all_ok &= (r.verdict == EscalationVerdict.REASSIGN and ep2.circuit_breaker_open)

    # ─────────────────────────────────────────────────────────────
    # 4. TRAZAS Y DEPURACIÓN
    # ─────────────────────────────────────────────────────────────
    section("4. Trazas y Depuración (Logs, Spans, Métricas)")

    layer_trace = ConflictResolutionLayer()
    for a in ["t1", "t2"]:
        layer_trace.reputation.record_episode(a, "init", True, 0.8, 0.8, "trading")

    beliefs_trace = [
        AgentBelief(agent_id="t1", proposition="BUY", confidence=0.85),
        AgentBelief(agent_id="t2", proposition="BUY", confidence=0.45),
    ]
    result = layer_trace.resolve(beliefs=beliefs_trace, domain="trading")

    # Logs
    logs = layer_trace.observability.get_logs()
    check(len(logs) > 0, f"Logs generados: {len(logs)}")
    if logs:
        log = logs[-1]
        check("timestamp" in log, "Log tiene timestamp")
        check("level" in log, "Log tiene level")
        check("message" in log, "Log tiene message")

    # Spans
    spans = layer_trace.observability.get_spans()
    check(len(spans) > 0, f"Spans generados: {len(spans)}")
    if spans:
        root_spans = [s for s in spans if s["parent_span_id"] is None]
        check(len(root_spans) >= 1, f"Span raíz encontrado: {len(root_spans)}")
        first = spans[0]
        check("trace_id" in first, "Span tiene trace_id")
        check("span_id" in first, "Span tiene span_id")
        check("parent_span_id" in first, "Span tiene parent_span_id")
        check("operation" in first, "Span tiene operation")

    # Métricas
    counters = layer_trace.observability.get_counters()
    check("conflict_negotiation_total" in counters, "Contador conflict_negotiation_total existe")
    check(len(counters["conflict_negotiation_total"]) > 0, "Contador tiene al menos un valor")

    # Exportar Prometheus
    prom_text = layer_trace.observability.export_prometheus()
    check(len(prom_text) > 0, "Exportación Prometheus genera texto")
    check("conflict" in prom_text.lower() or "negotiation" in prom_text.lower(),
          "Exportación Prometheus contiene métricas de conflictos")

    # Verificar métricas por nivel específico
    summary = layer_trace.get_observability_summary()
    check(summary["total_logs"] > 0, f"Resumen total_logs > 0: {summary['total_logs']}")
    check(summary["total_spans"] > 0, f"Resumen total_spans > 0: {summary['total_spans']}")

    all_ok &= (len(logs) > 0 and len(spans) > 0 and "conflict_negotiation_total" in counters
               and len(prom_text) > 0)

    # ─────────────────────────────────────────────────────────────
    # RESUMEN
    # ─────────────────────────────────────────────────────────────
    section("Resumen de Validación")
    if all_ok:
        print("  [OK] Todos los 4 procesos están funcionando correctamente.")
        sys.exit(0)
    else:
        print("  [FAIL] Algunas validaciones fallaron.")
        sys.exit(1)


if __name__ == "__main__":
    main()
