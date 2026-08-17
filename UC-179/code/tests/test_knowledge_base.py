def test_add_training_data_returns_row_id(kb):
    row_id = kb.add_training_data("entrada de prueba", "salida de prueba", source="test")
    assert row_id is not None


def test_add_training_data_deduplicates_by_hash(kb):
    first = kb.add_training_data("misma entrada", "misma salida", source="test")
    second = kb.add_training_data("misma entrada", "misma salida", source="test")
    assert first is not None
    assert second is None


def test_get_new_samples_count_only_counts_validated(kb):
    id1 = kb.add_training_data("entrada 1", "salida 1")
    kb.add_training_data("entrada 2", "salida 2")
    assert kb.get_new_samples_count() == 0

    kb.validate_samples([id1])
    assert kb.get_new_samples_count() == 1


def test_validate_samples_marks_as_validated(kb):
    row_id = kb.add_training_data("entrada", "salida")
    assert kb.get_training_data(validated_only=True) == []

    kb.validate_samples([row_id])
    validated = kb.get_training_data(validated_only=True)
    assert len(validated) == 1
    assert validated[0]["input"] == "entrada"


def test_validate_samples_empty_list_is_noop(kb):
    kb.add_training_data("entrada", "salida")
    kb.validate_samples([])  # no debe lanzar excepción
    assert kb.get_training_data(validated_only=True) == []


def test_register_model_sets_active(kb):
    kb.register_model("v1", "/tmp/v1.joblib", {"accuracy_mean": 0.9}, 100)
    assert kb.get_active_model_path() == "/tmp/v1.joblib"
    assert kb.get_active_model_metrics() == {"accuracy_mean": 0.9}


def test_register_model_deactivates_previous(kb):
    kb.register_model("v1", "/tmp/v1.joblib", {"accuracy_mean": 0.9}, 100)
    kb.register_model("v2", "/tmp/v2.joblib", {"accuracy_mean": 0.95}, 150)

    history = kb.get_model_history()
    active_versions = [h["model_version"] for h in history if h["is_active"]]
    assert active_versions == ["v2"]


def test_mark_model_deployed(kb):
    kb.register_model("v1", "/tmp/v1.joblib", {"accuracy_mean": 0.9}, 100)
    kb.mark_model_deployed("v1")

    deployed = kb.get_deployed_model()
    assert deployed["model_version"] == "v1"


def test_get_deployed_model_none_when_nothing_deployed(kb):
    assert kb.get_deployed_model() is None


def test_get_model_history_order_and_limit(kb):
    for i in range(3):
        kb.register_model(f"v{i}", f"/tmp/v{i}.joblib", {"accuracy_mean": 0.8}, 10)

    history = kb.get_model_history(limit=2)
    assert len(history) == 2
    assert history[0]["model_version"] == "v2"


def test_track_usage_and_add_annotation(kb):
    kb.track_usage("input", "output", 0.9, 15)
    row_id = kb.add_training_data("entrada", "salida")
    annotation_id = kb.add_annotation(row_id, "correction", "texto corregido")
    assert annotation_id is not None
