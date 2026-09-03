"""agent-core.py — Núcleo integrador BDI + Juice + World Model para UC-293.

Expone el orquestador que combina:
- Percepción de mercado (ticks, noticias, indicadores técnicos).
- World model neuronal para predicción de ticks y simulación.
- Agente BDI con Beliefs, Desires e Intentions.
- Filtro adversarial Confrontational Juice (ReAct + CoT).
- Grafo LangGraph de trading con compuerta de riesgo y ejecución.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import AppConfig, get_config
from graph import build_agent, run_agent
from market_data import SyntheticMarketDataGenerator
from models import (
    BDIBeliefs,
    BDIDesires,
    BDIIntention,
    BDIState,
    CandidateStrategy,
    CoTStep,
    JuiceVerdict,
    MarketSnapshot,
    Portfolio,
    RiskConstraints,
    SAMState,
    TradingRequest,
    WorkspaceContent,
    WorldModelObservation,
)


def build_sam_state(
    request: TradingRequest,
    snapshots: Optional[Dict[str, Any]] = None,
    signals: Optional[List[Dict[str, Any]]] = None,
    hypotheses: Optional[List[Dict[str, Any]]] = None,
    alerts: Optional[List[str]] = None,
    agent_identity: str = "UC294.Alpha",
) -> SAMState:
    """Construye el estado SAM completo para una solicitud."""
    from sam import (
        MetacognitionModule,
        SafetySupervisor,
        SituationalAwarenessMiddleware,
    )

    sam = SituationalAwarenessMiddleware(agent_identity=agent_identity)
    workspace = sam.build_workspace(
        request=request,
        snapshots=snapshots or {},
        signals=signals or [],
        hypotheses=hypotheses,
        alerts=alerts,
    )
    metacog = MetacognitionModule()
    meta = metacog.evaluate(workspace)
    safety = SafetySupervisor().check(
        workspace.selected_hypothesis or {},
        request,
        snapshots or {},
    )
    # Registrar episodio de percepción
    sam.store_episode(
        "PERCEPTION",
        f"Workspace built for {request.symbols} with {len(signals or [])} signals.",
    )
    return SAMState(
        self_model=sam.self_model.to_dict(),
        working_memory=[ep.to_dict() for ep in sam.working_memory],
        environment=workspace.environment,
        workspace=workspace.to_dict(),
        metacognition=meta,
        safety_decision=safety,
    )


def _feed_sam_memory_to_world_model(
    sam: Any,
    brain: Any,
) -> None:
    """Convierte episodios SAM en observaciones para entrenar el world model."""
    for ep in sam.working_memory:
        content = ep.content.upper()
        success = not ("ERROR" in content or "FALLO" in content or "REJECTED" in content)
        brain.world_model.update_from_observation(
            WorldModelObservation(
                action_type=ep.event_type,
                item_id=ep.episode_id,
                symbol=ep.metadata.get("symbol", ""),
                predicted_success_prob=max(0.0, 1.0 - brain.world_model.last_uncertainty),
                actual_success=success,
                actual_cost=0.0,
                reward=1.0 if success else -1.0,
            )
        )


def run_sam_aware_pipeline(
    request: TradingRequest,
    config: Optional[AppConfig] = None,
    central_brain: Optional[Any] = None,
    recursion_limit: int = 50,
) -> Dict[str, Any]:
    """Pipeline completo: SAM -> BDI/Juice -> World Model -> Ejecución.

    El cerebro central y el world model son los mismos objetos a lo largo de todo
    el flujo: SAM observa, el grafo BDI/Juice decide, y las observaciones resultantes
    (más los episodios SAM) se devuelven al world model para reentrenamiento.
    """
    from central_brain import CentralBrain
    from sam import (
        MetacognitionModule,
        SafetySupervisor,
        SituationalAwarenessMiddleware,
    )

    cfg = config or get_config()

    # Fase 1: Crear o reutilizar el cerebro central único para todo el pipeline
    brain = central_brain or CentralBrain(cfg)
    snapshots = brain.observe(request)
    snap_payload = {s: snap.to_dict() for s, snap in snapshots.items()}

    # Fase 2: Hipótesis del cerebro (siguiente tick) para poblar el workspace SAM
    hypotheses: List[Dict[str, Any]] = []
    for symbol in request.symbols:
        pred = brain.predict_next_price(symbol)
        hypotheses.append(
            {
                "symbol": symbol,
                "name": "next_tick_prediction",
                "confidence": max(0.0, 1.0 - pred.get("uncertainty", 0.5)),
                "risk_score": pred.get("uncertainty", 0.5),
                "predicted_next_price": pred.get("predicted_next_price"),
            }
        )

    # Fase 3: Workspace SAM con Self-Model, memoria y metacognición
    sam = SituationalAwarenessMiddleware(agent_identity="UC294.Pipeline")
    workspace = sam.build_workspace(
        request=request,
        snapshots=snap_payload,
        signals=[],
        hypotheses=hypotheses,
    )
    meta = MetacognitionModule().evaluate(workspace)
    safety = SafetySupervisor().check(
        workspace.selected_hypothesis or {}, request, snap_payload
    )
    sam.store_episode(
        "PERCEPTION",
        f"Workspace inicial para {request.symbols}; meta={meta['recommendation']}.",
        metadata={"symbols": request.symbols, "recommendation": meta["recommendation"]},
    )

    sam_state = SAMState(
        self_model=sam.self_model.to_dict(),
        working_memory=[ep.to_dict() for ep in sam.working_memory],
        environment=workspace.environment,
        workspace=workspace.to_dict(),
        metacognition=meta,
        safety_decision=safety,
    )

    # Fase 4: Metacognición puede abortar antes de BDI/Juice
    if meta.get("abort"):
        sam.store_episode("METACOGNITION", f"ABORT: {meta['issues']}")
        _feed_sam_memory_to_world_model(sam, brain)
        return {
            "request_id": request.request_id,
            "status": "aborted_by_sam",
            "sam_state": sam_state.to_dict(),
            "reflections": [
                {
                    "stage": "sam",
                    "message": "Metacognition aborted execution: " + str(meta.get("issues")),
                }
            ],
        }

    # Fase 5: Grafo BDI/Juice/Trading usando el MISMO cerebro central
    final_state = run_agent(
        request,
        cfg,
        central_brain=brain,
        recursion_limit=recursion_limit,
    )

    # Fase 6: Los resultados del grafo (éxitos/fallos) alimentan memoria SAM
    for obs in final_state.get("observations", []):
        success = obs.get("actual_success", True)
        sam.store_episode(
            "OBSERVATION",
            f"Action {obs.get('action_type')} success={success} reward={obs.get('reward', 0):.2f}",
            metadata={"symbol": obs.get("symbol", ""), "success": success},
        )

    # Fase 7: Episodios SAM + observaciones del grafo se convierten en experiencias
    # del world model y disparan reentrenamiento si procede.
    _feed_sam_memory_to_world_model(sam, brain)
    if (
        brain.world_model.observations_since_train
        >= brain.world_model.config.probabilistic.retrain_after
    ):
        brain.world_model.retrain()

    output = final_state.get("final_output") or {}
    if output:
        output["sam_state"] = sam_state.to_dict()
        output["sam_state"]["working_memory"] = [ep.to_dict() for ep in sam.working_memory]
        output["world_model_trained"] = brain.world_model._has_trained_return_model()
    return output or {"status": "failed", "sam_state": sam_state.to_dict()}


def build_bdi_from_request(
    request: TradingRequest,
    selected_strategy: Optional[Dict[str, Any]] = None,
    signals: Optional[List[Dict[str, Any]]] = None,
    evaluations: Optional[List[Dict[str, Any]]] = None,
    snapshots: Optional[Dict[str, Any]] = None,
) -> BDIState:
    """Construye el estado BDI completo a partir de una solicitud y estado parcial.

    Útil para exponer el estado BDI vía API sin ejecutar todo el pipeline.
    """
    from bdi import BDIBuilder, BDIStateBuilder
    from central_brain import CentralBrain

    symbol = request.symbols[0] if request.symbols else "AAPL"
    portfolio = request.portfolio or Portfolio()
    brain = CentralBrain(request.config if hasattr(request, "config") else get_config())
    snap_data = (snapshots or {}).get(symbol, {})
    if not snap_data:
        snap_data = brain.observe(request).get(symbol)
        if snap_data is None:
            raise ValueError(f"No se pudo construir snapshot para {symbol}")
    else:
        snap_data = MarketSnapshot(**snap_data)

    beliefs = BDIBuilder.build_beliefs(
        symbol=symbol,
        snapshot=snap_data,
        portfolio_cash=portfolio.cash,
        portfolio_position=portfolio.positions.get(symbol, 0.0),
        world_model=brain.world_model,
        cost_basis=portfolio.average_cost.get(symbol, snap_data.latest_price * 0.95),
    )
    desires = BDIBuilder.build_desires(request, request.constraints)

    intention: Optional[BDIIntention] = None
    if selected_strategy:
        cot_trace = BDIBuilder.build_cot_trace(signals or [], evaluations or [], selected_strategy)
        intention = BDIBuilder.build_intention(
            CandidateStrategy(**selected_strategy),
            cot_trace=cot_trace,
        )
    else:
        intention = BDIIntention(justification="Sin estrategia seleccionada todavía.")

    return BDIStateBuilder.build(beliefs=beliefs, desires=desires, draft=intention)


def run_bdi_trading_pipeline(
    request: TradingRequest,
    config: Optional[AppConfig] = None,
    recursion_limit: int = 50,
) -> Dict[str, Any]:
    """Ejecuta el pipeline completo de trading BDI + Juice + World Model."""
    cfg = config or get_config()
    final_state = run_agent(request, cfg, recursion_limit=recursion_limit)
    return final_state.get("final_output") or {}


def main() -> int:
    """Demostración rápida del núcleo SAM + BDI + Juice."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.pretty import pprint

    console = Console()
    console.print(Panel("[bold cyan]UC-294 — SAM + BDI + Juice + World Model Core Demo[/bold cyan]"))

    cfg = get_config()
    gen = SyntheticMarketDataGenerator(cfg.market, seed=42)
    ticks = gen.generate_ticks("AAPL", n=80)
    request = TradingRequest(
        symbols=["AAPL"],
        ticks=ticks,
        portfolio=Portfolio(cash=100_000.0),
        mode="paper",
        approved=False,
    )

    output = run_sam_aware_pipeline(request, cfg)
    pprint(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
