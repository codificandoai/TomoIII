"""Capa BDI (Beliefs-Desires-Intentions) para UC-293.

Construye estructuras BDI a partir del estado de mercado percibido, el portafolio,
las restricciones de riesgo y las predicciones del world model. También construye
la cadena de pensamiento ReAct (CoT) a partir de señales y evaluaciones.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import (
    AgentAction,
    BDIBeliefs,
    BDIDesires,
    BDIIntention,
    BDIState,
    CandidateStrategy,
    CoTStep,
    JuiceVerdict,
    MarketSnapshot,
    RiskConstraints,
    TradingRequest,
)
from world_model import TradingWorldModel


class BDIBuilder:
    """Construye creencias, deseos e intenciones BDI desde datos de trading."""

    @staticmethod
    def build_beliefs(
        symbol: str,
        snapshot: MarketSnapshot,
        portfolio_cash: float,
        portfolio_position: float,
        world_model: Optional[TradingWorldModel] = None,
        cost_basis: float = 0.0,
    ) -> BDIBeliefs:
        features = snapshot.features.to_dict() if snapshot.features else {}
        wm_uncertainty = 1.0
        empirical_success = 0.5
        predicted_next_price = snapshot.latest_price
        if world_model is not None:
            try:
                pred = world_model.predict_next_price(symbol, snapshot.latest_price, features)
                predicted_next_price = pred.get("predicted_next_price", snapshot.latest_price)
                wm_uncertainty = pred.get("uncertainty", 1.0)
            except Exception:
                pass
            try:
                estimate = world_model._get_estimate(symbol, "BUY")
                empirical_success = estimate.success_prob
            except Exception:
                pass

        return BDIBeliefs(
            symbol=symbol,
            current_price=snapshot.latest_price,
            cost_basis=cost_basis,
            latest_features=features,
            regime=snapshot.regime,
            news_sentiment=snapshot.news_sentiment,
            news_credibility=snapshot.news_credibility,
            volatility=features.get("volatility", 0.0),
            atr=features.get("atr", 0.0),
            rsi=features.get("rsi", 50.0),
            trend_direction=features.get("trend_direction", 0),
            empirical_success_prob=empirical_success,
            world_model_uncertainty=wm_uncertainty,
            predicted_next_price=predicted_next_price,
            portfolio_cash=portfolio_cash,
            portfolio_position=portfolio_position,
        )

    @staticmethod
    def build_desires(
        request: TradingRequest,
        constraints: Optional[RiskConstraints] = None,
    ) -> BDIDesires:
        c = constraints or request.constraints or RiskConstraints()
        return BDIDesires(
            primary_goal="Maximizar el retorno ajustado por riesgo.",
            secondary_goal="Preservar capital y limitar drawdown.",
            risk_tolerance=request.risk_tolerance,
            min_signal_confidence=c.min_signal_confidence,
            max_position_pct=c.max_position_pct,
            max_drawdown_pct=c.max_drawdown_pct,
            max_uncertainty=0.5,
            require_stop_loss=True,
            require_take_profit=True,
        )

    @staticmethod
    def build_intention(
        strategy: CandidateStrategy,
        justification: str = "",
        cot_trace: Optional[List[CoTStep]] = None,
    ) -> BDIIntention:
        actions = strategy.actions if isinstance(strategy.actions, list) else []
        if actions and isinstance(actions[0], dict):
            actions = [AgentAction(**a) for a in actions]
        main_action = actions[0] if actions else AgentAction(side="HOLD")
        return BDIIntention(
            planned_action=main_action.side,
            planned_params=main_action.to_dict(),
            actions=actions,
            justification=justification or f"Estrategia candidata seleccionada: {strategy.name}.",
            cot_trace=cot_trace or [],
            status="draft",
        )

    @staticmethod
    def build_cot_trace(
        signals: List[Dict[str, Any]],
        evaluations: List[Dict[str, Any]],
        selected_strategy: Optional[Dict[str, Any]] = None,
    ) -> List[CoTStep]:
        """Construye una cadena CoT a partir de las decisiones de los agentes."""
        trace: List[CoTStep] = []
        for i, sig in enumerate(signals[:5]):
            trace.append(
                CoTStep(
                    step=i + 1,
                    thought=f"El agente {sig.get('agent', 'unknown')} sugiere {sig.get('side')} con confianza {sig.get('confidence', 0)}.",
                    action="analyze_signal",
                    params=sig,
                    observation=(
                        f"Señal {sig.get('side')}: entry={sig.get('entry_price')}, "
                        f"stop={sig.get('stop_loss')}, target={sig.get('take_profit')}."
                    ),
                )
            )
        if evaluations:
            best = evaluations[0]
            trace.append(
                CoTStep(
                    step=len(trace) + 1,
                    thought="El crítico evaluó las estrategias candidatas y seleccionó la de mayor puntaje.",
                    action="evaluate_strategies",
                    params={"evaluations": evaluations},
                    observation=(
                        f"Mejor estrategia: score={best.get('final_score')}, "
                        f"expected_return={best.get('expected_return')}, "
                        f"risk={best.get('risk_score')}."
                    ),
                )
            )
        if selected_strategy:
            trace.append(
                CoTStep(
                    step=len(trace) + 1,
                    thought="Borrador de intención generado: ejecutar la estrategia seleccionada.",
                    action="draft_intention",
                    params=selected_strategy,
                    observation=f"Acción principal: {selected_strategy.get('name', 'unknown')}.",
                )
            )
        return trace


class BDIStateBuilder:
    """Construye el estado BDI serializable para API y auditoría."""

    @staticmethod
    def build(
        beliefs: BDIBeliefs,
        desires: BDIDesires,
        draft: Optional[BDIIntention] = None,
        verdict: Optional[JuiceVerdict] = None,
        committed: Optional[BDIIntention] = None,
    ) -> BDIState:
        return BDIState(
            beliefs=beliefs.to_dict(),
            desires=desires.to_dict(),
            draft_intention=draft.to_dict() if draft else None,
            juice_verdict=verdict.to_dict() if verdict else None,
            committed_intention=committed.to_dict() if committed else None,
            cot_trace=[step.to_dict() for step in (draft.cot_trace if draft else [])],
        )
