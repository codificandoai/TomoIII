"""Nodos LangGraph del sistema multi-agente de trading de UC-292."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from adversarial_juice import ConfrontationalJuice
from bdi import BDIBuilder, BDIStateBuilder
from central_brain import CentralBrain
from config import AppConfig
from critic import StrategyCritic
from models import JuiceVerdict as JuiceVerdictModel
from exchange import ExchangeSimulator
from models import (
    AgentAction,
    CandidateStrategy,
    MarketSnapshot,
    Portfolio,
    RiskConstraints,
    TradingRequest,
    WorldModelObservation,
    WorldModelState,
    now_iso,
)
from perception import MarketPerceptionPipeline
from planner import StrategyGenerator
from risk import RiskEngine
from simulator import MonteCarloSimulator
from trading_agents import (
    FundamentalAnalyst,
    PerceptionAgent,
    PortfolioManager,
    SentimentAnalyst,
    TechnicalAnalyst,
    TraderAgent,
)
from world_model import TradingWorldModel


class TradingAgentNodes:
    """Nodos del workflow de trading basado en modelo probabilístico."""

    def __init__(
        self,
        config: AppConfig,
        simulator: MonteCarloSimulator,
        critic: StrategyCritic,
        planner: StrategyGenerator,
        exchange: ExchangeSimulator,
        risk_engine: RiskEngine,
        central_brain: Optional[CentralBrain] = None,
        world_model: Optional[TradingWorldModel] = None,
        perception_pipeline: Optional[MarketPerceptionPipeline] = None,
    ) -> None:
        self.config = config
        self.brain = central_brain or CentralBrain(
            config,
            world_model=world_model,
            perception_pipeline=perception_pipeline,
        )
        self.world_model = self.brain.world_model
        self.simulator = simulator
        self.critic = critic
        self.planner = planner
        self.exchange = exchange
        self.perception = PerceptionAgent(self.brain.perception)
        self.risk_engine = risk_engine
        self.rng = np.random.default_rng(config.market.seed)

        self.technical = TechnicalAnalyst()
        self.sentiment = SentimentAnalyst()
        self.fundamental = FundamentalAnalyst()
        self.trader = TraderAgent(risk_engine)
        self.portfolio_manager = PortfolioManager(risk_engine)
        self.juice = ConfrontationalJuice()

    def _log(self, node: str, message: str) -> Dict[str, Any]:
        return {"node": node, "message": message, "timestamp": now_iso()}

    def _reflection(self, stage: str, message: str) -> Dict[str, Any]:
        return {"stage": stage, "message": message, "timestamp": now_iso()}

    # ------------------------------------------------------------------
    # 1. Percepción
    # ------------------------------------------------------------------
    def perceive_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TradingRequest.from_dict(state["request"])
        snapshots = self.brain.observe(request)

        return {
            "status": "analyzing",
            "snapshots": {s: snap.to_dict() for s, snap in snapshots.items()},
            "brain_state": self.brain.to_dict(),
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "perception",
                    f"Processed {len(request.ticks)} ticks and {len(request.news)} news items for {len(snapshots)} symbols.",
                )
            ],
            "logs": [self._log("perception", f"Built market snapshots for {list(snapshots.keys())}")],
        }

    # ------------------------------------------------------------------
    # 2. Análisis
    # ------------------------------------------------------------------
    def analyze_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        snapshots_data = state.get("snapshots", {})
        signals: List[Dict[str, Any]] = []
        for symbol, snap_data in snapshots_data.items():
            from models import MarketSnapshot

            snapshot = MarketSnapshot(**snap_data)
            t_signal = self.technical.analyze(snapshot)
            s_signal = self.sentiment.analyze(snapshot)
            f_signal = self.fundamental.analyze(snapshot)
            signals.extend([sig.to_dict() for sig in [t_signal, s_signal, f_signal] if sig.side != "HOLD" or sig.confidence > 0])

        return {
            "status": "validating",
            "signals": signals,
            "reflections": [
                self._reflection(
                    "analysis",
                    f"Analysts produced {len([s for s in signals if s.get('side') != 'HOLD'])} actionable signals.",
                )
            ],
            "logs": [self._log("analysis", f"Generated {len(signals)} signals")],
        }

    # ------------------------------------------------------------------
    # 3. Validación con Juice Agents
    # ------------------------------------------------------------------
    def validate_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from models import JuiceValidationResult, MarketSnapshot, TradingSignal
        from juice_agents import JuiceValidator

        validator = JuiceValidator(self.config.juice)
        snapshots_data = state.get("snapshots", {})
        validations: List[Dict[str, Any]] = []
        approved_signals: List[Dict[str, Any]] = []

        for sig in state.get("signals", []):
            signal = TradingSignal(**sig)
            snapshot = MarketSnapshot(**snapshots_data.get(signal.symbol, {}))
            result = validator.validate(signal, snapshot)
            validations.append(result.to_dict())
            if result.approved:
                approved_signals.append(sig)

        return {
            "status": "planning",
            "juice_validations": validations,
            "approved_signals": approved_signals,
            "reflections": [
                self._reflection(
                    "juice_validation",
                    f"Juice Agents approved {len(approved_signals)}/{len(state.get('signals', []))} signals.",
                )
            ],
            "logs": [self._log("juice", f"Validated {len(validations)} signals")],
        }

    # ------------------------------------------------------------------
    # 4. Generar estrategias
    # ------------------------------------------------------------------
    def plan_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TradingRequest.from_dict(state["request"])
        snapshots_data = state.get("snapshots", {})
        portfolio_data = state["request"].get("portfolio") or Portfolio().to_dict()

        action_sequences, meta = self.planner.generate(
            request,
            snapshots=snapshots_data,
            portfolio=portfolio_data,
        )
        candidates = [
            {
                "strategy_id": f"strategy-{i+1:03d}",
                "name": seq[0].metadata.get("strategy", "custom") if seq else "hold",
                "actions": [a.to_dict() for a in seq],
            }
            for i, seq in enumerate(action_sequences)
        ]

        return {
            "status": "simulating",
            "candidates": candidates,
            "reflections": [
                self._reflection(
                    "planner",
                    f"Generated {len(candidates)} candidate strategies using {meta.get('strategies')}.",
                )
            ],
            "logs": [self._log("planner", f"Generated {len(candidates)} candidates")],
        }

    # ------------------------------------------------------------------
    # 5. Simular estrategias
    # ------------------------------------------------------------------
    def simulate_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TradingRequest.from_dict(state["request"])
        portfolio = request.portfolio or Portfolio()
        snapshots_data = state.get("snapshots", {})
        initial_state = self._initial_world_state(request, portfolio, snapshots_data)

        candidate_actions: List[List[AgentAction]] = []
        for c in state.get("candidates", []):
            actions = [AgentAction(**a) for a in c.get("actions", [])]
            candidate_actions.append(actions)

        evaluated = self.simulator.simulate_candidates(
            candidate_actions,
            initial_state,
            request,
            rng=self.rng,
        )

        for c in evaluated:
            for sim in c.simulations[:3]:
                self.world_model.record_transition(
                    TransitionAdapter(c.actions, sim).to_transition()
                )

        return {
            "status": "evaluating",
            "candidates": [c.to_dict() for c in evaluated],
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "simulator",
                    f"Simulated {len(evaluated)} strategies with {self.config.model.mc_simulations_per_strategy} rollouts each.",
                )
            ],
            "logs": [self._log("simulator", f"Simulated {len(evaluated)} strategies")],
        }

    # ------------------------------------------------------------------
    # 6. Evaluar y seleccionar
    # ------------------------------------------------------------------
    def evaluate_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        candidates = [CandidateStrategy(**c) for c in state.get("candidates", [])]
        best = self.critic.select_best(candidates)
        evaluations = self.critic.evaluate(candidates)
        if best is None:
            return {
                "status": "awaiting_input",
                "reflections": [self._reflection("critic", "No candidate strategies available.")],
                "logs": [self._log("critic", "No candidates")],
            }
        return {
            "status": "risk_gating",
            "selected_strategy": best.to_dict(),
            "evaluations": [e.to_dict() for e in evaluations],
            "reflections": [
                self._reflection(
                    "critic",
                    f"Selected strategy {best.strategy_id} with score {best.final_score:.4f}.",
                )
            ],
            "logs": [self._log("critic", f"Selected strategy {best.strategy_id}")],
        }

    # ------------------------------------------------------------------
    # 6.5 Confrontación adversarial Juice (BDI)
    # ------------------------------------------------------------------
    def adversarial_confrontation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        selected = state.get("selected_strategy") or {}
        if not selected:
            return {
                "status": "awaiting_input",
                "reflections": [self._reflection("juice_bdi", "No selected strategy to confront.")],
                "logs": [self._log("juice_bdi", "No strategy to confront")],
            }

        request = TradingRequest.from_dict(state["request"])
        snapshots_data = state.get("snapshots", {})
        portfolio = request.portfolio or Portfolio()

        # Construir beliefs/desires/intención BDI para la acción principal
        actions = [AgentAction(**a) for a in selected.get("actions", [])]
        main_action = actions[0] if actions else AgentAction(side="HOLD")
        symbol = main_action.symbol or request.symbols[0]
        snapshot = MarketSnapshot(**snapshots_data.get(symbol, {}))

        beliefs = BDIBuilder.build_beliefs(
            symbol=symbol,
            snapshot=snapshot,
            portfolio_cash=portfolio.cash,
            portfolio_position=portfolio.positions.get(symbol, 0.0),
            world_model=self.world_model,
            cost_basis=portfolio.average_cost.get(symbol, snapshot.latest_price * 0.95),
        )
        desires = BDIBuilder.build_desires(request, request.constraints)
        cot_trace = BDIBuilder.build_cot_trace(
            state.get("signals", []),
            state.get("evaluations", []),
            selected,
        )
        intention = BDIBuilder.build_intention(
            CandidateStrategy(**selected),
            cot_trace=cot_trace,
        )

        verdict = self.juice.confront(beliefs, desires, intention)
        corrected = verdict.corrected_intention

        # Actualizar la estrategia seleccionada si el Juice la destiló o rechazó
        if not verdict.approved and corrected:
            corrected_action = corrected.get("planned_action", "HOLD")
            if corrected_action == "HOLD":
                selected = None
            else:
                # Escalar cantidades corregidas si hay acciones destiladas
                corrected_actions = corrected.get("actions", [])
                if corrected_actions:
                    selected["actions"] = corrected_actions

        bdi_state = BDIStateBuilder.build(
            beliefs=beliefs,
            desires=desires,
            draft=intention,
            verdict=JuiceVerdictModel(**verdict.to_dict()),
            committed=None,
        )

        return {
            "status": "risk_gating" if verdict.approved else ("blocked" if corrected_action == "HOLD" else "risk_gating"),
            "selected_strategy": selected,
            "bdi_state": bdi_state.to_dict(),
            "juice_verdict": verdict.to_dict(),
            "reflections": [
                self._reflection(
                    "juice_bdi",
                    f"Juice survival_score={verdict.survival_score:.1f}. Approved={verdict.approved}. Issues={verdict.issues}",
                )
            ],
            "logs": [
                self._log(
                    "juice_bdi",
                    f"Confronted strategy {selected.get('strategy_id') if selected else 'NONE'}; score={verdict.survival_score:.1f}",
                )
            ],
        }

    # ------------------------------------------------------------------
    # 7. Compuerta de riesgo
    # ------------------------------------------------------------------
    def risk_gate_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TradingRequest.from_dict(state["request"])
        selected = state.get("selected_strategy") or {}
        actions = [AgentAction(**a) for a in selected.get("actions", [])]
        portfolio = request.portfolio or Portfolio()
        snapshots_data = state.get("snapshots", {})
        prices = {s: snap["latest_price"] for s, snap in snapshots_data.items()}

        assessment = self.risk_engine.check_strategy(actions, portfolio, prices)
        if not assessment.allowed:
            return {
                "status": "blocked",
                "risk_decision": assessment.to_dict(),
                "reflections": [self._reflection("risk", f"Strategy blocked: {assessment.reasons}")],
                "logs": [self._log("risk", "Strategy blocked")],
            }
        return {
            "status": "awaiting_confirmation",
            "risk_decision": assessment.to_dict(),
            "requires_confirmation": self.config.agent.require_confirmation,
            "reflections": [
                self._reflection(
                    "risk",
                    f"Risk gate passed with score {assessment.risk_score:.4f}.",
                )
            ],
            "logs": [self._log("risk", "Risk gate passed")],
        }

    # ------------------------------------------------------------------
    # 8. Confirmación / Ejecución
    # ------------------------------------------------------------------
    def confirm_or_execute_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TradingRequest.from_dict(state["request"])
        selected = state.get("selected_strategy") or {}
        if not selected:
            return {
                "status": "failed",
                "reflections": [self._reflection("executor", "No strategy selected")],
            }

        if self.config.agent.require_confirmation and not request.approved:
            return {
                "status": "awaiting_confirmation",
                "requires_confirmation": True,
                "reflections": [
                    self._reflection("executor", "Strategy ready but requires user approval.")
                ],
                "logs": [self._log("executor", "Awaiting confirmation")],
            }
        return {"status": "executing", "requires_confirmation": False}

    def execute_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        request = TradingRequest.from_dict(state["request"])
        portfolio = (request.portfolio or Portfolio()).copy()
        selected = state.get("selected_strategy") or {}
        actions = [AgentAction(**a) for a in selected.get("actions", [])]
        snapshots_data = state.get("snapshots", {})
        results: List[Dict[str, Any]] = []
        all_success = True
        prices = {s: snap["latest_price"] for s, snap in snapshots_data.items()}

        for action in actions:
            price = prices.get(action.symbol, action.price)
            execution = self.exchange.submit_order(action, portfolio, price=price)
            results.append(execution.to_dict())
            if execution.status != "FILLED" or execution.filled_quantity == 0 and action.side != "HOLD":
                all_success = False
            self.risk_engine.register_outcome(execution.status == "FILLED")

        observations = []
        for action, exec_result in zip(actions, results):
            success = exec_result.get("status") == "FILLED"
            observations.append(
                WorldModelObservation(
                    action_type=action.side,
                    item_id=action.symbol,
                    symbol=action.symbol,
                    predicted_success_prob=action.confidence,
                    actual_success=success,
                    actual_cost=exec_result.get("fill_price", 0.0) * exec_result.get("filled_quantity", 0.0),
                    reward=exec_result.get("realized_pnl", 0.0),
                ).to_dict()
            )

        return {
            "status": "learning",
            "execution_result": {
                "strategy_id": selected.get("strategy_id"),
                "actions": results,
                "success": all_success,
            },
            "observations": observations,
            "portfolio": portfolio.to_dict(),
            "reflections": [
                self._reflection(
                    "executor",
                    f"Executed {len(actions)} actions. Success={all_success}.",
                )
            ],
            "logs": [self._log("executor", f"Executed strategy {selected.get('strategy_id')}")],
        }

    # ------------------------------------------------------------------
    # 9. Aprender del entorno real
    # ------------------------------------------------------------------
    def learn_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        for obs_data in state.get("observations", []):
            obs = WorldModelObservation(**obs_data)
            self.world_model.update_from_observation(obs)
        if self.world_model.observations_since_train >= self.config.model.probabilistic.retrain_after:
            self.world_model.retrain()
        return {
            "status": "done",
            "world_model": self.world_model.to_dict(),
            "reflections": [
                self._reflection(
                    "monitor",
                    f"Updated world model with {len(state.get('observations', []))} observations. "
                    f"Observations_since_train={self.world_model.observations_since_train}.",
                )
            ],
            "logs": [self._log("monitor", "World model updated")],
        }

    # ------------------------------------------------------------------
    # Finalizador
    # ------------------------------------------------------------------
    def finalize(self, state: Dict[str, Any]) -> Dict[str, Any]:
        status = state.get("status", "done")
        if status not in ("done", "awaiting_input", "awaiting_confirmation", "blocked", "failed"):
            status = "done"
        request = TradingRequest.from_dict(state["request"])
        selected = state.get("selected_strategy") or {}
        output = {
            "request_id": request.request_id,
            "user_id": request.user_id,
            "status": status,
            "mode": request.mode,
            "snapshots": state.get("snapshots", {}),
            "signals": state.get("signals", []),
            "juice_validations": state.get("juice_validations", []),
            "approved_signals": state.get("approved_signals", []),
            "bdi_state": state.get("bdi_state"),
            "juice_verdict": state.get("juice_verdict"),
            "selected_strategy": selected,
            "candidates": state.get("candidates", []),
            "evaluations": state.get("evaluations", []),
            "risk_decision": state.get("risk_decision"),
            "execution_result": state.get("execution_result"),
            "portfolio": state.get("portfolio"),
            "world_model": state.get("world_model", {}),
            "reflections": state.get("reflections", []),
            "logs": state.get("logs", []),
            "missing_info": state.get("missing_info", []),
            "requires_confirmation": state.get("requires_confirmation", False),
        }
        return {"status": status, "final_output": output}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _initial_world_state(
        self,
        request: TradingRequest,
        portfolio: Portfolio,
        snapshots_data: Dict[str, Any],
    ) -> WorldModelState:
        # Usa el primer símbolo como referencia para simulación
        symbol = request.symbols[0] if request.symbols else list(snapshots_data.keys())[0]
        snap = snapshots_data.get(symbol, {})
        price = snap.get("latest_price", 0.0)
        return WorldModelState(
            request_id=request.request_id,
            symbol=symbol,
            price=price,
            cash=portfolio.cash,
            position=portfolio.positions.get(symbol, 0.0),
            features=snap.get("features", {}),
            portfolio_value=portfolio.market_value({symbol: price}),
        )


class TransitionAdapter:
    """Genera una transición resumida a partir de una estrategia y simulación."""

    def __init__(self, actions: List[Any], sim: Dict[str, Any]) -> None:
        self.actions = actions
        self.sim = sim

    def to_transition(self):
        from models import Transition

        return Transition(
            prev_state={"actions": [a.to_dict() for a in self.actions]},
            action=self.actions[0].to_dict() if self.actions else {},
            next_state=self.sim.get("outcome", {}),
            reward=self.sim.get("utility", 0.0),
            probability=1.0,
            info={"source": "simulated_rollout"},
        )
