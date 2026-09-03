"""Filtro adversarial Confrontational Juice para UC-293.

Obliga al agente a confrontar su borrador de intención contra las Creencias
estrictas y los Deseos del sistema antes de comprometerse y actuar.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models import AgentAction, BDIBeliefs, BDIDesires, BDIIntention, JuiceVerdict


class ConfrontationalJuice:
    """Auditor interno que evalúa intenciones BDI mediante lógica estricta."""

    def __init__(self, commit_threshold: float = 80.0, distill_threshold: float = 50.0) -> None:
        self.commit_threshold = commit_threshold
        self.distill_threshold = distill_threshold

    def confront(
        self,
        beliefs: BDIBeliefs,
        desires: BDIDesires,
        intention: BDIIntention,
    ) -> JuiceVerdict:
        """Confronta una intención contra beliefs/desires y devuelve un veredicto."""
        issues: List[str] = []
        score = 100.0
        corrected = intention.model_copy(deep=True)

        # ------------------------------------------------------------------
        # 1. Restricciones duras (hard constraints)
        # ------------------------------------------------------------------
        action = corrected.planned_action.upper()
        actions = corrected.actions

        # Si la intención es HOLD o ESCALATE_HUMAN, no hay riesgo operativo.
        if action in ("HOLD", "ESCALATE_HUMAN"):
            corrected.status = "distilled" if action == "HOLD" else "rejected"
            corrected.justification = "Acción neutra o escalamiento humano. Sin compromiso automático."
            corrected.survival_score = 100.0 if action == "HOLD" else 0.0
            return JuiceVerdict(
                approved=action == "HOLD",
                survival_score=corrected.survival_score,
                issues=[],
                corrected_intention=corrected.to_dict(),
                confidence=1.0,
            )

        main_action = actions[0] if actions else AgentAction(side=action)
        price = main_action.price or beliefs.current_price
        quantity = main_action.quantity
        stop_loss = main_action.stop_loss
        take_profit = main_action.take_profit
        confidence = main_action.confidence

        # 1.1 Confianza mínima de señal
        if confidence < desires.min_signal_confidence:
            issues.append(
                f"confianza_baja: {confidence:.2f} < {desires.min_signal_confidence}"
            )
            score -= 25.0

        # 1.2 Sin stop-loss / take-profit requeridos
        if desires.require_stop_loss and (stop_loss is None or stop_loss <= 0):
            issues.append("stop_loss_missing")
            score -= 15.0
        if desires.require_take_profit and (take_profit is None or take_profit <= 0):
            issues.append("take_profit_missing")
            score -= 10.0

        # 1.3 Incertidumbre del world model demasiado alta
        if beliefs.world_model_uncertainty > desires.max_uncertainty:
            issues.append(
                f"incertidumbre_alta: {beliefs.world_model_uncertainty:.2f} > {desires.max_uncertainty}"
            )
            score -= 20.0

        # 1.4 Volatilidad extrema -> no operar
        if beliefs.volatility > 0.05:
            issues.append(f"volatilidad_extrema: {beliefs.volatility:.4f}")
            score -= 20.0

        # ------------------------------------------------------------------
        # 2. Coherencia con Creencias técnicas
        # ------------------------------------------------------------------
        # 2.1 Operar en contra de la tendencia
        if action == "BUY" and beliefs.trend_direction < 0:
            issues.append("buy_contra_tendencia_bajista")
            score -= 15.0
        if action == "SELL" and beliefs.trend_direction > 0:
            issues.append("sell_contra_tendencia_alcista")
            score -= 15.0

        # 2.2 RSI extremo
        if action == "BUY" and beliefs.rsi > 70:
            issues.append("buy_en_sobrecompra_rsi")
            score -= 10.0
        if action == "SELL" and beliefs.rsi < 30:
            issues.append("sell_en_sobraventa_rsi")
            score -= 10.0

        # 2.3 Sentimiento contradictorio
        if action == "BUY" and beliefs.news_sentiment < -0.4:
            issues.append("buy_contra_sentimiento_negativo")
            score -= 10.0
        if action == "SELL" and beliefs.news_sentiment > 0.4:
            issues.append("sell_contra_sentimiento_positivo")
            score -= 10.0

        # 2.4 Tamaño de posición vs máximo deseado
        if beliefs.current_price > 0:
            portfolio_value = beliefs.portfolio_cash + beliefs.portfolio_position * beliefs.current_price
            notional = quantity * price
            if portfolio_value > 0 and notional / portfolio_value > desires.max_position_pct:
                issues.append(
                    f"tamanio_excesivo: {notional/portfolio_value:.2%} > {desires.max_position_pct}"
                )
                score -= 20.0

        # 2.5 Precio predicho desfavorable
        if action == "BUY" and beliefs.predicted_next_price < beliefs.current_price * 0.99:
            issues.append("precio_predicho_bajista_para_buy")
            score -= 10.0
        if action == "SELL" and beliefs.predicted_next_price > beliefs.current_price * 1.01:
            issues.append("precio_predicho_alcista_para_sell")
            score -= 10.0

        # ------------------------------------------------------------------
        # 3. Saltos lógicos en la cadena CoT
        # ------------------------------------------------------------------
        observed_high_vol = any("volatilidad" in step.observation.lower() or "volatility" in step.observation.lower() for step in corrected.cot_trace)
        if observed_high_vol and beliefs.volatility > 0.03:
            issues.append("cot_ignora_volatilidad_observada")
            score -= 10.0

        observed_low_confidence = any(step.params.get("confidence", 1.0) < desires.min_signal_confidence for step in corrected.cot_trace if step.action == "analyze_signal")
        if observed_low_confidence and confidence >= desires.min_signal_confidence:
            # No penalizar si la intención final usó otra señal más fuerte
            pass

        # ------------------------------------------------------------------
        # 4. Decisión final
        # ------------------------------------------------------------------
        score = max(0.0, min(100.0, score))

        if score >= self.commit_threshold and not issues:
            corrected.is_committed = True
            corrected.status = "committed"
            corrected.survival_score = score
            corrected.justification = (
                f"JUICE APROBADO: coherencia perfecta con Creencias. Score={score:.1f}."
            )
            return JuiceVerdict(
                approved=True,
                survival_score=score,
                issues=issues,
                corrected_intention=corrected.to_dict(),
                confidence=min(1.0, score / 100.0),
            )

        if score >= self.distill_threshold:
            # Destilar: reducir riesgo, pero mantener acción
            corrected.status = "distilled"
            corrected.survival_score = score
            corrected.justification = (
                f"JUICE DESTILADO: se detectaron {len(issues)} problemas. Score={score:.1f}. "
                "Se reduce tamaño o se ajusta antes de compromiso."
            )
            if corrected.actions:
                for act in corrected.actions:
                    act.quantity *= 0.5  # reducir exposición a la mitad
            return JuiceVerdict(
                approved=False,
                survival_score=score,
                issues=issues,
                corrected_intention=corrected.to_dict(),
                confidence=min(1.0, score / 100.0),
            )

        # Rechazo drástico: fallback seguro
        corrected.planned_action = "HOLD"
        corrected.actions = []
        corrected.status = "rejected"
        corrected.survival_score = score
        corrected.justification = (
            f"JUICE RECHAZADO: {len(issues)} violaciones críticas. Score={score:.1f}. "
            "Fallback a HOLD / ESCALATE_HUMAN."
        )
        return JuiceVerdict(
            approved=False,
            survival_score=score,
            issues=issues,
            corrected_intention=corrected.to_dict(),
            confidence=0.0,
        )

    def confront_dict(
        self,
        beliefs: Dict[str, Any],
        desires: Dict[str, Any],
        intention: Dict[str, Any],
    ) -> JuiceVerdict:
        """Conveniencia para recibir diccionarios (API/CLI)."""
        return self.confront(
            BDIBeliefs(**beliefs),
            BDIDesires(**desires),
            BDIIntention(**intention),
        )
