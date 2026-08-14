"""
Codificando.AI - UC-119
Paquete de analizadores de métricas para monitoreo de LLMs.

Submódulos:
- diversity: diversidad léxica de entrada/salida.
- toxicity: detección de contenido tóxico o dañino.
- bias: detección de sesgos.
- hallucination: detección de alucinaciones.
- evasion: jailbreak, prompt injection, ofuscación.
- quality: groundedness, relevancia, fidelidad, coherencia, finalización de
  tareas, precisión de recuperación, satisfacción del usuario.
- security: PII, incumplimiento de políticas, guardarraíles, extracción de
  prompt, acceso no autorizado.
- cost: tokens, coste, TTFT, latencia, errores, caché.
"""

from .diversity import DiversityAnalyzer, DiversityMetrics
from .toxicity import ToxicityDetector, ToxicityMetrics
from .bias import BiasDetector, BiasMetrics
from .hallucination import HallucinationDetector, HallucinationMetrics
from .evasion import EvasionDetector, EvasionDetection
from .quality import QualityAnalyzer, QualityMetrics
from .security import SecurityAnalyzer, SecurityMetrics
from .cost import CostPerformanceAnalyzer, CostPerformanceMetrics

__all__ = [
    "DiversityAnalyzer", "DiversityMetrics",
    "ToxicityDetector", "ToxicityMetrics",
    "BiasDetector", "BiasMetrics",
    "HallucinationDetector", "HallucinationMetrics",
    "EvasionDetector", "EvasionDetection",
    "QualityAnalyzer", "QualityMetrics",
    "SecurityAnalyzer", "SecurityMetrics",
    "CostPerformanceAnalyzer", "CostPerformanceMetrics",
]
