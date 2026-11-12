from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh.offline import OfflineError, OfflinePack, PROFILES, enforce_engine, profile_for, sha256
from pdf2zh.translator import OllamaTranslator
from server.services.offline_service import public_failure


class OfflinePolicyTests(unittest.TestCase):
    def test_no_internet_or_dns_but_loopback_still_connects(self):
        code = '''
from pdf2zh.offline import install_network_guard, OfflineError
import socket
install_network_guard()
for host in ('example.com','8.8.8.8','192.168.1.2','::ffff:8.8.8.8'):
    try: socket.getaddrinfo(host,443)
    except OfflineError: pass
    else: raise AssertionError('DNS escaped')
    try:
        with socket.socket() as s: s.connect((host,443))
    except OfflineError: pass
    else: raise AssertionError('TCP escaped')
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    try: s.sendto(b'x',('8.8.8.8',53))
    except OfflineError: pass
    else: raise AssertionError('UDP escaped')
with socket.socket() as s:
    s.bind(('127.0.0.1',0));s.listen()
    with socket.create_connection(s.getsockname(),timeout=2): pass
'''
        subprocess.run([sys.executable, "-c", code], check=True, timeout=15)

    def test_cloud_engines_and_arbitrary_model_are_rejected(self):
        with mock.patch.dict(os.environ, {"PDF_TRANSLATE_OFFLINE": "1"}):
            for engine, model in (("azure", None), ("google", None), ("handoff", None),
                                  ("ollama", "anything:cloud")):
                with self.subTest(engine=engine), self.assertRaises(OfflineError):
                    enforce_engine(engine, model)
            enforce_engine("ollama", PROFILES["fast"].model)

    def test_profiles_have_different_budgets_but_same_safety_guards(self):
        instances = []
        for ident in PROFILES:
            with mock.patch.dict(os.environ, {"PDF_TRANSLATE_OFFLINE": "1",
                                              "PDF_TRANSLATE_PROCESSING_PROFILE": ident}):
                translator = OllamaTranslator("en", "vi", PROFILES[ident].model)
                instances.append(translator)
                self.assertFalse(translator.session.trust_env)
                self.assertEqual(translator.cache_revision_params()["profile"], ident)
        self.assertEqual([t.ATTEMPTS for t in instances], [1, 2, 3])
        self.assertEqual([len(t.RESCUE_ATTEMPTS) for t in instances], [0, 1, 3])
        self.assertEqual([t.fallback_model for t in instances], [None, None, "local-rescue:latest"])
        with self.assertRaises(OfflineError):
            profile_for("<private-model>")

    def test_public_errors_do_not_reflect_raw_engine_or_path(self):
        code, message = public_failure(RuntimeError("private-engine C:/secret/weights.bin"))
        self.assertEqual(code, "PROCESSING_FAILED")
        self.assertNotIn("private-engine", message)
        self.assertNotIn("weights", message)

    def test_cache_is_invalidated_when_local_data_pack_changes(self):
        keys = []
        for revision in ("pack-before", "pack-after"):
            with mock.patch.dict(os.environ, {"PDF_TRANSLATE_OFFLINE": "1",
                                              "PDF_TRANSLATE_DATA_REVISION": revision}):
                translator = OllamaTranslator("en", "vi", PROFILES["balanced"].model)
                keys.append(translator.cache.translate_engine_params)
        self.assertNotEqual(*keys)

    def test_packaged_ocr_sidecar_uses_the_verified_font_when_legacy_path_is_missing(self):
        import pymupdf
        from pdf2zh.ocr import OcrLine, _insert_sidecar_lines
        font = Path(__file__).resolve().parents[1] / "app/fonts/BeVietnamPro-Regular.ttf"
        with pymupdf.open() as doc, mock.patch.dict(os.environ, {"PDF_TRANSLATE_OCR_FONT": str(font)}), \
                mock.patch("pdf2zh.ocr.OCR_FONT_PATH", Path("missing-install-font.ttf")):
            page = doc.new_page(width=400, height=200)
            line = OcrLine("Offline source text", ((20, 30), (280, 30), (280, 60), (20, 60)), .99)
            self.assertEqual(_insert_sidecar_lines(page, [line], 1), 1)
            self.assertIn("Offline source text", page.get_text())
            self.assertEqual(tuple(page.rect), (0, 0, 400, 200))


class OfflinePackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        data = self.root / "asset.bin"
        data.write_bytes(b"local test asset")
        names = ["layout", "font", "ocr_font", "worker", "ocr_det_small", "ocr_rec_small",
                 "ocr_det_medium", "ocr_rec_medium", "ocr_cls"]
        self.manifest = {
            "version": 1, "files": {"asset.bin": {"size": data.stat().st_size,
                                                    "sha256": sha256(data)}},
            "assets": {key: "asset.bin" for key in names},
            "profiles": {ident: p.model for ident, p in PROFILES.items()},
        }
        digest = sha256(data)
        relative = f"models/blobs/sha256-{digest}"
        blob = self.root / relative
        blob.parent.mkdir(parents=True)
        blob.write_bytes(data.read_bytes())
        self.manifest["files"][relative] = {"size": blob.stat().st_size, "sha256": digest}
        for name in ("local-fast", "local-balanced", "local-quality", "local-rescue"):
            relative = f"models/manifests/registry.ollama.ai/library/{name}/latest"
            path = self.root / relative
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"config": {"digest": f"sha256:{digest}"}, "layers": []}), encoding="utf-8")
            self.manifest["files"][relative] = {"size": path.stat().st_size, "sha256": sha256(path)}
        self.write()

    def write(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_validated_pack_detects_later_changes(self):
        pack = OfflinePack(self.root)
        pack.verify()
        pack.unchanged()
        (self.root / "asset.bin").write_bytes(b"tampered")
        with self.assertRaises(OfflineError):
            pack.unchanged()

    def test_removed_file_returns_neutral_data_error_after_ready(self):
        pack = OfflinePack(self.root)
        pack.verify()
        (self.root / "asset.bin").unlink()
        with self.assertRaises(OfflineError) as result:
            pack.unchanged()
        self.assertEqual(result.exception.code, "LOCAL_DATA_MISSING")

    def test_hash_mismatch_and_missing_asset_fail_closed(self):
        self.manifest["files"]["asset.bin"]["sha256"] = "0" * 64
        self.write()
        with self.assertRaises(OfflineError):
            OfflinePack(self.root).verify()
        (self.root / "asset.bin").unlink()
        with self.assertRaises(OfflineError):
            OfflinePack(self.root).verify()

    def test_ocr_sidecar_font_is_required_before_accepting_jobs(self):
        del self.manifest["assets"]["ocr_font"]
        self.write()
        with self.assertRaises(OfflineError):
            OfflinePack(self.root).verify()

    def test_manifest_cannot_escape_pack(self):
        pack = OfflinePack(self.root)
        with self.assertRaises(OfflineError):
            pack.path("../manifest.json")
        with self.assertRaises(OfflineError):
            pack.path(str(self.root / "asset.bin"))

    def test_profile_mapping_cannot_introduce_cloud_identity(self):
        self.manifest["profiles"]["fast"] = "arbitrary:cloud"
        self.write()
        with self.assertRaises(OfflineError):
            OfflinePack(self.root).verify()

    def test_missing_rescue_or_blob_is_rejected_before_any_job(self):
        for relative in ("models/manifests/registry.ollama.ai/library/local-rescue/latest",
                         next(key for key in self.manifest["files"] if key.startswith("models/blobs/"))):
            with self.subTest(relative=relative):
                entry = self.manifest["files"].pop(relative)
                self.write()
                with self.assertRaises(OfflineError):
                    OfflinePack(self.root).verify()
                self.manifest["files"][relative] = entry
