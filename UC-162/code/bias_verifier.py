"""
UC-162 — Verificador de sesgo.

Detecta sesgo sistemático en el diseño lógico del corpus:
- Representatividad demográfica (género, región).
- Balance de perspectivas (técnica, legal, ética, económica, social).
- Temporalidad (dominancia de un periodo).
- Fuente y autoría (académica, gubernamental, corporativa, crowd).
- Lenguaje y cultura (idioma, variante regional).

El sesgo no es un ataque; es un defecto de diseño lógico. Un batch puede
pasar todos los gates criptográficos de UC-087 y aun así contener sesgo.
"""

import math
from collections import Counter
from typing import Dict, List, Optional, Any

from models_162 import (
    BiasCheck,
    BiasReport,
    CorpusDocument,
    LLMOpsConfig,
)
from logical_data_model import LogicalSchema


class BiasVerifier:
    """Verifica sesgo en el corpus contra el esquema lógico."""

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.config = config or LLMOpsConfig()
        self.schema = LogicalSchema(config=self.config)

    def verify(self, documents: List[CorpusDocument]) -> BiasReport:
        """Ejecuta todos los controles de sesgo sobre el corpus."""
        report = BiasReport()
        if len(documents) < self.config.min_documents_for_bias_check:
            report.all_passed = True
            report.actions.append(
                f"Insuficientes documentos ({len(documents)} < "
                f"{self.config.min_documents_for_bias_check}) para verificación completa"
            )
            return report

        checks: List[BiasCheck] = []
        checks.append(self._check_dominance(
            documents, "genero_autor", "demographic",
            self.config.max_demographic_dominance,
        ))
        checks.append(self._check_dominance(
            documents, "region_geografica", "demographic",
            self.config.max_region_dominance,
        ))
        checks.append(self._check_dominance(
            documents, "perspectiva_tematica", "perspective",
            self.config.max_perspective_dominance,
        ))
        checks.append(self._check_perspective_representation(documents))
        checks.append(self._check_dominance(
            documents, "periodo_temporal", "temporal",
            self.config.max_temporal_dominance,
        ))
        checks.append(self._check_dominance(
            documents, "fuente_tipo", "source",
            self.config.max_source_type_dominance,
        ))
        checks.append(self._check_dominance(
            documents, "idioma", "language",
            self.config.max_language_dominance,
        ))

        # Métricas calculadas
        report.metrics = self._compute_metrics(documents)

        # Consolidar
        report.checks = checks
        report.all_passed = all(c.passed for c in checks)
        for c in checks:
            if not c.passed and c.action not in report.actions:
                report.actions.append(c.action)

        return report

    def _check_dominance(
        self,
        documents: List[CorpusDocument],
        field_name: str,
        control_type: str,
        threshold: float,
    ) -> BiasCheck:
        """Verifica que ningún valor de un campo domine por encima del umbral."""
        values = [
            getattr(doc.metadata, field_name, "") or "unknown"
            for doc in documents
        ]
        counter = Counter(values)
        total = len(values)
        if total == 0:
            return BiasCheck(
                control_type=control_type,
                field_name=field_name,
                dominance=0.0,
                threshold=threshold,
                action="pass",
                passed=True,
                details={"error": "no documents"},
            )
        top_value, top_count = counter.most_common(1)[0]
        dominance = top_count / total
        threshold_obj = self.schema.get_bias_threshold(field_name)
        action = "pass"
        passed = True
        if dominance > threshold and threshold_obj:
            action = threshold_obj.action_if_exceeds
            passed = action == "pass"
        return BiasCheck(
            control_type=control_type,
            field_name=field_name,
            dominance=round(dominance, 4),
            threshold=threshold,
            action=action,
            passed=passed,
            details={
                "top_value": top_value,
                "top_count": top_count,
                "total": total,
                "distribution": dict(counter),
            },
        )

    def _check_perspective_representation(
        self, documents: List[CorpusDocument]
    ) -> BiasCheck:
        """Verifica que cada perspectiva tenga al menos min_representation."""
        perspectives = self.schema.perspective_types
        values = [
            getattr(doc.metadata, "perspectiva_tematica", "") or "unknown"
            for doc in documents
        ]
        counter = Counter(values)
        total = len(values)
        missing = []
        for p in perspectives:
            ratio = counter.get(p, 0) / total if total > 0 else 0
            if ratio < self.config.min_perspective_representation:
                missing.append(p)
        threshold_obj = self.schema.get_bias_threshold("perspectiva_tematica")
        action = "pass"
        passed = True
        if missing and threshold_obj:
            action = threshold_obj.action_if_missing
            passed = False
        return BiasCheck(
            control_type="perspective",
            field_name="perspectiva_tematica_representation",
            dominance=0.0,
            threshold=self.config.min_perspective_representation,
            action=action,
            passed=passed,
            details={
                "missing_perspectives": missing,
                "distribution": dict(counter),
                "required_perspectives": perspectives,
            },
        )

    def _compute_metrics(
        self, documents: List[CorpusDocument]
    ) -> Dict[str, float]:
        """Calcula métricas de sesgo: entropía de Shannon, disparidad."""
        metrics: Dict[str, float] = {}

        # Entropía de Shannon de regiones
        regions = [
            getattr(doc.metadata, "region_geografica", "") or "unknown"
            for doc in documents
        ]
        metrics["entropia_shannon_regiones"] = round(
            self._shannon_entropy(regions), 4
        )

        # Entropía de perspectivas
        perspectives = [
            getattr(doc.metadata, "perspectiva_tematica", "") or "unknown"
            for doc in documents
        ]
        metrics["entropia_shannon_perspectivas"] = round(
            self._shannon_entropy(perspectives), 4
        )

        # Disparidad de género
        genders = [
            getattr(doc.metadata, "genero_autor", "") or "unknown"
            for doc in documents
        ]
        counter = Counter(genders)
        total = len(genders)
        if total > 0:
            pct_m = counter.get("masculino", 0) / total
            pct_f = counter.get("femenino", 0) / total
            pct_nb = max(counter.get("no_binario", 0) / total, 0.001)
            metrics["disparidad_genero"] = round(
                abs(pct_m - pct_f) / pct_nb, 4
            )
        else:
            metrics["disparidad_genero"] = 0.0

        # Concentración temporal (entropy)
        periods = [
            getattr(doc.metadata, "periodo_temporal", "") or "unknown"
            for doc in documents
        ]
        metrics["entropia_shannon_temporal"] = round(
            self._shannon_entropy(periods), 4
        )

        return metrics

    @staticmethod
    def _shannon_entropy(values: List[str]) -> float:
        """Calcula entropía de Shannon. Mayor = más diversidad."""
        if not values:
            return 0.0
        counter = Counter(values)
        total = len(values)
        entropy = 0.0
        for count in counter.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
