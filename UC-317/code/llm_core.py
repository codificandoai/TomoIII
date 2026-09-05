"""UC-317 — LLM Core: enrutador de modelos con backends mock, OpenAI, Ollama."""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from kernel_config import KernelConfig, ModelConfig


@dataclass
class LLMResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = None
    usage: Dict[str, int] = None
    model: str = "unknown"
    provider: str = "unknown"

    def __post_init__(self) -> None:
        if self.tool_calls is None:
            self.tool_calls = []
        if self.usage is None:
            self.usage = {}


class LLMBackend(ABC):
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        ...


class MockLLMBackend(LLMBackend):
    """Backend determinista para tests y demostraciones."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.responses = {
            "hello": "Hello! How can I help?",
            "plan": "I will break this task into steps.",
            "default": "Mock LLM response.",
        }

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        last = messages[-1].get("content", "").lower() if messages else ""
        content = self.responses.get("default")
        for key, value in self.responses.items():
            if key in last:
                content = value
                break

        tool_calls = []
        if tools:
            for tool in tools:
                name = tool.get("function", {}).get("name", "")
                if name in last or name.replace("_", " ") in last:
                    tool_calls.append({
                        "id": f"call_{name}",
                        "type": "function",
                        "function": {"name": name, "arguments": "{}"},
                    })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            model=self.config.model,
            provider="mock",
        )


class OpenAIBackend(LLMBackend):
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = config.base_url or "https://api.openai.com/v1"

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        return LLMResponse(
            content=choice.get("content", ""),
            tool_calls=choice.get("tool_calls", []),
            usage=data.get("usage", {}),
            model=self.config.model,
            provider="openai",
        )


class OllamaBackend(LLMBackend):
    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.base_url = config.base_url or "http://localhost:11434"

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message", {})
        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=message.get("tool_calls", []),
            usage=data.get("eval_count", {}),
            model=self.config.model,
            provider="ollama",
        )


class LLMCore:
    """Enrutador de inferencias a distintos backends."""

    def __init__(self, config: KernelConfig) -> None:
        self.config = config
        self._backends: Dict[str, LLMBackend] = {}

    def _get_backend(self, name: Optional[str] = None) -> LLMBackend:
        model_cfg = self.config.get_model(name)
        key = model_cfg.provider
        if key not in self._backends:
            if model_cfg.provider == "mock":
                self._backends[key] = MockLLMBackend(model_cfg)
            elif model_cfg.provider == "openai":
                self._backends[key] = OpenAIBackend(model_cfg)
            elif model_cfg.provider == "ollama":
                self._backends[key] = OllamaBackend(model_cfg)
            else:
                self._backends[key] = MockLLMBackend(model_cfg)
        return self._backends[key]

    def generate(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        return self._get_backend(model).generate(messages, tools)

    def list_models(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "provider": cfg.provider, "model": cfg.model}
            for name, cfg in self.config.models.items()
        ]
