import pytest

from tests.conftest import make_dataset


def _ingest_and_validate(pipeline, n_per_class=15):
    support = [{"query": f"pregunta de soporte tecnico numero {i}",
                "response": "respuesta_soporte", "rating": 5} for i in range(n_per_class)]
    billing = [{"query": f"pregunta de facturacion mensual numero {i}",
                "response": "respuesta_facturacion", "rating": 5} for i in range(n_per_class)]
    result = pipeline.ingest([{"type": "user_feedback", "data": support + billing}])
    pipeline.kb.validate_samples(result["stored_ids"])
    return result


def test_ingest_stores_filtered_items(pipeline):
    result = _ingest_and_validate(pipeline, n_per_class=15)
    assert result["stored"] > 0
    assert result["stored"] == len(result["stored_ids"])


def test_check_retraining_trigger_no_training_when_below_thresholds(pipeline):
    assert pipeline.check_retraining_trigger() == "no_training"


def test_check_retraining_trigger_fine_tuning(pipeline):
    pipeline.config.fine_tuning.min_samples = 1
    pipeline.config.retraining.min_new_samples_since_last_training = 10_000
    _ingest_and_validate(pipeline, n_per_class=5)
    assert pipeline.check_retraining_trigger() == "fine_tuning"


def test_train_full_retraining_and_validate(pipeline):
    _ingest_and_validate(pipeline, n_per_class=15)
    result = pipeline.train(training_type="full_retraining")

    assert result["status"] == "trained"
    assert result["training_type"] == "full_retraining"
    assert "validation" in result
    assert result["validation"]["status"] == "validated"


def test_train_skips_when_insufficient_data(pipeline):
    result = pipeline.train(training_type="full_retraining")
    assert result["status"] == "skipped"


def test_deploy_rejects_when_metrics_below_threshold(pipeline, monkeypatch):
    _ingest_and_validate(pipeline, n_per_class=15)
    train_result = pipeline.train(training_type="full_retraining", validate_after=False)

    monkeypatch.setattr(pipeline.validator, "should_deploy", lambda metrics, thresholds=None: False)
    result = pipeline.deploy(train_result["model_version"])
    assert result["status"] == "rejected"


def test_deploy_succeeds_and_updates_kb(pipeline):
    _ingest_and_validate(pipeline, n_per_class=15)
    train_result = pipeline.train(training_type="full_retraining")
    result = pipeline.deploy(train_result["model_version"])

    assert result["status"] == "deployed"
    assert pipeline.kb.get_deployed_model()["model_version"] == train_result["model_version"]


def test_deploy_with_force_skips_validation(pipeline, monkeypatch):
    _ingest_and_validate(pipeline, n_per_class=15)
    train_result = pipeline.train(training_type="full_retraining", validate_after=False)

    def _fail(*args, **kwargs):
        raise AssertionError("validate() no debería llamarse cuando force=True")

    monkeypatch.setattr(pipeline, "validate", _fail)
    result = pipeline.deploy(train_result["model_version"], force=True)
    assert result["status"] == "deployed"


def test_deploy_unknown_version_raises(pipeline):
    with pytest.raises(KeyError):
        pipeline.deploy("does-not-exist", force=True)


def test_predict_without_deployment_raises(pipeline):
    with pytest.raises(RuntimeError):
        pipeline.predict("hola")


def test_predict_after_deployment_tracks_usage(pipeline):
    _ingest_and_validate(pipeline, n_per_class=15)
    train_result = pipeline.train(training_type="full_retraining")
    pipeline.deploy(train_result["model_version"])

    result = pipeline.predict("pregunta de facturacion mensual reciente")
    assert "prediction" in result
    assert result["processing_time_ms"] >= 0


def test_rollback_without_backup_raises(pipeline):
    with pytest.raises(RuntimeError):
        pipeline.rollback()


def test_status_reports_pipeline_state(pipeline):
    status = pipeline.status()
    assert status["next_trigger"] == "no_training"
    assert status["deployed_model"] is None
