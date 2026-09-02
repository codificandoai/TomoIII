"""Almacenamiento persistente de subárboles MCTS para UC-292."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional


class MCTSPersistentStore:
    """Cache ligero de estadísticas MCTS por firma de solicitud."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or ""
        self.cache: Dict[str, Any] = {}
        if self.path and os.path.exists(self.path):
            self._load()

    @staticmethod
    def signature(request: Dict[str, Any]) -> str:
        """Firma estable para una solicitud de trading."""
        keys = ["symbols", "risk_tolerance", "mode"]
        parts = []
        for k in keys:
            v = request.get(k)
            if isinstance(v, list):
                v = sorted(v)
            parts.append(f"{k}={v}")
        text = "|".join(parts)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def get(self, request: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        sig = self.signature(request)
        entry = self.cache.get(sig)
        if not entry:
            return None
        return entry.get("children")

    def save(
        self,
        request: Dict[str, Any],
        children: List[Dict[str, Any]],
    ) -> None:
        sig = self.signature(request)
        self.cache[sig] = {"children": children}
        self._persist()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.cache = {}

    def _persist(self) -> None:
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False)
        except OSError:
            pass
