"""
Codificando.AI
UC-290: Human-in-the-Loop (HITL) con Razonamiento Transparente
Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

UC-290 es la capa HITL que se interpone entre UC-315 (decide) y UC-317 (ejecuta).
La IA no toma la decisión de ejecución; construye un Expediente de Decisión
que incluye datos procesados, razonamiento paso a paso y una sugerencia.
Si el riesgo es alto o la confianza es baja, se activa un Punto de Escalamiento
obligando a intervención humana.

    UC-315 decide → UC-290 HITL revisa → UC-317 ejecuta
                         ↓ si riesgo alto
                    Revisor Humano
                         ↓
                   approve / modify / reject
"""

import sys
import os
import time
import random
import json

# Asegurar path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models_290 import (
    HITLConfig,
    DecisionInput,
    ReasoningStep,
    ReasoningStepType,
    HumanAction,
    HITLDecision,
    RiskLevel,
)
from hitl_guardian import HITLGuardian


# ---------------------------------------------------------------------------
# Generadores de datos de demo
# ---------------------------------------------------------------------------

def _make_reasoning_steps(suggestion: str, confidence: float) -> list:
    """Genera pasos de razonamiento transparente de la IA."""
    steps = [
        ReasoningStep(
            step_number=1,
            step_type=ReasoningStepType.DATA,
            description="Tendencia: Precio > MA20 > MA50 (alcista fuerte)",
            evidence="current_price=105.2, ma_20=98.5, ma_50=97.0",
            confidence=0.9,
            source="uc315",
        ),
        ReasoningStep(
            step_number=2,
            step_type=ReasoningStepType.DATA,
            description="Volumen: Alto (75,000) - confirma fuerza del movimiento",
            evidence="volume=75000, threshold=70000",
            confidence=0.8,
            source="uc315",
        ),
        ReasoningStep(
            step_number=3,
            step_type=ReasoningStepType.PROJECTION,
            description=f"Proyección: movimiento de +$3.35 basado en desviación de MA20",
            evidence="predicted_move = (105.2 - 98.5) * 0.5 = 3.35",
            confidence=confidence,
            source="uc315",
        ),
    ]
    return steps


def _make_low_risk_decision() -> DecisionInput:
    """Decisión de bajo riesgo: debe auto-ejecutarse."""
    return DecisionInput(
        decision_id="dec_001",
        trace_id="trace_001",
        context={"current_price": 105.2, "predicted_move": 1.5, "volume": 75000},
        ai_suggestion="BUY",
        ai_confidence=0.85,
        ai_reasoning_steps=_make_reasoning_steps("BUY", 0.85),
        uc087_integrity_passed=True,
        uc087_integrity_details={"hash": "abc123", "signature": "valid"},
        uc162_llmops_passed=True,
        uc162_llmops_details={"bias": "ok", "hallucination": "none"},
        uc325_reflection_score=0.82,
        uc325_reflection_details={"quality": "high"},
        uc322_conflict_detected=False,
        uc322_conflict_details={},
        uc329_graph_paths=[{"path": "A->B->C", "score": 0.9}],
        source_agent="uc315",
    )


def _make_high_risk_decision() -> DecisionInput:
    """Decisión de alto riesgo: debe escalar a humano."""
    return DecisionInput(
        decision_id="dec_002",
        trace_id="trace_002",
        context={"current_price": 100.0, "predicted_move": 8.0, "volume": 95000},
        ai_suggestion="BUY",
        ai_confidence=0.55,
        ai_reasoning_steps=_make_reasoning_steps("BUY", 0.55),
        uc087_integrity_passed=True,
        uc087_integrity_details={"hash": "def456", "signature": "valid"},
        uc162_llmops_passed=True,
        uc162_llmops_details={"bias": "ok", "hallucination": "none"},
        uc325_reflection_score=0.45,
        uc325_reflection_details={"quality": "low", "issues": ["insufficient_evidence"]},
        uc322_conflict_detected=True,
        uc322_conflict_details={"agents": ["uc329", "uc325"], "conflict": "contradictory_paths"},
        uc329_graph_paths=[{"path": "A->B->C", "score": 0.9}, {"path": "A->D->E", "score": 0.3}],
        source_agent="uc315",
    )


