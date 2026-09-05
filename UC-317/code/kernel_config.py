"""Configuración nativa del kernel AIOS-style de UC-317."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ModelConfig:
    provider: str  # "mock", "openai", "ollama", "huggingface", "azure"
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KernelConfig:
    default_model: str = "mock"
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    max_agents: int = 8
    memory_backend: str = "local"  # local, chromadb
    storage_backend: str = "local"  # local, sqlite
    tool_timeout: float = 30.0
    log_level: str = "INFO"

    @classmethod
    def default(cls) -> "KernelConfig":
        return cls(
            default_model="mock",
            models={
                "mock": ModelConfig(provider="mock", model="mock-llm"),
                "openai": ModelConfig(
                    provider="openai",
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=os.getenv("OPENAI_API_KEY"),
                ),
                "ollama": ModelConfig(
                    provider="ollama",
                    model=os.getenv("OLLAMA_MODEL", "llama3.1"),
                    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                ),
            },
        )

    def get_model(self, name: Optional[str] = None) -> ModelConfig:
        key = name or self.default_model
        return self.models.get(key, self.models.get("mock", ModelConfig(provider="mock", model="mock-llm")))
