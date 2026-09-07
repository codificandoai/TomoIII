"""
UC-083 — Validador de datos para respuesta a incidentes de inferencia batch.

Implementa validaciones tempranas de volumen, esquema, completitud y
distribución de datos sin depender de pandas/pandera externo.
"""

import csv
import statistics
from typing import Dict, List, Optional, Any
from collections import Counter

from incident_models import ValidationReport, IncidentResponseConfig


class DataValidator:
    """
    Valida un archivo CSV/TSV batch antes de cargarlo completamente en
memoria. Lee solo una muestra configurable y calcula estadísticas de
distribución.
    """

    def __init__(self, config: Optional[IncidentResponseConfig] = None):
        self.config = config or IncidentResponseConfig()

    def validate(
        self,
        file_path: str,
        expected_columns: Optional[List[str]] = None,
        sample_rows: int = 1000,
    ) -> List[ValidationReport]:
        """Ejecuta todas las validaciones tempranas sobre una muestra."""
        reports = []
        reports.append(self._validate_volume(file_path, sample_rows))
        reports.append(self._validate_schema(file_path, expected_columns, sample_rows))
        reports.append(self._validate_completeness(file_path, sample_rows))
        reports.append(self._validate_distribution(file_path, sample_rows))
        return reports

    def _count_rows(self, file_path: str) -> int:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f) - 1  # header
        except Exception:
            return 0

    def _sample(self, file_path: str, sample_rows: int) -> List[Dict[str, str]]:
        rows = []
        try:
            with open(file_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= sample_rows:
                        break
                    rows.append(row)
        except Exception:
            pass
        return rows

    def _validate_volume(self, file_path: str, sample_rows: int) -> ValidationReport:
        total_rows = self._count_rows(file_path)
        if total_rows == 0:
            return ValidationReport(
                check_name="volume",
                passed=False,
                message="No se pudo leer el archivo o está vacío.",
                details={"total_rows": total_rows},
            )
        if total_rows > self.config.max_allowed_rows:
            return ValidationReport(
                check_name="volume",
                passed=False,
                message=f"🚨 VOLUMEN EXCESO: {total_rows} filas superan el límite de {self.config.max_allowed_rows}. Requiere chunking/distribuido.",
                details={"total_rows": total_rows, "max_allowed_rows": self.config.max_allowed_rows},
            )
        return ValidationReport(
            check_name="volume",
            passed=True,
            message=f"Volumen aceptable: {total_rows} filas.",
            details={"total_rows": total_rows},
        )

    def _validate_schema(
        self,
        file_path: str,
        expected_columns: Optional[List[str]],
        sample_rows: int,
    ) -> ValidationReport:
        if not expected_columns:
            return ValidationReport(
                check_name="schema",
                passed=True,
                message="No se proporcionaron columnas esperadas; validación omitida.",
                details={},
            )
        rows = self._sample(file_path, 1)
        if not rows:
            return ValidationReport(
                check_name="schema",
                passed=False,
                message="No se pudo leer encabezado del archivo.",
                details={},
            )
        columns = set(rows[0].keys())
        missing = [c for c in expected_columns if c not in columns]
        extra = [c for c in columns if c not in expected_columns]
        if missing or extra:
            return ValidationReport(
                check_name="schema",
                passed=False,
                message=f"Schema drift detectado. Faltantes: {missing}, Extra: {extra}",
                details={"missing": missing, "extra": extra, "columns": list(columns)},
            )
        return ValidationReport(
            check_name="schema",
            passed=True,
            message="Esquema coincide con expected_columns.",
            details={"columns": list(columns)},
        )

    def _validate_completeness(self, file_path: str, sample_rows: int) -> ValidationReport:
        rows = self._sample(file_path, sample_rows)
        if not rows:
            return ValidationReport(
                check_name="completeness",
                passed=False,
                message="No hay filas para validar completitud.",
                details={},
            )
        total_cells = len(rows) * len(rows[0].keys()) if rows else 0
        empty_cells = 0
        for row in rows:
            for v in row.values():
                if v is None or str(v).strip() == "":
                    empty_cells += 1
        ratio = empty_cells / total_cells if total_cells else 0.0
        passed = ratio <= 0.05
        return ValidationReport(
            check_name="completeness",
            passed=passed,
            message=f"Completitud: {1-ratio:.2%} ({empty_cells}/{total_cells} celdas vacías)." if passed else f"🚨 COMPLETITUD BAJA: {1-ratio:.2%}",
            details={"empty_cells": empty_cells, "total_cells": total_cells, "ratio": ratio},
        )

    def _validate_distribution(self, file_path: str, sample_rows: int) -> ValidationReport:
        rows = self._sample(file_path, sample_rows)
        if not rows:
            return ValidationReport(
                check_name="distribution",
                passed=True,
                message="Sin datos para analizar distribución.",
                details={},
            )
        # Usar primera columna numérica si existe
        numeric_values = []
        for col in rows[0].keys():
            for row in rows:
                try:
                    numeric_values.append(float(row[col]))
                except Exception:
                    continue
            if len(numeric_values) >= len(rows) * 0.5:
                break
            numeric_values.clear()

        if len(numeric_values) < 2:
            return ValidationReport(
                check_name="distribution",
                passed=True,
                message="No se encontró columna numérica representativa.",
                details={},
            )

        mean = statistics.mean(numeric_values)
        stdev = statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0.0
        z_values = [(x - mean) / stdev if stdev else 0 for x in numeric_values]
        outliers = [z for z in z_values if abs(z) > self.config.anomaly_zscore]
        passed = len(outliers) <= len(numeric_values) * 0.05
        return ValidationReport(
            check_name="distribution",
            passed=passed,
            message=f"Distribución {'aceptable' if passed else '🚨 ANÓMALA'}: {len(outliers)} outliers (z>{self.config.anomaly_zscore})." ,
            details={"mean": mean, "stdev": stdev, "outliers": len(outliers)},
        )

    def baseline_comparison(
        self,
        current_row_count: int,
        historical_counts: List[int],
    ) -> ValidationReport:
        """Compara volumen actual contra baseline histórico."""
        if not historical_counts:
            return ValidationReport(
                check_name="baseline_volume",
                passed=True,
                message="No hay baseline histórico.",
                details={"current": current_row_count},
            )
        mean = statistics.mean(historical_counts)
        stdev = statistics.stdev(historical_counts) if len(historical_counts) > 1 else 0.0
        z = (current_row_count - mean) / stdev if stdev else 0.0
        if current_row_count > mean + self.config.anomaly_zscore * stdev:
            return ValidationReport(
                check_name="baseline_volume",
                passed=False,
                message=f"🚨 Volumen {current_row_count} excede baseline ({mean:.0f} ± {stdev:.0f}) con z={z:.2f}.",
                details={"current": current_row_count, "baseline_mean": mean, "zscore": z},
            )
        return ValidationReport(
            check_name="baseline_volume",
            passed=True,
            message=f"Volumen dentro del baseline ({mean:.0f} ± {stdev:.0f}).",
            details={"current": current_row_count, "baseline_mean": mean, "zscore": z},
        )

    def reset(self) -> None:
        pass
