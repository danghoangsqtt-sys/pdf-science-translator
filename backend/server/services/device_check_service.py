"""Bounded background proof that a local profile can run on this machine."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import uuid
from typing import Awaitable, Callable

from pdf2zh.offline import OfflineError, PROFILES
from pdf2zh.runtime_policy import EffectivePolicy, ResourceSnapshot, candidate_policies
from server.services.hardware_service import HardwareService, hardware
from server.services.runtime_service import LocalRuntime, runtime

Probe = Callable[[str, EffectivePolicy], Awaitable[bool]]


@dataclass(frozen=True)
class DeviceCheck:
    check_id: str
    profile: str
    status: str
    reason_code: str | None = None
    policy: EffectivePolicy | None = None

    def public(self) -> dict[str, object]:
        return {
            "check_id": self.check_id, "profile": self.profile, "status": self.status,
            "reason_code": self.reason_code,
            "policy_revision": self.policy.revision if self.policy else None,
        }


class DeviceCheckService:
    def __init__(self, runtime_service: LocalRuntime, hardware_service: HardwareService,
                 idle: Callable[[], bool] = lambda: True,
                 probe: Probe | None = None) -> None:
        self.runtime = runtime_service
        self.hardware = hardware_service
        self.idle = idle
        self.probe = probe or self._probe_owned_runtime
        self._states: dict[str, DeviceCheck] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._worker_lock = asyncio.Lock()

    async def _probe_owned_runtime(self, alias: str, policy: EffectivePolicy) -> bool:
        return await asyncio.to_thread(self.runtime.probe, alias, policy, 60)

    def get(self, profile: str) -> DeviceCheck | None:
        return self._states.get(profile)

    def start(self, profile: str) -> DeviceCheck:
        if profile not in PROFILES:
            raise OfflineError("PROFILE_UNAVAILABLE")
        current = self._states.get(profile)
        if current is not None and current.status in ("queued", "checking"):
            return current
        check = DeviceCheck(uuid.uuid4().hex, profile, "queued")
        self._states[profile] = check
        self._tasks[check.check_id] = asyncio.create_task(self._run(check))
        return check

    def cancel(self, check_id: str) -> bool:
        task = self._tasks.get(check_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def _run(self, check: DeviceCheck) -> None:
        try:
            async with self._worker_lock:
                if not self.idle():
                    self._states[check.profile] = DeviceCheck(
                        check.check_id, check.profile, "unavailable", "LOCAL_BUSY"
                    )
                    return
                self._states[check.profile] = DeviceCheck(check.check_id, check.profile, "checking")
                pack = await asyncio.to_thread(self.runtime.require)
                pack.require_profile(check.profile)
                measured = await self.hardware.snapshot_async(refresh=True)
                view = ResourceSnapshot(
                    measured.ram_total_bytes, measured.ram_available_bytes,
                    max((gpu.total_bytes for gpu in measured.gpus if gpu.total_bytes is not None),
                        default=None),
                    max((gpu.free_bytes for gpu in measured.gpus if gpu.free_bytes is not None),
                        default=None),
                    measured.logical_processors,
                )
                revision = os.environ.get("PDF_TRANSLATE_DATA_REVISION", "unknown")
                policies = candidate_policies(check.profile, view, revision)
                if not policies:
                    raise OfflineError("PROFILE_UNAVAILABLE")
                aliases = [PROFILES[check.profile].model]
                if PROFILES[check.profile].fallback:
                    aliases.append(PROFILES[check.profile].fallback)
                last_reason = "PROFILE_UNAVAILABLE"
                for policy in policies[:2]:
                    try:
                        for alias in aliases:
                            if not await asyncio.wait_for(self.probe(alias, policy), timeout=60):
                                raise OfflineError("PROFILE_UNAVAILABLE")
                        self._states[check.profile] = DeviceCheck(
                            check.check_id, check.profile, "ready", policy=policy
                        )
                        return
                    except asyncio.TimeoutError:
                        last_reason = "LOCAL_CHECK_TIMEOUT"
                        continue
                    except OfflineError as error:
                        last_reason = error.code
                        continue
                raise OfflineError(last_reason)
        except asyncio.CancelledError:
            self._states[check.profile] = DeviceCheck(
                check.check_id, check.profile, "cancelled", "LOCAL_CHECK_CANCELLED"
            )
        except OfflineError as error:
            self._states[check.profile] = DeviceCheck(
                check.check_id, check.profile, "unavailable", error.code
            )
        except Exception:
            self._states[check.profile] = DeviceCheck(
                check.check_id, check.profile, "unavailable", "LOCAL_RUNTIME_UNAVAILABLE"
            )


checks = DeviceCheckService(runtime, hardware)
