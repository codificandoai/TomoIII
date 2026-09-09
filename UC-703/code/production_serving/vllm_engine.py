"""Motor de inferencia vLLM simulado para serving de producción."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from production_serving.models_serving import InferenceRequest, InferenceResponse, TokenUsage


class VLLMInferenceEngine:
    """
    Simula un motor de inferencia vLLM de alto rendimiento con continuous
    batching y paged attention. Es determinista e in-memory.
    """

    def __init__(self, default_model: str = "domain-lora-awq") -> None:
        self.default_model = default_model
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        self.load_model(default_model)

    def load_model(self, model_id: str, quantization: str = "awq") -> None:
        self._loaded_models[model_id] = {
            "quantization": quantization,
            "peft_adapter": True,
            "status": "ready",
        }

    def generate(
        self,
        request: InferenceRequest,
        max_tokens: int = 128,
        temperature: float = 0.7,
    ) -> InferenceResponse:
        start = time.time()
        model_id = request.model_id or self.default_model
        if model_id not in self._loaded_models:
            self.load_model(model_id)

        prompt = request.prompt
        # deterministic simulated response
        words = prompt.split() if prompt else ["hello"]
        generated = " ".join(words[:5]) + " [generated]"
        prompt_tokens = len(words)
        completion_tokens = min(max_tokens, len(generated.split()))
        latency_ms = (time.time() - start) * 1000.0
        # ensure non-zero latency for tests
        latency_ms = max(latency_ms, 0.01)

        return InferenceResponse(
            request_id=request.request_id,
            session_id=request.session_id,
            model_id=model_id,
            generated_text=generated,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            latency_ms=round(latency_ms, 4),
            metadata={"temperature": temperature, "max_tokens": max_tokens},
        )

    def stream_generate(self, request: InferenceRequest, max_tokens: int = 20):
        """Generador simulado de tokens para streaming."""
        response = self.generate(request, max_tokens=max_tokens)
        for token in response.generated_text.split():
            yield token
