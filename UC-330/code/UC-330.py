"""
Codificando.AI
UC-330: Exploitation–Exploration Governance — Balance Adaptativo para AGI.

Capa de control del equilibrio entre exploración y explotación para UTRON.ai AGI.
Garantiza que la exploración ocurra solo en sandbox y que las acciones de
producción sean explotadoras y autorizadas.

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

from typing import List, Dict, Optional, Any

from balance_ex_models import BalanceExConfig, ContextSnapshot
from balance_ex_engine import BalanceExEngine


class UCBalanceExLayer:
    """Wrapper de alto nivel para UC-330 Balance-EX."""

    def __init__(
        self,
        actions: List[str],
        feature_keys: List[str],
        config: Optional[BalanceExConfig] = None,
    ):
        self.engine = BalanceExEngine(
            actions=actions,
            feature_keys=feature_keys,
            config=config,
        )

    def decide(
        self,
        context: Dict[str, float],
        domain: str = "default",
        environment: str = "sandbox",
        authorized_actions: Optional[List[str]] = None,
        risk_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Decide modo y acción para un contexto."""
        snapshot = ContextSnapshot(features=context, domain=domain)
        decision = self.engine.decide(
            context=snapshot,
            environment=environment,
            authorized_actions=authorized_actions,
            risk_score=risk_score,
        )
        return decision.to_dict()

    def update(
        self,
        decision: Dict[str, Any],
        context: Dict[str, float],
        reward: float,
        next_context: Optional[Dict[str, float]] = None,
        domain: str = "default",
    ) -> Dict[str, Any]:
        """Actualiza modelos con el resultado de una acción."""
        from balance_ex_models import Decision, ExplorationStrategy
        dec = Decision(
            decision_id=decision.get("decision_id", ""),
            mode=decision.get("mode", "exploit"),
            strategy=decision.get("strategy", "random"),
            action=decision.get("action", ""),
            epsilon=float(decision.get("epsilon", 0.0)),
            uncertainty=float(decision.get("uncertainty", 0.0)),
            risk_score=float(decision.get("risk_score", 0.0)),
            justification=decision.get("justification", ""),
            metadata=decision.get("metadata", {}),
        )
        snapshot = ContextSnapshot(features=context, domain=domain)
        next_snapshot = None
        if next_context is not None:
            next_snapshot = ContextSnapshot(features=next_context, domain=domain)
        record = self.engine.update(dec, snapshot, reward, next_snapshot)
        return record.to_dict()

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del motor."""
        return self.engine.get_statistics()

    def recommend(self) -> List[str]:
        """Retorna recomendaciones basadas en métricas."""
        return self.engine.recommend()

    def reset(self) -> None:
        """Reinicia el motor."""
        self.engine.reset()


def demo() -> None:
    """Demostración de UC-330 Balance-EX."""
    print("=" * 80)
    print("UC-330 — Exploitation–Exploration Governance")
    print("=" * 80)

    actions = ["buy_tech", "buy_health", "buy_energy", "hold", "sell"]
    features = ["volatility", "volume", "sentiment"]
    layer = UCBalanceExLayer(
        actions=actions,
        feature_keys=features,
        config=BalanceExConfig(
            epsilon_initial=0.3,
            epsilon_min=0.05,
            decay_rate=0.99,
            exploration_budget=100.0,
        ),
    )

    # Simulación: episodio en sandbox
    contexts = [
        {"volatility": 0.2, "volume": 0.5, "sentiment": 0.6},
        {"volatility": 0.4, "volume": 0.7, "sentiment": 0.3},
        {"volatility": 0.1, "volume": 0.3, "sentiment": 0.8},
        {"volatility": 0.5, "volume": 0.9, "sentiment": 0.2},
        {"volatility": 0.2, "volume": 0.4, "sentiment": 0.7},
    ]
    rewards = [0.5, -0.2, 0.8, -0.1, 0.6]

    print("\nRunning sandbox episode...")
    result = layer.engine.run_episode(
        contexts=[ContextSnapshot(features=c) for c in contexts],
        rewards=rewards,
        environment="sandbox",
    )

    print(f"Total steps: {result.metrics.total_steps}")
    print(f"Exploration rate: {result.metrics.exploration_rate:.2%}")
    print(f"Success rate: {result.metrics.success_rate:.2%}")
    print(f"Average reward: {result.metrics.avg_reward:.4f}")
    print(f"Regret: {result.metrics.regret:.4f}")
    print(f"Recommendations: {result.recommendations}")

    print("\n--- Production decision ---")
    decision = layer.decide(
        context={"volatility": 0.15, "volume": 0.4, "sentiment": 0.75},
        environment="production",
        authorized_actions=["buy_tech", "hold"],
        risk_score=0.2,
    )
    print(f"Mode: {decision['mode']}")
    print(f"Action: {decision['action']}")
    print(f"Justification: {decision['justification']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    demo()
