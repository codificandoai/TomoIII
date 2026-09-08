"""
Codificando.AI
UC-162: LLMOps — Modelado lógico, sesgo, linaje semántico,
hallucination, drift conceptual y prompt versioning.

Capa externa de LLMOps que protege la calidad conceptual y semántica
del conocimiento que alimenta al cerebro AGI (UC-315). Complementa a
UC-087 (MLSecOps) que valida integridad criptográfica.

UC-087 responde: "¿los datos fueron manipulados?"
UC-162 responde: "¿los datos están conceptualmente bien estructurados
y son libres de sesgo?"

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.
"""

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))

from typing import List, Dict, Any, Optional

from models_162 import (
    LLMOpsConfig,
    CorpusDocument,
    DocumentMetadata,
)
from llmops_guardian import LLMOpsGuardian


class UCLLMOpsLayer:
    """Wrapper de alto nivel para UC-162."""

    def __init__(self, config: Optional[LLMOpsConfig] = None):
        self.guardian = LLMOpsGuardian(config=config)

    def process_corpus(
        self,
        documents: List[Dict[str, Any]],
        source: str = "unknown",
    ) -> Dict[str, Any]:
        """Procesa un corpus: verifica sesgo, registra linaje, decide."""
        docs = self._to_documents(documents)
        result = self.guardian.process_corpus(docs, source=source)
        return result.to_dict()

    def evaluate_response(
        self,
        response: str,
        retrieved_chunks: List[str],
        prompt_version: str = "",
        model: str = "",
    ) -> Dict[str, Any]:
        """Evalúa una respuesta del LLM: detecta hallucination."""
        result = self.guardian.evaluate_response(
            response=response,
            retrieved_chunks=retrieved_chunks,
            prompt_version=prompt_version,
            model=model,
        )
        return result.to_dict()

    def check_drift(
        self,
        concept_name: str,
        current_contexts: List[str],
        current_co_occurrences: List[List[str]] = None,
    ) -> Dict[str, Any]:
        """Verifica drift conceptual."""
        result = self.guardian.check_drift(
            concept_name=concept_name,
            current_contexts=current_contexts,
            current_co_occurrences=current_co_occurrences,
        )
        return result.to_dict()

    def set_baseline(
        self,
        concept_name: str,
        contexts: List[str],
        co_occurrences: List[List[str]] = None,
    ):
        self.guardian.set_baseline(concept_name, contexts, co_occurrences)

    def register_prompt(
        self,
        template: str,
        version: str = "",
        tags: List[str] = None,
    ) -> Dict[str, Any]:
        return self.guardian.register_prompt(template, version, tags)

    def approve_prompt(
        self,
        prompt_id: str,
        approved_by: str = "compliance_officer",
    ) -> Optional[Dict[str, Any]]:
        return self.guardian.approve_prompt(prompt_id, approved_by)

    def get_status(self) -> Dict[str, Any]:
        return self.guardian.get_status()

    def get_metrics(self) -> str:
        return self.guardian.get_metrics()

    @staticmethod
    def _to_documents(items: List[Dict[str, Any]]) -> List[CorpusDocument]:
        docs = []
        for item in items:
            meta = item.get("metadata", {})
            metadata = DocumentMetadata(
                id_documento=meta.get("id_documento", item.get("id", "")),
                fuente=meta.get("fuente", ""),
                fuente_tipo=meta.get("fuente_tipo", ""),
                fecha_creacion=meta.get("fecha_creacion", ""),
                categoria_tema=meta.get("categoria_tema", ""),
                genero_autor=meta.get("genero_autor", ""),
                region_geografica=meta.get("region_geografica", ""),
                perspectiva_tematica=meta.get("perspectiva_tematica", ""),
                idioma=meta.get("idioma", "es"),
                variante_regional=meta.get("variante_regional", ""),
                contexto_cultural=meta.get("contexto_cultural", ""),
                nivel_confianza=meta.get("nivel_confianza", 0.5),
                periodo_temporal=meta.get("periodo_temporal", ""),
            )
            docs.append(CorpusDocument(
                id=item.get("id", ""),
                text=item.get("text", ""),
                metadata=metadata,
            ))
        return docs


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _generate_balanced_corpus(n: int = 30) -> List[Dict[str, Any]]:
    """Genera un corpus balanceado (sin sesgo) de forma determinística."""
    genders = ["masculino", "femenino", "no_binario"]
    regions = ["latam", "europa", "norteamerica", "asia"]
    perspectives = ["tecnica", "legal", "etica", "economica", "social"]
    source_types = ["academica", "gubernamental", "corporativa", "crowd"]
    periods = ["2023", "2024", "2025"]
    languages = ["es", "en", "es", "en"]
    topics = ["trading", "reservas", "pagos", "riesgo"]
    docs = []
    for i in range(n):
        docs.append({
            "id": f"doc_{i:03d}",
            "text": f"Documento {i} sobre {topics[i % len(topics)]}.",
            "metadata": {
                "id_documento": f"doc_{i:03d}",
                "fuente": f"source_{i % 5}",
                "fuente_tipo": source_types[i % len(source_types)],
                "fecha_creacion": f"{periods[i % len(periods)]}-01-01",
                "categoria_tema": topics[i % len(topics)],
                "genero_autor": genders[i % len(genders)],
                "region_geografica": regions[i % len(regions)],
                "perspectiva_tematica": perspectives[i % len(perspectives)],
                "idioma": languages[i % len(languages)],
                "variante_regional": ["es-ES", "es-MX", "es-AR", "en-US"][i % 4],
                "periodo_temporal": periods[i % len(periods)],
                "nivel_confianza": 0.5 + (i % 5) * 0.1,
            },
        })
    return docs


