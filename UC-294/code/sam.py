"""Situational Awareness Middleware (SAM) para UC-294.

Implementa una arquitectura inspirada en Global Workspace Theory (GWT) con
conciencia funcional: Self-Model, Memoria Episódica, Workspace Global y Monitor
Metacognitivo. Toda la comunicación interna sigue un contrato JSON estricto.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models import (
    EnvironmentState,
    MemoryEpisode,
    RiskConstraints,
    SAMState,
    SelfModel,
    TradingRequest,
    WorkspaceContent,
)


class Envelope:
    """Sobre JSON estricto para trazabilidad de mensajes entre módulos SAM."""

    @staticmethod
    def pack(
        source: str,
        destination: str,
        message_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "envelope_version": "1.0",
            "source": source,
            "destination": destination,
            "message_type": message_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "metadata": metadata or {},
        }

    @staticmethod
    def unpack(envelope: Dict[str, Any]) -> Dict[str, Any]:
        return envelope.get("payload", {})


class SituationalAwarenessMiddleware:
    """Middleware que centraliza percepción, workspace, memoria y self-model."""

    def __init__(
        self,
        agent_identity: str = "UC294.Alpha",
        max_memory_items: int = 7,
        confidence_recovery_rate: float = 0.1,
    ) -> None:
        self.self_model = SelfModel(
            agent_identity=agent_identity,
            max_memory_items=max_memory_items,
        )
        self.working_memory: List[MemoryEpisode] = []
        self.max_memory_items = max_memory_items
        self.confidence_recovery_rate = confidence_recovery_rate
        self.envelope = Envelope()
        self.tick_counter = 0

    # ------------------------------------------------------------------
    # Percepción + Inyección dinámica de contexto
    # ------------------------------------------------------------------
    def perceive_environment(
        self,
        request: TradingRequest,
        snapshots: Dict[str, Any],
        alerts: Optional[List[str]] = None,
    ) -> EnvironmentState:
        """Construye el 'Aquí y Ahora' a partir del request y snapshots."""
        now = datetime.now(timezone.utc)
        # Calidad de datos: proporción de ticks esperados vs recibidos
        expected = max(1, request.config.features.history_window if hasattr(request, "config") else 50)
        ticks_count = len(request.ticks)
        data_quality = min(1.0, ticks_count / expected)
        # Determinar salud API y volatilidad a partir de snapshots
        api_health = "HEALTHY"
        market_volatility = "NORMAL"
        if not snapshots:
            api_health = "DEGRADED"
        else:
            snap = list(snapshots.values())[0]
            vol = snap.get("features", {}).get("volatility", 0.0)
            if vol > 0.05:
                market_volatility = "HIGH"
            elif vol > 0.02:
                market_volatility = "ELEVATED"
            if data_quality < 0.5:
                api_health = "DEGRADED"

        return EnvironmentState(
            system_clock=now.isoformat(),
            api_health=api_health,
            market_volatility=market_volatility,
            active_alerts=alerts or [],
            data_quality=data_quality,
            latency_ms=0.0,
        )

    def store_episode(
        self,
        event_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEpisode:
        """Almacena un episodio en memoria de trabajo (limitada)."""
        self.tick_counter += 1
        episode = MemoryEpisode(
            tick=self.tick_counter,
            event_type=event_type,
            content=content,
            metadata=metadata or {},
        )
        self.working_memory.append(episode)
        if len(self.working_memory) > self.max_memory_items:
            self.working_memory.pop(0)
        if event_type in ("ACTION", "OBSERVATION"):
            self._update_metacognition()
        return episode

    def _update_metacognition(self) -> None:
        """Actualiza Self-Model con base en episodios recientes."""
        recent = self.working_memory[-self.max_memory_items :]
        failed = sum(
            1
            for ep in recent
            if ep.event_type in ("ACTION", "OBSERVATION")
            and ("ERROR" in ep.content.upper() or "FALLO" in ep.content.upper() or "REJECTED" in ep.content.upper())
        )
        self.self_model.recent_errors = failed
        if failed >= 2:
            self.self_model.confidence_level = max(0.1, self.self_model.confidence_level - 0.3)
            self.self_model.cognitive_load = "HIGH"
        elif failed == 1:
            self.self_model.confidence_level = max(0.4, self.self_model.confidence_level - 0.1)
            self.self_model.cognitive_load = "MEDIUM"
        else:
            self.self_model.confidence_level = min(
                1.0, self.self_model.confidence_level + self.confidence_recovery_rate
            )
            self.self_model.cognitive_load = "LOW"

    # ------------------------------------------------------------------
    # Global Workspace Theory: competencia, selección y broadcast
    # ------------------------------------------------------------------
    def build_workspace(
        self,
        request: TradingRequest,
        snapshots: Dict[str, Any],
        signals: List[Dict[str, Any]],
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        alerts: Optional[List[str]] = None,
    ) -> WorkspaceContent:
        """Compila el workspace global a partir de percepción, memoria y self-model."""
        env = self.perceive_environment(request, snapshots, alerts=alerts)
        memory_payload = [ep.to_dict() for ep in self.working_memory]

        # Selección saliente: hipótesis con mayor confianza y menor riesgo
        selected = None
        if hypotheses:
            ranked = sorted(
                hypotheses,
                key=lambda h: (
                    h.get("confidence", 0.0),
                    -h.get("risk_score", 1.0),
                ),
                reverse=True,
            )
            if ranked and ranked[0].get("confidence", 0) >= 0.5:
                selected = ranked[0]

        workspace = WorkspaceContent(
            perception={"snapshots": snapshots, "signals": signals},
            environment=env.to_dict(),
            self_model=self.self_model.to_dict(),
            memory=memory_payload,
            hypotheses=hypotheses or [],
            selected_hypothesis=selected,
            broadcast={
                "capacity": self.max_memory_items,
                "selected": selected,
                "flags": [],
            },
        )
        # Si hay alertas activas, marcar broadcast
        if env.active_alerts or env.api_health != "HEALTHY":
            workspace.broadcast["flags"].append("context_alert")
        if self.self_model.confidence_level < 0.5:
            workspace.broadcast["flags"].append("low_self_confidence")
        if env.market_volatility == "HIGH":
            workspace.broadcast["flags"].append("high_volatility")
        return workspace

    def broadcast_to_modules(self, workspace: WorkspaceContent) -> List[Dict[str, Any]]:
        """Simula el broadcast del contenido seleccionado a todos los módulos."""
        broadcast = workspace.broadcast
        messages: List[Dict[str, Any]] = []
        for module in ("risk", "strategy", "execution", "memory", "metacognition"):
            messages.append(
                self.envelope.pack(
                    source="global_workspace",
                    destination=module,
                    message_type="broadcast",
                    payload=workspace.to_dict(),
                    metadata={"flag": broadcast.get("flags", [])},
                )
            )
        return messages


class MetacognitionModule:
    """Monitor metacognitivo: evalúa calidad del razonamiento y decide control."""

    def evaluate(
        self,
        workspace: WorkspaceContent,
        selected_strategy: Optional[Dict[str, Any]] = None,
        constraints: Optional[RiskConstraints] = None,
    ) -> Dict[str, Any]:
        """Devuelve dictamen metacognitivo con flags de control ejecutivo."""
        sm = workspace.self_model
        env = workspace.environment
        issues: List[str] = []
        controls: List[str] = []

        confidence = sm.get("confidence_level", 1.0)
        if confidence < 0.5:
            issues.append(f"baja_confianza_self: {confidence:.2f}")
            controls.append("ask_human_help")
        if env.get("api_health") != "HEALTHY":
            issues.append(f"api_degradada: {env.get('api_health')}")
            controls.append("reflect")
        if env.get("market_volatility") == "HIGH":
            issues.append("alta_volatilidad_mercado")
            controls.append("reduce_exposure")
        if env.get("data_quality", 1.0) < 0.5:
            issues.append(f"baja_calidad_datos: {env.get('data_quality')}")
            controls.append("ask_human_help")

        # Conflicto entre módulos: si señales contradictorias fuertes
        sides = [s.get("side") for s in workspace.perception.get("signals", []) if s.get("side") in ("BUY", "SELL")]
        if "BUY" in sides and "SELL" in sides:
            issues.append("conflicto_senales_buy_sell")
            controls.append("reflect")

        # Alineación tarea-capacidad
        if selected_strategy:
            actions = selected_strategy.get("actions", [])
            if actions:
                side = actions[0].get("side", "HOLD")
                profile = sm.get("competence_profile", {})
                capability = profile.get(f"{side.lower()}_execution", 0.5)
                if capability < 0.6:
                    issues.append(f"capacidad_limitada_{side}: {capability}")
                    controls.append("delegate")

        need_review = bool(issues)
        abort = confidence < 0.3 or env.get("api_health") == "DEGRADED" and env.get("data_quality", 1.0) < 0.3

        return {
            "assessment_id": sm.get("self_model_id", "meta"),
            "confidence_level": confidence,
            "issues": issues,
            "controls": list(set(controls)),
            "need_review": need_review,
            "abort": abort,
            "recommendation": (
                "ABORT" if abort else ("REVIEW" if need_review else "PROCEED")
            ),
        }


class SafetySupervisor:
    """Última barrera de seguridad antes de la ejecución de una acción."""

    def check(
        self,
        strategy: Dict[str, Any],
        request: TradingRequest,
        snapshots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Verifica precondiciones de seguridad y genera rollback plan."""
        issues: List[str] = []
        allowed = True
        constraints = request.constraints or RiskConstraints()
        actions = strategy.get("actions", []) if strategy else []
        if not actions:
            return {"allowed": True, "issues": [], "rollback": None}

        portfolio = request.portfolio
        total_value = portfolio.cash if portfolio else 0.0
        for symbol, snap in snapshots.items():
            price = snap.get("latest_price", 0.0)
            qty = portfolio.positions.get(symbol, 0.0) if portfolio else 0.0
            total_value += qty * price

        notional = 0.0
        for action in actions:
            price = action.get("price", 0.0) or snapshots.get(action.get("symbol", ""), {}).get("latest_price", 0.0)
            qty = action.get("quantity", 0.0)
            notional += price * qty
            if action.get("side") in ("BUY", "SELL") and action.get("confidence", 0.0) < constraints.min_signal_confidence:
                issues.append("confianza_baja")
                allowed = False
            if not action.get("stop_loss"):
                issues.append("stop_loss_missing")
                allowed = False

        if total_value > 0 and notional / total_value > constraints.max_position_pct:
            issues.append("exposicion_maxima_superada")
            allowed = False

        rollback = {
            "action": "REVERT_TO_HOLD",
            "cancel_open_orders": True,
            "notify": True,
        }

        return {"allowed": allowed, "issues": issues, "rollback": rollback}
