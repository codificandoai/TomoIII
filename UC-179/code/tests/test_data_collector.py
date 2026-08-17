import pytest


def test_collect_from_user_feedback_filters_low_rating(collector):
    sources = [{"type": "user_feedback", "data": [
        {"query": "buena pregunta", "response": "buena respuesta", "rating": 5},
        {"query": "mala pregunta", "response": "mala respuesta", "rating": 2},
    ]}]
    collected = collector.collect_from_sources(sources)
    assert len(collected) == 1
    assert collected[0]["quality_score"] == 1.0


def test_collect_from_annotations(collector):
    sources = [{"type": "annotations", "data": [
        {"input": "entrada anotada", "output": "salida anotada", "confidence": 0.9},
        {"input": "entrada incompleta"},  # sin 'output', se descarta
    ]}]
    collected = collector.collect_from_sources(sources)
    assert len(collected) == 1
    assert collected[0]["source"] == "annotation"
    assert collected[0]["quality_score"] == 0.9


def test_collect_from_external_api(collector):
    sources = [{"type": "external_api", "data": [
        {"input": "entrada externa", "output": "salida externa", "provider": "acme", "quality_score": 0.5},
    ]}]
    collected = collector.collect_from_sources(sources)
    assert collected[0]["source"] == "acme"
    assert collected[0]["quality_score"] == 0.5


def test_collect_unknown_source_type_raises(collector):
    with pytest.raises(ValueError):
        collector.collect_from_sources([{"type": "unknown", "data": []}])


def test_filter_data_removes_short_texts(collector):
    data = [{"input": "hi", "output": "ok", "source": "test", "quality_score": 1.0}]
    assert collector.filter_data(data) == []


def test_filter_data_removes_spam(collector):
    data = [{"input": "compra ahora click here para ganar", "output": "respuesta valida completa",
             "source": "test", "quality_score": 1.0}]
    assert collector.filter_data(data) == []


def test_filter_data_removes_low_quality_language(collector):
    data = [{"input": "12345 67890 54321 11111", "output": "respuesta valida completa",
             "source": "test", "quality_score": 1.0}]
    assert collector.filter_data(data) == []


def test_filter_data_keeps_valid_diverse_items(collector):
    data = [
        {"input": "como configuro mi cuenta de usuario", "output": "ve a ajustes de cuenta",
         "source": "test", "quality_score": 1.0},
        {"input": "necesito ayuda con la facturacion mensual", "output": "revisa el modulo de facturacion",
         "source": "test", "quality_score": 1.0},
    ]
    filtered = collector.filter_data(data)
    assert len(filtered) == 2


def test_filter_data_deduplicates_semantically_similar(collector):
    data = [
        {"input": "como configuro mi cuenta de usuario en el sistema", "output": "respuesta uno",
         "source": "test", "quality_score": 1.0},
        {"input": "como configuro mi cuenta de usuario en el sistema hoy", "output": "respuesta dos",
         "source": "test", "quality_score": 1.0},
    ]
    filtered = collector.filter_data(data)
    assert len(filtered) == 1


def test_cluster_and_sample_returns_input_when_small(collector):
    data = [{"input": f"texto {i}", "output": "y"} for i in range(3)]
    result = collector.cluster_and_sample(data, n_clusters=10)
    assert result == data
