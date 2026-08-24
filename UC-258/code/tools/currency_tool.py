"""Herramienta simulada de conversión de divisas."""
from __future__ import annotations

from typing import Any

from models import ExternalData
from tools.base import ExternalTool


class CurrencyConverterTool(ExternalTool):
    """Conversor de divisas simulado con tasa fija de referencia."""

    name = "currency_converter"

    RATES = {
        "USD": 1.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "JPY": 150.0,
        "COP": 3900.0,
    }

    def call(self, amount: float, from_currency: str, to_currency: str, **kwargs: Any) -> ExternalData:
        from_rate = self.RATES.get(from_currency.upper())
        to_rate = self.RATES.get(to_currency.upper())
        if from_rate is None or to_rate is None:
            return ExternalData(
                value=None,
                source="currency_converter",
                confidence=0.0,
                verified=False,
                note=f"Moneda no soportada: {from_currency} -> {to_currency}",
            )
        converted = amount * (to_rate / from_rate)
        return ExternalData(
            value=round(converted, 2),
            source="simulated_ecb_rates",
            confidence=0.95,
            verified=True,
            note="Tasa referencial simulada. Usar proveedor financiero real en producción.",
        )
