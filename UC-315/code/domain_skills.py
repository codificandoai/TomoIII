"""UC-315 — Skills de dominio para trading y reservas de viajes.

Cada skill encapsula una capacidad operacional y expone un `executor` simulado.
No comparten credenciales, datos ni políticas con otros dominios.
"""
from __future__ import annotations

from skill_contracts import ActionClass, RiskLevel, SkillContract, SkillParameter


# -----------------------------------------------------------------------------
# Trading skills
# -----------------------------------------------------------------------------
def _market_data_executor(inputs: dict, domain: str) -> dict:
    symbol = inputs.get("symbol", "UNKNOWN")
    return {
        "domain": domain,
        "symbol": symbol,
        "bid": 150.25,
        "ask": 150.30,
        "feed_quality": "OK",
    }


def _market_prediction_executor(inputs: dict, domain: str) -> dict:
    symbol = inputs.get("symbol", "UNKNOWN")
    return {
        "domain": domain,
        "symbol": symbol,
        "predicted_bid": 151.10,
        "predicted_ask": 151.15,
        "confidence": 0.78,
        "side": "BUY",
    }


def _financial_risk_executor(inputs: dict, domain: str) -> dict:
    exposure = inputs.get("exposure_usd", 0.0)
    limit = inputs.get("limit_usd", 1_000_000.0)
    within_limit = exposure <= limit
    return {
        "domain": domain,
        "exposure_usd": exposure,
        "limit_usd": limit,
        "allowed": within_limit,
        "margin_utilization": exposure / limit if limit else 0.0,
    }


def _market_execution_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "order_id": "ORD-12345",
        "status": "FILLED",
        "filled_price": inputs.get("limit_price", 150.30),
        "quantity": inputs.get("quantity", 100),
    }


# -----------------------------------------------------------------------------
# Reservation skills
# -----------------------------------------------------------------------------
def _flight_search_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "origin": inputs.get("origin"),
        "destination": inputs.get("destination"),
        "date": inputs.get("date"),
        "options": [
            {"flight": "AA101", "departure": "08:00", "price": 320.0, "seats": 12},
            {"flight": "DL405", "departure": "14:30", "price": 275.0, "seats": 4},
        ],
    }


def _rail_search_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "origin": inputs.get("origin"),
        "destination": inputs.get("destination"),
        "date": inputs.get("date"),
        "options": [
            {"train": "AVE123", "departure": "09:15", "price": 95.0, "seats": 45},
            {"train": "REG456", "departure": "11:00", "price": 55.0, "seats": 120},
        ],
    }


def _payment_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "transaction_id": "TX-98765",
        "amount": inputs.get("amount"),
        "currency": inputs.get("currency", "USD"),
        "status": "AUTHORIZED",
    }


def _identity_validation_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "user_id": inputs.get("user_id"),
        "verified": True,
        "method": "KYC_DOCUMENT",
    }


def _notification_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "channel": inputs.get("channel", "email"),
        "recipient": inputs.get("to"),
        "status": "SENT",
    }


def _change_cancel_executor(inputs: dict, domain: str) -> dict:
    return {
        "domain": domain,
        "reservation_id": inputs.get("reservation_id"),
        "action": inputs.get("action"),
        "refund_amount": 120.0 if inputs.get("action") == "cancel" else 0.0,
        "status": "CONFIRMED",
    }


# -----------------------------------------------------------------------------
# Factory de contratos
# -----------------------------------------------------------------------------
def trading_skills() -> list:
    return [
        SkillContract(
            name="MarketDataSkill",
            domain="trading",
            purpose="Ingesta de datos de mercado: precios bid/ask, libros de órdenes y calidad del feed.",
            inputs=[SkillParameter("symbol", "string", "Símbolo del activo.", True)],
            outputs=[SkillParameter("bid", "float"), SkillParameter("ask", "float"), SkillParameter("feed_quality", "string")],
            action_class=ActionClass.READ,
            estimated_cost=0.1,
            estimated_latency_ms=10.0,
            preconditions=["Conexión a feed de mercado activa"],
            postconditions=["Datos de mercado disponibles para el símbolo"],
            risk_level=RiskLevel.LOW,
            executor=_market_data_executor,
        ),
        SkillContract(
            name="MarketPredictionSkill",
            domain="trading",
            purpose="Generación de señales y estimaciones de precio; sin autoridad para ejecutar órdenes.",
            inputs=[SkillParameter("symbol", "string", "Símbolo del activo.", True)],
            outputs=[SkillParameter("predicted_bid", "float"), SkillParameter("predicted_ask", "float"), SkillParameter("confidence", "float"), SkillParameter("side", "string")],
            action_class=ActionClass.PREDICT,
            estimated_cost=0.5,
            estimated_latency_ms=50.0,
            preconditions=["Datos de mercado recientes disponibles"],
            postconditions=["Señal generada con confianza"],
            risk_level=RiskLevel.LOW,
            reversible=True,
            executor=_market_prediction_executor,
        ),
        SkillContract(
            name="FinancialRiskSkill",
            domain="trading",
            purpose="Cálculo determinista de exposición, límites de posición, pérdidas y liquidez permitida.",
            inputs=[SkillParameter("exposure_usd", "float", "Exposición actual.", True), SkillParameter("limit_usd", "float", "Límite permitido.", True)],
            outputs=[SkillParameter("allowed", "boolean"), SkillParameter("margin_utilization", "float")],
            action_class=ActionClass.ANALYZE,
            estimated_cost=0.05,
            estimated_latency_ms=5.0,
            preconditions=["Exposición y límites definidos"],
            postconditions=["Decisión de riesgo determinista emitida"],
            risk_level=RiskLevel.MEDIUM,
            executor=_financial_risk_executor,
        ),
        SkillContract(
            name="MarketExecutionSkill",
            domain="trading",
            purpose="Envío de órdenes al mercado únicamente tras autorización de riesgo.",
            inputs=[SkillParameter("symbol", "string", True), SkillParameter("side", "string", True), SkillParameter("quantity", "integer", True), SkillParameter("limit_price", "float", True)],
            outputs=[SkillParameter("order_id", "string"), SkillParameter("status", "string"), SkillParameter("filled_price", "float")],
            permissions=["market.order.send"],
            required_roles=["trader"],
            action_class=ActionClass.EXECUTE,
            estimated_cost=2.0,
            estimated_latency_ms=30.0,
            preconditions=["Validación de riesgo aprobada", "Circuit breaker abierto"],
            postconditions=["Orden enviada y confirmada por el exchange"],
            risk_level=RiskLevel.CRITICAL,
            reversible=False,
            compensation="CancelOrderSkill",
            executor=_market_execution_executor,
        ),
    ]


