"""Cliente para el predictor de retrasos de vuelos con fallback robusto."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from config import PredictorConfig, get_config
from models import parse_iso

logger = logging.getLogger("uc260-predictor")


_WEEKDAY_ES = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miercoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sabado",
    "Sunday": "Domingo",
}


def flight_to_prediction_request(flight_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Mapea un ítem de itinerario al formato esperado por el predictor."""
    if flight_item.get("item_type") != "flight":
        return None
    details = flight_item.get("details", {})
    dep = details.get("departure")
    if not dep:
        return None
    dt = parse_iso(dep) or datetime.fromisoformat(dep)
    weekday = _WEEKDAY_ES.get(dt.strftime("%A"), dt.strftime("%A"))
    return {
        "OPERA": details.get("airline", "Unknown"),
        "TIPOVUELO": "I" if details.get("origin") != details.get("destination") else "N",
        "MES": dt.month,
        "DIA": dt.day,
        "DIANOM": weekday,
        "SIGLAORI": details.get("origin", ""),
        "SIGLAPOS": details.get("destination", ""),
        "NROVUELO": details.get("flight_number", flight_item.get("id", "")[-5:]),
        "CLASEVUELO": details.get("cabin_class", "Y"),
        "TIPOPLANO": details.get("aircraft_type", "B738"),
    }


class FlightDelayPredictor:
    """Cliente para el servicio de predicción de retrasos.

    Si el servicio no responde, devuelve un fallback que indica la incertidumbre
    para que el agente BDI decida con cautela.
    """

    def __init__(self, config: Optional[PredictorConfig] = None) -> None:
        self.config = config or get_config().predictor

    def predict(self, flight_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = [r for r in (flight_to_prediction_request(f) for f in flight_items) if r]
        if not payload:
            return {
                "success": False,
                "source": "fallback",
                "error": "No valid flights to predict",
                "predictions": [],
            }

        try:
            response = requests.post(
                self.config.url,
                json={"flights": payload},
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            predictions = self._normalize_predictions(data, len(payload))
            return {
                "success": True,
                "source": "flight_delays_api",
                "predictions": predictions,
            }
        except requests.exceptions.Timeout:
            logger.warning("Flight delay predictor timed out after %ss", self.config.timeout)
            return self._fallback(payload, "timeout")
        except requests.exceptions.RequestException as exc:
            logger.warning("Flight delay predictor request failed: %s", exc)
            return self._fallback(payload, str(exc))
        except Exception as exc:
            logger.warning("Flight delay predictor unexpected error: %s", exc)
            return self._fallback(payload, str(exc))

    def _fallback(self, payload: List[Dict[str, Any]], error: str) -> Dict[str, Any]:
        return {
            "success": False,
            "source": "fallback",
            "error": error,
            "predictions": [
                {
                    "flight_index": i,
                    "delay_probability": 0.0,
                    "predicted_delay_minutes": 0,
                    "confidence": 0.5,
                    "fallback": True,
                }
                for i in range(len(payload))
            ],
        }

    def _normalize_predictions(self, data: Any, count: int) -> List[Dict[str, Any]]:
        """Acepta distintos formatos de respuesta y los normaliza."""
        predictions: List[Dict[str, Any]] = []
        raw_list: List[Any] = []
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            raw_list = data.get("predictions") or data.get("flights") or [data]

        for i in range(count):
            raw = raw_list[i] if i < len(raw_list) else {}
            if not isinstance(raw, dict):
                raw = {"prediction": raw}
            prob = self._extract_number(
                raw,
                ["delay_probability", "probability", "delay_prob", "prob"],
                default=0.0,
            )
            minutes = self._extract_number(
                raw,
                ["predicted_delay_minutes", "delay_minutes", "predicted_delay", "delay"],
                default=0,
            )
            predictions.append(
                {
                    "flight_index": i,
                    "delay_probability": float(prob),
                    "predicted_delay_minutes": int(minutes),
                    "confidence": float(raw.get("confidence", 0.85)),
                }
            )
        return predictions

    @staticmethod
    def _extract_number(data: Dict[str, Any], keys: List[str], default: Any) -> Any:
        for key in keys:
            val = data.get(key)
            if val is not None:
                try:
                    return type(default)(val)
                except (TypeError, ValueError):
                    continue
        return default
