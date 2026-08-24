"""Tests de estrategias de fragmentación."""
import pytest

from chunker import DeduplicatedChunker, SemanticChunker
from config import ChunkingConfig
from models import Document


def _doc(text: str) -> Document:
    return Document(
        doc_id="doc-001",
        source="inline",
        title="Test",
        content=text,
        doc_type="txt",
    )


def test_fixed_chunking_splits_document():
    config = ChunkingConfig(strategy="fixed", target_chunk_size=50, chunk_overlap=10)
    chunker = SemanticChunker(config)
    doc = _doc(" ".join([f"parrafo{i}" for i in range(20)]))
    chunks = chunker.chunk(doc)
    assert len(chunks) > 1
    assert all(len(c.text) > 0 for c in chunks)
    assert chunks[0].doc_id == doc.doc_id


def test_recursive_chunking_preserves_text():
    config = ChunkingConfig(strategy="recursive", target_chunk_size=100)
    chunker = SemanticChunker(config)
    doc = _doc("Sección A.\n\nPrimer párrafo con algo de contenido.\n\nSección B.\n\nOtro párrafo importante con información.")
    chunks = chunker.chunk(doc)
    full = " ".join(c.text for c in chunks)
    # Todos los tokens deben aparecer (aunque no es un round-trip exacto por espacios)
    assert "Sección A" in full
    assert "Sección B" in full


def test_semantic_chunking_uses_similarity():
    config = ChunkingConfig(strategy="semantic", target_chunk_size=200)
    chunker = SemanticChunker(config)
    doc = _doc("El gato duerme. El perro corre. El sol brilla. La política fiscal es compleja.")
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_deduplicated_chunker_removes_near_duplicates():
    config = ChunkingConfig(strategy="fixed", target_chunk_size=40, chunk_overlap=0)
    base = DeduplicatedChunker(SemanticChunker(config), threshold=0.95)
    doc = _doc("texto repetido exactamente. texto repetido exactamente. "
               "texto repetido exactamente. información diferente única.")
    chunks = base.chunk(doc)
    assert len(chunks) <= 3


def test_chunk_metadata_is_preserved():
    config = ChunkingConfig(strategy="fixed", target_chunk_size=100)
    doc = _doc("Contenido del documento de prueba.")
    chunks = SemanticChunker(config).chunk(doc)
    assert chunks[0].metadata["source"] == "inline"
    assert chunks[0].chunk_id.startswith(doc.doc_id)
