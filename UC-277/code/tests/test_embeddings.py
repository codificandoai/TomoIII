"""Tests del SimpleEmbeddingModel para UC-277."""
from embeddings import SimpleEmbeddingModel


def test_encode_returns_correct_dim():
    model = SimpleEmbeddingModel(dim=64)
    emb = model.encode("hello world")
    assert len(emb) == 64


def test_encode_is_normalized():
    model = SimpleEmbeddingModel(dim=64)
    emb = model.encode("test sentence")
    import math
    norm = math.sqrt(sum(x * x for x in emb))
    assert abs(norm - 1.0) < 0.01


def test_encode_deterministic():
    model = SimpleEmbeddingModel(dim=64)
    e1 = model.encode("same text")
    e2 = model.encode("same text")
    assert e1 == e2


def test_encode_different_texts():
    model = SimpleEmbeddingModel(dim=64)
    e1 = model.encode("machine learning")
    e2 = model.encode("cooking recipes")
    assert e1 != e2


def test_similarity_same_text():
    model = SimpleEmbeddingModel(dim=64)
    e1 = model.encode("hello world")
    sim = model.similarity(e1, e1)
    assert abs(sim - 1.0) < 0.01


def test_similarity_different_texts():
    model = SimpleEmbeddingModel(dim=64)
    e1 = model.encode("machine learning algorithms")
    e2 = model.encode("cooking italian pasta")
    sim = model.similarity(e1, e2)
    assert -1.0 <= sim <= 1.0


def test_similarity_similar_texts():
    model = SimpleEmbeddingModel(dim=64)
    e1 = model.encode("machine learning algorithms")
    e2 = model.encode("machine learning models")
    sim = model.similarity(e1, e2)
    assert sim > 0.5


def test_encode_empty_string():
    model = SimpleEmbeddingModel(dim=64)
    emb = model.encode("")
    assert len(emb) == 64
    assert all(x == 0.0 for x in emb)


def test_similarity_empty():
    model = SimpleEmbeddingModel(dim=64)
    e1 = model.encode("")
    e2 = model.encode("hello")
    sim = model.similarity(e1, e2)
    assert sim == 0.0
