"""
Codificando.AI - UC-179
Recolección, normalización y filtrado de datos de entrenamiento
provenientes de múltiples fuentes (feedback de usuarios, anotaciones
humanas, APIs externas). Aplica un pipeline de calidad (longitud mínima,
detección de spam, validez lingüística básica y deduplicación semántica)
antes de que los datos lleguen a `core.knowledge_base.KnowledgeBase`.

Nota de diseño: la validación lingüística original dependía de `spacy`
(modelo `es_core_news_sm`), lo que exige descargar un modelo de idioma
adicional. Se reemplazó por un heurístico ligero basado en tokenización
por regex (conteo de tokens alfabéticos, ratio de mayúsculas, repetición
de caracteres) para mantener el pipeline reutilizable sin dependencias
pesadas ni descargas de modelos; sigue siendo sustituible por spacy/NLP
avanzado si el despliegue lo requiere.
"""

import re
from typing import Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import CONFIG

_TOKEN_RE = re.compile(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]+")

_SPAM_PATTERNS = [
    re.compile(r"buy now", re.IGNORECASE),
    re.compile(r"click here", re.IGNORECASE),
    re.compile(r"free money", re.IGNORECASE),
    re.compile(r"\b(viagra|casino|lottery)\b", re.IGNORECASE),
    re.compile(r"[!]{3,}"),
]


class DataCollector:
    def __init__(self, knowledge_base, data_quality_config=None):
        self.kb = knowledge_base
        self.quality = data_quality_config or CONFIG.data_quality

    # ------------------------------------------------------------------
    # Recolección desde múltiples fuentes
    # ------------------------------------------------------------------
    def collect_from_sources(self, sources: List[Dict]) -> List[Dict]:
        """Normaliza items heterogéneos de distintas fuentes al formato
        común {'input', 'output', 'source', 'quality_score'}."""
        collected: List[Dict] = []

        for source in sources:
            source_type = source.get("type")
            data = source.get("data", [])
            if source_type == "user_feedback":
                collected.extend(self._process_user_feedback(data))
            elif source_type == "annotations":
                collected.extend(self._process_annotations(data))
            elif source_type == "external_api":
                collected.extend(self._process_external_data(data))
            else:
                raise ValueError(f"Tipo de fuente no soportado: {source_type!r}")

        return collected

    def _process_user_feedback(self, feedback_data: List[Dict]) -> List[Dict]:
        """Solo se conserva feedback con calificación positiva (>= 4/5)."""
        processed = []
        for item in feedback_data:
            if item.get("rating", 0) >= 4:
                processed.append({
                    "input": item["query"],
                    "output": item["response"],
                    "source": "user_feedback",
                    "quality_score": item["rating"] / 5.0,
                })
        return processed

    def _process_annotations(self, annotation_data: List[Dict]) -> List[Dict]:
        """Anotaciones humanas: se asume mayor confiabilidad por defecto
        (revisadas por un anotador), salvo que se indique lo contrario."""
        processed = []
        for item in annotation_data:
            if "input" not in item or "output" not in item:
                continue
            processed.append({
                "input": item["input"],
                "output": item["output"],
                "source": "annotation",
                "quality_score": float(item.get("confidence", 0.95)),
            })
        return processed

    def _process_external_data(self, external_data: List[Dict]) -> List[Dict]:
        """Datos de APIs externas: se pondera la calidad a la baja por
        defecto, ya que no han sido validados por un humano ni por
        feedback explícito de usuario."""
        processed = []
        for item in external_data:
            if "input" not in item or "output" not in item:
                continue
            processed.append({
                "input": item["input"],
                "output": item["output"],
                "source": item.get("provider", "external_api"),
                "quality_score": float(item.get("quality_score", 0.6)),
            })
        return processed

    # ------------------------------------------------------------------
    # Filtrado de calidad
    # ------------------------------------------------------------------
    def filter_data(self, data: List[Dict]) -> List[Dict]:
        filtered: List[Dict] = []

        for item in data:
            if len(item["input"]) < self.quality.min_input_length:
                continue
            if len(item["output"]) < self.quality.min_output_length:
                continue
            if self._is_spam(item["input"]) or self._is_spam(item["output"]):
                continue
            if not self._validate_language_quality(item["input"]):
                continue
            if self._is_semantic_duplicate(item, filtered):
                continue
            filtered.append(item)

        return filtered

    def _is_spam(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in _SPAM_PATTERNS)

    def _validate_language_quality(self, text: str) -> bool:
        """Heurístico ligero: exige un número mínimo de tokens
        alfabéticos y descarta texto dominado por mayúsculas (spam-like)."""
        tokens = _TOKEN_RE.findall(text)
        if len(tokens) < self.quality.min_token_count:
            return False

        alpha_chars = [c for c in text if c.isalpha()]
        if alpha_chars:
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_ratio > 0.7 and len(alpha_chars) > 10:
                return False

        return True

    def _is_semantic_duplicate(self, new_item: Dict, existing: List[Dict]) -> bool:
        if not existing:
            return False

        recent = existing[-50:]
        texts = [new_item["input"]] + [item["input"] for item in recent]

        try:
            vectorizer = TfidfVectorizer(max_features=100)
            tfidf_matrix = vectorizer.fit_transform(texts)
        except ValueError:
            # Vocabulario vacío (p.ej. solo stopwords/tokens no alfanuméricos)
            return False

        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])
        return bool(np.max(similarities) > self.quality.semantic_duplicate_threshold)

    def cluster_and_sample(self, data: List[Dict], n_clusters: int = 10,
                            sample_ratio: float = 0.2) -> List[Dict]:
        """Agrupa por similitud (TF-IDF + KMeans) y muestrea de cada
        cluster para preservar diversidad temática en el dataset final."""
        from sklearn.cluster import KMeans

        if len(data) <= n_clusters:
            return data

        vectorizer = TfidfVectorizer(max_features=500)
        texts = [item["input"] for item in data]
        tfidf_matrix = vectorizer.fit_transform(texts)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(tfidf_matrix)

        sampled = []
        for cluster_id in range(n_clusters):
            cluster_items = [data[i] for i, c in enumerate(clusters) if c == cluster_id]
            if cluster_items:
                sample_size = max(1, int(len(cluster_items) * sample_ratio))
                sampled.extend(cluster_items[:sample_size])

        return sampled
