import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh import offline


class VerifyCacheTests(unittest.TestCase):
    """A second launch must not re-hash unchanged data, but must notice changes."""

    def make_pack(self, root: Path) -> offline.OfflinePack:
        files = {}
        for name in ("a.bin", "b.bin"):
            content = name.encode() * 10
            (root / name).write_bytes(content)
            files[name] = {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        pack = offline.OfflinePack.__new__(offline.OfflinePack)
        pack.root = root.resolve()
        pack.data = {"files": files}
        pack.signatures = {}
        pack._trusted = {}
        (root / "manifest.json").write_text(json.dumps(pack.data))
        return pack

    def test_unchanged_files_are_not_hashed_again(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "cache" / "verified.json"
            pack = self.make_pack(root)
            pack._verify_files({"a.bin", "b.bin"})
            pack._save_cache(cache)

            again = self.make_pack(root)
            for name in ("a.bin", "b.bin"):  # keep the cached signatures valid
                st = (root / name).stat()
                os.utime(root / name, ns=(st.st_atime_ns, pack.signatures[name][1]))
            again._load_cache(cache)
            with mock.patch.object(offline, "sha256", wraps=offline.sha256) as hashed:
                again._verify_files({"a.bin", "b.bin"})
            self.assertFalse([c for c in hashed.call_args_list if c.args[0].name.endswith(".bin")])

    def test_modified_file_is_hashed_and_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "verified.json"
            pack = self.make_pack(root)
            pack._verify_files({"a.bin", "b.bin"})
            pack._save_cache(cache)
            original = pack.data
            path = root / "a.bin"
            path.write_bytes(b"X" * path.stat().st_size)  # same size, new content and mtime
            tampered = offline.OfflinePack.__new__(offline.OfflinePack)
            tampered.root, tampered.data, tampered.signatures, tampered._trusted = root.resolve(), original, {}, {}
            (root / "manifest.json").write_text(json.dumps(original))
            tampered._load_cache(cache)
            with self.assertRaises(offline.OfflineError):
                tampered._verify_files({"a.bin"})


if __name__ == "__main__":
    unittest.main()
