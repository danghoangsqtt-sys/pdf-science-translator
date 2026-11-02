"""Run unchanged tests with writable cache/temp and real bundled layout asset."""
from __future__ import annotations
import faulthandler
faulthandler.dump_traceback_later(45, repeat=True)
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

root = Path.cwd().resolve()
sys.path.insert(0, str(root))
audit_root = root / 'tmp' / 'audit-20261029-controlled'
audit_root.mkdir(parents=True, exist_ok=True)
temp_root = audit_root / 'temp'
temp_root.mkdir(exist_ok=True)
os.environ['TEMP'] = str(temp_root)
os.environ['TMP'] = str(temp_root)
tempfile.tempdir = str(temp_root)
os.environ.pop('PDF_TRANSLATE_MODEL', None)
with mock.patch('os.path.expanduser', return_value=str(audit_root)):
    cache = importlib.import_module('pdf2zh.cache')
print('AUDIT ROOT:', root, flush=True)
print('PYTHON:', sys.version.split()[0], flush=True)
print('CACHE:', cache.db.database, flush=True)
asset = root / 'app/assets/doclayout.onnx'
assert asset.is_file(), asset
with mock.patch('pdf2zh.doclayout.get_doclayout_onnx_model_path', return_value=str(asset)):
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=pattern) for pattern in sys.argv[1:]) if len(sys.argv) > 1 else unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)


