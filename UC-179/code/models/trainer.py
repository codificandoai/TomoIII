"""
Codificando.AI - UC-179
Entrenador de modelos: implementa el pipeline de texto->etiqueta
(TF-IDF + RandomForest) reutilizado tanto para el reentrenamiento
completo como para el fine-tuning ligero (reentrenamiento incremental
sobre datos combinados nuevos + históricos validados).

Corrección respecto al stub original: `_get_active_model` accedía a
`sqlite3` directamente sin importarlo y sin pasar por
`core.knowledge_base.KnowledgeBase`, rompiendo la encapsulación de acceso
a datos. Ahora delega en `KnowledgeBase.get_active_model_path()`.
"""

from pathlib import Path
from typing import Dict, List, Union

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import Pipeline


class ModelTrainer:
    def __init__(self, knowledge_base, model_dir: Union[str, Path] = "models/versions"):
        self.kb = knowledge_base
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train_full(self, data: List[Dict], version: str) -> str:
        """Entrenamiento completo desde cero con todo el dataset validado."""
        X = [item["input"] for item in data]
        y = [item["output"] for item in data]

        pipeline = self._build_pipeline()
        pipeline.fit(X, y)

        model_path = self.model_dir / f"{version}.joblib"
        joblib.dump(pipeline, model_path)

        metrics = self._calculate_training_metrics(pipeline, X, y)
        self.kb.register_model(version, str(model_path), metrics, len(data), training_type="full")

        return str(model_path)

    def fine_tune(self, new_data: List[Dict], version: str, history_limit: int = 1000) -> str:
        """Fine-tuning ligero: combina el modelo/datos existentes con las
        muestras nuevas y reentrena. Si no hay modelo activo, degrada a
        entrenamiento completo."""
        active_model_path = self.kb.get_active_model_path()
        if not active_model_path or not Path(active_model_path).exists():
            return self.train_full(new_data, version)

        existing_data = self.kb.get_training_data(validated_only=True, limit=history_limit)
        combined = existing_data + new_data
        X = [item["input"] for item in combined]
        y = [item["output"] for item in combined]

        # Re-entrena un pipeline nuevo con datos combinados; conserva el
        # mismo tipo de pipeline que el entrenamiento completo para
        # garantizar compatibilidad de features entre versiones.
        pipeline = self._build_pipeline()
        pipeline.fit(X, y)

        model_path = self.model_dir / f"{version}.joblib"
        joblib.dump(pipeline, model_path)

        metrics = self._calculate_training_metrics(pipeline, X, y)
        self.kb.register_model(version, str(model_path), metrics, len(new_data), training_type="fine_tune")

        return str(model_path)

    def _build_pipeline(self) -> Pipeline:
        return Pipeline([
            ("vectorizer", TfidfVectorizer(max_features=5000)),
            ("classifier", RandomForestClassifier(n_estimators=100, random_state=42)),
        ])

    def _calculate_training_metrics(self, model: Pipeline, X: List[str], y: List[str]) -> Dict:
        classes = set(y)
        n_classes = len(classes)
        min_class_count = min((y.count(c) for c in classes), default=0)
        cv_folds = min(5, min_class_count)

        if len(X) < 2 or n_classes < 2 or cv_folds < 2:
            # Muestra insuficiente para validación cruzada: se reporta el
            # accuracy de entrenamiento como aproximación.
            accuracy = model.score(X, y)
            return {"accuracy_mean": float(accuracy), "accuracy_std": 0.0, "training_samples": len(X)}

        scores = cross_val_score(model, X, y, cv=cv_folds, scoring="accuracy")
        return {
            "accuracy_mean": float(scores.mean()),
            "accuracy_std": float(scores.std()),
            "training_samples": len(X),
        }

    def get_current_model_metrics(self) -> Dict:
        return self.kb.get_active_model_metrics()

    def load_model(self, model_path: Union[str, Path]) -> Pipeline:
        return joblib.load(model_path)
