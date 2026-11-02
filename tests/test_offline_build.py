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
