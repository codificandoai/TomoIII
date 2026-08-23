"""UC-702 — Agente de nodo.

Se ejecuta en cada server/nodo (on-premise o en la nube) y:
  1. Recolecta CPU, GPU, memoria, disco y red en tiempo real.
  2. Registra el nodo y publica su telemetría hacia la API central
     (`POST /api/v1/nodes/<id>/telemetry`), que sumariza la capacidad
     subutilizada disponible en el pool compartido.
  3. Opcionalmente vigila interrupciones de instancia spot en paralelo.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Optional

import requests

from config import MonitorConfig, SpotWatcherConfig
from models import InstanceLifecycle, NodeInfo, ProviderKind
from resource_monitor import ResourceMonitor, detect_platform, get_hostname
from spot_watcher import AWSSpotWatcher

logger = logging.getLogger("uc702-node-agent")


def detect_provider() -> ProviderKind:
    env_provider = os.environ.get("UC702_PROVIDER", "").lower()
    mapping = {
        "aws": ProviderKind.AWS,
        "gcp": ProviderKind.GCP,
        "azure": ProviderKind.AZURE,
        "on-premise": ProviderKind.ON_PREMISE,
        "onprem": ProviderKind.ON_PREMISE,
    }
    return mapping.get(env_provider, ProviderKind.ON_PREMISE)


def detect_lifecycle() -> InstanceLifecycle:
    env_lifecycle = os.environ.get("UC702_LIFECYCLE", "").lower()
    mapping = {
        "spot": InstanceLifecycle.SPOT,
        "on-demand": InstanceLifecycle.ON_DEMAND,
        "free-tier": InstanceLifecycle.FREE_TIER,
        "reserved": InstanceLifecycle.RESERVED,
    }
    return mapping.get(env_lifecycle, InstanceLifecycle.UNKNOWN)


def build_node_info(node_id: Optional[str] = None) -> NodeInfo:
    import platform as _platform

    return NodeInfo(
        node_id=node_id or os.environ.get("UC702_NODE_ID") or f"{get_hostname()}-{uuid.uuid4().hex[:6]}",
        hostname=get_hostname(),
        platform=detect_platform(),
        architecture=_platform.machine(),
        provider=detect_provider(),
        lifecycle=detect_lifecycle(),
        region=os.environ.get("UC702_REGION"),
        zone=os.environ.get("UC702_ZONE"),
        rack=os.environ.get("UC702_RACK"),
        site=os.environ.get("UC702_SITE", "default"),
    )


class NodeAgent:
    def __init__(
        self,
        api_base_url: Optional[str] = None,
        node_info: Optional[NodeInfo] = None,
        monitor_config: Optional[MonitorConfig] = None,
        spot_config: Optional[SpotWatcherConfig] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = monitor_config or MonitorConfig()
        self.api_base_url = api_base_url or self.config.api_base_url
        self.info = node_info or build_node_info()
        self.resource_monitor = ResourceMonitor()
        self.session = session or requests.Session()
        self.spot_config = spot_config or SpotWatcherConfig()
        self._stop_event = threading.Event()

    def register(self) -> None:
        resp = self.session.post(
            f"{self.api_base_url}/api/v1/nodes/register", json=self.info.to_dict(), timeout=10
        )
        resp.raise_for_status()

    def publish_once(self) -> dict:
        snapshot = self.resource_monitor.snapshot()
        resp = self.session.post(
            f"{self.api_base_url}/api/v1/nodes/{self.info.node_id}/telemetry",
            json=snapshot.to_dict(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def run_telemetry_loop(self, max_iterations: Optional[int] = None) -> None:
        self.register()
        iterations = 0
        while not self._stop_event.is_set() and (max_iterations is None or iterations < max_iterations):
            try:
                self.publish_once()
            except requests.RequestException as exc:
                logger.warning("fallo publicando telemetría: %s", exc)
            iterations += 1
            self._stop_event.wait(self.config.poll_interval_seconds)

    def start_spot_watch_background(self) -> Optional[threading.Thread]:
        if self.info.provider != ProviderKind.AWS:
            return None
        watcher = AWSSpotWatcher(self.info.node_id, config=self.spot_config)

        def _on_event(event):
            try:
                self.session.post(
                    f"{self.api_base_url}/api/v1/spot/events", json=event.to_dict(), timeout=10
                )
            except requests.RequestException as exc:
                logger.warning("fallo reportando evento spot a la API: %s", exc)

        thread = threading.Thread(target=watcher.run, kwargs={"on_event": _on_event}, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop_event.set()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    agent = NodeAgent()
    agent.start_spot_watch_background()
    agent.run_telemetry_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
