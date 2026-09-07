"""
UC-087 — Validador de provenancia e integridad de datos de entrenamiento.

Combina comprobaciones de hash, firma, lineage y estructura básica.
"""

from typing import Any, Dict, List, Optional

from data_signing import DataSigning
from models_087 import ProvenanceCheck, ValidationReport, DataPoint


class ProvenanceValidator:
    """
    Valida que un batch de datos provenga de una fuente confiable y no haya
sido alterado antes del entrenamiento.
    """

    REQUIRED_FIELDS = ["features", "label"]

    def __init__(self, signing: Optional[DataSigning] = None):
        self.signing = signing or DataSigning()

    def validate_batch(
        self,
        data: List[DataPoint],
        expected_hash: Optional[str] = None,
        signature_envelope: Optional[Dict[str, str]] = None,
        source: str = "unknown",
        allowed_sources: Optional[List[str]] = None,
    ) -> ValidationReport:
        """Valida un batch completo: estructura, hash, firma y fuente."""
        checks = []

        # 1. Estructura
        checks.append(self._check_structure(data))

        # 2. Hash
        if expected_hash:
            checks.append(self._check_hash(data, expected_hash))
        else:
            checks.append(ProvenanceCheck(
                check_name="hash",
                passed=True,
                message="No se proporcionó hash esperado; validación omitida.",
            ))

        # 3. Firma
        if signature_envelope:
            checks.append(self._check_signature(data, signature_envelope))
        else:
            checks.append(ProvenanceCheck(
                check_name="signature",
                passed=True,
                message="No se proporcionó firma; validación omitida.",
            ))

        # 4. Fuente permitida
        checks.append(self._check_source(source, allowed_sources))

        # 5. Lineage
        checks.append(self._check_lineage(data, source))

        all_passed = all(c.passed for c in checks)
        return ValidationReport(
            all_passed=all_passed,
            provenance_checks=checks,
        )

    def _check_structure(self, data: List[DataPoint]) -> ProvenanceCheck:
        if not data:
            return ProvenanceCheck(
                check_name="structure",
                passed=False,
                message="El batch está vacío.",
            )
        first_dim = len(data[0].features)
        for i, dp in enumerate(data):
            if not isinstance(dp.features, (list, tuple)) or len(dp.features) != first_dim:
                return ProvenanceCheck(
                    check_name="structure",
                    passed=False,
                    message=f"Punto {i} tiene dimensiones inconsistentes.",
                    details={"expected_dim": first_dim, "index": i},
                )
        return ProvenanceCheck(
            check_name="structure",
            passed=True,
            message=f"Estructura consistente: {len(data)} puntos, dimensión {first_dim}.",
            details={"n_points": len(data), "dim": first_dim},
        )

    def _check_hash(self, data: List[DataPoint], expected_hash: str) -> ProvenanceCheck:
        ok = self.signing.verify_hash([dp.to_dict() for dp in data], expected_hash)
        return ProvenanceCheck(
            check_name="hash",
            passed=ok,
            message="Hash coincide." if ok else "🚨 Hash mismatch: los datos fueron alterados.",
            details={"expected_hash": expected_hash},
        )

    def _check_signature(self, data: List[DataPoint], envelope: Dict[str, str]) -> ProvenanceCheck:
        ok = self.signing.verify_signature([dp.to_dict() for dp in data], envelope)
        return ProvenanceCheck(
            check_name="signature",
            passed=ok,
            message="Firma válida." if ok else "🚨 Firma inválida: origen no autenticado.",
        )

    def _check_source(self, source: str, allowed_sources: Optional[List[str]]) -> ProvenanceCheck:
        if not allowed_sources:
            return ProvenanceCheck(
                check_name="source",
                passed=True,
                message="No hay lista de fuentes permitidas; validación omitida.",
            )
        ok = source in allowed_sources
        return ProvenanceCheck(
            check_name="source",
            passed=ok,
            message=f"Fuente '{source}' permitida." if ok else f"🚨 Fuente '{source}' no está en la lista blanca.",
            details={"source": source, "allowed": allowed_sources},
        )

    def _check_lineage(self, data: List[DataPoint], source: str) -> ProvenanceCheck:
        dataset_hash = self.signing.hash_batch([dp.to_dict() for dp in data])
        lineage = self.signing.record_lineage(source, dataset_hash, ["ingested"])
        return ProvenanceCheck(
            check_name="lineage",
            passed=True,
            message="Lineage registrado.",
            details=lineage,
        )
