class DummyModel:
    """Modelo simulado con interfaz scikit-learn (`predict`)."""

    def __init__(self, mapping, default="unknown"):
        self.mapping = mapping
        self.default = default

    def predict(self, X):
        return [self.mapping.get(x, self.default) for x in X]


def test_validate_model_perfect_predictions(validator):
    test_data = [{"input": "a", "output": "y1"}, {"input": "b", "output": "y2"}]
    model = DummyModel({"a": "y1", "b": "y2"})

    metrics = validator.validate_model(model, test_data)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert all(case["status"] == "pass" for case in metrics["edge_cases"].values())


def test_validate_model_with_wrong_predictions(validator):
    test_data = [{"input": "a", "output": "y1"}, {"input": "b", "output": "y2"}]
    model = DummyModel({"a": "y2", "b": "y2"})

    metrics = validator.validate_model(model, test_data)
    assert metrics["accuracy"] == 0.5


def test_validate_model_with_baseline_computes_improvement(validator):
    test_data = [{"input": "a", "output": "y1"}, {"input": "b", "output": "y2"}]
    model = DummyModel({"a": "y1", "b": "y2"})
    baseline = {"accuracy": 0.5, "f1_score": 0.5, "precision": 0.5, "recall": 0.5}

    metrics = validator.validate_model(model, test_data, baseline_metrics=baseline)
    assert metrics["improvement"]["accuracy"]["percentage"] == 100.0


def test_edge_case_failure_marks_status_fail(validator):
    class FailingModel:
        def predict(self, X):
            raise RuntimeError("boom")

    metrics = validator.validate_model(FailingModel(), [])
    assert all(case["status"] == "fail" for case in metrics["edge_cases"].values())


def test_should_deploy_true_when_metrics_pass(validator):
    metrics = {"accuracy": 0.95, "f1_score": 0.9, "edge_cases": {"a": {"status": "pass"}}}
    assert validator.should_deploy(metrics) is True


def test_should_deploy_false_when_accuracy_below_threshold(validator):
    metrics = {"accuracy": 0.5, "f1_score": 0.9, "edge_cases": {}}
    assert validator.should_deploy(metrics) is False


def test_should_deploy_false_when_edge_case_fails(validator):
    metrics = {"accuracy": 0.95, "f1_score": 0.9, "edge_cases": {"a": {"status": "fail"}}}
    assert validator.should_deploy(metrics) is False


def test_should_deploy_false_when_regression_exceeds_threshold(validator):
    metrics = {
        "accuracy": 0.95, "f1_score": 0.9, "edge_cases": {},
        "improvement": {"accuracy": {"percentage": -10.0}},
    }
    assert validator.should_deploy(metrics) is False
