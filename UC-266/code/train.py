"""Entrenamiento del world model probabilístico con datos sintéticos."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from config import AppConfig, get_config
from model_persistence import ModelPersistence
from models import TrainingBatch, WorldModelObservation
from probabilistic_model import GPTransitionModel, NeuralTransitionModel
from synthetic_data import SyntheticDataGenerator
from travel_world import TravelWorldSimulator
from world_model import TravelWorldModel


def train_world_model(
    n_samples: int = 1000,
    config: Optional[AppConfig] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Genera datos sintéticos, entrena modelos y los guarda en disco.

    Args:
        n_samples: Número de trayectorias sintéticas a generar.
        config: Configuración de la aplicación.
        output_dir: Directorio donde guardar los modelos.

    Returns:
        Diccionario con estadísticas del entrenamiento y rutas guardadas.
    """
    cfg = config or get_config()
    generator = SyntheticDataGenerator(cfg)
    transitions, observations = generator.generate_batch(n_samples)

    simulator = TravelWorldSimulator(cfg.world)
    world_model = TravelWorldModel(cfg.model, simulator, app_config=cfg)

    # Evitar reentrenar en cada lote mientras se alimentan datos; entrenamos una sola vez al final.
    old_retrain_after = world_model.config.probabilistic.retrain_after
    world_model.config.probabilistic.retrain_after = 10**9

    # Alimentar observaciones reales al world model
    for obs in observations:
        world_model.update_from_observation(WorldModelObservation(**obs))

    world_model.config.probabilistic.retrain_after = old_retrain_after

    # Alimentar transiciones al modelo probabilístico
    for t in transitions:
        world_model.probabilistic_model.add_experience(
            t.get("prev_state", {}),
            t.get("action", {}),
            t.get("next_state", {}),
            t.get("reward", 0.0),
            t.get("info", {}).get("real_success", True),
        )

    world_model.retrain()

    persistence = ModelPersistence(output_dir)
    metadata = {
        "n_samples": n_samples,
        "n_transitions": len(transitions),
        "n_observations": len(observations),
        "model_type": cfg.model.probabilistic.model_type,
        "embedding_dim": cfg.model.probabilistic.embedding_dim,
    }
    neural_model = (
        world_model.probabilistic_model
        if isinstance(world_model.probabilistic_model, NeuralTransitionModel)
        else None
    )
    gp_model = (
        world_model.probabilistic_model
        if isinstance(world_model.probabilistic_model, GPTransitionModel)
        else None
    )
    saved = persistence.save(neural_model=neural_model, gp_model=gp_model, metadata=metadata)

    return {
        "status": "trained",
        "metadata": metadata,
        "saved_paths": saved,
        "world_model": world_model.to_dict(),
    }


def load_trained_model(
    world_model: TravelWorldModel, output_dir: Optional[str] = None
) -> bool:
    """Carga modelos previamente entrenados y los conecta a un world model existente."""
    persistence = ModelPersistence(output_dir)
    if not persistence.exists():
        return False
    attached_neural, attached_gp = persistence.attach_to_world_model(world_model)
    return attached_neural or attached_gp


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    out = sys.argv[2] if len(sys.argv) > 2 else None
    result = train_world_model(n_samples=n, output_dir=out)
    import json

    print(json.dumps(result, indent=2, ensure_ascii=False))