def _make_blocked_decision() -> DecisionInput:
    """Decisión bloqueada: UC-087 rechazó integridad."""
    return DecisionInput(
        decision_id="dec_003",
        trace_id="trace_003",
        context={"current_price": 100.0, "predicted_move": 1.0},
        ai_suggestion="SELL",
        ai_confidence=0.90,
        ai_reasoning_steps=_make_reasoning_steps("SELL", 0.90),
        uc087_integrity_passed=False,
        uc087_integrity_details={"error": "hash_mismatch", "expected": "abc", "actual": "xyz"},
        uc162_llmops_passed=True,
        uc325_reflection_score=0.80,
        uc322_conflict_detected=False,
        source_agent="uc315",
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def run_demo():
    """Ejecuta el demo completo del pipeline HITL."""
    print("=" * 70)
    print("UC-290 — Human-in-the-Loop (HITL) con Razonamiento Transparente")
    print("IA = Analista Operativo | Humano = Director de Estrategia")
    print("=" * 70)

    guardian = HITLGuardian()

    # --- Escenario 1: Decisión de bajo riesgo (auto-execute) ---
    print("\n" + "=" * 70)
    print("ESCENARIO 1: Decisión de bajo riesgo (fast path → auto-execute)")
    print("=" * 70)

    decision = _make_low_risk_decision()
    result = guardian.process_decision(decision)

    print(f"\n  Decision: {result.decision.value}")
    print(f"  Risk level: {result.risk_level}")
    print(f"  Risk score: {result.risk_score:.2f}")
    print(f"  Confidence: {result.confidence_score:.2f}")
    print(f"  Escalated: {result.escalated}")
    print(f"  Final action: {result.final_action}")
    print(f"  Duration: {result.duration_ms:.2f}ms")

    # --- Escenario 2: Decisión de alto riesgo (escalar a humano) ---
    print("\n" + "=" * 70)
    print("ESCENARIO 2: Decisión de alto riesgo (slow path → escalar)")
    print("=" * 70)

    decision = _make_high_risk_decision()
    result = guardian.process_decision(decision)

    print(f"\n  Decision: {result.decision.value}")
    print(f"  Risk level: {result.risk_level}")
    print(f"  Risk score: {result.risk_score:.2f}")
    print(f"  Confidence: {result.confidence_score:.2f}")
    print(f"  Escalated: {result.escalated}")
    print(f"  Escalation reasons:")
    for reason in result.escalation_reasons:
        print(f"    - {reason}")

    # Mostrar expediente pendiente
    pending = guardian.get_pending_reviews()
    print(f"\n  Expedientes pendientes: {len(pending)}")
    if pending:
        dossier_id = pending[0]["dossier_id"]
        print(f"  Dossier ID: {dossier_id[:8]}...")

        # Presentar expediente
        presentation = guardian.present_dossier(dossier_id)
        if presentation:
            print(f"\n  --- PRESENTACIÓN DEL EXPEDIENTE ---")
            print(presentation["presentation"])

        # Simular revisión humana: APPROVE
        print(f"\n  --- SIMULANDO REVISIÓN HUMANA: APPROVE ---")
        reviewed = guardian.submit_human_review(
            dossier_id=dossier_id,
            reviewer_id="trader_001",
            action=HumanAction.APPROVE,
            review_notes="Riesgo aceptable tras revisar contexto macro.",
        )
        if reviewed:
            print(f"  Status: {reviewed['status']}")
            print(f"  Decision: {reviewed['decision']}")

    # --- Escenario 3: Decisión bloqueada (UC-087 rechazó) ---
    print("\n" + "=" * 70)
    print("ESCENARIO 3: Decisión bloqueada (UC-087 rechazó integridad)")
    print("=" * 70)

    decision = _make_blocked_decision()
    result = guardian.process_decision(decision)

    print(f"\n  Decision: {result.decision.value}")
    print(f"  Issues: {result.issues}")

    # --- Auditoría ---
    print("\n" + "=" * 70)
    print("AUDITORÍA")
    print("=" * 70)

    status = guardian.get_status()
    print(f"\n  Dossiers total: {status['dossiers_total']}")
    print(f"  Pending reviews: {status['pending_reviews']}")
    print(f"  Completed reviews: {status['completed_reviews']}")
    print(f"  Audit entries: {status['audit_entries']}")
    print(f"  Chain verified: {status['audit_chain_verified']}")

    # Trail de auditoría
    trail = guardian.get_audit_trail()
    print(f"\n  Trail de auditoría ({len(trail)} entradas):")
    for entry in trail:
        print(f"    [{entry['actor']}] {entry['event']} (dossier: {entry['dossier_id'][:8]}...)")

    # Métricas
    print("\n" + "=" * 70)
    print("MÉTRICAS PROMETHEUS")
    print("=" * 70)
    print()
    print(guardian.get_metrics())

    print("=" * 70)
    print("Demo completado.")
    print("=" * 70)


def run_trading_demo():
    """
    Demo original de trading con simulación de mercado.
    Mantiene la funcionalidad del código base original pero integrada
    con el guardian HITL.
    """
    print("=" * 70)
    print("UC-290 — Trading Desk HITL (simulación de mercado)")
    print("=" * 70)

    guardian = HITLGuardian()
    prices = [100.0]
    ma_20 = 98.5
    ma_50 = 97.0

    for tick in range(1, 6):
        # Simular mercado
        shock = random.uniform(-2.0, 2.0)
        trend = 0.2 if tick < 3 else -0.3
        price = max(80.0, prices[-1] + shock + trend)
        prices.append(price)
        ma_20 = ma_20 * 0.9 + price * 0.1
        ma_50 = ma_50 * 0.95 + price * 0.05
        volume = random.randint(30000, 90000)
        predicted_move = (price - ma_20) * 0.5

        # Determinar sugerencia
        if price > ma_20 > ma_50 and volume > 70000:
            suggestion = "BUY"
            confidence = 0.85
        elif price < ma_20 < ma_50:
            suggestion = "SELL"
            confidence = 0.85
        else:
            suggestion = "HOLD"
            confidence = 0.50

        # Crear decisión
        decision = DecisionInput(
            decision_id=f"trade_{tick}",
            trace_id=f"trade_trace_{tick}",
            context={
                "current_price": price,
                "predicted_move": predicted_move,
                "volume": volume,
                "ma_20": ma_20,
                "ma_50": ma_50,
            },
            ai_suggestion=suggestion,
            ai_confidence=confidence,
            ai_reasoning_steps=[
                ReasoningStep(
                    step_number=1,
                    step_type=ReasoningStepType.DATA,
                    description=f"Tick {tick}: Precio=${price:.2f}, MA20=${ma_20:.2f}, MA50=${ma_50:.2f}",
                    evidence=f"volume={volume}",
                    confidence=confidence,
                    source="uc315",
                ),
                ReasoningStep(
                    step_number=2,
                    step_type=ReasoningStepType.PROJECTION,
                    description=f"Proyección: ${predicted_move:+.2f} ({predicted_move/price*100:+.1f}%)",
                    evidence="predicted_move = (price - ma_20) * 0.5",
                    confidence=confidence,
                    source="uc315",
                ),
            ],
            uc087_integrity_passed=True,
            uc162_llmops_passed=True,
            uc325_reflection_score=0.75,
            uc322_conflict_detected=False,
        )

        result = guardian.process_decision(decision)
        print(f"\n  Tick {tick}: ${price:.2f} | IA: {suggestion} ({confidence:.0%}) | "
              f"HITL: {result.decision.value} | Riesgo: {result.risk_level}")

        if result.escalated:
            for reason in result.escalation_reasons:
                print(f"    ESCALADO: {reason}")

    # Resumen
    status = guardian.get_status()
    print(f"\n  Resumen: {status['dossiers_total']} decisiones, "
          f"{status['pending_reviews']} pendientes, "
          f"{status['completed_reviews']} completadas")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="UC-290 HITL Guardian")
    parser.add_argument("command", nargs="?", default="demo",
                        choices=["demo", "trading", "api"],
                        help="Comando a ejecutar")
    parser.add_argument("--port", type=int, default=5290)
    args = parser.parse_args()

    if args.command == "demo":
        run_demo()
    elif args.command == "trading":
        run_trading_demo()
    elif args.command == "api":
        from api_290 import main as api_main
        sys.argv = ["api_290.py", "--port", str(args.port)]
        api_main()


if __name__ == "__main__":
    main()
