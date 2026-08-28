"""Cliente A2A para UC-268.

Descubre agentes mediante Agent Card y envía tareas via JSON-RPC 2.0 sobre HTTPS.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, Optional

from config import AppConfig, get_config
from models import AgentCard, JSONRPCRequest, JSONRPCResponse, Task
from security import SecurityManager


class A2AClientError(Exception):
    pass


class A2AClient:
    """Cliente A2A que consume agentes remotos."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self.config = config or get_config()
        self.security = SecurityManager(self.config.security)
        self._cards: Dict[str, AgentCard] = {}

    def discover(self, agent_url: str) -> AgentCard:
        """Descubre la Agent Card desde /.well-known/agent.json."""
        self.security.check_transport_security(agent_url)
        well_known = agent_url.rstrip("/") + "/.well-known/agent.json"
        try:
            with urllib.request.urlopen(well_known, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise A2AClientError(f"Failed to fetch Agent Card: {exc}") from exc
        card = AgentCard.model_validate(data)
        self._cards[agent_url] = card
        return card

    def send_task(
        self,
        agent_url: str,
        task: Task,
        *,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> JSONRPCResponse:
        """Envía una tarea al endpoint A2A del agente remoto."""
        self.security.check_transport_security(agent_url)
        card = self._cards.get(agent_url)
        if card is None:
            card = self.discover(agent_url)
        endpoint = agent_url.rstrip("/") + "/a2a"

        request = JSONRPCRequest(
            method="tasks/send",
            params={"task": task.model_dump(mode="json")},
            id=task.task_id,
        )
        body = request.model_dump_json().encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif api_key:
            headers["X-API-Key"] = api_key

        req = urllib.request.Request(
            endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise A2AClientError(
                f"A2A request failed: {exc.code} {exc.reason}"
            ) from exc
        except Exception as exc:
            raise A2AClientError(f"A2A request failed: {exc}") from exc

        return JSONRPCResponse.model_validate_json(raw)

    def get_task(
        self,
        agent_url: str,
        task_id: str,
        *,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> JSONRPCResponse:
        """Consulta el estado de una tarea enviada previamente."""
        endpoint = agent_url.rstrip("/") + "/a2a"
        request = JSONRPCRequest(
            method="tasks/get",
            params={"task_id": task_id},
            id=task_id,
        )
        body = request.model_dump_json().encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif api_key:
            headers["X-API-Key"] = api_key

        req = urllib.request.Request(
            endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise A2AClientError(
                f"A2A request failed: {exc.code} {exc.reason}"
            ) from exc
        return JSONRPCResponse.model_validate_json(raw)
