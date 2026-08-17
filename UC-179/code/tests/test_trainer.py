from tests.conftest import make_dataset


def test_train_full_creates_model_file_and_registers(trainer, kb):
    data = make_dataset(15)
    model_path = trainer.train_full(data, "v1")

    from pathlib import Path
    assert Path(model_path).exists()
    assert kb.get_active_model_path() == model_path


def test_train_full_model_can_predict(trainer):
    data = make_dataset(15)
    model_path = trainer.train_full(data, "v1")
    model = trainer.load_model(model_path)

    prediction = model.predict(["pregunta de facturacion numero 99"])
    assert prediction[0] in ("respuesta_soporte", "respuesta_facturacion")


def test_fine_tune_without_active_model_falls_back_to_full(trainer, kb):
    data = make_dataset(5)
    model_path = trainer.fine_tune(data, "ft1")

    history = kb.get_model_history()
    assert history[0]["training_type"] == "full"


def test_fine_tune_with_active_model_combines_data(trainer, kb):
    initial = make_dataset(15)
    trainer.train_full(initial, "v1")

    new_data = make_dataset(3)
    model_path = trainer.fine_tune(new_data, "ft1")

    history = kb.get_model_history()
    assert history[0]["training_type"] == "fine_tune"
    assert history[0]["model_version"] == "ft1"


def test_get_current_model_metrics(trainer, kb):
    data = make_dataset(15)
    trainer.train_full(data, "v1")
    metrics = trainer.get_current_model_metrics()
    assert "accuracy_mean" in metrics