def _generate_biased_corpus(n: int = 20) -> List[Dict[str, Any]]:
    """Genera un corpus sesgado (dominancia de género y región)."""
    docs = []
    for i in range(n):
        docs.append({
            "id": f"doc_{i:03d}",
            "text": f"Documento {i} sobre trading.",
            "metadata": {
                "id_documento": f"doc_{i:03d}",
                "fuente": "single_source",
                "fuente_tipo": "corporativa",
                "fecha_creacion": "2025-01-01",
                "categoria_tema": "trading",
                "genero_autor": "masculino",  # 100% masculino
                "region_geografica": "norteamerica",  # 100% norteamerica
                "perspectiva_tematica": "tecnica",  # 100% tecnica
                "idioma": "en",
                "variante_regional": "en-US",
                "periodo_temporal": "2025",
                "nivel_confianza": 0.9,
            },
        })
    return docs


def run_demo():
    """Demo del sistema LLMOps UC-162."""
    print("=" * 70)
    print("UC-162 — LLMOps Guardian Demo")
    print("=" * 70)

    layer = UCLLMOpsLayer()

    # 1. Corpus balanceado
    print("\n1. Procesando corpus balanceado...")
    balanced = _generate_balanced_corpus(20)
    result1 = layer.process_corpus(balanced, source="trusted_pipeline")
    print(f"   Decision: {result1['decision']}")
    print(f"   Bias all_passed: {result1['bias_report']['all_passed']}")
    print(f"   Bias checks: {len(result1['bias_report']['checks'])}")
    print(f"   Lineage nodes: {result1['lineage_graph']['node_count']}")
    print(f"   Duration: {result1['duration_ms']}ms")
    if result1["issues"]:
        print(f"   Issues: {result1['issues']}")

    # 2. Corpus sesgado
    print("\n2. Procesando corpus sesgado...")
    biased = _generate_biased_corpus(20)
    result2 = layer.process_corpus(biased, source="unknown")
    print(f"   Decision: {result2['decision']}")
    print(f"   Bias all_passed: {result2['bias_report']['all_passed']}")
    print(f"   Bias actions: {result2['bias_report']['actions']}")
    print(f"   Bias metrics: {result2['bias_report']['metrics']}")
    if result2["issues"]:
        print(f"   Issues: {result2['issues']}")

    # 3. Evaluación de respuesta (sin hallucination)
    print("\n3. Evaluando respuesta coherente...")
    chunks = [
        "La política de reembolso permite cancelar dentro de 30 días.",
        "El reembolso se procesa en 5-7 días hábiles.",
    ]
    good_response = "Según la política, puede cancelar dentro de 30 días y el reembolso se procesa en 5-7 días hábiles."
    result3 = layer.evaluate_response(good_response, chunks, prompt_version="v1")
    print(f"   Decision: {result3['decision']}")
    print(f"   Hallucination severity: {result3['hallucination_report']['severity']}")
    print(f"   Coverage: {result3['hallucination_report']['coverage_score']}")

    # 4. Evaluación de respuesta (con hallucination)
    print("\n4. Evaluando respuesta con hallucination...")
    bad_response = "El reembolso es inmediato y sin límite de tiempo. Además, incluye un bonus del 200%."
    result4 = layer.evaluate_response(bad_response, chunks, prompt_version="v1")
    print(f"   Decision: {result4['decision']}")
    print(f"   Hallucination severity: {result4['hallucination_report']['severity']}")
    print(f"   Is hallucination: {result4['hallucination_report']['is_hallucination']}")
    print(f"   Unsupported claims: {len(result4['hallucination_report']['unsupported_claims'])}")

    # 5. Drift conceptual
    print("\n5. Verificando drift conceptual...")
    layer.set_baseline(
        "spread",
        contexts=["bid_ask", "bid_ask", "bid_ask", "credit", "bid_ask"],
        co_occurrences=[["mercado", "orden"], ["precio", "compra"]],
    )
    drift_result = layer.check_drift(
        "spread",
        current_contexts=["volatilidad", "volatilidad", "credit", "volatilidad"],
        current_co_occurrences=[["opciones", "volatilidad"]],
    )
    print(f"   Decision: {drift_result['decision']}")
    print(f"   Drift type: {drift_result['drift_report']['drift_type']}")
    print(f"   Drift score: {drift_result['drift_report']['drift_score']}")

    # 6. Prompt versioning
    print("\n6. Registrando y aprobando prompt...")
    prompt = layer.register_prompt(
        "Responde la pregunta usando solo los chunks proporcionados.",
        version="v1.0",
        tags=["rag", "support"],
    )
    print(f"   Prompt registrado: {prompt['version']}")
    approved = layer.approve_prompt(prompt["id"], approved_by="compliance")
    if approved:
        print(f"   Prompt aprobado: {approved['approved']}")

    # 7. Estado final
    print("\n7. Estado final del guardian:")
    status = layer.get_status()
    print(f"   Lineage nodes: {status['lineage_nodes']}")
    print(f"   Prompts registered: {status['prompts_registered']}")
    print(f"   Prompts approved: {status['prompts_approved']}")
    print(f"   Baselines: {status['baselines']}")

    print("\n" + "=" * 70)
    print("Demo completado.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
