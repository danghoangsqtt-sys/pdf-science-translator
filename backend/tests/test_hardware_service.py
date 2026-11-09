from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from server.services import hardware_service as hardware


class HardwareServiceTests(unittest.TestCase):
    def test_nvidia_csv_parses_four_gib_and_multiple_devices(self) -> None:
        output = "NVIDIA RTX 3050, 4096, 3072, 555.99\nIntegrated, N/A, N/A, 1.0\n"
        devices = hardware._parse_nvidia_csv(output)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0].total_bytes, 4 * 1024**3)
        self.assertEqual(devices[0].free_bytes, 3 * 1024**3)
        self.assertIsNone(devices[1].total_bytes)

    def test_gpu_query_uses_fixed_argv_no_shell_and_three_second_timeout(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "GPU, 4096, 2048, 555.1\n", "")
        runner = mock.Mock(return_value=completed)
        devices, status = hardware._gpu_memory(runner, Path("C:/trusted/nvidia-smi.exe"))
        self.assertEqual(status, "ready")
        self.assertEqual(devices[0].free_bytes, 2 * 1024**3)
        kwargs = runner.call_args.kwargs
        self.assertEqual(kwargs["timeout"], 3)
        self.assertFalse(kwargs["shell"])
        self.assertEqual(runner.call_args.args[0][0], "C:\\trusted\\nvidia-smi.exe")

    def test_gpu_timeout_and_bad_rows_are_unknown(self) -> None:
        runner = mock.Mock(side_effect=subprocess.TimeoutExpired("gpu", 3))
        self.assertEqual(hardware._gpu_memory(runner, Path("C:/trusted/gpu.exe")), ((), "unknown"))
        self.assertEqual(hardware._parse_nvidia_csv("raw private failure"), ())

    def test_snapshot_keeps_unknown_separate_from_zero_and_caches_five_seconds(self) -> None:
        clock = mock.Mock(side_effect=[10.0, 12.0, 16.0])
        service = hardware.HardwareService(Path("C:/data"), ttl_seconds=5, clock=clock)
        with (mock.patch.object(hardware, "_windows_memory", return_value=(24 * 1024**3, 0, "ready")) as ram,
              mock.patch.object(hardware, "_gpu_memory", return_value=((), "unknown")) as gpu,
              mock.patch.object(hardware, "_disk", return_value=(None, None, "unknown")),
              mock.patch.object(hardware, "_cpu_name", return_value=None)):
            first = service.snapshot()
            second = service.snapshot()
            third = service.snapshot()
        self.assertIs(first, second)
        self.assertIsNot(second, third)
        self.assertEqual(ram.call_count, 2)
        self.assertEqual(gpu.call_count, 2)
        self.assertEqual(first.ram_available_bytes, 0)
        self.assertEqual(first.sources["gpu"], "unknown")
        self.assertEqual(first.gpus, ())

    def test_public_snapshot_has_no_identifier_or_private_path(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            service = hardware.HardwareService(Path(folder))
            gpu = hardware.GpuMemory("RTX 3050", 4 * 1024**3, 3 * 1024**3, "555.1")
            with (mock.patch.object(hardware, "_windows_memory", return_value=(24, 12, "ready")),
                  mock.patch.object(hardware, "_gpu_memory", return_value=((gpu,), "ready")),
                  mock.patch.object(hardware, "_cpu_name", return_value="Core i7")):
                public = service.snapshot().public()
        text = str(public).lower()
        self.assertNotIn("uuid", text)
        self.assertNotIn("serial", text)
        self.assertNotIn(folder.lower(), text)
        self.assertEqual(public["memory"]["total_bytes"], 24)

    def test_async_snapshot_runs_without_blocking_call_site(self) -> None:
        service = mock.Mock(spec=hardware.HardwareService)
        expected = object()
        service.snapshot.return_value = expected
        result = asyncio.run(hardware.HardwareService.snapshot_async(service, True))
        self.assertIs(result, expected)
        service.snapshot.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
