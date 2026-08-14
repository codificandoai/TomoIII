from analyzers.quality import QualityAnalyzer


def test_relevant_grounded_response():
    analyzer = QualityAnalyzer()
    result = analyzer.analyze(
        prompt="¿Cuál es la capital de Francia?",
        response="La capital de Francia es París.",
        context="Francia es un país europeo. Su capital es París.",
    )
    assert result.relevance_score > 0.0
    assert result.groundedness_score > 0.0
    assert result.task_completed is True


def test_refusal_response_marks_task_incomplete():
    analyzer = QualityAnalyzer()
    result = analyzer.analyze(
        prompt="¿Cuál es la capital de Francia?",
        response="I cannot help with that request.",
    )
    assert result.task_completed is False


def test_retrieval_precision_computed_when_docs_provided():
    analyzer = QualityAnalyzer()
    result = analyzer.analyze(
        prompt="¿Qué es Python?",
        response="Python es un lenguaje de programación interpretado.",
        retrieved_docs=[
            "Python es un lenguaje de programación interpretado y de alto nivel.",
            "El clima en Marte es muy frío.",
        ],
    )
    assert result.retrieval_precision is not None
    assert 0.0 <= result.retrieval_precision <= 1.0


def test_user_rating_normalized():
    analyzer = QualityAnalyzer()
    result = analyzer.analyze(prompt="p", response="r", user_rating=5)
    assert result.user_satisfaction == 1.0
