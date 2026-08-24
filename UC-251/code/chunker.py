"""Estrategias de fragmentación semántica y jerárquica de documentos."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Tuple

from config import ChunkingConfig
from models import Chunk, Document
from text_utils import (
    approximate_duplicate,
    estimate_tokens,
    extract_headings,
    paragraph_split,
    sentence_split,
)

logger = logging.getLogger("uc251-chunker")


class Embedder(Protocol):
    """Protocolo ligero para calcular embeddings durante el chunking semántico."""

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...


def _make_chunk_id(doc: Document, index: int) -> str:
    return f"{doc.doc_id}-chunk-{index:06d}"


class SemanticChunker:
    """Fragmentación semántica configurable."""

    def __init__(self, config: ChunkingConfig, embedder: Optional[Embedder] = None):
        self.config = config
        self.embedder = embedder

    def chunk(self, doc: Document) -> List[Chunk]:
        strategy = self.config.strategy
        if strategy == "fixed":
            return self._fixed_chunks(doc)
        if strategy == "recursive":
            return self._recursive_chunks(doc)
        if strategy == "hierarchical":
            return self._hierarchical_chunks(doc)
        return self._semantic_chunks(doc)

    def _fixed_chunks(self, doc: Document) -> List[Chunk]:
        size = self.config.target_chunk_size
        overlap = self.config.chunk_overlap
        chunks: List[Chunk] = []
        text = doc.content
        start = 0
        index = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunk_text = text[start:end]
            if len(chunk_text) >= self.config.min_chunk_length:
                chunks.append(self._build_chunk(doc, index, chunk_text, start, end))
                index += 1
            start = end if end == len(text) else end - overlap
        return chunks

    def _recursive_chunks(self, doc: Document) -> List[Chunk]:
        """Divide recursivamente por jerarquía de separadores."""
        separators = ["\n\n", "\n", ". ", "! ", "? ", " "]
        chunks: List[Chunk] = []
        index = 0
        self._split_recursive(
            doc, doc.content, 0, len(doc.content), separators, chunks, index_ref=[0]
        )
        return chunks

    def _split_recursive(
        self,
        doc: Document,
        text: str,
        start_char: int,
        end_char: int,
        separators: List[str],
        chunks: List[Chunk],
        index_ref: List[int],
    ) -> None:
        if not text.strip():
            return
        size = self.config.target_chunk_size
        if len(text) <= size:
            if len(text) >= self.config.min_chunk_length:
                chunks.append(
                    self._build_chunk(doc, index_ref[0], text, start_char, end_char)
                )
                index_ref[0] += 1
            return
        if not separators:
            # Forzar corte por caracteres
            self._force_split(doc, text, start_char, end_char, chunks, index_ref)
            return
        sep = separators[0]
        parts = text.split(sep)
        current_text = ""
        current_start = start_char
        for part in parts:
            part_len = len(part) + (len(sep) if sep != " " else 1)
            if current_text and len(current_text) + part_len > size:
                self._split_recursive(
                    doc,
                    current_text,
                    current_start,
                    current_start + len(current_text),
                    separators[1:],
                    chunks,
                    index_ref,
                )
                current_text = part
                current_start = current_start + len(current_text) + len(sep)
            else:
                current_text = (current_text + sep + part) if current_text else part
        if current_text:
            self._split_recursive(
                doc,
                current_text,
                current_start,
                current_start + len(current_text),
                separators[1:],
                chunks,
                index_ref,
            )

    def _force_split(
        self,
        doc: Document,
        text: str,
        start_char: int,
        end_char: int,
        chunks: List[Chunk],
        index_ref: List[int],
    ) -> None:
        size = self.config.target_chunk_size
        overlap = self.config.chunk_overlap
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            piece = text[start:end]
            if len(piece) >= self.config.min_chunk_length:
                chunks.append(
                    self._build_chunk(
                        doc, index_ref[0], piece, start_char + start, start_char + end
                    )
                )
                index_ref[0] += 1
            start = end if end == len(text) else end - overlap

    def _semantic_chunks(self, doc: Document) -> List[Chunk]:
        """Agrupa oraciones en chunks coherentes según similitud de embeddings."""
        sentences = sentence_split(doc.content)
        if not sentences:
            return self._fixed_chunks(doc)
        if self.embedder is None or len(sentences) < 2:
            return self._paragraph_chunks(doc)

        embeddings = self.embedder.embed_texts(sentences)
        if not embeddings or len(embeddings) != len(sentences):
            return self._paragraph_chunks(doc)

        chunks: List[Chunk] = []
        current_sents = [sentences[0]]
        current_start = 0
        current_len = len(sentences[0])
        index = 0
        for i in range(1, len(sentences)):
            prev_emb = embeddings[i - 1]
            curr_emb = embeddings[i]
            sim = self._cosine(prev_emb, curr_emb)
            sent = sentences[i]
            sent_len = len(sent) + 1
            if sim >= self.config.semantic_similarity_threshold and (
                current_len + sent_len <= self.config.target_chunk_size
            ):
                current_sents.append(sent)
                current_len += sent_len
            else:
                chunk_text = " ".join(current_sents)
                if len(chunk_text) >= self.config.min_chunk_length:
                    end = current_start + len(chunk_text)
                    chunks.append(
                        self._build_chunk(doc, index, chunk_text, current_start, end)
                    )
                    index += 1
                current_sents = [sent]
                current_start = sum(len(s) + 1 for s in sentences[:i])
                current_len = sent_len
        if current_sents:
            chunk_text = " ".join(current_sents)
            if len(chunk_text) >= self.config.min_chunk_length:
                start = current_start
                end = start + len(chunk_text)
                chunks.append(
                    self._build_chunk(doc, index, chunk_text, start, end)
                )
        return chunks

    def _paragraph_chunks(self, doc: Document) -> List[Chunk]:
        """Fallback a párrafos."""
        paragraphs = paragraph_split(doc.content)
        chunks: List[Chunk] = []
        index = 0
        pos = 0
        for para in paragraphs:
            if len(para) >= self.config.min_chunk_length:
                chunks.append(
                    self._build_chunk(doc, index, para, pos, pos + len(para))
                )
                index += 1
            pos += len(para) + 2
        return chunks

    def _hierarchical_chunks(self, doc: Document) -> List[Chunk]:
        """Chunks padre (párrafos/secciones) e hijos (ventanas fijas)."""
        headings = extract_headings(doc.content) or doc.metadata.get("extracted_headings", [])
        chunks: List[Chunk] = []
        index = 0
        for para in paragraph_split(doc.content):
            if len(para) < self.config.min_chunk_length:
                continue
            # child chunks sliding over the parent paragraph
            child_size = max(self.config.target_chunk_size // 2, 128)
            overlap = self.config.chunk_overlap // 2
            start = 0
            while start < len(para):
                end = min(start + child_size, len(para))
                child_text = para[start:end]
                if len(child_text) >= self.config.min_chunk_length // 2:
                    chunk = self._build_chunk(
                        doc, index, child_text, start, end, content_type="child"
                    )
                    chunk.metadata["parent_text"] = para
                    chunk.metadata["headings"] = headings
                    chunks.append(chunk)
                    index += 1
                start = end if end == len(para) else end - overlap
        return chunks

    def _build_chunk(
        self,
        doc: Document,
        index: int,
        text: str,
        start: int,
        end: int,
        content_type: str = "paragraph",
    ) -> Chunk:
        return Chunk(
            chunk_id=_make_chunk_id(doc, index),
            doc_id=doc.doc_id,
            text=text,
            index=index,
            start_char=start,
            end_char=end,
            headings=doc.metadata.get("extracted_headings", []),
            content_type=content_type,
            metadata={
                "source": doc.source,
                "title": doc.title,
                "doc_type": doc.doc_type,
                **doc.metadata,
            },
            references=[],
        )

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        import math

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class DeduplicatedChunker:
    """Decorador que elimina chunks duplicados aproximados."""

    def __init__(self, inner: SemanticChunker, threshold: float = 0.95):
        self.inner = inner
        self.threshold = threshold

    def chunk(self, doc: Document) -> List[Chunk]:
        chunks = self.inner.chunk(doc)
        unique: List[Chunk] = []
        for c in chunks:
            if not any(
                approximate_duplicate(c.text, u.text, self.threshold) for u in unique
            ):
                unique.append(c)
        if len(unique) < len(chunks):
            logger.info("Descartados %d chunks duplicados", len(chunks) - len(unique))
        return unique
