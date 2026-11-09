"""Read-only local hardware snapshot for offline capacity decisions."""
from __future__ import annotations

import asyncio
import ctypes
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time
from typing import Callable


@dataclass(frozen=True)
class GpuMemory:
    name: str | None
    total_bytes: int | None
    free_bytes: int | None
    driver: str | None


@dataclass(frozen=True)
class HardwareSnapshot:
    measured_at: float
    cpu_name: str | None
    architecture: str
    logical_processors: int | None
    ram_total_bytes: int | None
    ram_available_bytes: int | None
    gpus: tuple[GpuMemory, ...]
    disk_total_bytes: int | None
    disk_free_bytes: int | None
    sources: dict[str, str]

    def public(self) -> dict[str, object]:
        return {
            "measured_at": self.measured_at,
            "cpu": {
                "name": self.cpu_name,
                "architecture": self.architecture,
                "logical_processors": self.logical_processors,
            },
            "memory": {
                "total_bytes": self.ram_total_bytes,
                "available_bytes": self.ram_available_bytes,
            },
            "gpus": [asdict(gpu) for gpu in self.gpus],
            "disk": {"total_bytes": self.disk_total_bytes, "free_bytes": self.disk_free_bytes},
            "sources": dict(self.sources),
        }


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


def _windows_memory() -> tuple[int | None, int | None, str]:
    if os.name != "nt":
        return None, None, "unknown"
    status = _MemoryStatus()
    status.length = ctypes.sizeof(status)
    try:
        function = ctypes.windll.kernel32.GlobalMemoryStatusEx
        function.argtypes = [ctypes.POINTER(_MemoryStatus)]
        function.restype = ctypes.c_int
        if not function(ctypes.byref(status)):
            return None, None, "unknown"
        return int(status.total_physical), int(status.available_physical), "ready"
    except (AttributeError, OSError, ValueError):
        return None, None, "unknown"


def _cpu_name() -> str | None:
    name = platform.processor().strip()
    if name:
        return name[:160]
    if os.name != "nt":
        return None
    try:
        import winreg
        key_name = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name) as key:
            value = str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
            return value[:160] or None
    except (OSError, ValueError):
        return None


def _trusted_nvidia_smi() -> Path | None:
    candidates = (
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/nvidia-smi.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "NVIDIA Corporation/NVSMI/nvidia-smi.exe",
    )
    return next((path.resolve() for path in candidates if path.is_file()), None)


def _mib(value: str) -> int | None:
    try:
        amount = float(value.strip())
        return int(amount * 1024 * 1024) if amount >= 0 else None
    except ValueError:
        return None


def _parse_nvidia_csv(output: str) -> tuple[GpuMemory, ...]:
    devices: list[GpuMemory] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 4:
            continue
        name, total, free, driver = fields
        devices.append(GpuMemory(
            name=name[:120] or None,
            total_bytes=_mib(total),
            free_bytes=_mib(free),
            driver=driver[:40] or None,
        ))
    return tuple(devices)


def _gpu_memory(runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
                executable: Path | None = None) -> tuple[tuple[GpuMemory, ...], str]:
    binary = executable or _trusted_nvidia_smi()
    if binary is None:
        return (), "unknown"
    try:
        result = runner(
            [str(binary), "--query-gpu=name,memory.total,memory.free,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=3, check=False, shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return (), "unknown"
    devices = _parse_nvidia_csv(result.stdout) if result.returncode == 0 else ()
    return devices, "ready" if devices else "unknown"


def _disk(path: Path) -> tuple[int | None, int | None, str]:
    try:
        usage = shutil.disk_usage(path.resolve())
        return int(usage.total), int(usage.free), "ready"
    except OSError:
        return None, None, "unknown"


class HardwareService:
    def __init__(self, disk_path: Path, ttl_seconds: float = 5.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.disk_path = disk_path
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._lock = threading.Lock()
        self._snapshot: HardwareSnapshot | None = None
        self._cached_at = 0.0

    def snapshot(self, refresh: bool = False) -> HardwareSnapshot:
        now = self.clock()
        with self._lock:
            if (not refresh and self._snapshot is not None
                    and now - self._cached_at < self.ttl_seconds):
                return self._snapshot
            ram_total, ram_free, ram_status = _windows_memory()
            gpus, gpu_status = _gpu_memory()
            disk_total, disk_free, disk_status = _disk(self.disk_path)
            snapshot = HardwareSnapshot(
                measured_at=time.time(), cpu_name=_cpu_name(),
                architecture=platform.machine() or "unknown",
                logical_processors=os.cpu_count(),
                ram_total_bytes=ram_total, ram_available_bytes=ram_free,
                gpus=gpus, disk_total_bytes=disk_total, disk_free_bytes=disk_free,
                sources={"memory": ram_status, "gpu": gpu_status, "disk": disk_status},
            )
            self._snapshot = snapshot
            self._cached_at = now
            return snapshot

    async def snapshot_async(self, refresh: bool = False) -> HardwareSnapshot:
        return await asyncio.to_thread(self.snapshot, refresh)


hardware = HardwareService(Path(__file__).resolve().parents[2])
