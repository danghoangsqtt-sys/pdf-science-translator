from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import MappingProxyType

from scripts.translate_pdf import Translation
from webui.backend.services import job_service

HAS_WEB_DEPS = all(importlib.util.find_spec(name) for name in ("fastapi", "httpx", "multipart"))
_TEMP_DATA = tempfile.TemporaryDirectory()
os.environ.setdefault("PDFTRANSLATE_DATA_DIR", _TEMP_DATA.name)

if HAS_WEB_DEPS:
    from fastapi.testclient import TestClient
    from webui.backend import main as backend


class JobOutcomeTests(unittest.TestCase):
    def test_partial_result_reports_ratio_reasons_and_scan_pages(self):
        result = Translation(
            Path("result.pdf"),
            3,
            MappingProxyType(Counter({"FormulaPlaceholderError": 3})),
            image_only_pages=(1,),
            total_segments=10,
        )
        job = job_service.TranslationJob(
            "id", "paper.pdf", Path("in.pdf"), Path("out"), "vi"
        )
        job.record(result)

        body = job.to_dict()
        self.assertEqual(body["translated_ratio"], 0.7)
        self.assertEqual(body["segments"]["translated"], 7)
        self.assertEqual(body["segments"]["kept"]["formula"], 3)
        self.assertTrue(body["warnings"])
        self.assertEqual(job_service.finished_status(result), "complete")

    def test_mostly_untranslated_result_has_warning_status(self):
        result = Translation(
            Path("result.pdf"),
            6,
            MappingProxyType(Counter({"ConnectionError": 6})),
            total_segments=10,
        )
        self.assertEqual(job_service.finished_status(result), "complete_with_warnings")


@unittest.skipUnless(HAS_WEB_DEPS, "web backend dependencies are unavailable")
class CorsTests(unittest.TestCase):
    def test_packaged_file_origin_is_allowed_but_token_is_still_required(self):
        with TestClient(backend.app) as client:
            preflight = client.options(
                "/api/jobs/missing",
                headers={
                    "Origin": "null",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "X-PDFTranslate-Token",
                },
            )
            self.assertEqual(preflight.status_code, 200)
            self.assertEqual(preflight.headers["access-control-allow-origin"], "null")

            unauthorized = client.get("/api/jobs/missing", headers={"Origin": "null"})
            self.assertEqual(unauthorized.status_code, 401)
            self.assertEqual(unauthorized.headers["access-control-allow-origin"], "null")

            wrong_token = client.get(
                "/api/jobs/missing",
                headers={"Origin": "null", "X-PDFTranslate-Token": "wrong"},
            )
            self.assertEqual(wrong_token.status_code, 401)

            valid_token = client.get(
                "/api/jobs/missing",
                headers={"Origin": "null", "X-PDFTranslate-Token": "dev-token"},
            )
            self.assertEqual(valid_token.status_code, 404)

            rejected = client.options(
                "/api/jobs/missing",
                headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"},
            )
            self.assertNotEqual(rejected.headers.get("access-control-allow-origin"), "https://example.com")


if __name__ == "__main__":
    unittest.main()