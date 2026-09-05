"""UC-320 — HuggingFace Model Gateway con backend mock y HF opcional."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from model_catalog import ModelCatalog


@dataclass
class ModelResult:
    model_id: str
    provider: str
    text: str
    latency_ms: float
    request_id: str
    confidence: Optional[float] = None
    input_hash: str = ""
    output_hash: str = ""
    cost_estimate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "text": self.text,
            "latency_ms": round(self.latency_ms, 2),
            "request_id": self.request_id,
            "confidence": self.confidence,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "cost_estimate": self.cost_estimate,
            "metadata": self.metadata,
        }


class MockBackend:
    """Backend determinista para tests y demos sin red."""

    def __init__(self, catalog: ModelCatalog) -> None:
        self.catalog = catalog

    def chat(
        self,
        model_id: str,
        provider: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        entry = self.catalog.get(model_id)
        task = entry.task if entry else "text-generation"

        last_content = messages[-1].get("content", "") if messages else ""

        if task == "sentiment":
            lower = last_content.lower()
            if any(w in lower for w in ["beat", "surge", "rally", "positive", "up", "gain"]):
                label, conf = "positive", 0.88
            elif any(w in lower for w in ["miss", "drop", "fall", "negative", "down", "loss"]):
                label, conf = "negative", 0.85
            elif any(w in lower for w in ["uncertain", "mixed", "unclear"]):
                label, conf = "uncertain", 0.60
            else:
                label, conf = "neutral", 0.70
            text = json.dumps({
                "label": label,
                "confidence": conf,
                "entities": [],
                "rationale": f"Mock sentiment for {model_id}",
            })
        elif task == "embeddings":
            # Hash determinista como vector simulado de 384 dims.
            h = hashlib.sha256(last_content.encode()).hexdigest()
            vector = [(int(h[i : i + 2], 16) / 255.0) for i in range(0, 64, 1)][:384]
            text = json.dumps({"embedding": vector, "dim": len(vector)})
        elif task == "zero-shot-classification":
            text = json.dumps({
                "labels": ["billing", "support", "cancellation", "escalation"],
                "scores": [0.4, 0.3, 0.2, 0.1],
            })
        elif task == "asr":
            text = "Mock transcription of audio input."
        elif task == "ocr":
            text = "Mock OCR extracted text."
        elif task == "rerank":
            text = json.dumps({"ranked": [0, 2, 1], "scores": [0.9, 0.7, 0.5]})
        else:
            text = f"Mock response from {model_id}: {last_content[:100]}"

        return {
            "text": text,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


class HuggingFaceBackend:
    """Backend real usando huggingface_hub.InferenceClient."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or os.environ.get("HF_TOKEN")
        if not self.token:
            raise RuntimeError("HF_TOKEN not configured")
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            raise RuntimeError("huggingface_hub not installed") from exc
        self.client = InferenceClient(token=self.token)

    def chat(
        self,
        model_id: str,
        provider: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        output = self.client.chat.completions.create(
            model=f"{model_id}:{provider}" if provider != "hf-inference" else model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = output.choices[0].message.content or ""
        return {"text": text, "usage": getattr(output, "usage", {}) or {}}


class HuggingFaceModelGateway:
    """Gateway unificado de modelos con allowlist, validación y auditoría.

    UC-315 invoca este gateway mediante contratos tipados. UC-324 intercepta
    cada operación. El gateway no permite que el modelo llame tools ni
    ejecute acciones externas.
    """

    MAX_INPUT_CHARS = 12000

    def __init__(
        self,
        catalog: Optional[ModelCatalog] = None,
        backend: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self.catalog = catalog or ModelCatalog()
        self.backend_name = backend or os.environ.get("UC320_BACKEND", "mock")
        self.token = token or os.environ.get("HF_TOKEN")
        self._mock = MockBackend(self.catalog)
        self._hf: Optional[HuggingFaceBackend] = None
        self.audit_log: List[Dict[str, Any]] = []

    def _get_backend(self) -> Any:
        if self.backend_name == "huggingface":
            if self._hf is None:
                self._hf = HuggingFaceBackend(token=self.token)
            return self._hf
        return self._mock

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def chat(
        self,
        *,
        model_id: str,
        provider: str,
        messages: List[Dict[str, str]],
        request_id: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> ModelResult:
        rid = request_id or f"req_{uuid.uuid4().hex[:12]}"

        # Validaciones de frontera.
        if not self.catalog.is_allowed(model_id):
            raise PermissionError(f"model_not_allowlisted: {model_id}")
        entry = self.catalog.get(model_id)
        if entry and entry.provider != provider and provider != "mock":
            raise PermissionError(f"provider_not_allowlisted: {provider}")
        if any(len(m.get("content", "")) > self.MAX_INPUT_CHARS for m in messages):
            raise ValueError("input_too_large")

        input_text = json.dumps(messages, ensure_ascii=False)
        input_hash = self._hash(input_text)

        started = time.perf_counter()
        backend = self._get_backend()
        raw = backend.chat(model_id, provider, messages, max_tokens, temperature)
        latency_ms = (time.perf_counter() - started) * 1000

        text = raw.get("text", "")
        output_hash = self._hash(text)
        cost = (len(input_text) / 1000) * (entry.cost_per_1k if entry else 0.0)

        result = ModelResult(
            model_id=model_id,
            provider=provider,
            text=text,
            latency_ms=latency_ms,
            request_id=rid,
            input_hash=input_hash,
            output_hash=output_hash,
            cost_estimate=round(cost, 6),
            metadata={"usage": raw.get("usage", {}), "task": entry.task if entry else "unknown"},
        )

        self.audit_log.append({
            "request_id": rid,
            "model_id": model_id,
            "provider": provider,
            "latency_ms": round(latency_ms, 2),
            "cost_estimate": result.cost_estimate,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "timestamp": time.time(),
        })

        return result

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.audit_log[-limit:]
