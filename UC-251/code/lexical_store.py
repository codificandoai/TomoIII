"""Índice léxico BM25 ligero con filtrado por metadatos."""
from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional

from config import LexicalConfig
from models import Chunk
from text_utils import tokenize

logger = logging.getLogger("uc251-lexical-store")


class BM25Index:
    """BM25 clásico sobre tokens alfanuméricos."""

    def __init__(self, config: LexicalConfig):
        self.config = config
        self.k1 = config.k1
        self.b = config.b
        self.stopwords = set(config.stopwords)
        self.chunks: List[Chunk] = []
        self.tokenized_docs: List[List[str]] = []
        self.doc_freq: Dict[str, int] = Counter()
        self.total_tokens_per_doc: List[int] = []
        self.avg_doc_len: float = 0.0

    def add_chunks(self, chunks: List[Chunk]) -> None:
        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            self.chunks.append(chunk)
            self.tokenized_docs.append(tokens)
            self.total_tokens_per_doc.append(len(tokens))
            for token in set(tokens):
                self.doc_freq[token] += 1
        self.avg_doc_len = (
            sum(self.total_tokens_per_doc) / len(self.total_tokens_per_doc)
            if self.total_tokens_per_doc
            else 0.0
        )

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in tokenize(text) if t not in self.stopwords]

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_fn: Optional[Callable[[Chunk], bool]] = None,
    ) -> List[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        n = len(self.chunks)
        scores: Dict[int, float] = defaultdict(float)
        for i, tokens in enumerate(self.tokenized_docs):
            chunk = self.chunks[i]
            if filter_fn and not filter_fn(chunk):
                continue
            doc_len = self.total_tokens_per_doc[i]
            tf = Counter(tokens)
            score = 0.0
            for t in q_tokens:
                df = self.doc_freq.get(t, 0)
                idf = math.log(((n - df + 0.5) / (df + 0.5)) + 1.0)
                f = tf.get(t, 0)
                denom = f + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                score += idf * ((f * (self.k1 + 1)) / denom) if denom else 0.0
            if score > 0:
                scores[i] = score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.chunks[i], s) for i, s in ranked]

    def count(self) -> int:
        return len(self.chunks)
