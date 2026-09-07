"""
UC-328 — Gestor de Caché para ORQUESTA-R.

Implementa una caché en memoria con TTL y contadores de acceso/hits.
En producción, este stub puede ser reemplazado por Redis, Memcached u
otro store distribuido.
"""

from typing import Optional, Any, Dict
import time
import hashlib
import json

from orquesta_models import CacheEntry


class CacheManager:
    """
    Caché semántica para resultados de subconsultas.

    Clave: hash normalizado de (subquery_text + source_id + time_bucket).
    TTL: configurable por fuente y tipo de dato (volátil vs estático).
    """

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}

    def _build_key(
        self,
        subquery_text: str,
        source_id: str,
        context: str = "",
    ) -> str:
        """Construye una clave de caché determinística."""
        normalized = " ".join(subquery_text.lower().split())
        raw = f"{normalized}|{source_id}|{context}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(
        self,
        subquery_text: str,
        source_id: str,
        context: str = "",
    ) -> Optional[Any]:
        """Recupera un valor de caché si no ha expirado."""
        key = self._build_key(subquery_text, source_id, context)
        entry = self._cache.get(key)
        if not entry:
            return None
        entry.access_count += 1
        if entry.is_expired:
            del self._cache[key]
            return None
        entry.hit_count += 1
        return entry.value

    def set(
        self,
        subquery_text: str,
        source_id: str,
        value: Any,
        context: str = "",
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Almacena un valor en caché."""
        key = self._build_key(subquery_text, source_id, context)
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds or self.default_ttl_seconds,
            created_at=time.time(),
            access_count=1,
            hit_count=0,
        )
        self._cache[key] = entry
        return key

    def invalidate(self, subquery_text: str = "", source_id: str = "") -> int:
        """Invalida entradas de caché. Si ambos están vacíos, limpia todo."""
        if not subquery_text and not source_id:
            count = len(self._cache)
            self._cache.clear()
            return count

        removed = 0
        keys_to_remove = []
        for key, entry in self._cache.items():
            # Best-effort: cannot reverse key, so remove all if source_id matches.
            # For stricter invalidation, iterate all and check value metadata.
            if source_id and entry.value and isinstance(entry.value, dict):
                if entry.value.get("source_id") == source_id:
                    keys_to_remove.append(key)
            else:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            if key in self._cache:
                del self._cache[key]
                removed += 1
        return removed

    def cleanup_expired(self) -> int:
        """Elimina entradas expiradas."""
        expired = [k for k, e in self._cache.items() if e.is_expired]
        for k in expired:
            del self._cache[k]
        return len(expired)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de la caché."""
        total = len(self._cache)
        hits = sum(e.hit_count for e in self._cache.values())
        accesses = sum(e.access_count for e in self._cache.values())
        expired = sum(1 for e in self._cache.values() if e.is_expired)
        return {
            "entries": total,
            "expired_entries": expired,
            "total_hits": hits,
            "total_accesses": accesses,
            "hit_rate": round(hits / accesses, 4) if accesses > 0 else 0.0,
        }

    def reset(self) -> None:
        """Limpia la caché."""
        self._cache.clear()
