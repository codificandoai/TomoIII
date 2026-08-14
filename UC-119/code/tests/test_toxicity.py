from analyzers.toxicity import ToxicityDetector


def test_clean_text_is_low_risk():
    detector = ToxicityDetector(use_ml_model=False)
    result = detector.analyze("Hoy es un día soleado y agradable.")
    assert result.overall_risk == "LOW"
    assert result.toxicity_score == 0.0


def test_toxic_terms_are_flagged():
    detector = ToxicityDetector(use_ml_model=False)
    result = detector.analyze(
        "I will kill, murder, attack and destroy everything, you idiot stupid loser."
    )
    assert result.toxicity_score > 0.0
    assert result.overall_risk in ("MEDIUM", "HIGH", "CRITICAL")
    assert len(result.flagged_terms) > 0


def test_empty_text_returns_low_risk():
    detector = ToxicityDetector(use_ml_model=False)
    result = detector.analyze("")
    assert result.overall_risk == "LOW"
    assert result.flagged_terms == []
