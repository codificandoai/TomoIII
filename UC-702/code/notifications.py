"""UC-702 — Despachador de notificaciones.

Envía avisos de interrupción de instancia spot (u otros eventos
críticos) a múltiples canales: AWS SNS, Slack, webhooks genéricos. Cada
canal falla de forma aislada para no bloquear la cadena de checkpoint y
limpieza que corre en paralelo.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

import requests

from config import SpotWatcherConfig
from models import SpotInterruptionEvent

logger = logging.getLogger("uc702-notifications")


class NotificationDispatcher:
    def __init__(self, config: SpotWatcherConfig) -> None:
        self.config = config

    def notify(self, event: SpotInterruptionEvent) -> List[str]:
        """Dispara la notificación en todos los canales configurados.
        Retorna la lista de canales que se ejecutaron correctamente."""
        delivered: List[str] = []
        subject = "Spot Interruption Warning"
        message = (
            f"El nodo {event.node_id} ({event.provider.value}) recibió un aviso de "
            f"terminación de instancia spot. Acción: {event.action}. "
            f"Tiempo estimado de terminación: {event.termination_time or 'desconocido'}."
        )

        if self.config.sns_topic_arn:
            if self._notify_sns(subject, message):
                delivered.append("sns")
        if self.config.slack_webhook_url:
            if self._notify_slack(message):
                delivered.append("slack")
        for url in self.config.generic_webhook_urls:
            if self._notify_webhook(url, event):
                delivered.append(f"webhook:{url}")
        return delivered

    def _notify_sns(self, subject: str, message: str) -> bool:
        try:
            import boto3
        except ImportError:
            logger.warning("boto3 no disponible; se omite notificación SNS")
            return False
        try:
            sns = boto3.client("sns")
            sns.publish(TopicArn=self.config.sns_topic_arn, Subject=subject, Message=message)
            return True
        except Exception as exc:  # pragma: no cover - depende de credenciales/red reales
            logger.warning("fallo notificando por SNS: %s", exc)
            return False

    def _notify_slack(self, message: str) -> bool:
        try:
            resp = requests.post(self.config.slack_webhook_url, json={"text": message}, timeout=5)
            return resp.status_code < 300
        except requests.RequestException as exc:
            logger.warning("fallo notificando por Slack: %s", exc)
            return False

    def _notify_webhook(self, url: str, event: SpotInterruptionEvent) -> bool:
        try:
            resp = requests.post(url, json=event.to_dict(), timeout=5)
            return resp.status_code < 300
        except requests.RequestException as exc:
            logger.warning("fallo notificando webhook %s: %s", url, exc)
            return False