def reservation_skills() -> list:
    return [
        SkillContract(
            name="FlightBookingSkill",
            domain="reservations",
            purpose="Búsqueda de vuelos, tarifas, horarios, disponibilidad y selección de itinerario.",
            inputs=[SkillParameter("origin", "string", True), SkillParameter("destination", "string", True), SkillParameter("date", "string", True)],
            outputs=[SkillParameter("options", "list")],
            action_class=ActionClass.READ,
            estimated_cost=0.2,
            estimated_latency_ms=200.0,
            preconditions=["Origen, destino y fecha válidos"],
            postconditions=["Opciones de vuelo disponibles"],
            risk_level=RiskLevel.LOW,
            executor=_flight_search_executor,
        ),
        SkillContract(
            name="RailBookingSkill",
            domain="reservations",
            purpose="Búsqueda de trayectos ferroviarios, tarifas, horarios y disponibilidad.",
            inputs=[SkillParameter("origin", "string", True), SkillParameter("destination", "string", True), SkillParameter("date", "string", True)],
            outputs=[SkillParameter("options", "list")],
            action_class=ActionClass.READ,
            estimated_cost=0.2,
            estimated_latency_ms=200.0,
            preconditions=["Origen, destino y fecha válidos"],
            postconditions=["Opciones de tren disponibles"],
            risk_level=RiskLevel.LOW,
            executor=_rail_search_executor,
        ),
        SkillContract(
            name="PaymentSkill",
            domain="reservations",
            purpose="Procesamiento de pagos tras confirmación de disponibilidad y consentimiento.",
            inputs=[SkillParameter("amount", "float", True), SkillParameter("currency", "string", False), SkillParameter("payment_method", "string", True)],
            outputs=[SkillParameter("transaction_id", "string"), SkillParameter("status", "string")],
            permissions=["payment.charge"],
            required_roles=["payment_processor"],
            action_class=ActionClass.TRANSACT,
            estimated_cost=1.0,
            estimated_latency_ms=300.0,
            preconditions=["Disponibilidad confirmada", "Precio confirmado", "Consentimiento del usuario", "Medio de pago autorizado"],
            postconditions=["Pago autorizado y registrado"],
            risk_level=RiskLevel.HIGH,
            reversible=True,
            compensation="RefundSkill",
            executor=_payment_executor,
        ),
        SkillContract(
            name="IdentityValidationSkill",
            domain="reservations",
            purpose="Verificación de identidad del pasajero antes de la transacción.",
            inputs=[SkillParameter("user_id", "string", True)],
            outputs=[SkillParameter("verified", "boolean"), SkillParameter("method", "string")],
            action_class=ActionClass.ANALYZE,
            estimated_cost=0.3,
            estimated_latency_ms=500.0,
            preconditions=["Identificación proporcionada"],
            postconditions=["Identidad validada o rechazada"],
            risk_level=RiskLevel.MEDIUM,
            executor=_identity_validation_executor,
        ),
        SkillContract(
            name="NotificationSkill",
            domain="reservations",
            purpose="Envío de confirmaciones, alertas y recordatorios al usuario.",
            inputs=[SkillParameter("to", "string", True), SkillParameter("channel", "string", False), SkillParameter("message", "string", True)],
            outputs=[SkillParameter("status", "string")],
            action_class=ActionClass.READ,
            estimated_cost=0.05,
            estimated_latency_ms=50.0,
            risk_level=RiskLevel.LOW,
            executor=_notification_executor,
        ),
        SkillContract(
            name="ChangeCancelSkill",
            domain="reservations",
            purpose="Gestión de cambios y cancelaciones con políticas de reembolso.",
            inputs=[SkillParameter("reservation_id", "string", True), SkillParameter("action", "string", True)],
            outputs=[SkillParameter("refund_amount", "float"), SkillParameter("status", "string")],
            permissions=["reservation.modify"],
            action_class=ActionClass.DELETE,
            estimated_cost=0.5,
            estimated_latency_ms=150.0,
            preconditions=["Reserva existente", "Política de cambio/cancelación aplicable"],
            postconditions=["Reserva modificada o cancelada"],
            risk_level=RiskLevel.MEDIUM,
            reversible=False,
            compensation=None,
            executor=_change_cancel_executor,
        ),
    ]


def build_default_registry():
    """Registro con skills de trading y reservas."""
    from skill_contracts import SkillRegistry
    registry = SkillRegistry()
    for skill in trading_skills() + reservation_skills():
        registry.register(skill)
    return registry
