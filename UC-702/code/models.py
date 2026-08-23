"""UC-702 — Modelos de datos.

Representan el inventario de nodos, sus recursos (CPU, GPU, memoria,
disco, red), la capacidad subutilizada disponible y las asignaciones
realizadas contra el pool compartido de capacidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class Platform(str, Enum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


class ProviderKind(str, Enum):
    ON_PREMISE = "on-premise"
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    UNKNOWN = "unknown"


class InstanceLifecycle(str, Enum):
    ON_DEMAND = "on-demand"
    SPOT = "spot"
    FREE_TIER = "free-tier"
    RESERVED = "reserved"
    UNKNOWN = "unknown"


@dataclass
class GPUSnapshot:
    index: int
    name: str
    vendor: str = "unknown"
    utilization_pct: Optional[float] = None
    memory_total_mb: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_free_mb: Optional[float] = None
    temperature_c: Optional[float] = None
    power_watts: Optional[float] = None

    @property
    def memory_free_pct(self) -> Optional[float]:
        if not self.memory_total_mb:
            return None
        free = self.memory_free_mb if self.memory_free_mb is not None else (
            self.memory_total_mb - (self.memory_used_mb or 0)
        )
        return max(0.0, min(100.0, (free / self.memory_total_mb) * 100.0))

    @property
    def idle_pct(self) -> Optional[float]:
        if self.utilization_pct is None:
            return None
        return max(0.0, 100.0 - self.utilization_pct)


def _gpu_from_dict(d: Dict[str, Any]) -> GPUSnapshot:
    return GPUSnapshot(
        index=int(d.get("index", 0)),
        name=d.get("name", "unknown"),
        vendor=d.get("vendor", "unknown"),
        utilization_pct=d.get("utilization_pct"),
        memory_total_mb=d.get("memory_total_mb"),
        memory_used_mb=d.get("memory_used_mb"),
        memory_free_mb=d.get("memory_free_mb"),
        temperature_c=d.get("temperature_c"),
        power_watts=d.get("power_watts"),
    )


@dataclass
class ResourceSnapshot:
    """Foto instantánea de utilización de recursos de un nodo."""

    timestamp: datetime
    cpu_percent: float
    cpu_count_logical: int
    cpu_count_physical: int
    load_avg_1m: Optional[float]
    memory_total_mb: float
    memory_used_mb: float
    memory_available_mb: float
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    net_bytes_sent: int
    net_bytes_recv: int
    net_sent_rate_bps: float
    net_recv_rate_bps: float
    gpus: List[GPUSnapshot] = field(default_factory=list)

    @property
    def cpu_idle_pct(self) -> float:
        return max(0.0, 100.0 - self.cpu_percent)

    @property
    def memory_available_pct(self) -> float:
        if not self.memory_total_mb:
            return 0.0
        return max(0.0, min(100.0, (self.memory_available_mb / self.memory_total_mb) * 100.0))

    @property
    def disk_available_pct(self) -> float:
        if not self.disk_total_gb:
            return 0.0
        return max(0.0, min(100.0, (self.disk_free_gb / self.disk_total_gb) * 100.0))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": round(self.cpu_percent, 2),
            "cpu_idle_pct": round(self.cpu_idle_pct, 2),
            "cpu_count_logical": self.cpu_count_logical,
            "cpu_count_physical": self.cpu_count_physical,
            "load_avg_1m": self.load_avg_1m,
            "memory_total_mb": round(self.memory_total_mb, 2),
            "memory_used_mb": round(self.memory_used_mb, 2),
            "memory_available_mb": round(self.memory_available_mb, 2),
            "memory_available_pct": round(self.memory_available_pct, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_free_gb": round(self.disk_free_gb, 2),
            "disk_available_pct": round(self.disk_available_pct, 2),
            "net_bytes_sent": self.net_bytes_sent,
            "net_bytes_recv": self.net_bytes_recv,
            "net_sent_rate_bps": round(self.net_sent_rate_bps, 2),
            "net_recv_rate_bps": round(self.net_recv_rate_bps, 2),
            "gpus": [
                {
                    "index": g.index,
                    "name": g.name,
                    "vendor": g.vendor,
                    "utilization_pct": g.utilization_pct,
                    "idle_pct": g.idle_pct,
                    "memory_total_mb": g.memory_total_mb,
                    "memory_used_mb": g.memory_used_mb,
                    "memory_free_mb": g.memory_free_mb,
                    "memory_free_pct": g.memory_free_pct,
                    "temperature_c": g.temperature_c,
                    "power_watts": g.power_watts,
                }
                for g in self.gpus
            ],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ResourceSnapshot":
        ts = d.get("timestamp")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        elif isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now(timezone.utc)
        return cls(
            timestamp=timestamp,
            cpu_percent=float(d.get("cpu_percent", 0.0)),
            cpu_count_logical=int(d.get("cpu_count_logical", 0)),
            cpu_count_physical=int(d.get("cpu_count_physical", 0)),
            load_avg_1m=d.get("load_avg_1m"),
            memory_total_mb=float(d.get("memory_total_mb", 0.0)),
            memory_used_mb=float(d.get("memory_used_mb", 0.0)),
            memory_available_mb=float(d.get("memory_available_mb", 0.0)),
            disk_total_gb=float(d.get("disk_total_gb", 0.0)),
            disk_used_gb=float(d.get("disk_used_gb", 0.0)),
            disk_free_gb=float(d.get("disk_free_gb", 0.0)),
            net_bytes_sent=int(d.get("net_bytes_sent", 0)),
            net_bytes_recv=int(d.get("net_bytes_recv", 0)),
            net_sent_rate_bps=float(d.get("net_sent_rate_bps", 0.0)),
            net_recv_rate_bps=float(d.get("net_recv_rate_bps", 0.0)),
            gpus=[_gpu_from_dict(g) for g in d.get("gpus", [])],
        )


@dataclass
class AvailableCapacity:
    """Capacidad subutilizada y candidata a compartirse en el pool."""

    cpu_cores_available: float
    memory_available_mb: float
    disk_available_gb: float
    gpu_count_available: int
    gpu_memory_available_mb: float
    is_subutilized: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores_available": round(self.cpu_cores_available, 2),
            "memory_available_mb": round(self.memory_available_mb, 2),
            "disk_available_gb": round(self.disk_available_gb, 2),
            "gpu_count_available": self.gpu_count_available,
            "gpu_memory_available_mb": round(self.gpu_memory_available_mb, 2),
            "is_subutilized": self.is_subutilized,
            "reasons": self.reasons,
        }


@dataclass
class NodeInfo:
    """Identidad y ubicación topológica de un nodo (server/nodo/rack)."""

    node_id: str
    hostname: str
    platform: Platform
    architecture: str
    provider: ProviderKind
    lifecycle: InstanceLifecycle
    region: Optional[str] = None
    zone: Optional[str] = None
    rack: Optional[str] = None
    site: str = "default"
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "platform": self.platform.value if isinstance(self.platform, Platform) else self.platform,
            "architecture": self.architecture,
            "provider": self.provider.value if isinstance(self.provider, ProviderKind) else self.provider,
            "lifecycle": self.lifecycle.value if isinstance(self.lifecycle, InstanceLifecycle) else self.lifecycle,
            "region": self.region,
            "zone": self.zone,
            "rack": self.rack,
            "site": self.site,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NodeInfo":
        def _enum(enum_cls, value, default):
            try:
                return enum_cls(value)
            except (ValueError, TypeError):
                return default

        return cls(
            node_id=d["node_id"],
            hostname=d.get("hostname", d["node_id"]),
            platform=_enum(Platform, d.get("platform"), Platform.UNKNOWN),
            architecture=d.get("architecture", "unknown"),
            provider=_enum(ProviderKind, d.get("provider"), ProviderKind.UNKNOWN),
            lifecycle=_enum(InstanceLifecycle, d.get("lifecycle"), InstanceLifecycle.UNKNOWN),
            region=d.get("region"),
            zone=d.get("zone"),
            rack=d.get("rack"),
            site=d.get("site", "default"),
            tags=d.get("tags", {}) or {},
        )


@dataclass
class NodeRecord:
    """Estado agregado de un nodo dentro del pool compartido."""

    info: NodeInfo
    last_snapshot: Optional[ResourceSnapshot] = None
    last_capacity: Optional[AvailableCapacity] = None
    last_seen: Optional[datetime] = None

    def is_stale(self, now: datetime, stale_after_seconds: float) -> bool:
        if not self.last_seen:
            return True
        return (now - self.last_seen).total_seconds() > stale_after_seconds

    def to_dict(self, now: Optional[datetime] = None, stale_after_seconds: float = 60.0) -> Dict[str, Any]:
        stale = self.is_stale(now, stale_after_seconds) if now else None
        return {
            **self.info.to_dict(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "stale": stale,
            "snapshot": self.last_snapshot.to_dict() if self.last_snapshot else None,
            "available_capacity": self.last_capacity.to_dict() if self.last_capacity else None,
        }


@dataclass
class ResourceDemand:
    """Demanda de una aplicación/servicio a satisfacer con el pool."""

    requester: str
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    disk_gb: float = 0.0
    gpu_count: int = 0
    gpu_memory_mb: float = 0.0
    preferred_site: Optional[str] = None


@dataclass
class Allocation:
    """Asignación resuelta de un demand contra uno o más nodos del pool."""

    allocation_id: str
    requester: str
    node_id: str
    cpu_cores: float
    memory_mb: float
    disk_gb: float
    gpu_count: int
    gpu_memory_mb: float
    created_at: datetime
    released: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "requester": self.requester,
            "node_id": self.node_id,
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_gb": self.disk_gb,
            "gpu_count": self.gpu_count,
            "gpu_memory_mb": self.gpu_memory_mb,
            "created_at": self.created_at.isoformat(),
            "released": self.released,
        }


@dataclass
class SpotInterruptionEvent:
    """Evento de interrupción de instancia spot detectado."""

    node_id: str
    provider: ProviderKind
    detected_at: datetime
    action: str
    termination_time: Optional[str] = None
    lead_time_seconds: Optional[float] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "provider": self.provider.value if isinstance(self.provider, ProviderKind) else self.provider,
            "detected_at": self.detected_at.isoformat(),
            "action": self.action,
            "termination_time": self.termination_time,
            "lead_time_seconds": self.lead_time_seconds,
            "raw": self.raw,
        }
