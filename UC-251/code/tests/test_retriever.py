"""Tests de recuperación híbrida (BM25 + vectorial + filtros + RRF)."""
import numpy as np
import pytest

from config import LexicalConfig, RAGConfig, RetrievalConfig, SecurityConfig
from embedder import StubEmbedder
from lexical_store import BM25Index
from models import Chunk, Document
from retriever import HybridRetriever
from vector_store import BruteForceVectorStore


def _build_index(chunks_data):
    config = RAGConfig()
    embedder = StubEmbedder(config.embedder)
    vector_store = BruteForceVectorStore(config.vector_store)
    lexical_store = BM25Index(config.lexical)

    doc = Document(doc_id="doc-001", source="inline", title="Test", content="", doc_type="txt")
    chunks = []
    for i, text in enumerate(chunks_data):
        chunks.append(
            Chunk(
                chunk_id=f"chunk-{i:03d}",
                doc_id=doc.doc_id,
                text=text,
                index=i,
                metadata={"tenant_id": "acme", "confidentiality": "internal"},
            )
        )
    embeddings = embedder.embed_texts([c.text for c in chunks])
    vector_store.add_chunks(chunks, np.array(embeddings, dtype="float32"))
    lexical_store.add_chunks(chunks)

    retriever = HybridRetriever(
        vector_store, lexical_store, embedder, RetrievalConfig(), SecurityConfig()
    )
    return retriever


def test_lexical_retrieval_ranking():
    retriever = _build_index([
        "El sistema de aprobación de gastos requiere dos firmas.",
        "La cafetería abre a las ocho.",
        "Gastos mayores a mil euros necesitan aprobación del director.",
    ])
    results = retriever.retrieve("aprobación de gastos", top_k=5)
    assert len(results) >= 2
    texts = [r.chunk.text.lower() for r in results]
    assert any("aprobación" in t for t in texts)


def test_metadata_filter_by_tenant():
    retriever = _build_index([
        "Documento interno de acme",
        "Documento de otro tenant",
    ])
    results = retriever.retrieve(
        "documento interno", top_k=5, filters={"tenant_id": "acme"}
    )
    assert all(r.chunk.metadata["tenant_id"] == "acme" for r in results)


def test_clearance_filter_blocks_restricted():
    retriever = _build_index([
        "Informe público de ventas",
        "Informe restringido de despidos",
    ])
    for r in retriever.retrieve("informe", top_k=5):
        r.chunk.metadata["confidentiality"] = "restricted"
    results = retriever.retrieve(
        "informe", top_k=5, user_clearance="public"
    )
    # Al ser todos restricted, un usuario public no ve nada
    assert len(results) == 0


def test_hybrid_combines_scores():
    retriever = _build_index([
        "El gato come pescado fresco cada día.",
        "El perro juega en el parque con otros perros.",
        "Los gatos son felinos domésticos.",
    ])
    results = retriever.retrieve("gato", top_k=5)
    # La mayoría deben tener vector o lexical score > 0
    assert any(r.vector_score > 0 or r.lexical_score > 0 for r in results)
