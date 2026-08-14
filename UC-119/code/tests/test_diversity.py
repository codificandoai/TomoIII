from analyzers.diversity import DiversityAnalyzer


def test_empty_text_returns_zero_scores():
    analyzer = DiversityAnalyzer()
    result = analyzer.analyze("")
    assert result.overall_score == 0.0
    assert result.entropy == 0.0


def test_repetitive_text_has_low_diversity():
    analyzer = DiversityAnalyzer()
    result = analyzer.analyze("test test test test test test")
    assert result.unique_tokens_ratio < 0.5


def test_varied_text_has_higher_diversity_than_repetitive():
    analyzer = DiversityAnalyzer()
    repetitive = analyzer.analyze("gato gato gato gato gato gato")
    varied = analyzer.analyze("el perro corre rápido por el parque verde")
    assert varied.overall_score > repetitive.overall_score


def test_only_stopwords_returns_zero():
    analyzer = DiversityAnalyzer()
    result = analyzer.analyze("el la los las un una")
    assert result.overall_score == 0.0
