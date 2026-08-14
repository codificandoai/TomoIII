from analyzers.hallucination import HallucinationDetector


def test_confident_short_response_is_low_risk():
    detector = HallucinationDetector(use_nli=False)
    result = detector.analyze("What is 2+2?", "4")
    assert result.risk_level == "LOW"


def test_uncertain_repetitive_response_is_flagged():
    detector = HallucinationDetector(use_nli=False)
    response = (
        "maybe perhaps not sure possibly not sure not sure not sure not sure "
        "not sure not sure not sure not sure not sure not sure"
    )
    result = detector.analyze("Summarize the report", response)
    assert result.hallucination_probability > 0.0
    assert result.risk_level in ("MEDIUM", "HIGH")


def test_empty_response_does_not_crash():
    detector = HallucinationDetector(use_nli=False)
    result = detector.analyze("prompt", "")
    assert result.risk_level == "LOW"
