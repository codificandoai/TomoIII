"""UC-320 — Model Catalog: registro y allowlist de modelos aprobados."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ModelEntry:
    model_id: str
    provider: str
    revision: str  # commit SHA pinned
    license: str
    task: str  # sentiment, embeddings, text-generation, asr, vision, rerank
    hardware: str = "cpu"
    cost_per_1k: float = 0.0
    latency_ms: float = 500.0
    languages: List[str] = field(default_factory=lambda: ["en"])
    limitations: List[str] = field(default_factory=list)
    approved: bool = False
    approved_date: Optional[str] = None
    model_card_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "revision": self.revision,
            "license": self.license,
            "task": self.task,
            "hardware": self.hardware,
            "cost_per_1k": self.cost_per_1k,
            "latency_ms": self.latency_ms,
            "languages": self.languages,
            "limitations": self.limitations,
            "approved": self.approved,
            "approved_date": self.approved_date,
            "model_card_url": self.model_card_url,
        }


class ModelCatalog:
    """Registro interno de modelos aprobados para UTRON.ai."""

    def __init__(self) -> None:
        self._models: Dict[str, ModelEntry] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            ModelEntry(
                model_id="mock/sentiment-mock",
                provider="mock",
                revision="mock-v1",
                license="internal",
                task="sentiment",
                cost_per_1k=0.0,
                latency_ms=1.0,
                languages=["en", "es"],
                approved=True,
                approved_date="2026-01-01",
            ),
            ModelEntry(
                model_id="ProsusAI/finbert",
                provider="hf-inference",
                revision="main",
                license="MIT",
                task="sentiment",
                cost_per_1k=0.001,
                latency_ms=800.0,
                languages=["en"],
                limitations=["No debe aprobar operaciones de trading por sí solo."],
                approved=True,
                approved_date="2026-01-15",
                model_card_url="https://huggingface.co/ProsusAI/finbert",
            ),
            ModelEntry(
                model_id="sentence-transformers/all-MiniLM-L6-v2",
                provider="hf-inference",
                revision="main",
                license="Apache-2.0",
                task="embeddings",
                cost_per_1k=0.0001,
                latency_ms=100.0,
                languages=["en"],
                approved=True,
                approved_date="2026-01-15",
                model_card_url="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2",
            ),
            ModelEntry(
                model_id="BAAI/bge-m3",
                provider="hf-inference",
                revision="main",
                license="MIT",
                task="embeddings",
                cost_per_1k=0.0002,
                latency_ms=200.0,
                languages=["en", "es", "fr", "de", "zh", "ja"],
                approved=True,
                approved_date="2026-02-01",
                model_card_url="https://huggingface.co/BAAI/bge-m3",
            ),
            ModelEntry(
                model_id="BAAI/bge-reranker-v2-m3",
                provider="hf-inference",
                revision="main",
                license="MIT",
                task="rerank",
                cost_per_1k=0.0003,
                latency_ms=300.0,
                approved=True,
                approved_date="2026-02-01",
            ),
            ModelEntry(
                model_id="Qwen/Qwen3-8B",
                provider="hf-inference",
                revision="main",
                license="Apache-2.0",
                task="text-generation",
                cost_per_1k=0.01,
                latency_ms=1500.0,
                languages=["en", "es", "zh", "ja"],
                approved=True,
                approved_date="2026-02-10",
            ),
            ModelEntry(
                model_id="mistralai/Mistral-7B-Instruct-v0.3",
                provider="hf-inference",
                revision="main",
                license="Apache-2.0",
                task="text-generation",
                cost_per_1k=0.008,
                latency_ms=1200.0,
                approved=True,
                approved_date="2026-02-10",
            ),
            ModelEntry(
                model_id="openai/whisper-large-v3",
                provider="hf-inference",
                revision="main",
                license="MIT",
                task="asr",
                cost_per_1k=0.02,
                latency_ms=5000.0,
                approved=True,
                approved_date="2026-02-15",
            ),
            ModelEntry(
                model_id="facebook/bart-large-mnli",
                provider="hf-inference",
                revision="main",
                license="MIT",
                task="zero-shot-classification",
                cost_per_1k=0.002,
                latency_ms=600.0,
                approved=True,
                approved_date="2026-02-15",
            ),
            ModelEntry(
                model_id="microsoft/trocr-base-handwritten",
                provider="hf-inference",
                revision="main",
                license="MIT",
                task="ocr",
                cost_per_1k=0.005,
                latency_ms=1000.0,
                approved=True,
                approved_date="2026-02-20",
            ),
            ModelEntry(
                model_id="stabilityai/stable-diffusion-xl-base-1.0",
                provider="hf-inference",
                revision="main",
                license="CreativeML Open RAIL++-M",
                task="image-generation",
                cost_per_1k=0.05,
                latency_ms=8000.0,
                limitations=["Requiere revisión de licencia para uso comercial."],
                approved=False,
                approved_date=None,
            ),
        ]
        for m in defaults:
            self._models[m.model_id] = m

    def register(self, entry: ModelEntry) -> None:
        self._models[entry.model_id] = entry

    def get(self, model_id: str) -> Optional[ModelEntry]:
        return self._models.get(model_id)

    def is_allowed(self, model_id: str) -> bool:
        entry = self._models.get(model_id)
        return entry is not None and entry.approved

    def list_models(self, task: Optional[str] = None) -> List[Dict[str, Any]]:
        models = list(self._models.values())
        if task:
            models = [m for m in models if m.task == task]
        return [m.to_dict() for m in models]

    def allowed_models(self) -> Set[str]:
        return {m.model_id for m in self._models.values() if m.approved}

    def allowed_providers(self) -> Set[str]:
        return {m.provider for m in self._models.values() if m.approved}
