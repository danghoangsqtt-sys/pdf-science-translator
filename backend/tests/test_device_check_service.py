from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from pdf2zh.offline import PROFILES
from pdf2zh.runtime_policy import GIB
from server.services.device_check_service import DeviceCheckService
from server.services.hardware_service import GpuMemory, HardwareSnapshot


class _Pack:
    def __init__(self, profiles: set[str]) -> None:
        self.profiles = profiles

    def require_profile(self, profile: str):
        if profile not in self.profiles:
            from pdf2zh.offline import OfflineError
            raise OfflineError("PROFILE_UNAVAILABLE")
        return PROFILES[profile]


class _Runtime:
    def __init__(self, profiles: set[str]) -> None:
        self.pack = _Pack(profiles)

    def require(self) -> _Pack:
        return self.pack


class _Hardware:
    def __init__(self, vram: int = 12 * GIB) -> None:
        self.vram = vram

    async def snapshot_async(self, refresh: bool = False) -> HardwareSnapshot:
        return HardwareSnapshot(
            1.0, "CPU", "AMD64", 20, 24 * GIB, 12 * GIB,
            (GpuMemory("GPU", self.vram, self.vram - GIB, "1"),),
            100 * GIB, 50 * GIB, {"memory": "ready", "gpu": "ready", "disk": "ready"},
        )


class DeviceCheckServiceTests(unittest.IsolatedAsyncioTestCase):
    async def wait(self, service: DeviceCheckService, check_id: str) -> None:
        await service._tasks[check_id]

    async def test_fast_probe_becomes_ready_and_is_anonymous_publicly(self) -> None:
        calls = []

        async def probe(alias, policy):
            calls.append((alias, policy))
            return True

        service = DeviceCheckService(_Runtime({"fast"}), _Hardware(4 * GIB), probe=probe)
        check = service.start("fast")
        await self.wait(service, check.check_id)
        result = service.get("fast")
        self.assertEqual(result.status, "ready")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("local-fast", str(result.public()))

    async def test_quality_probes_primary_and_rescue_sequentially(self) -> None:
        aliases = []

        async def probe(alias, policy):
            aliases.append(alias)
            return True

        service = DeviceCheckService(_Runtime({"quality"}), _Hardware(), probe=probe)
        check = service.start("quality")
        await self.wait(service, check.check_id)
        self.assertEqual(aliases, [PROFILES["quality"].model, PROFILES["quality"].fallback])
        self.assertEqual(service.get("quality").status, "ready")

    async def test_failed_probe_tries_no_more_than_two_policies(self) -> None:
        calls = 0

        async def probe(alias, policy):
            nonlocal calls
            calls += 1
            return False

        service = DeviceCheckService(_Runtime({"fast"}), _Hardware(), probe=probe)
        check = service.start("fast")
        await self.wait(service, check.check_id)
        self.assertEqual(calls, 2)
        self.assertEqual(service.get("fast").reason_code, "PROFILE_UNAVAILABLE")

    async def test_concurrent_same_profile_is_deduplicated(self) -> None:
        release = asyncio.Event()

        async def probe(alias, policy):
            await release.wait()
            return True

        service = DeviceCheckService(_Runtime({"fast"}), _Hardware(), probe=probe)
        first = service.start("fast")
        await asyncio.sleep(0)
        second = service.start("fast")
        self.assertEqual(first.check_id, second.check_id)
        release.set()
        await self.wait(service, first.check_id)

    async def test_busy_worker_does_not_probe(self) -> None:
        probe = mock.AsyncMock(return_value=True)
        service = DeviceCheckService(_Runtime({"fast"}), _Hardware(), idle=lambda: False, probe=probe)
        check = service.start("fast")
        await self.wait(service, check.check_id)
        self.assertEqual(service.get("fast").reason_code, "LOCAL_BUSY")
        probe.assert_not_awaited()

    async def test_cancel_only_stops_owned_check_task(self) -> None:
        async def probe(alias, policy):
            await asyncio.Event().wait()
            return True

        service = DeviceCheckService(_Runtime({"fast"}), _Hardware(), probe=probe)
        check = service.start("fast")
        await asyncio.sleep(0)
        self.assertTrue(service.cancel(check.check_id))
        await self.wait(service, check.check_id)
        self.assertEqual(service.get("fast").status, "cancelled")

    async def test_probe_timeout_has_neutral_bounded_reason(self) -> None:
        async def probe(alias, policy):
            raise asyncio.TimeoutError

        service = DeviceCheckService(_Runtime({"fast"}), _Hardware(), probe=probe)
        check = service.start("fast")
        await self.wait(service, check.check_id)
        result = service.get("fast")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "LOCAL_CHECK_TIMEOUT")
        self.assertNotIn("local-fast", str(result.public()))


if __name__ == "__main__":
    unittest.main()
