"""
UC-087 — Filtrado de entradas: outliers, OOD y feature squeezing.

Implementa detección de outliers con z-score, distancia de Mahalanobis
simplificada y feature squeezing para detectar entradas adversariales.
"""

import math
import statistics
from typing import List, Dict, Tuple, Any

from models_087 import DataPoint


class InputFilter:
    """
    Limpia un batch de entrenamiento antes de que llegue al modelo:
    - Detección y eliminación de outliers estadísticos.
    - Feature squeezing: si una predicción cambia mucho tras comprimir, la
      muestra es marcada como sospechosa.
    """

    def __init__(self, outlier_threshold: float = 3.0, squeeze_epsilon: float = 0.01):
        self.outlier_threshold = outlier_threshold
        self.squeeze_epsilon = squeeze_epsilon

    def _median(self, values: List[float]) -> float:
        s = sorted(values)
        n = len(s)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2.0

    def _mad(self, values: List[float]) -> float:
        """Mediana de desviaciones absolutas respecto a la mediana."""
        med = self._median(values)
        deviations = [abs(v - med) for v in values]
        return self._median(deviations) or 1e-9

    def filter_outliers(self, data: List[DataPoint]) -> Tuple[List[DataPoint], int]:
        """Elimina puntos con alguna feature fuera usando mediana + MAD."""
        if not data:
            return [], 0
        dim = len(data[0].features)
        medians = []
        mads = []
        for j in range(dim):
            values = [dp.features[j] for dp in data]
            medians.append(self._median(values))
            mads.append(self._mad(values))

        clean = []
        dropped = 0
        for dp in data:
            max_z = 0.0
            for j, value in enumerate(dp.features):
                z = abs(value - medians[j]) / mads[j]
                max_z = max(max_z, z)
            if max_z <= self.outlier_threshold:
                clean.append(dp)
            else:
                dropped += 1
        return clean, dropped

    def mahalanobis_squared(self, point: List[float], means: List[float], inv_cov: List[List[float]]) -> float:
        """Calcula distancia de Mahalanobis al cuadrado para punto."""
        diff = [point[i] - means[i] for i in range(len(point))]
        result = 0.0
        for i in range(len(point)):
            for j in range(len(point)):
                result += diff[i] * inv_cov[i][j] * diff[j]
        return result

    def inverse_covariance_identity(self, dim: int) -> List[List[float]]:
        """Aproximación de inversa de covarianza como identidad."""
        return [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]

    def filter_mahalanobis(self, data: List[DataPoint], threshold: float = 3.0) -> Tuple[List[DataPoint], int]:
        """Filtra usando Mahalanobis aproximada (identidad = distancia euclídea normalizada)."""
        if not data:
            return [], 0
        dim = len(data[0].features)
        means = [statistics.mean([dp.features[j] for dp in data]) for j in range(dim)]
        inv_cov = self.inverse_covariance_identity(dim)

        clean = []
        dropped = 0
        for dp in data:
            d2 = self.mahalanobis_squared(dp.features, means, inv_cov)
            if math.sqrt(d2) <= threshold:
                clean.append(dp)
            else:
                dropped += 1
        return clean, dropped

    def squeeze(self, features: List[float]) -> List[float]:
        """Aplica feature squeezing redondeando decimales."""
        return [round(v / self.squeeze_epsilon) * self.squeeze_epsilon for v in features]

    def detect_squeezing_changes(
        self,
        data: List[DataPoint],
        predict_fn,
    ) -> Tuple[List[DataPoint], int, List[Dict[str, Any]]]:
        """
        Para cada punto, compara la predicción original vs. la del punto
comprimido. Si cambia drásticamente, se considera adversarial.

        predict_fn: callable que recibe una lista de features y retorna una
        predicción (label o probabilidad).
        """
        clean = []
        adversarial = 0
        details = []
        for i, dp in enumerate(data):
            pred_original = predict_fn(dp.features)
            squeezed = self.squeeze(dp.features)
            pred_squeezed = predict_fn(squeezed)
            changed = pred_original != pred_squeezed
            if changed:
                adversarial += 1
                details.append({
                    "index": i,
                    "original": pred_original,
                    "squeezed": pred_squeezed,
                    "flag": "squeezing_mismatch",
                })
            else:
                clean.append(dp)
        return clean, adversarial, details

    def statistics(self, data: List[DataPoint]) -> Dict[str, Any]:
        if not data:
            return {}
        dim = len(data[0].features)
        return {
            "n_points": len(data),
            "dim": dim,
            "means": [round(statistics.mean([dp.features[j] for dp in data]), 4) for j in range(dim)],
            "stdevs": [round(statistics.stdev([dp.features[j] for dp in data]), 4) if len(data) > 1 else 0.0 for j in range(dim)],
        }
