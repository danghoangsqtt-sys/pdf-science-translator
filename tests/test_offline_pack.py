from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh.offline import OfflineError, OfflinePack, PROFILES, sha256
from pdf2zh.resource_pack import REQUIRED_ASSETS


class ManifestV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add_file(self, relative: str, content: bytes) -> str:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return relative

    def build(self, profiles: tuple[str, ...] = ("fast",), edition: str = "lite") -> dict:
        common = self.add_file("runtime/common.bin", b"trusted local runtime and resources")
        files: dict[str, dict[str, int | str]] = {}
        profile_data: dict[str, dict[str, object]] = {}
        for ident in profiles:
            resources: list[str] = []
            aliases = [PROFILES[ident].model]
            if PROFILES[ident].fallback:
                aliases.append(PROFILES[ident].fallback)
            for alias in aliases:
                name, tag = alias.split(":", 1)
                blob_content = f"{ident}:{alias}".encode()
                digest = __import__("hashlib").sha256(blob_content).hexdigest()
                blob = self.add_file(f"models/blobs/sha256-{digest}", blob_content)
                manifest = self.add_file(
                    f"models/manifests/registry.ollama.ai/library/{name}/{tag}",
                    json.dumps({"config": {"digest": f"sha256:{digest}"}, "layers": []}).encode(),
                )
                resources.extend((blob, manifest))
            profile_data[ident] = {"model": PROFILES[ident].model, "files": resources}
        for path in self.root.rglob("*"):
            if path.is_file():
                relative = path.relative_to(self.root).as_posix()
                files[relative] = {"size": path.stat().st_size, "sha256": sha256(path)}
        manifest = {
            "version": 2,
            "edition": edition,
            "compatibility": {
                "platform": "windows", "architecture": "amd64", "runtime_revision": 1,
            },
            "assets": {name: common for name in REQUIRED_ASSETS},
            "native": [common],
            "common": [common],
            "profiles": profile_data,
            "files": files,
        }
        self.write(manifest)
        return manifest

    def write(self, manifest: dict) -> None:
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_lite_pack_runs_fast_without_large_profiles(self) -> None:
        self.build()
        pack = OfflinePack(self.root)
        pack.verify()
        self.assertEqual(pack.available_profiles, {"fast"})
        self.assertEqual(pack.require_profile("fast").label, "Nhanh")
        with self.assertRaises(OfflineError) as error:
            pack.require_profile("balanced")
        self.assertEqual(error.exception.code, "PROFILE_UNAVAILABLE")
        self.assertEqual(pack.installed_aliases(), {PROFILES["fast"].model})
        with mock.patch("webui.backend.services.offline_service.runtime.require", return_value=pack):
            from webui.backend.services.offline_service import capabilities, require_profile
            self.assertEqual(require_profile("fast").id, "fast")
            with self.assertRaises(OfflineError) as backend_error:
                require_profile("balanced")
            self.assertEqual(backend_error.exception.code, "PROFILE_UNAVAILABLE")
            public = capabilities()
            self.assertEqual(public["default_profile"], "fast")
            status = {item["id"]: item for item in public["profiles"]}
            self.assertTrue(status["fast"]["available"])
            self.assertFalse(status["balanced"]["available"])
            self.assertEqual(status["balanced"]["reason_code"], "PROFILE_UNAVAILABLE")
            self.assertNotIn("local-fast", json.dumps(public))

    def test_corrupt_profile_does_not_block_independent_profile(self) -> None:
        manifest = self.build(("fast", "balanced"), "full")
        broken = manifest["profiles"]["balanced"]["files"][0]
        (self.root / broken).write_bytes(b"corrupt")
        pack = OfflinePack(self.root)
        pack.verify()
        self.assertEqual(pack.available_profiles, {"fast"})
        self.assertEqual(pack.profile_errors, {"balanced": "LOCAL_DATA_INVALID"})

    def test_missing_common_resource_blocks_entire_pack(self) -> None:
        manifest = self.build()
        (self.root / manifest["common"][0]).unlink()
        with self.assertRaises(OfflineError) as error:
            OfflinePack(self.root).verify()
        self.assertEqual(error.exception.code, "LOCAL_DATA_MISSING")

    def test_quality_requires_rescue_dependency_closure(self) -> None:
        manifest = self.build(("quality",), "full")
        rescue = next(path for path in manifest["profiles"]["quality"]["files"]
                      if "local-rescue" in path)
        manifest["profiles"]["quality"]["files"].remove(rescue)
        self.write(manifest)
        with self.assertRaises(OfflineError) as error:
            OfflinePack(self.root).verify()
        self.assertEqual(error.exception.code, "LOCAL_DATA_INVALID")

    def test_traversal_and_wrong_runtime_revision_are_rejected_neutrally(self) -> None:
        manifest = self.build()
        entry = manifest["common"][0]
        manifest["common"] = ["../outside.bin"]
        manifest["files"]["../outside.bin"] = manifest["files"].pop(entry)
        self.write(manifest)
        with self.assertRaises(OfflineError) as traversal:
            OfflinePack(self.root)
        self.assertEqual(traversal.exception.code, "LOCAL_DATA_INVALID")
        self.assertNotIn("outside", str(traversal.exception))

        manifest = self.build()
        manifest["compatibility"]["runtime_revision"] = 999
        self.write(manifest)
        with self.assertRaises(OfflineError) as revision:
            OfflinePack(self.root)
        self.assertEqual(revision.exception.code, "LOCAL_DATA_INVALID")

    def test_unreferenced_self_hashed_native_file_is_rejected(self) -> None:
        manifest = self.build()
        canary = self.add_file("worker/replacement.exe", b"self declared binary")
        manifest["files"][canary] = {
            "size": (self.root / canary).stat().st_size, "sha256": sha256(self.root / canary),
        }
        self.write(manifest)
        with self.assertRaises(OfflineError) as error:
            OfflinePack(self.root)
        self.assertEqual(error.exception.code, "LOCAL_DATA_INVALID")

    def test_symlink_cannot_redirect_a_declared_resource(self) -> None:
        manifest = self.build()
        common = self.root / manifest["common"][0]
        outside = self.root.parent / f"{self.root.name}-outside.bin"
        outside.write_bytes(common.read_bytes())
        self.addCleanup(outside.unlink, missing_ok=True)
        common.unlink()
        try:
            os.symlink(outside, common)
        except OSError as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        with self.assertRaises(OfflineError) as result:
            OfflinePack(self.root).verify()
        self.assertEqual(result.exception.code, "LOCAL_DATA_INVALID")


if __name__ == "__main__":
    unittest.main()
