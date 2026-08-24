"""Selección, deduplicación y ensamblaje del contexto final para el LLM."""
from __future__ import annotations

import logging
from typing import List, Tuple

from config import RetrievalConfig
from models import Chunk, RetrievalResult
from text_utils import approximate_duplicate, estimate_tokens

logger = logging.getLogger("uc251-context-assembler")


class ContextAssembler:
    """Construye el contexto final a partir de resultados re-rankeados."""

    def __init__(self, config: RetrievalConfig):
        self.config = config

    def assemble(
        self, results: List[RetrievalResult]
    ) -> Tuple[str, List[RetrievalResult]]:
        """Devuelve (context_string, selected_results)."""
        deduped = self._deduplicate(results)
        selected = self._select(deduped)
        context_parts = []
        for i, res in enumerate(selected, start=1):
            meta = res.chunk.metadata
            header = (
                f"[{i}] chunk_id={res.chunk.chunk_id} "
                f"source={meta.get('source', 'unknown')} "
                f"title={meta.get('title', 'unknown')}"
            )
            context_parts.append(f"{header}\n{res.chunk.text}")
        context = "\n\n".join(context_parts)
        return context, selected

    def _deduplicate(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Elimina chunks con contenido casi idéntico, conservando el de mayor score."""
        kept: List[RetrievalResult] = []
        for res in sorted(results, key=lambda r: r.rerank_score or 0.0, reverse=True):
            if not any(
                approximate_duplicate(res.chunk.text, k.chunk.text, threshold=0.92)
                for k in kept
            ):
                kept.append(res)
        return kept

    def _select(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Selecciona los top-k fragmentos que caben en la ventana de tokens."""
        selected: List[RetrievalResult] = []
        total_tokens = 0
        # estimación rápida: 1 token ~ 4 caracteres + overhead de encabezado
        for res in results:
            chunk_tokens = estimate_tokens(res.chunk.text) + 10
            if len(selected) >= self.config.final_context_chunks:
                break
            if total_tokens + chunk_tokens > self.config.max_context_tokens:
                # Si el fragmento es muy grande, intentar truncar no es responsabilidad
                # del assembler; simplemente omitimos chunks que no caben.
                continue
            selected.append(res)
            total_tokens += chunk_tokens
        return selected

    @staticmethod
    def detect_conflicts(results: List[RetrievalResult]) -> List[Tuple[str, str, str]]:
        """Heurística simple de conflictos: señales de negación opuesta.

        Devuelve tripletas (chunk_a_id, chunk_b_id, reason).
        """
        conflicts = []
        negations = {"no", "not", "nunca", "never", "false"}
        positives = {"sí", "yes", "siempre", "always", "true"}
        for i, a in enumerate(results):
            at = a.chunk.text.lower()
            for b in results[i + 1 :]:
                bt = b.chunk.text.lower()
                has_neg_a = any(n in at for n in negations)
                has_pos_a = any(p in at for p in positives)
                has_neg_b = any(n in bt for n in negations)
                has_pos_b = any(p in bt for p in positives)
                if (has_neg_a and has_pos_b) or (has_pos_a and has_neg_b):
                    conflicts.append(
                        (a.chunk.chunk_id, b.chunk.chunk_id, "posible contradicción")
                    )
        return conflicts
