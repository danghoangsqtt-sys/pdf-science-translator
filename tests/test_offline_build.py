from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import build_offline_windows as builder


class OfflineBuildTests(unittest.TestCase):
    def test_existing_build_is_preserved_before_pack_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            sentinel = target / "user.txt"
            sentinel.write_text("keep")
            with self.assertRaises(FileExistsError):
                builder.preflight(target, target / "missing-pack")
            self.assertEqual(sentinel.read_text(), "keep")

    def test_output_inside_pack_is_rejected_without_creating_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "new"
            with self.assertRaises(ValueError):
                builder.preflight(target, Path(folder))
            self.assertFalse(target.exists())

    def test_missing_notice_fails_before_any_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            required = ("webui/frontend/dist/index.html", "webui/frontend/dist-electron/main.cjs",
                        "webui/frontend/dist-electron/preload.mjs",
                        "webui/frontend/node_modules/electron/dist/electron.exe")
            for name in required:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            target = root / "output"
            with mock.patch.object(builder, "ROOT", root), mock.patch.object(builder, "OfflinePack") as pack:
                with self.assertRaisesRegex(FileNotFoundError, "LICENSE"):
                    builder.preflight(target, root / "data")
                pack.assert_not_called()
            self.assertFalse(target.exists())


class PreparePackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def write(self, relative: str, content: bytes = b"x") -> Path:
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def model(self, name: str, tag: str) -> None:
        import hashlib
        import json
        content = f"{name}:{tag}".encode()
        digest = hashlib.sha256(content).hexdigest()
        self.write(f"models/blobs/sha256-{digest}", content)
        self.write(f"models/manifests/registry.ollama.ai/library/{name}/{tag}",
                   json.dumps({"config": {"digest": f"sha256:{digest}"}, "layers": []}).encode())

    def test_lite_pack_carries_only_the_fast_model_and_verifies(self):
        from pdf2zh.offline import OfflinePack
        from scripts import prepare_offline_pack as prep

        for name in ("app/assets/doclayout.onnx", "app/assets/GoNotoKurrent-Regular.ttf",
                     "app/fonts/BeVietnamPro-Regular.ttf", "app/fonts/BeVietnamPro-OFL.txt"):
            self.write(f"repo/{name}", name.encode())
        worker = self.write("runtime/ollama.exe", b"worker")
        self.write("runtime/lib/cuda.dll", b"native")
        for name in ("det_small", "rec_small", "det_medium", "rec_medium"):
            self.write(f"ocr/PP-OCRv6_{name}.onnx", name.encode())
        self.write("ocr/ch_ppocr_mobile_v2.0_cls_mobile.onnx", b"cls")
        # Only the 4B model exists: a lite pack must not need the 12B or rescue models.
        self.model("translategemma", "4b")

        target = self.base / "pack"
        with mock.patch.object(prep, "ROOT", self.base / "repo"):
            prep.prepare(target, worker, self.base / "models", self.base / "ocr", edition="lite")

        pack = OfflinePack(target)
        pack.verify()
        self.assertEqual(pack.available_profiles, {"fast"})
        blobs = list((target / "models/blobs").iterdir())
        self.assertEqual(len(blobs), 1)

    def test_full_pack_refuses_to_start_without_the_large_models(self):
        from scripts import prepare_offline_pack as prep

        self.model("translategemma", "4b")
        with self.assertRaises(FileNotFoundError):
            prep.prepare(self.base / "pack", self.base / "worker.exe", self.base / "models",
                         self.base / "ocr", edition="full")
        self.assertFalse((self.base / "pack").exists())
