"""UC-320 — UTRON.ai Product Templates: plantillas comerciales reutilizables."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProductTemplate:
    """Plantilla de producto UTRON.ai empaquetada con modelos, skills y config."""

    template_id: str
    name: str
    description: str
    models: List[Dict[str, str]]  # [{"role": "embeddings", "model_id": "..."}]
    skills: List[str]
    deployment_profile: str  # local, hf-provider, hf-endpoint
    priority: int  # 1 = highest
    vertical: str  # legal, support, finance, etc.
    limitations: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "models": self.models,
            "skills": self.skills,
            "deployment_profile": self.deployment_profile,
            "priority": self.priority,
            "vertical": self.vertical,
            "limitations": self.limitations,
            "config": self.config,
        }


class TemplateRegistry:
    """Registro de plantillas de producto UTRON.ai."""

    def __init__(self) -> None:
        self._templates: Dict[str, ProductTemplate] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            ProductTemplate(
                template_id="utron-enterprise-rag",
                name="UTRON Enterprise RAG",
                description="Chat con documentos, buscador jurídico, base de conocimiento multilingüe.",
                models=[
                    {"role": "embeddings", "model_id": "BAAI/bge-m3"},
                    {"role": "reranker", "model_id": "BAAI/bge-reranker-v2-m3"},
                    {"role": "llm", "model_id": "Qwen/Qwen3-8B"},
                ],
                skills=["semantic_embedding", "zero_shot_classification"],
                deployment_profile="hf-endpoint",
                priority=1,
                vertical="knowledge",
                limitations=["Requiere validación de PII en documentos."],
            ),
            ProductTemplate(
                template_id="utron-contact-center",
                name="UTRON Contact Center",
                description="Transcripción, routing, resumen y respuesta asistida.",
                models=[
                    {"role": "asr", "model_id": "openai/whisper-large-v3"},
                    {"role": "embeddings", "model_id": "sentence-transformers/all-MiniLM-L6-v2"},
                    {"role": "llm", "model_id": "Qwen/Qwen3-8B"},
                    {"role": "classifier", "model_id": "facebook/bart-large-mnli"},
                ],
                skills=["semantic_embedding", "zero_shot_classification"],
                deployment_profile="hf-endpoint",
                priority=2,
                vertical="support",
            ),
            ProductTemplate(
                template_id="utron-document-intelligence",
                name="UTRON Document Intelligence",
                description="Digitalización de formularios, recibos y órdenes manuscritos.",
                models=[
                    {"role": "ocr", "model_id": "microsoft/trocr-base-handwritten"},
                    {"role": "embeddings", "model_id": "BAAI/bge-m3"},
                    {"role": "llm", "model_id": "mistralai/Mistral-7B-Instruct-v0.3"},
                ],
                skills=["semantic_embedding"],
                deployment_profile="hf-provider",
                priority=3,
                vertical="back-office",
                limitations=["Requiere revisión humana de campos críticos."],
            ),
            ProductTemplate(
                template_id="utron-market-intelligence",
                name="UTRON Market Intelligence",
                description="Monitor de noticias, sentimiento de activos, alertas de riesgo.",
                models=[
                    {"role": "sentiment", "model_id": "ProsusAI/finbert"},
                    {"role": "embeddings", "model_id": "BAAI/bge-m3"},
                    {"role": "llm", "model_id": "Qwen/Qwen3-8B"},
                ],
                skills=["market_sentiment", "semantic_embedding"],
                deployment_profile="hf-endpoint",
                priority=4,
                vertical="finance",
                limitations=["No debe aprobar operaciones de trading por sí solo."],
            ),
            ProductTemplate(
                template_id="utron-private-assistant",
                name="UTRON Private Assistant",
                description="Chat privado on-premise para pymes con privacidad de datos.",
                models=[
                    {"role": "llm", "model_id": "mistralai/Mistral-7B-Instruct-v0.3"},
                    {"role": "embeddings", "model_id": "sentence-transformers/all-MiniLM-L6-v2"},
                ],
                skills=["semantic_embedding"],
                deployment_profile="local",
                priority=5,
                vertical="privacy",
            ),
            ProductTemplate(
                template_id="utron-creative-studio",
                name="UTRON Creative Studio",
                description="Generación de piezas de marketing y prototipos visuales.",
                models=[
                    {"role": "image", "model_id": "stabilityai/stable-diffusion-xl-base-1.0"},
                    {"role": "llm", "model_id": "Qwen/Qwen3-8B"},
                ],
                skills=[],
                deployment_profile="hf-endpoint",
                priority=6,
                vertical="marketing",
                limitations=["Requiere revisión de licencia para uso comercial."],
            ),
        ]
        for t in defaults:
            self._templates[t.template_id] = t

    def register(self, template: ProductTemplate) -> None:
        self._templates[template.template_id] = template

    def get(self, template_id: str) -> Optional[ProductTemplate]:
        return self._templates.get(template_id)

    def list_templates(self, sort_by_priority: bool = True) -> List[Dict[str, Any]]:
        templates = list(self._templates.values())
        if sort_by_priority:
            templates.sort(key=lambda t: t.priority)
        return [t.to_dict() for t in templates]
