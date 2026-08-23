"""UC-702 — Detector de interrupción de instancias spot (AWS y extensible).

Sigue `http://169.254.169.254/latest/meta-data/spot/instance-action`:
cuando AWS va a terminar la instancia, ese endpoint devuelve un JSON con
el tiempo de terminación (~120 segundos antes). Este módulo:

  1. Sondea el endpoint cada `poll_interval_seconds`.
  2. Detecta el aviso (usa IMDSv2 con token cuando está disponible).
  3. Dispara notificaciones (SNS, Slack, webhook) vía `NotificationDispatcher`.
  4. Ejecuta scripts de checkpoint/cleanup antes de que expire el tiempo.

Extensible a otros proveedores (GCP `preempted`, Azure Scheduled Events)
implementando `BaseSpotWatcher`.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from checkpoint_manager import CheckpointManager
from config import SpotWatcherConfig
from models import ProviderKind, SpotInterruptionEvent
from notifications import NotificationDispatcher

logger = logging.getLogger("uc702-spot-watcher")

OnEventCallback = Callable[[SpotInterruptionEvent], None]


class BaseSpotWatcher(ABC):
    provider: ProviderKind

    def __init__(
        self,
        node_id: str,
        config: Optional[SpotWatcherConfig] = None,
        dispatcher: Optional[NotificationDispatcher] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.node_id = node_id
        self.config = config or SpotWatcherConfig()
        self.dispatcher = dispatcher or NotificationDispatcher(self.config)
        self.checkpoints = checkpoint_manager or CheckpointManager(self.config.checkpoint_storage_path)
        self.session = session or requests.Session()

    @abstractmethod
    def check_once(self) -> Optional[SpotInterruptionEvent]:
        """Realiza una única consulta al endpoint de metadatos. Retorna un
        `SpotInterruptionEvent` si hay aviso de terminación, o `None`."""
        raise NotImplementedError

    def handle_event(self, event: SpotInterruptionEvent) -> dict:
        """Ejecuta la respuesta completa ante una interrupción detectada:
        notificar y disparar checkpoint/cleanup."""
        logger.warning("Interrupción detectada en %s: %s", event.node_id, event.action)
        delivered = self.dispatcher.notify(event)
        checkpoint = self.checkpoints.create_checkpoint(event.node_id, payload=event.to_dict())
        checkpoint_script_result = self.checkpoints.run_script(
            self.config.checkpoint_script, env_extra={"UC702_NODE_ID": event.node_id}
        )
        cleanup_script_result = self.checkpoints.run_script(
            self.config.cleanup_script, env_extra={"UC702_NODE_ID": event.node_id}
        )
        return {
            "event": event.to_dict(),
            "notifications_delivered": delivered,
            "checkpoint": dict(checkpoint),
            "checkpoint_script": checkpoint_script_result,
            "cleanup_script": cleanup_script_result,
        }

    def run(self, max_iterations: Optional[int] = None, on_event: Optional[OnEventCallback] = None, sleep_fn: Callable[[float], None] = time.sleep) -> Optional[SpotInterruptionEvent]:
        """Bucle de sondeo. Se detiene tras detectar el primer evento (ya
        que la instancia va a terminar) o tras `max_iterations` si se
        especifica (útil en pruebas)."""
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            try:
                event = self.check_once()
                if event:
                    self.handle_event(event)
                    if on_event:
                        on_event(event)
                    return event
            except Exception as exc:  # pragma: no cover - resiliencia ante fallos de red puntuales
                logger.debug("chequeo de interrupción falló: %s", exc)
            iterations += 1
            sleep_fn(self.config.poll_interval_seconds)
        return None


class AWSSpotWatcher(BaseSpotWatcher):
    """Implementación para AWS EC2 Spot vía IMDS (v1/v2)."""

    provider = ProviderKind.AWS

    def _imds_token(self) -> Optional[str]:
        if not self.config.use_imdsv2:
            return None
        try:
            resp = self.session.put(
                self.config.token_url,
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                timeout=self.config.request_timeout_seconds,
            )
            if resp.status_code == 200:
                return resp.text
        except requests.RequestException as exc:
            logger.debug("no se pudo obtener token IMDSv2: %s", exc)
        return None

    def check_once(self) -> Optional[SpotInterruptionEvent]:
        headers = {}
        token = self._imds_token()
        if token:
            headers["X-aws-ec2-metadata-token"] = token
        try:
            resp = self.session.get(
                self.config.metadata_url, headers=headers, timeout=self.config.request_timeout_seconds
            )
        except requests.RequestException as exc:
            logger.debug("fallo consultando metadata endpoint: %s", exc)
            return None

        if resp.status_code != 200 or not resp.text.strip():
            return None

        raw_text = resp.text.strip()
        action = "terminate"
        termination_time = None
        raw_payload = None
        try:
            raw_payload = json.loads(raw_text)
            action = raw_payload.get("action", action)
            termination_time = raw_payload.get("time")
        except ValueError:
            # El endpoint puede devolver texto plano en vez de JSON.
            raw_payload = {"raw": raw_text}

        return SpotInterruptionEvent(
            node_id=self.node_id,
            provider=self.provider,
            detected_at=datetime.now(timezone.utc),
            action=action,
            termination_time=termination_time,
            lead_time_seconds=self.config.lead_time_seconds,
            raw=raw_payload,
        )


def build_watcher(node_id: str, provider: ProviderKind = ProviderKind.AWS, **kwargs) -> BaseSpotWatcher:
    if provider == ProviderKind.AWS:
        return AWSSpotWatcher(node_id, **kwargs)
    raise ValueError(f"proveedor no soportado todavía: {provider}")
