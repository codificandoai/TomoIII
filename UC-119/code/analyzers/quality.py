"""Métricas de calidad: groundedness, relevancia, fidelidad, coherencia,
finalización de tareas, precisión de recuperación y satisfacción de usuario.

Estas métricas complementan la detección de alucinaciones y están
diseñadas para funcionar sin dependencias de modelos pesados, usando
similitud léxica (solapamiento de tokens) como aproximación explicable.
Si se dispone de embeddings/LLM-as-judge, `overlap_score` puede
sustituirse inyectando una función de similitud personalizada.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class QualityMetrics:
    """Métricas agregadas de calidad de una respuesta."""
    groundedness_score: float
    relevance_score: float
    fidelity_score: float
    coherence_score: float
    task_completed: bool
    retrieval_precision: Optional[float]
    user_satisfaction: Optional[float]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑüÜ0-9]+", (text or "").lower())


def _overlap_score(a: str, b: str) -> float:
    """Similitud léxica Jaccard entre dos textos (0-1)."""
    tokens_a = set(_tokenize(a))
    tokens_b = set(_tokenize(b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


class QualityAnalyzer:
    """Calcula métricas de calidad de respuestas de un LLM."""

    def analyze(
        self,
        prompt: str,
        response: str,
        context: str = "",
        retrieved_docs: Optional[List[str]] = None,
        expected_completion: Optional[bool] = None,
        user_rating: Optional[float] = None,
        similarity_fn=None,
    ) -> QualityMetrics:
        """
        Args:
            prompt: pregunta/instrucción del usuario.
            response: respuesta generada por el modelo.
            context: contexto/documentos concatenados usados para responder (RAG).
            retrieved_docs: lista de fragmentos recuperados (para precisión de recuperación).
            expected_completion: si se conoce externamente si la tarea se resolvió.
            user_rating: calificación de usuario (0-5) si está disponible.
            similarity_fn: función opcional `(a, b) -> float` para sustituir
                la heurística de solapamiento léxico por embeddings/LLM-judge.
        """
        sim = similarity_fn or _overlap_score

        relevance = sim(prompt, response)

        if context:
            groundedness = sim(context, response)
            fidelity = groundedness
        else:
            groundedness = 0.0
            fidelity = 0.0

        coherence = self._coherence(response)

        task_completed = (
            expected_completion
            if expected_completion is not None
            else self._infer_task_completion(response)
        )

        retrieval_precision = None
        if retrieved_docs:
            relevant_docs = [d for d in retrieved_docs if sim(d, response) > 0.1 or sim(d, prompt) > 0.1]
            retrieval_precision = round(len(relevant_docs) / len(retrieved_docs), 4)

        user_satisfaction = None
        if user_rating is not None:
            user_satisfaction = round(min(max(user_rating, 0), 5) / 5, 4)

        return QualityMetrics(
            groundedness_score=round(groundedness, 4),
            relevance_score=round(relevance, 4),
            fidelity_score=round(fidelity, 4),
            coherence_score=round(coherence, 4),
            task_completed=bool(task_completed),
            retrieval_precision=retrieval_precision,
            user_satisfaction=user_satisfaction,
        )

    @staticmethod
    def _coherence(response: str) -> float:
        """Heurística de coherencia: penaliza fragmentos muy cortos,
        contradicciones explícitas y repeticiones excesivas de frases."""
        if not response or len(response.strip()) == 0:
            return 0.0

        sentences = [s.strip() for s in re.split(r'[.!?]+', response) if s.strip()]
        if not sentences:
            return 0.0

        contradiction_markers = [
            'but actually', 'however this is wrong', 'pero en realidad no',
            'contradicting', 'contradiction',
        ]
        contradiction_penalty = 0.3 if any(
            m in response.lower() for m in contradiction_markers
        ) else 0.0

        unique_sentences = set(sentences)
        repetition_penalty = 0.3 * (1 - len(unique_sentences) / len(sentences))

        length_bonus = min(len(sentences) / 5, 1.0) * 0.2

        score = 1.0 - contradiction_penalty - repetition_penalty
        score = max(0.0, min(1.0, score + length_bonus * 0.0))
        return score

    @staticmethod
    def _infer_task_completion(response: str) -> bool:
        """Heurística: una respuesta vacía, de error o de rechazo explícito
        se considera una tarea NO completada."""
        if not response or len(response.strip()) < 2:
            return False
        refusal_markers = [
            "i can't help", "i cannot help", "no puedo ayudar",
            "as an ai", "i don't know", "no lo sé", "error",
        ]
        lower = response.lower()
        return not any(marker in lower for marker in refusal_markers)
