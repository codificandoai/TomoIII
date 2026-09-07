"""
UC-083 — Gestor de runbooks para respuesta a incidentes de inferencia batch.

Mantiene protocolos de respuesta estructurados por tipo de síntoma,
con pasos de diagnóstico, mitigación y prevención.
"""

from typing import Dict, List, Optional, Any

from incident_models import RootCauseCategory


class RunbookManager:
    """
    Proporciona runbooks para incidentes de inferencia batch. Los runbooks
son plantillas rellenadas dinámicamente según la causa raíz identificada.
    """

    DEFAULT_RUNBOOKS = {
        RootCauseCategory.OOM: {
            "title": "🚨 Runbook: Out of Memory en Inferencia Batch",
            "symptom": "Workers terminan con Killed / OOM / memory limit exceeded.",
            "detection": [
                "Alerta de uso de memoria > 90% en Grafana/Prometheus/CloudWatch.",
                "Log del orquestador indica 'Killed process ... out of memory'.",
                "Workers reinician sin completar particiones.",
            ],
            "diagnosis": [
                "1. Revisar logs de Prefect/Airflow en tarea validate_and_prepare_data. ¿Saltó alerta de VOLUMEN EXCESIVO?",
                "2. Confirmar conteo de filas del lote vs baseline histórico.",
                "3. Revisar Dask Dashboard por 'spilling to disk' excesivo.",
                "4. Verificar versión del modelo y configuración de despliegue.",
            ],
            "mitigation": [
                "A. Detener reintentos automáticos para evitar consumo adicional y duplicación.",
                "B. Si volumen es anómalo (duplicación/errores upstream): contactar Data Engineering; no reintentar.",
                "C. Si volumen es legítimo: reanudar con chunking y concurrencia controlada (max_workers limitado).",
                "D. Escalar temporalmente recursos del worker (ej. RAM de 4GB a 8GB).",
                "E. Reprocesar particiones afectadas usando checkpoints idempotentes.",
            ],
            "prevention": [
                "Agregar validación temprana de volumen, esquema y completitud.",
                "Configurar alertas predictivas de presión de memoria.",
                "Implementar chunking distribuido y límites de concurrencia.",
                "Actualizar runbook con lecciones aprendidas.",
            ],
            "escalation": "Escalar a equipo de Plataforma si el crecimiento es legítimo y requiere rediseño de arquitectura.",
        },
        RootCauseCategory.TIMEOUT: {
            "title": "🚨 Runbook: Timeout en Inferencia Batch",
            "symptom": "Pipeline excede duración máxima esperada.",
            "detection": [
                "Alerta de duración del job > umbral.",
                "Logs indican 'timeout' o 'deadline exceeded'.",
            ],
            "diagnosis": [
                "1. Comparar duración actual vs baseline.",
                "2. Verificar si el volumen de entrada creció significativamente.",
                "3. Revisar cuellos de botella en workers y colas.",
            ],
            "mitigation": [
                "A. Aplicar chunking distribuido para reducir tiempo por worker.",
                "B. Aumentar concurrencia dentro de límites seguros.",
                "C. Escalar horizontalmente el clúster de workers.",
            ],
            "prevention": [
                "Alertas predictivas de duración basadas en tamaño del lote.",
                "Auto-escalamiento de workers según volumen.",
            ],
            "escalation": "Escalar a SRE si el timeout persiste tras escalamiento.",
        },
        RootCauseCategory.DATA_VOLUME: {
            "title": "🚨 Runbook: Pico de Volumen de Datos Upstream",
            "symptom": "El lote supera el percentil 95 del tamaño histórico.",
            "detection": [
                "Alerta de VOLUMEN EXCESIVO en validación temprana.",
                "Conteo de filas excede max_allowed_rows.",
            ],
            "diagnosis": [
                "1. Validar contra baseline histórico.",
                "2. Revisar pipeline de ingesta upstream por duplicaciones.",
                "3. Confirmar que el esquema no cambió.",
            ],
            "mitigation": [
                "A. Si es error upstream: detener y contactar Data Engineering.",
                "B. Si es legítimo: activar modo distribuido con chunking y escalar recursos.",
            ],
            "prevention": [
                "Regla en data lake que alerte si archivo diario supera P95 histórico.",
                "Ajustar max_allowed_rows dinámicamente según capacidad.",
            ],
            "escalation": "Escalar a Data Engineering y Producto si el cambio de volumen es permanente.",
        },
        RootCauseCategory.SCHEMA_DRIFT: {
            "title": "🚨 Runbook: Schema Drift en Datos de Entrada",
            "symptom": "Columnas faltantes, extra o tipos inesperados.",
            "detection": [
                "Validación de esquema falla en Prefect/Airflow.",
                "Logs de parsing errors en workers.",
            ],
            "diagnosis": [
                "1. Comparar columnas actuales vs expected schema.",
                "2. Revisar cambios recientes en fuente upstream.",
            ],
            "mitigation": [
                "A. Rechazar lote y notificar al equipo de datos.",
                "B. Si el drift es esperado: actualizar schema y reentrenar si es necesario.",
            ],
            "prevention": [
                "Validación de esquema en capa de ingesta.",
                "Contratos de datos con alertas automáticas.",
            ],
            "escalation": "Escalar a Data Engineering.",
        },
        RootCauseCategory.INFRASTRUCTURE: {
            "title": "🚨 Runbook: Falla de Infraestructura",
            "symptom": "Workers fallan por problemas de red, disco o nodo.",
            "detection": [
                "Logs de infraestructura indican caídas de nodos.",
                "Métricas de disco o red anómalas.",
            ],
            "diagnosis": [
                "1. Verificar estado del clúster y nodos.",
                "2. Revisar eventos de cloud provider.",
            ],
            "mitigation": [
                "A. Reintentar en zona/nodo alternativo.",
                "B. Reprocesar particiones afectadas con checkpoints.",
            ],
            "prevention": [
                "Multi-zona para workers críticos.",
                "Health checks y auto-reinicio.",
            ],
            "escalation": "Escalar a SRE / CloudOps.",
        },
        RootCauseCategory.MODEL_FAILURE: {
            "title": "🚨 Runbook: Falla del Modelo",
            "symptom": "El modelo arroja excepciones o predicciones inválidas.",
            "detection": [
                "Logs de predicción con excepciones.",
                "Distribución de predicciones fuera de rango esperado.",
            ],
            "diagnosis": [
                "1. Verificar versión y artefacto del modelo.",
                "2. Validar distribución de features vs entrenamiento.",
            ],
            "mitigation": [
                "A. Rollback a versión anterior del modelo.",
                "B. Aislar registros problemáticos y reprocesar el resto.",
            ],
            "prevention": [
                "Shadow testing y monitoreo de drift.",
                "Rollback automático si error rate supera umbral.",
            ],
            "escalation": "Escalar a equipo de Data Science / MLOps.",
        },
        RootCauseCategory.UNKNOWN: {
            "title": "🚨 Runbook: Incidente de Inferencia Batch — Causa Desconocida",
            "symptom": "Pipeline falló sin patrón claro.",
            "detection": [
                "Falla general del pipeline.",
            ],
            "diagnosis": [
                "1. Recopilar logs, métricas y muestra de datos.",
                "2. Correlacionar eventos por timestamp y trace_id.",
                "3. Comparar contra baseline histórico.",
            ],
            "mitigation": [
                "A. Detener reintentos automáticos.",
                "B. Escalar a equipo de guardia con evidencia recopilada.",
            ],
            "prevention": [
                "Mejorar observabilidad y cobertura de logs.",
            ],
            "escalation": "Escalar a On-call / SRE.",
        },
    }

    def __init__(self, base_url: str = "https://wiki.trackprice.ai/runbooks"):
        self.base_url = base_url
        self._runbooks = dict(self.DEFAULT_RUNBOOKS)

    def get(self, category: RootCauseCategory) -> Dict[str, Any]:
        runbook = dict(self._runbooks.get(category, self._runbooks[RootCauseCategory.UNKNOWN]))
        runbook["category"] = category.value
        runbook["url"] = f"{self.base_url}/{category.value}"
        return runbook

    def get_runbook_url(self, category: RootCauseCategory) -> str:
        return f"{self.base_url}/{category.value}"

    def list_runbooks(self) -> List[Dict[str, str]]:
        return [
            {"category": cat.value, "title": data["title"], "url": f"{self.base_url}/{cat.value}"}
            for cat, data in self._runbooks.items()
        ]

    def update_runbook(self, category: RootCauseCategory, section: str, item: str) -> None:
        """Permite añadir mejoras permanentes tras un incidente."""
        if category not in self._runbooks:
            category = RootCauseCategory.UNKNOWN
        self._runbooks[category].setdefault(section, []).append(item)

    def generate_postmortem_improvements(self, category: RootCauseCategory) -> List[str]:
        runbook = self._runbooks.get(category, self._runbooks[RootCauseCategory.UNKNOWN])
        return runbook.get("prevention", [])
