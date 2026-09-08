"""
UC-162 — Modelado lógico de datos para LLMOps.

Define el esquema conceptual con constraints de sesgo ANTES de la
implementación física. Los controles de sesgo y linaje son parte integral
del diseño lógico, no plugins añadidos después.
"""

import hashlib
import json
from typing import Dict, List, Optional, Any

from models_162 import (
    BiasThreshold,
    CorpusDocument,
    DocumentMetadata,
    LLMOpsConfig,
)


class LogicalSchema:
    """
    Esquema lógico del corpus LLMOps.

    Define:
    - Campos obligatorios del modelo lógico.
    - Metadatos de gobernanza con constraints de sesgo.
    - Métricas de sesgo calculadas.
    - Reglas de linaje semántico.

    Este esquema es el "contrato de gobernanza": antes de que los datos
    existan físicamente, las reglas de sesgo y linaje ya están definidas.
    """

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.config = config or LLMOpsConfig()
        self.version = "2.1"
        self.name = "llmops_logical_schema"
        self.required_fields = [
            "id_documento",
            "texto",
            "fuente",
            "fecha_creacion",
            "categoria_tema",
        ]
        self.governance_fields = [
            "genero_autor",
            "region_geografica",
            "perspectiva_tematica",
            "fuente_tipo",
            "idioma",
            "variante_regional",
            "periodo_temporal",
            "nivel_confianza",
        ]
        self.bias_thresholds: Dict[str, BiasThreshold] = self._build_thresholds()
        self.lineage_stages = [
            "ingest", "clean", "chunk", "embed", "index", "retrieve", "generate",
        ]
        self.perspective_types = ["tecnica", "legal", "etica", "economica", "social"]
        self.source_types = ["academica", "gubernamental", "corporativa", "crowd"]

    def _build_thresholds(self) -> Dict[str, BiasThreshold]:
        """Construye los thresholds de sesgo desde la configuración."""
        return {
            "genero_autor": BiasThreshold(
                field_name="genero_autor",
                max_dominance=self.config.max_demographic_dominance,
                action_if_exceeds="flag_for_review",
            ),
            "region_geografica": BiasThreshold(
                field_name="region_geografica",
                max_dominance=self.config.max_region_dominance,
                action_if_exceeds="reject_lot",
            ),
            "perspectiva_tematica": BiasThreshold(
                field_name="perspectiva_tematica",
                max_dominance=self.config.max_perspective_dominance,
                min_representation=self.config.min_perspective_representation,
                action_if_exceeds="flag_for_review",
                action_if_missing="enrich_with_complementary_sources",
            ),
            "periodo_temporal": BiasThreshold(
                field_name="periodo_temporal",
                max_dominance=self.config.max_temporal_dominance,
                action_if_exceeds="flag_for_review",
            ),
            "fuente_tipo": BiasThreshold(
                field_name="fuente_tipo",
                max_dominance=self.config.max_source_type_dominance,
                action_if_exceeds="flag_for_review",
            ),
            "idioma": BiasThreshold(
                field_name="idioma",
                max_dominance=self.config.max_language_dominance,
                action_if_exceeds="flag_for_review",
            ),
        }

    def validate_structure(self, doc: CorpusDocument) -> List[str]:
        """Valida que un documento cumple con los campos obligatorios."""
        issues = []
        meta = doc.metadata
        for field_name in self.required_fields:
            if field_name == "texto":
                val = doc.text or ""
            else:
                val = getattr(meta, field_name, "") or ""
            if not val:
                issues.append(f"Campo obligatorio faltante: {field_name}")
        return issues

    def get_bias_threshold(self, field_name: str) -> Optional[BiasThreshold]:
        return self.bias_thresholds.get(field_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "required_fields": self.required_fields,
            "governance_fields": self.governance_fields,
            "bias_thresholds": {
                k: v.to_dict() for k, v in self.bias_thresholds.items()
            },
            "lineage_stages": self.lineage_stages,
            "perspective_types": self.perspective_types,
            "source_types": self.source_types,
        }

    def to_yaml(self) -> str:
        """Exporta el esquema lógico en formato YAML-like para documentación."""
        lines = [
            f'version: "{self.version}"',
            f'name: {self.name}',
            "",
            "campos_obligatorios:",
        ]
        for f in self.required_fields:
            lines.append(f"  - {f}")
        lines.append("")
        lines.append("metadatos_gobernanza:")
        for field_name, threshold in self.bias_thresholds.items():
            lines.append(f"  - nombre: {field_name}")
            lines.append(f"    maximo_dominancia: {threshold.max_dominance}")
            lines.append(f"    accion_si_excede: {threshold.action_if_exceeds}")
            if threshold.min_representation > 0:
                lines.append(f"    minimo_representacion: {threshold.min_representation}")
                lines.append(f"    accion_si_falta: {threshold.action_if_missing}")
            lines.append("")
        lines.append("etapas_linaje:")
        for stage in self.lineage_stages:
            lines.append(f"  - {stage}")
        return "\n".join(lines)


def compute_hash(data: Any, algorithm: str = "sha256") -> str:
    """Computa hash criptográfico de datos serializados."""
    serialized = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    h = hashlib.new(algorithm)
    h.update(serialized)
    return h.hexdigest()


def document_to_dict(doc: CorpusDocument) -> Dict[str, Any]:
    """Serializa un documento a dict canonical para hashing."""
    return {
        "id": doc.id,
        "text": doc.text,
        "metadata": doc.metadata.to_dict(),
    }
