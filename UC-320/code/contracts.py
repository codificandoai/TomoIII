"""UC-320 — Secure Contract: contrato tipado entre UC-315, UC-317 y UC-324."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SecureContract(BaseModel):
    """Contrato seguro entre los sistemas.

    Ningún modelo descargado, inferencia, dataset, checkpoint o endpoint
    puede autorizar por sí mismo una compra, reserva, pago, cambio de
    infraestructura o modificación de políticas.
    """

    request_id: str = Field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:8]}")
    caller: str = "UC-315"
    executor: str = "UC-317"
    guard: str = "UC-324"
    operation: str = "model_inference"
    domain: str = "trading"
    model_id: str = ""
    model_revision: str = ""
    provider: str = ""
    input_class: str = "market_news_public"
    action_class: str = "read"
    risk_level: str = "low"
    max_cost: float = 0.05
    max_latency_ms: float = 3000.0
    output_schema: str = "SentimentEvidence.v1"
    allow_tools: bool = False
    requires_human_approval: bool = False
    audit_required: bool = True
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = Field(default_factory=time.time)
    input: Dict[str, Any] = Field(default_factory=dict)

    def to_gate_dict(self, allowed_models: Optional[set] = None, estimated_cost: float = 0.0, estimated_latency: float = 500.0) -> Dict[str, Any]:
        """Convierte el contrato al formato esperado por UC324GateIntegrator."""
        d = self.model_dump()
        d["_allowed_models"] = allowed_models or set()
        d["_estimated_cost"] = estimated_cost
        d["_estimated_latency"] = estimated_latency
        return d


class ContractBuilder:
    """Helper para construir contratos seguros."""

    @staticmethod
    def sentiment_inference(
        ticker: str,
        article: str,
        model_id: str = "mock/sentiment-mock",
        provider: str = "mock",
    ) -> SecureContract:
        return SecureContract(
            operation="model_inference",
            domain="trading",
            model_id=model_id,
            provider=provider,
            input_class="market_news_public",
            action_class="read",
            risk_level="low",
            output_schema="SentimentEvidence.v1",
            allow_tools=False,
            requires_human_approval=False,
            input={"ticker": ticker, "article": article},
        )

    @staticmethod
    def embedding(
        text: str,
        model_id: str = "sentence-transformers/all-MiniLM-L6-v2",
        provider: str = "hf-inference",
    ) -> SecureContract:
        return SecureContract(
            operation="embedding",
            domain="memory",
            model_id=model_id,
            provider=provider,
            input_class="internal_text",
            action_class="read",
            risk_level="low",
            output_schema="EmbeddingResult.v1",
            input={"text": text},
        )

    @staticmethod
    def training(
        base_model: str,
        dataset_id: str,
        dataset_revision: str,
        objective: str,
    ) -> SecureContract:
        return SecureContract(
            operation="training",
            domain="model_development",
            model_id=base_model,
            input_class="internal_dataset",
            action_class="execute",
            risk_level="high",
            max_cost=10.0,
            max_latency_ms=3600000,  # 1 hour
            output_schema="TrainingJob.v1",
            requires_human_approval=True,
            input={
                "base_model": base_model,
                "dataset_id": dataset_id,
                "dataset_revision": dataset_revision,
                "objective": objective,
            },
        )

    @staticmethod
    def model_promotion(job_id: str, checkpoint_hash: str) -> SecureContract:
        return SecureContract(
            operation="model_promotion",
            domain="deployment",
            action_class="execute",
            risk_level="critical",
            max_cost=0.0,
            requires_human_approval=True,
            input={"job_id": job_id, "checkpoint_hash": checkpoint_hash},
        )
