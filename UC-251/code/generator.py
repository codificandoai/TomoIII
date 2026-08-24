"""Generación de respuestas con prompts estructurados y citas."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import List

from config import GeneratorConfig
from models import Citation, RetrievalResult

logger = logging.getLogger("uc251-generator")


class PromptBuilder:
    """Construye el prompt final para el LLM."""

    SYSTEM = (
        "Eres un asistente empresarial que responde ÚNICAMENTE con información "
        "presente en el contexto recuperado. No inventes datos ni uses conocimiento externo. "
        "Cada afirmación debe ir acompañada de una cita con el formato [chunk_id]. "
        "Si el contexto no contiene la respuesta, di exactamente: "
        "'No dispongo de información suficiente para responder con seguridad.'"
    )

    @classmethod
    def build(cls, question: str, context: str, config: GeneratorConfig) -> str:
        system = config.system_prompt or cls.SYSTEM
        return (
            f"{system}\n\n"
            f"--- CONTEXTO ---\n{context}\n\n"
            f"--- PREGUNTA ---\n{question}\n\n"
            "Responde de forma concisa, fundamentada y con citas [chunk_id]."
        )


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        question: str,
        context: str,
        selected_results: List[RetrievalResult],
        config: GeneratorConfig,
    ) -> tuple[str, List[Citation], bool]:
        """Devuelve (answer, citations, insufficient_info)."""
        ...


class StubLLMClient(BaseLLMClient):
    """Generador determinista para tests y entornos sin API key."""

    INSUFFICIENT_PHRASE = (
        "No dispongo de información suficiente para responder con seguridad."
    )

    def generate(
        self,
        question: str,
        context: str,
        selected_results: List[RetrievalResult],
        config: GeneratorConfig,
    ) -> tuple[str, List[Citation], bool]:
        if not selected_results:
            return self.INSUFFICIENT_PHRASE, [], True

        parts = ["Según el contexto proporcionado:"]
        citations = []
        for res in selected_results[:3]:
            excerpt = res.chunk.text[:200].replace("\n", " ")
            parts.append(
                f"- [{res.chunk.chunk_id}]: {excerpt}..."
            )
            citations.append(
                Citation(
                    chunk_id=res.chunk.chunk_id,
                    doc_id=res.chunk.doc_id,
                    source=res.chunk.metadata.get("source", "unknown"),
                    excerpt=excerpt,
                    score=res.rerank_score or res.hybrid_score,
                )
            )
        answer = " ".join(parts)
        return answer, citations, False


class OpenAILLMClient(BaseLLMClient):
    """Cliente OpenAI compatible. Requiere OPENAI_API_KEY."""

    def generate(
        self,
        question: str,
        context: str,
        selected_results: List[RetrievalResult],
        config: GeneratorConfig,
    ) -> tuple[str, List[Citation], bool]:
        try:
            import openai
        except Exception as exc:  # pragma: no cover
            raise ImportError("openai no está instalado") from exc

        prompt = PromptBuilder.build(question, context, config)
        start = time.time()
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model=config.model_name,
            messages=[
                {"role": "system", "content": PromptBuilder.SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        latency_ms = (time.time() - start) * 1000
        logger.info("OpenAI generation latency_ms=%.2f", latency_ms)
        answer = resp.choices[0].message.content or ""
        insufficient = StubLLMClient.INSUFFICIENT_PHRASE in answer
        citations = _build_citations_from_answer(answer, selected_results)
        return answer, citations, insufficient


def _build_citations_from_answer(
    answer: str, selected_results: List[RetrievalResult]
) -> List[Citation]:
    """Extrae citas del texto del LLM vinculándolas con los chunks seleccionados."""
    import re

    cited_ids = set(re.findall(r"\[([a-zA-Z0-9_\-]+)\]", answer))
    citations = []
    for cid in cited_ids:
        for res in selected_results:
            if res.chunk.chunk_id == cid:
                citations.append(
                    Citation(
                        chunk_id=cid,
                        doc_id=res.chunk.doc_id,
                        source=res.chunk.metadata.get("source", "unknown"),
                        excerpt=res.chunk.text[:200],
                        score=res.rerank_score or res.hybrid_score,
                    )
                )
                break
    return citations


def build_llm_client(config: GeneratorConfig) -> BaseLLMClient:
    if config.provider == "openai":
        return OpenAILLMClient()
    if config.provider == "stub":
        return StubLLMClient()
    raise ValueError(f"Proveedor de LLM desconocido: {config.provider}")
