"""UC-320 — Skills de UC-315 que usan el HF Gateway."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from hf_gateway import HuggingFaceModelGateway, ModelResult
from pydantic import BaseModel, Field


class SentimentEvidence(BaseModel):
    """Evidencia de sentimiento de mercado — nunca es una orden ejecutable."""

    label: str = Field(pattern="^(positive|neutral|negative|uncertain)$")
    confidence: float = Field(ge=0.0, le=1.0)
    entities: List[str] = Field(default_factory=list)
    rationale: str = ""
    model_id: str = ""
    request_id: str = ""
    timestamp: float = 0.0


class EmbeddingResult(BaseModel):
    """Resultado de embeddings para búsqueda semántica."""

    vector: List[float]
    dim: int
    model_id: str = ""
    request_id: str = ""


class ClassificationResult(BaseModel):
    """Resultado de clasificación zero-shot."""

    labels: List[str]
    scores: List[float]
    model_id: str = ""
    request_id: str = ""


class MarketSentimentSkill:
    """Skill de solo lectura: clasifica sentimiento de noticias de mercado.

    UC-315 combina esta evidencia con precio, volumen, volatilidad y memoria.
    Una confianza de 0.92 NO significa autorización para operar.
    """

    action_class = "read"
    risk_level = "low"
    reversible = True

    def __init__(self, gateway: HuggingFaceModelGateway, model_id: str = "mock/sentiment-mock") -> None:
        self.hf = gateway
        self.model_id = model_id

    def run(self, ticker: str, article: str, request_id: Optional[str] = None) -> SentimentEvidence:
        rid = request_id or f"sent_{uuid.uuid4().hex[:12]}"
        result = self.hf.chat(
            model_id=self.model_id,
            provider=self.hf.catalog.get(self.model_id).provider if self.hf.catalog.get(self.model_id) else "mock",
            request_id=rid,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify market sentiment. Return JSON only with label, "
                        "confidence, entities and rationale. Do not propose trades."
                    ),
                },
                {"role": "user", "content": f"Ticker: {ticker}\nArticle: {article}"},
            ],
        )
        try:
            data = json.loads(result.text)
        except json.JSONDecodeError:
            data = {"label": "uncertain", "confidence": 0.0, "entities": [], "rationale": "parse_error"}
        return SentimentEvidence(
            label=data.get("label", "uncertain"),
            confidence=float(data.get("confidence", 0.0)),
            entities=data.get("entities", []),
            rationale=data.get("rationale", ""),
            model_id=result.model_id,
            request_id=result.request_id,
            timestamp=__import__("time").time(),
        )


class SemanticEmbeddingSkill:
    """Skill de solo lectura: genera embeddings para búsqueda semántica."""

    action_class = "read"
    risk_level = "low"
    reversible = True

    def __init__(self, gateway: HuggingFaceModelGateway, model_id: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.hf = gateway
        self.model_id = model_id

    def run(self, text: str, request_id: Optional[str] = None) -> EmbeddingResult:
        import time as _t
        rid = request_id or f"emb_{uuid.uuid4().hex[:12]}"
        entry = self.hf.catalog.get(self.model_id)
        result = self.hf.chat(
            model_id=self.model_id,
            provider=entry.provider if entry else "mock",
            request_id=rid,
            messages=[{"role": "user", "content": text}],
        )
        try:
            data = json.loads(result.text)
            vector = data.get("embedding", [])
            dim = data.get("dim", len(vector))
        except json.JSONDecodeError:
            vector, dim = [], 0
        return EmbeddingResult(
            vector=vector,
            dim=dim,
            model_id=result.model_id,
            request_id=result.request_id,
        )


class ZeroShotClassificationSkill:
    """Skill de solo lectura: clasificación zero-shot para routing."""

    action_class = "read"
    risk_level = "low"
    reversible = True

    def __init__(self, gateway: HuggingFaceModelGateway, model_id: str = "facebook/bart-large-mnli") -> None:
        self.hf = gateway
        self.model_id = model_id

    def run(self, text: str, candidate_labels: Optional[List[str]] = None, request_id: Optional[str] = None) -> ClassificationResult:
        rid = request_id or f"cls_{uuid.uuid4().hex[:12]}"
        entry = self.hf.catalog.get(self.model_id)
        labels_hint = ", ".join(candidate_labels) if candidate_labels else ""
        result = self.hf.chat(
            model_id=self.model_id,
            provider=entry.provider if entry else "mock",
            request_id=rid,
            messages=[
                {"role": "system", "content": f"Classify into: {labels_hint}. Return JSON with labels and scores."},
                {"role": "user", "content": text},
            ],
        )
        try:
            data = json.loads(result.text)
            labels = data.get("labels", [])
            scores = data.get("scores", [])
        except json.JSONDecodeError:
            labels, scores = [], []
        return ClassificationResult(
            labels=labels,
            scores=scores,
            model_id=result.model_id,
            request_id=result.request_id,
        )
