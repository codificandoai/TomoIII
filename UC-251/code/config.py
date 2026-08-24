"""Configuración centralizada del pipeline RAG híbrido de UC-251.

Todos los parámetros ajustables (chunking, modelos, umbrales de seguridad,
pesos de fusión, etc.) se cargan desde variables de entorno para facilitar
la experimentación sin modificar código fuente.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class ChunkingConfig:
    """Parámetros de fragmentación semántica."""

    strategy: str = _env_str("UC251_CHUNK_STRATEGY", "semantic")
    # semantic | fixed | recursive | hierarchical
    target_chunk_size: int = _env_int("UC251_CHUNK_SIZE", 512)
    chunk_overlap: int = _env_int("UC251_CHUNK_OVERLAP", 64)
    # Umbral de similitud coseno para fusionar oraciones en chunking semántico
    semantic_similarity_threshold: float = _env_float(
        "UC251_SEMANTIC_SIMILARITY_THRESHOLD", 0.78
    )
    # Tamaño mínimo de chunk en caracteres (descartar residuos muy cortos)
    min_chunk_length: int = _env_int("UC251_MIN_CHUNK_LENGTH", 64)


@dataclass
class EmbedderConfig:
    """Configuración del encoder de embeddings."""

    # 'stub' usa vectores deterministas sin descargar pesos. Recomendado en
    # pruebas/CI. En producción usar sentence-transformers con modelos BGE/E5.
    model_name: str = _env_str("UC251_EMBEDDER_MODEL", "stub")
    embedding_dim: int = _env_int("UC251_EMBEDDING_DIM", 64)
    batch_size: int = _env_int("UC251_EMBEDDER_BATCH_SIZE", 32)
    normalize: bool = _env_bool("UC251_EMBEDDER_NORMALIZE", True)


@dataclass
class VectorStoreConfig:
    """Configuración del almacén vectorial."""

    # 'auto' intenta FAISS y cae a fuerza bruta con numpy si no está disponible
    backend: str = _env_str("UC251_VECTOR_BACKEND", "auto")
    work_dir: str = _env_str("UC251_WORK_DIR", "./uc251_work")


@dataclass
class LexicalConfig:
    """Configuración del índice léxico BM25."""

    k1: float = _env_float("UC251_BM25_K1", 1.5)
    b: float = _env_float("UC251_BM25_B", 0.75)
    # stopwords básicas español/inglés
    stopwords: List[str] = field(default_factory=lambda: [
        "el", "la", "los", "las", "un", "una", "de", "del", "en", "y", "o",
        "a", "que", "con", "por", "para", "su", "se", "es", "al", "lo",
        "como", "the", "a", "an", "of", "in", "on", "and", "or", "to",
        "is", "it", "for", "this", "that", "with",
    ])


@dataclass
class RetrievalConfig:
    """Configuración de recuperación híbrida."""

    top_k_vector: int = _env_int("UC251_TOP_K_VECTOR", 20)
    top_k_lexical: int = _env_int("UC251_TOP_K_LEXICAL", 20)
    rrf_k: int = _env_int("UC251_RRF_K", 60)
    # Número de candidatos que pasan a re-ranking
    rerank_candidates: int = _env_int("UC251_RERANK_CANDIDATES", 10)
    # Número final de fragmentos que se envían al generador
    final_context_chunks: int = _env_int("UC251_FINAL_CONTEXT_CHUNKS", 5)
    # Máximo de tokens estimados del contexto (aprox 4 caracteres/token)
    max_context_tokens: int = _env_int("UC251_MAX_CONTEXT_TOKENS", 2048)
    # Umbral mínimo de score híbrido para considerar un chunk relevante
    min_score_threshold: float = _env_float("UC251_MIN_SCORE_THRESHOLD", 0.01)


@dataclass
class RerankerConfig:
    """Configuración del re-ranker."""

    # 'stub' reordena por solapamiento léxico. Producción: cross-encoder.
    model_name: str = _env_str("UC251_RERANKER_MODEL", "stub")


@dataclass
class GeneratorConfig:
    """Configuración del modelo generativo."""

    # 'stub' devuelve respuestas deterministas con citas. Producción: openai.
    provider: str = _env_str("UC251_GENERATOR_PROVIDER", "stub")
    model_name: str = _env_str("UC251_GENERATOR_MODEL", "stub")
    temperature: float = _env_float("UC251_GENERATOR_TEMPERATURE", 0.0)
    max_tokens: int = _env_int("UC251_GENERATOR_MAX_TOKENS", 512)
    # Prompt de sistema; puede sobrescribirse con UC251_SYSTEM_PROMPT
    system_prompt: str = _env_str(
        "UC251_SYSTEM_PROMPT",
        "Responde exclusivamente con la información proporcionada en el contexto. "
        "Cita los IDs de fragmento entre corchetes, p. ej. [chunk-123]. "
        "Si no hay información suficiente, responde: 'No dispongo de información "
        "suficiente para responder con seguridad.'",
    )


@dataclass
class SecurityConfig:
    """Configuración de seguridad y gobernanza."""

    enabled: bool = _env_bool("UC251_SECURITY_ENABLED", True)
    prompt_injection_threshold: int = _env_int(
        "UC251_PROMPT_INJECTION_THRESHOLD", 1
    )
    pii_redaction_enabled: bool = _env_bool("UC251_PII_REDACTION_ENABLED", True)
    # Niveles de confidencialidad ordenados de menor a mayor
    confidentiality_levels: List[str] = field(default_factory=lambda: [
        "public", "internal", "confidential", "restricted"
    ])


@dataclass
class EvaluationConfig:
    """Configuración de evaluación RAGAS."""

    # 'heuristic' no requiere API key. 'openai' usa LLM-as-a-Judge.
    judge_provider: str = _env_str("UC251_JUDGE_PROVIDER", "heuristic")
    judge_model: str = _env_str("UC251_JUDGE_MODEL", "stub")


@dataclass
class RAGConfig:
    """Configuración global del pipeline."""

    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    lexical: LexicalConfig = field(default_factory=LexicalConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    generator: GeneratorConfig = field(default_factory=GeneratorConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)


# Singleton global (puede reemplazarse en tests)
CONFIG = RAGConfig()
