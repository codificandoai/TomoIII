"""
Codificando.AI - UC-127
Cliente base para las integraciones externas (SIEM, colaboración, Wiki.js,
model router, gateway, escalado, ticketing).

Todas las integraciones heredan de `BaseIntegrationClient`, que centraliza
el modo `dry_run` (por defecto activo): en `dry_run`, la acción se registra
en el log y en la traza de auditoría, pero no se realiza ninguna llamada
HTTP real — esto permite ejecutar la suite de pruebas y las demos sin
depender de servicios externos (Splunk, Slack, Wiki.js, Kubernetes, Jira),
tal como se hizo con los modelos ML opcionales en UC-119.
"""

import logging
from typing import Any, Dict, Optional

from config import CONFIG

logger = logging.getLogger(__name__)


class BaseIntegrationClient:
    """Funcionalidad común: HTTP con timeout, manejo de errores y modo
    `dry_run` para todas las integraciones externas de UC-127."""

    def __init__(self, dry_run: Optional[bool] = None, timeout: Optional[float] = None):
        self.dry_run = CONFIG.integrations.dry_run if dry_run is None else dry_run
        self.timeout = timeout or CONFIG.integrations.request_timeout_s

    def _post(self, url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> bool:
        """Realiza un POST HTTP si no está en `dry_run` y hay una URL
        configurada. Devuelve `True` si la operación fue exitosa (o
        simulada), `False` si hubo un error real de red/HTTP."""
        if self.dry_run or not url:
            logger.info(f"[dry_run] POST {url or '(sin URL configurada)'} payload_keys={list(payload.keys())}")
            return True

        try:
            import requests
            response = requests.post(url, json=payload, headers=headers or {}, timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception as e:  # pragma: no cover - depende de infra externa
            logger.error(f"Fallo al invocar integración externa {url}: {e}")
            return False
