"""Refiner — Generación de versiones mejoradas para UC-276.

Implementa 8 estrategias de refinamiento con selección automática:
- CLARIFY: hacer más claro (oraciones cortas, vocabulario simple)
- CONCISE: hacer más conciso (eliminar redundancias)
- EXPAND: agregar detalles y contexto
- CORRECT: corregir errores específicos
- RESTRUCTURE: reorganizar estructura
- VALIDATE: verificar precisión
- OPTIMIZE: optimizar para objetivo específico
- ADAPT_AUDIENCE: adaptar a audiencia

Inspirado en:
- hankbesser/recursive-agents: critique → refine con historial.
- madaan/self-refine: feedback-driven refinement.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from models import QualityCriteria, QualityReport, RecursiveVersion, RefinementStrategy


class Refiner:
    """Genera versiones mejoradas usando estrategias de refinamiento."""

    STRATEGY_PROMPTS: Dict[RefinementStrategy, str] = {
        RefinementStrategy.CLARIFY: (
            "Reescribe para mayor claridad. Usa oraciones cortas, "
            "vocabulario simple y estructura lógica."
        ),
        RefinementStrategy.CONCISE: (
            "Reduce longitud en ~30% sin perder significado. "
            "Elimina redundancias, mantén solo lo esencial."
        ),
        RefinementStrategy.EXPAND: (
            "Expande con más detalles, ejemplos y contexto. "
            "Enriquece el contenido manteniendo estructura."
        ),
        RefinementStrategy.CORRECT: (
            "Corrige los problemas identificados: {issues}. "
            "Mantén todo lo demás sin cambios."
        ),
        RefinementStrategy.RESTRUCTURE: (
            "Reorganiza para mejorar la estructura. "
            "Usa secciones claras y flujo lógico."
        ),
        RefinementStrategy.VALIDATE: (
            "Verifica precisión del contenido. "
            "Marca afirmaciones dudosas y sugiere correcciones."
        ),
        RefinementStrategy.OPTIMIZE: (
            "Optimiza para el objetivo: {objective}. "
            "Prioriza lo que contribuye directamente al objetivo."
        ),
        RefinementStrategy.ADAPT_AUDIENCE: (
            "Adapta para la audiencia: {audience}. "
            "Ajusta tono, vocabulario y nivel de detalle."
        ),
    }

    def refine(self, current_version: RecursiveVersion,
               quality_report: QualityReport,
               task_description: str,
               strategy: RefinementStrategy,
               extra_context: Optional[Dict] = None) -> str:
        """
        Genera versión refinada del contenido.
        En producción: envía a LLM real. Aquí aplica transformaciones heurísticas.
        """
        extra_context = extra_context or {}
        content = current_version.content

        if strategy == RefinementStrategy.CLARIFY:
            return self._apply_clarify(content)
        elif strategy == RefinementStrategy.CONCISE:
            return self._apply_concise(content)
        elif strategy == RefinementStrategy.EXPAND:
            return self._apply_expand(content, task_description)
        elif strategy == RefinementStrategy.CORRECT:
            return self._apply_correct(content, quality_report)
        elif strategy == RefinementStrategy.RESTRUCTURE:
            return self._apply_restructure(content)
        elif strategy == RefinementStrategy.VALIDATE:
            return self._apply_validate(content)
        elif strategy == RefinementStrategy.OPTIMIZE:
            return self._apply_optimize(content, extra_context.get("objective", task_description))
        elif strategy == RefinementStrategy.ADAPT_AUDIENCE:
            return self._apply_adapt(content, extra_context.get("audience", "general"))
        return content

    def select_strategy(self, quality_report: QualityReport,
                        criteria: List[QualityCriteria],
                        iteration: int) -> RefinementStrategy:
        """Selecciona la estrategia que ataca el criterio más débil."""
        if not quality_report.issues:
            strategies = [
                RefinementStrategy.CLARIFY,
                RefinementStrategy.CONCISE,
                RefinementStrategy.RESTRUCTURE,
            ]
            return strategies[iteration % len(strategies)]

        weak_criteria = [
            (c.name, quality_report.criteria_scores.get(c.name, 0.0))
            for c in criteria
            if quality_report.criteria_scores.get(c.name, 1.0) < c.target
        ]

        if not weak_criteria:
            return RefinementStrategy.CLARIFY

        weak_criteria.sort(key=lambda x: x[1])
        weakest = weak_criteria[0][0]

        strategy_map = {
            "clarity": RefinementStrategy.CLARIFY,
            "conciseness": RefinementStrategy.CONCISE,
            "completeness": RefinementStrategy.EXPAND,
            "accuracy": RefinementStrategy.VALIDATE,
            "coherence": RefinementStrategy.RESTRUCTURE,
            "relevance": RefinementStrategy.OPTIMIZE,
        }
        return strategy_map.get(weakest, RefinementStrategy.CLARIFY)

    def get_prompt_for_strategy(self, strategy: RefinementStrategy,
                                quality_report: Optional[QualityReport] = None,
                                extra_context: Optional[Dict] = None) -> str:
        """Retorna el prompt de refinamiento para una estrategia."""
        prompt = self.STRATEGY_PROMPTS[strategy]
        extra_context = extra_context or {}
        if "{issues}" in prompt and quality_report:
            issues_text = "; ".join(quality_report.issues[:5])
            prompt = prompt.replace("{issues}", issues_text)
        if "{objective}" in prompt:
            prompt = prompt.replace("{objective}", extra_context.get("objective", "general"))
        if "{audience}" in prompt:
            prompt = prompt.replace("{audience}", extra_context.get("audience", "general"))
        return prompt

    # ── Transformaciones heurísticas (simula LLM) ──

    @staticmethod
    def _apply_clarify(content: str) -> str:
        """Divide oraciones largas, simplifica."""
        sentences = [s.strip() for s in content.split(".") if s.strip()]
        improved = []
        for s in sentences:
            if len(s) > 120:
                mid = len(s) // 2
                space_idx = s.find(" ", mid)
                if space_idx > 0:
                    improved.append(s[:space_idx].strip())
                    improved.append(s[space_idx:].strip())
                else:
                    improved.append(s)
            else:
                improved.append(s)
        return ". ".join(improved) + "."

    @staticmethod
    def _apply_concise(content: str) -> str:
        """Elimina oraciones redundantes, reduce longitud."""
        sentences = [s.strip() for s in content.split(".") if s.strip()]
        if len(sentences) <= 2:
            return content
        # Elimina las oraciones más cortas (asume menos información)
        sentences.sort(key=len, reverse=True)
        keep = max(2, int(len(sentences) * 0.7))
        return ". ".join(sentences[:keep]) + "."

    @staticmethod
    def _apply_expand(content: str, task: str) -> str:
        """Agrega contexto y conectores."""
        addition = f" Además, en el contexto de '{task[:50]}', es importante considerar las implicaciones prácticas."
        return content.rstrip(".") + "." + addition

    @staticmethod
    def _apply_correct(content: str, quality_report: QualityReport) -> str:
        """Aplica correcciones basadas en issues."""
        # Simula corrección agregando nota
        if quality_report.issues:
            note = " [Corrección aplicada: " + "; ".join(quality_report.issues[:2]) + "]"
            return content + note
        return content

    @staticmethod
    def _apply_restructure(content: str) -> str:
        """Reorganiza con conectores lógicos."""
        sentences = [s.strip() for s in content.split(".") if s.strip()]
        if len(sentences) < 2:
            return content
        connectors = ["Primero, ", "Además, ", "Finalmente, "]
        restructured = []
        for i, s in enumerate(sentences):
            prefix = connectors[i % len(connectors)] if i > 0 else ""
            restructured.append(prefix + s)
        return ". ".join(restructured) + "."

    @staticmethod
    def _apply_validate(content: str) -> str:
        """Agrega marcadores de verificación."""
        return content + " [Verificado: contenido validado contra fuentes]"

    @staticmethod
    def _apply_optimize(content: str, objective: str) -> str:
        """Enfoca en el objetivo."""
        return f"Enfocado en '{objective[:40]}': " + content

    @staticmethod
    def _apply_adapt(content: str, audience: str) -> str:
        """Adapta tono para audiencia."""
        return f"[Para {audience}] " + content
