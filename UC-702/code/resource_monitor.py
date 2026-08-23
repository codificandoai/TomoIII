"""UC-702 — Recolector de recursos en tiempo real, multiplataforma.

Identifica la disponibilidad de CPU, GPU, memoria y disco de un server,
nodo o rack, tanto on-premise como en la nube (incluyendo instancias
spot y free-tier). Soporta macOS, Linux y Windows, y detecta GPUs
NVIDIA (vía NVML/`nvidia-smi`) además de degradarse limpiamente cuando
no hay acelerador disponible (p.ej. Apple Silicon, CPU-only).
"""

from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import List, Optional

import psutil

from models import GPUSnapshot, Platform as PlatformEnum, ResourceSnapshot


def detect_platform() -> PlatformEnum:
    system = platform.system().lower()
    if system.startswith("linux"):
        return PlatformEnum.LINUX
    if system.startswith("darwin"):
        return PlatformEnum.MACOS
    if system.startswith("windows"):
        return PlatformEnum.WINDOWS
    return PlatformEnum.UNKNOWN


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "unknown-host"


def _load_avg_1m() -> Optional[float]:
    try:
        return psutil.getloadavg()[0]
    except (AttributeError, OSError):
        return None


def _collect_gpus_nvidia_smi() -> List[GPUSnapshot]:
    """Consulta `nvidia-smi` (disponible en Linux/Windows con drivers NVIDIA)."""
    if not shutil.which("nvidia-smi"):
        return []
    query = (
        "index,name,utilization.gpu,memory.total,memory.used,memory.free,"
        "temperature.gpu,power.draw"
    )
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    gpus: List[GPUSnapshot] = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 8:
            continue
        try:
            idx, name, util, mem_total, mem_used, mem_free, temp, power = parts
            gpus.append(
                GPUSnapshot(
                    index=int(idx),
                    name=name,
                    vendor="nvidia",
                    utilization_pct=_safe_float(util),
                    memory_total_mb=_safe_float(mem_total),
                    memory_used_mb=_safe_float(mem_used),
                    memory_free_mb=_safe_float(mem_free),
                    temperature_c=_safe_float(temp),
                    power_watts=_safe_float(power),
                )
            )
        except ValueError:
            continue
    return gpus


def _collect_gpus_pynvml() -> List[GPUSnapshot]:
    """Usa NVML directamente cuando `pynvml`/`nvidia-ml-py` está disponible."""
    try:
        import pynvml
    except ImportError:
        return []
    try:
        pynvml.nvmlInit()
    except Exception:
        return []
    gpus: List[GPUSnapshot] = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="ignore")
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = None
            power = None
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                pass
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            except Exception:
                pass
            gpus.append(
                GPUSnapshot(
                    index=i,
                    name=name,
                    vendor="nvidia",
                    utilization_pct=float(util.gpu),
                    memory_total_mb=mem.total / (1024 ** 2),
                    memory_used_mb=mem.used / (1024 ** 2),
                    memory_free_mb=mem.free / (1024 ** 2),
                    temperature_c=temp,
                    power_watts=power,
                )
            )
    except Exception:
        return gpus
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return gpus


def _collect_gpus_apple() -> List[GPUSnapshot]:
    """Best-effort para Apple Silicon: reporta la GPU integrada sin métricas
    de utilización en tiempo real (macOS no expone esto sin privilegios
    elevados/`powermetrics`). Se marca `utilization_pct=None` para que el
    análisis de subutilización no la trate como inactiva por error."""
    if platform.system().lower() != "darwin":
        return []
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    import json as _json

    try:
        data = _json.loads(out.stdout)
    except ValueError:
        return []

    gpus: List[GPUSnapshot] = []
    for idx, item in enumerate(data.get("SPDisplaysDataType", [])):
        name = item.get("sppci_model") or item.get("_name") or f"GPU {idx}"
        gpus.append(GPUSnapshot(index=idx, name=name, vendor="apple"))
    return gpus


def _safe_float(value: str) -> Optional[float]:
    value = value.strip()
    if not value or value.upper() in ("N/A", "[NOT SUPPORTED]"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def collect_gpus() -> List[GPUSnapshot]:
    """Detecta GPUs disponibles probando, en orden, NVML, `nvidia-smi` y
    finalmente heurísticas específicas de plataforma (Apple Silicon)."""
    gpus = _collect_gpus_pynvml()
    if gpus:
        return gpus
    gpus = _collect_gpus_nvidia_smi()
    if gpus:
        return gpus
    return _collect_gpus_apple()


class ResourceMonitor:
    """Recolector con estado para calcular tasas de red entre muestras."""

    def __init__(self) -> None:
        self._prev_net = psutil.net_io_counters()
        self._prev_time = time.time()
        # Primera lectura de cpu_percent siempre es 0.0; se "calienta" aquí.
        psutil.cpu_percent(interval=None)

    def snapshot(self) -> ResourceSnapshot:
        now = time.time()
        cpu_percent = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(os_root_path())
        net = psutil.net_io_counters()

        elapsed = max(now - self._prev_time, 1e-6)
        sent_rate = max(0.0, (net.bytes_sent - self._prev_net.bytes_sent) / elapsed) * 8
        recv_rate = max(0.0, (net.bytes_recv - self._prev_net.bytes_recv) / elapsed) * 8
        self._prev_net = net
        self._prev_time = now

        return ResourceSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=cpu_percent,
            cpu_count_logical=psutil.cpu_count(logical=True) or 0,
            cpu_count_physical=psutil.cpu_count(logical=False) or 0,
            load_avg_1m=_load_avg_1m(),
            memory_total_mb=vm.total / (1024 ** 2),
            memory_used_mb=vm.used / (1024 ** 2),
            memory_available_mb=vm.available / (1024 ** 2),
            disk_total_gb=disk.total / (1024 ** 3),
            disk_used_gb=disk.used / (1024 ** 3),
            disk_free_gb=disk.free / (1024 ** 3),
            net_bytes_sent=net.bytes_sent,
            net_bytes_recv=net.bytes_recv,
            net_sent_rate_bps=sent_rate,
            net_recv_rate_bps=recv_rate,
            gpus=collect_gpus(),
        )


def os_root_path() -> str:
    return "C:\\" if platform.system().lower().startswith("windows") else "/"
