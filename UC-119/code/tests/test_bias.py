from analyzers.bias import BiasDetector


def test_no_bias_terms_returns_zero():
    detector = BiasDetector()
    result = detector.analyze("The weather is nice today.")
    assert result.overall_bias_score == 0.0
    assert result.biased_terms == []


def test_gender_imbalance_detected():
    detector = BiasDetector()
    text = "he said he would help him because he is his friend he he he"
    result = detector.analyze(text)
    assert result.gender_bias_score > 0.5
    assert "gender_imbalance" in result.biased_terms


def test_balanced_gender_terms_has_low_bias():
    detector = BiasDetector()
    text = "he and she both agreed to help"
    result = detector.analyze(text)
    assert result.gender_bias_score == 0.0
