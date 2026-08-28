"""Adaptador del modelo de retraso de vuelos de flight-delays para UC-265.

Carga el modelo entrenado (model.pkl) y expone una función para predecir la
probabilidad de retraso (>15 min) de un vuelo a partir de los datos disponibles
en las acciones del planner.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# El módulo del challenge no está en PYTHON_PATH por defecto. Lo añadimos
code_dir = os.path.dirname(os.path.abspath(__file__))
flight_delays_dir = os.path.join(code_dir, "flight-delays")
if flight_delays_dir not in sys.path:
    sys.path.append(flight_delays_dir)

import pandas as pd  # noqa: E402
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="xgboost")
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

try:
    from challenge.model import DelayModel  # type: ignore
except Exception:  # pragma: no cover
    DelayModel = None


# Mapeo aproximado de aerolíneas de nuestro simulador a OPERA del challenge.
AIRLINE_TO_OPERA = {
    "AA": "American Airlines",
    "IB": "Iberia",
    "LATAM": "Grupo LATAM",
    "AV": "Avianca",
    "UX": "Air Europa",
    "Delta": "Delta Air",
}


class FlightDelayAdapter:
    """Envuelve el DelayModel para predecir retrasos en planes de viaje."""

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model: Optional[Any] = None
        self._model_loaded = False
        self._model_path = model_path or ""
        self._load_error = False

    def _load(self) -> None:
        if self._model_loaded or self._load_error or DelayModel is None:
            return
        try:
            self.model = DelayModel()
            if self._model_path and os.path.exists(self._model_path):
                self.model._load()
            else:
                default_path = os.path.join(
                    flight_delays_dir, "challenge", "model.pkl"
                )
                if os.path.exists(default_path):
                    self.model._MODEL_PATH = default_path
                    self.model._load()
            self._model_loaded = True
        except Exception:
            self.model = None
            self._load_error = True
            self._model_loaded = True

    @property
    def available(self) -> bool:
        if not self._model_loaded:
            self._load()
        return DelayModel is not None and self.model is not None

    def predict_delay_probability(self, flight: Dict[str, Any]) -> float:
        """Devuelve probabilidad [0,1] de que el vuelo se retrase >15 min.

        Si el modelo no está disponible o faltan datos, devuelve 0.0 (sin riesgo).
        """
        if not self.available:
            return 0.0
        try:
            df = self._build_dataframe(flight)
            if df is None:
                return 0.0
            features = self.model.preprocess(df)
            # XGBClassifier predict devuelve 0/1; para probabilidad usamos predict_proba
            if hasattr(self.model._model, "predict_proba"):
                proba = self.model._model.predict_proba(features)[:, 1]
                return float(proba[0])
            prediction = self.model.predict(features)
            return float(prediction[0])
        except Exception:
            return 0.0

    def _build_dataframe(self, flight: Dict[str, Any]) -> Optional[pd.DataFrame]:
        details = flight.get("details") or flight
        departure = details.get("departure") or flight.get("departure")
        if not departure:
            return None
        # Aceptar ISO o fecha simple
        if isinstance(departure, str):
            try:
                fecha_i = datetime.fromisoformat(departure.replace("Z", "+00:00"))
            except ValueError:
                try:
                    fecha_i = datetime.strptime(departure, "%Y-%m-%d")
                except ValueError:
                    return None
        else:
            fecha_i = departure

        airline = details.get("airline") or flight.get("airline") or "Unknown"
        opera = AIRLINE_TO_OPERA.get(airline, airline)
        origin = details.get("origin") or flight.get("origin") or ""
        destination = details.get("destination") or flight.get("destination") or ""
        # Tipo de vuelo internacional si el origen y destino difieren de manera simple
        tipo_vuelo = "I" if origin and destination and origin != destination else "N"

        return pd.DataFrame([{
            "Fecha-I": fecha_i.strftime("%Y-%m-%d %H:%M:%S"),
            "OPERA": opera,
            "TIPOVUELO": tipo_vuelo,
            "MES": fecha_i.month,
        }])
