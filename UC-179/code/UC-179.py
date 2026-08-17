"""
Codificando.AI
UC-179: Sistema autónomo de reentrenamiento continuo — ¿cómo diseñar un
pipeline reutilizable que recolecte y filtre datos de múltiples fuentes
(feedback de usuarios, anotaciones humanas, APIs externas), decida
autónomamente cuándo disparar un reentrenamiento completo o un
fine-tuning ligero según umbrales configurables, valide el modelo
candidato (métricas + casos extremos) contra el modelo en producción, y
lo despliegue de forma segura (con respaldo y rollback), retroalimentando
el propio pipeline con la telemetría de uso en producción?

Products:
- bloower.com: AI-Native Platform.
- c4ml.io: Infrastructure as Code.
- analitycsdata.com: etl(batch-online-offline).
- cloudatasecure.com: vault.
- qbex.ai: AI-Native Cost & Migrations Operations.
- utron.ai: AI-Solutions ready for you.
- trackpro.ai: AI-Native Projects Ready to deploy.

La lógica del pipeline vive en los módulos reutilizables
(`config.py`, `core/`, `models/`, `pipeline_service.py`). Este archivo es
el punto de entrada de línea de comandos (CLI) y sirve como demostración
ejecutable del caso de uso. Para exponerlo vía API HTTP, ver `app.py`.
Para orquestación programada, ver `workflows/` (Airflow).

Uso:
    python UC-179.py                 # demo end-to-end con datos sintéticos
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from logging_utils import configure_logging
from pipeline_service import ContinuousLearningPipeline


def _synthetic_sources() -> list:
    """Genera datos sintéticos de dos categorías (soporte técnico y
    facturación) para poblar la base de conocimiento en la demo."""
    support = [
        {"query": f"no puedo iniciar sesion en la plataforma caso {i}",
         "response": "restablece tu contraseña desde la pantalla de inicio de sesion", "rating": 5}
        for i in range(20)
    ] + [
        {"query": f"la aplicacion se cierra al abrir el modulo de reportes {i}",
         "response": "actualiza la aplicacion a la ultima version disponible", "rating": 4}
        for i in range(20)
    ]
    billing = [
        {"query": f"quiero generar una factura electronica para el pedido {i}",
         "response": "ingresa al modulo de facturacion y selecciona generar factura electronica", "rating": 5}
        for i in range(20)
    ] + [
        {"query": f"como aplico un descuento a la factura del cliente {i}",
         "response": "usa la opcion aplicar descuento dentro del modulo de facturacion", "rating": 5}
        for i in range(20)
    ]
    return [{"type": "user_feedback", "data": support + billing}]


def run_demo() -> int:
    configure_logging()

    with tempfile.TemporaryDirectory(prefix="uc179_demo_") as tmp:
        tmp_path = Path(tmp)
        pipeline = ContinuousLearningPipeline(
            db_path=tmp_path / "knowledge_base.db",
            model_versions_dir=tmp_path / "models" / "versions",
            production_dir=tmp_path / "models" / "production",
        )

        print(f"\n{'=' * 80}\n1) Ingesta de datos desde múltiples fuentes\n{'=' * 80}")
        ingest_result = pipeline.ingest(_synthetic_sources())
        print(json.dumps(ingest_result, indent=2, ensure_ascii=False))

        print(f"\n{'=' * 80}\n2) Aprobación humana de las muestras recolectadas\n{'=' * 80}")
        approve_result = pipeline.approve_samples(ingest_result["stored_ids"])
        print(json.dumps(approve_result, indent=2, ensure_ascii=False))

        print(f"\n{'=' * 80}\n3) Verificación del disparador de reentrenamiento\n{'=' * 80}")
        trigger = pipeline.check_retraining_trigger()
        print(f"Disparador evaluado: {trigger}")

        print(f"\n{'=' * 80}\n4) Entrenamiento completo (forzado para la demo) + validación\n{'=' * 80}")
        train_result = pipeline.train(training_type="full_retraining")
        print(json.dumps(train_result, indent=2, ensure_ascii=False, default=str))

        if train_result["status"] != "trained":
            print("\nNo se generó un modelo entrenado; fin de la demo.")
            return 0

        model_version = train_result["model_version"]

        print(f"\n{'=' * 80}\n5) Despliegue a producción\n{'=' * 80}")
        deploy_result = pipeline.deploy(model_version)
        print(json.dumps(deploy_result, indent=2, ensure_ascii=False, default=str))

        print(f"\n{'=' * 80}\n6) Inferencia en producción (retroalimenta la knowledge base)\n{'=' * 80}")
        prediction = pipeline.predict("necesito generar la factura del pedido de hoy")
        print(json.dumps(prediction, indent=2, ensure_ascii=False, default=str))

        print(f"\n{'=' * 80}\n7) Estado general del pipeline\n{'=' * 80}")
        print(json.dumps(pipeline.status(), indent=2, ensure_ascii=False, default=str))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="UC-179: Sistema autónomo de reentrenamiento continuo "
                     "(ingesta -> entrenamiento -> validación -> despliegue -> inferencia)."
    )
    parser.parse_args()
    return run_demo()


if __name__ == "__main__":
    sys.exit(main())
