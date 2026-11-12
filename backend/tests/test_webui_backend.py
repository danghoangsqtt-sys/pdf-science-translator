from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from scripts.translate_pdf import Translation, TranslationCancelled, TranslationError

HAS_FASTAPI = all(
    importlib.util.find_spec(name) for name in ("fastapi", "httpx", "multipart")
)
DATA_DIR = tempfile.TemporaryDirectory()

if HAS_FASTAPI:
    os.environ.setdefault("PDFTRANSLATE_DATA_DIR", DATA_DIR.name)
    os.environ.setdefault("PDFTRANSLATE_API_TOKEN", "test-session-token")
    from fastapi.testclient import TestClient

    from server import main as backend
    from server.services import offline_service, job_service
    from pdf2zh.offline import profile_for

TOKEN = {"X-PDFTranslate-Token": backend.API_TOKEN} if HAS_FASTAPI else {}
PDF = b"%PDF-1.7\n%test\n"


def _translation(path: Path | None, total: int, reasons: dict[str, int], **extra) -> Translation:
    return Translation(
        path,
        sum(reasons.values()),
        MappingProxyType(Counter(reasons)),
        total_segments=total,
        engine="ollama",
        model="translategemma:12b",
        **extra,
    )


@unittest.skipUnless(HAS_FASTAPI, "webui backend dependencies are not installed")
class JobOutcomeTests(unittest.TestCase):
    def test_mostly_untranslated_output_is_complete_with_warnings(self):
        result = _translation(Path("x.pdf"), 10, {"TranslationServiceUnavailable": 6})
        self.assertEqual(job_service.finished_status(result), "complete_with_warnings")

    def test_a_partial_result_above_half_is_complete_but_still_warned(self):
        result = _translation(Path("x.pdf"), 10, {"FormulaPlaceholderError": 3})
        self.assertEqual(job_service.finished_status(result), "complete")
        warnings = job_service.translation_warnings(result)
        self.assertEqual(len(warnings), 1)
        self.assertIn("3 đoạn", warnings[0])
        self.assertIn("công thức", warnings[0])

    def test_each_reason_gets_its_own_vietnamese_line(self):
        result = _translation(
            Path("x.pdf"),
            40,
            {
                "TranslationServiceUnavailable": 2,
                "FormulaPlaceholderError": 1,
                "single line needs less than 50% font size": 1,
                "SegmentTooLongError": 1,
            },
            image_only_pages=(2, 6),
            service_failure="Không kết nối được Ollama tại http://127.0.0.1:11434.",
        )
        warnings = job_service.translation_warnings(result)
        self.assertEqual(len(warnings), 6)
        self.assertTrue(warnings[0].startswith("Bộ xử lý cục bộ"))
        self.assertIn("Trang 3, 7 là ảnh quét", warnings[-1])


@unittest.skipUnless(HAS_FASTAPI, "webui backend dependencies are not installed")
class SessionTokenTests(unittest.TestCase):
    def test_a_backend_without_a_token_does_not_accept_the_dev_token(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            first, second = backend.session_token(), backend.session_token()
        self.assertNotEqual(first, backend.DEV_TOKEN)
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 32)

    def test_the_dev_token_needs_an_explicit_opt_in(self):
        with mock.patch.dict(os.environ, {"PDFTRANSLATE_DEV": "1"}, clear=True):
            self.assertEqual(backend.session_token(), backend.DEV_TOKEN)
        with mock.patch.dict(os.environ, {"PDFTRANSLATE_API_TOKEN": "abc", "PDFTRANSLATE_DEV": "1"}, clear=True):
            self.assertEqual(backend.session_token(), "abc")


@unittest.skipUnless(HAS_FASTAPI, "webui backend dependencies are not installed")
class LeftoverCleanupTests(unittest.TestCase):
    def test_startup_empties_only_the_given_folders(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            uploads, outputs, keep = root / "uploads", root / "outputs", root / "keep.txt"
            (outputs / "old-job").mkdir(parents=True)
            (outputs / "old-job" / "paper-vi.pdf").write_bytes(PDF)
            uploads.mkdir()
            (uploads / "old-job.pdf").write_bytes(PDF)
            keep.write_text("user file")

            job_service.remove_leftovers(uploads, outputs, root / "missing")

            self.assertEqual(list(uploads.iterdir()), [])
            self.assertEqual(list(outputs.iterdir()), [])
            self.assertTrue(keep.exists())


@unittest.skipUnless(HAS_FASTAPI, "webui backend dependencies are not installed")
class BackendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # One client for the class: the job queue belongs to the event loop
        # the app started on, as it does in the real single-loop server.
        for patcher in (
            mock.patch.object(offline_service, 'require_profile', side_effect=profile_for),
            mock.patch.object(job_service, 'require_profile', side_effect=profile_for),
            mock.patch.object(offline_service.runtime, 'require', return_value=mock.Mock()),
        ):
            patcher.start()
            cls.addClassCleanup(patcher.stop)
        cls.client = TestClient(backend.app)
        cls.client.__enter__()
        cls.addClassCleanup(cls.client.__exit__, None, None, None)

    def test_packaged_file_origin_is_allowed_but_public_schema_is_disabled(self):
        response = self.client.options('/api/capabilities', headers={
            'Origin': 'null', 'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'X-PDFTranslate-Token',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], 'null')
        self.assertEqual(self.client.get('/api/capabilities', headers={'Origin': 'null'}).status_code, 401)
        for route in ('/docs', '/redoc', '/openapi.json'):
            self.assertEqual(self.client.get(route).status_code, 404)

    def _submit(self, **form) -> str:
        response = self.client.post(
            "/api/jobs",
            headers=TOKEN,
            files={"file": ("paper.pdf", PDF, "application/pdf")},
            data=form,
        )
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()["job_id"]

    def _wait(self, job_id: str, until=("complete", "complete_with_warnings", "error", "cancelled")):
        for _ in range(200):
            body = self.client.get(f"/api/jobs/{job_id}", headers=TOKEN).json()
            if body["status"] in until:
                return body
            time.sleep(0.02)
        self.fail(f"job {job_id} never finished: {body}")

    @staticmethod
    def _writes_output(total: int, reasons: dict[str, int]):
        def fake(input_pdf, output_dir, **kwargs):
            output = Path(output_dir) / "paper-vi.pdf"
            output.write_bytes(PDF)
            return _translation(output, total, reasons)

        return fake

    def test_status_reports_engine_ratio_and_warnings(self):
        fake = mock.Mock(side_effect=self._writes_output(10, {"FormulaPlaceholderError": 6}))
        with mock.patch.object(job_service, "translate_pdf", fake):
            job_id = self._submit(profile="fast")
            body = self._wait(job_id)

        self.assertEqual(body["status"], "complete_with_warnings")
        self.assertEqual(body["profile"], "fast")
        self.assertNotIn("model", body)
        self.assertNotIn("engine", body)
        self.assertEqual(body["translated_ratio"], 0.4)
        self.assertEqual(body["segments"]["kept"]["formula"], 6)
        self.assertTrue(body["warnings"])
        self.assertEqual(fake.call_args.kwargs["engine"], "ollama")
        self.assertEqual(fake.call_args.kwargs["model"], "local-fast:latest")
        self.assertEqual(fake.call_args.kwargs["ocr"], "standard")
        result = self.client.get(f"/api/jobs/{job_id}/result", headers=TOKEN)
        self.assertEqual(result.status_code, 200)

    def test_a_fully_translated_job_is_complete_without_warnings(self):
        fake = mock.Mock(side_effect=self._writes_output(10, {}))
        with mock.patch.object(job_service, "translate_pdf", fake):
            body = self._wait(self._submit())

        self.assertEqual(body["status"], "complete")
        self.assertEqual(body["translated_ratio"], 1.0)
        self.assertEqual(body["profile"], "balanced")
        self.assertEqual(body["warnings"], [])
        self.assertEqual(fake.call_args.kwargs["engine"], "ollama")

    def test_nothing_translated_is_an_error_with_the_reason(self):
        """The 26/10/2026 incident: Google blocked the IP, the app said done."""
        fake = mock.Mock(side_effect=TranslationError("Google đã tạm chặn máy này."))
        with mock.patch.object(job_service, "translate_pdf", fake):
            job_id = self._submit(profile="balanced")
            body = self._wait(job_id)

        self.assertEqual(body["status"], "error")
        self.assertNotIn("Google", body["error"])
        self.assertEqual(body["error_code"], "PROCESSING_FAILED")
        result = self.client.get(f"/api/jobs/{job_id}/result", headers=TOKEN)
        self.assertEqual(result.status_code, 409)

    def test_a_cancelled_job_reports_cancelled_and_has_no_result(self):
        def stopped(input_pdf, output_dir, cancel_event, **kwargs):
            self.assertTrue(cancel_event.wait(5))
            raise TranslationCancelled("Đã hủy tác vụ dịch.")

        with mock.patch.object(job_service, "translate_pdf", side_effect=stopped):
            job_id = self._submit()
            self._wait(job_id, until=("running",))
            cancelled = self.client.post(f"/api/jobs/{job_id}/cancel", headers=TOKEN)
            self.assertEqual(cancelled.status_code, 200)
            body = self._wait(job_id)

        self.assertEqual(body["status"], "cancelled")
        result = self.client.get(f"/api/jobs/{job_id}/result", headers=TOKEN)
        self.assertEqual(result.status_code, 409)

    def test_a_failure_after_translation_still_ends_the_job(self):
        """BUG-017: an error while reading the result left the job 'running'."""
        fake = mock.Mock(side_effect=self._writes_output(10, {}))
        with mock.patch.object(job_service, "translate_pdf", fake), \
                mock.patch.object(job_service.TranslationJob, "record",
                                  side_effect=KeyError("kept_by_reason")):
            body = self._wait(self._submit())

        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error_code"], "PROCESSING_FAILED")
        self.assertNotIn("kept_by_reason", body["error"])

    def test_the_upload_is_deleted_when_the_job_ends_but_the_result_stays(self):
        """BUG-014: every source PDF used to stay in the data folder forever."""
        fake = mock.Mock(side_effect=self._writes_output(10, {}))
        with mock.patch.object(job_service, "translate_pdf", fake):
            job_id = self._submit()
            self._wait(job_id)

        self.assertFalse((backend.UPLOADS_DIR / f"{job_id}.pdf").exists())
        result = self.client.get(f"/api/jobs/{job_id}/result", headers=TOKEN)
        self.assertEqual(result.status_code, 200)

    def test_only_the_newest_finished_jobs_are_kept(self):
        fake = mock.Mock(side_effect=self._writes_output(10, {}))
        with mock.patch.object(job_service, "translate_pdf", fake):
            jobs = []
            for _ in range(job_service.MAX_KEPT_JOBS + 1):
                jobs.append(self._submit())
                self._wait(jobs[-1])

        oldest, newest = jobs[0], jobs[-1]
        self.assertEqual(self.client.get(f"/api/jobs/{oldest}", headers=TOKEN).status_code, 404)
        self.assertFalse((backend.OUTPUTS_DIR / oldest).exists())
        self.assertEqual(
            self.client.get(f"/api/jobs/{newest}/result", headers=TOKEN).status_code, 200)

    def test_the_chosen_source_language_reaches_the_translator(self):
        fake = mock.Mock(side_effect=self._writes_output(10, {}))
        with mock.patch.object(job_service, "translate_pdf", fake):
            self._wait(self._submit(source_language="vi", target_language="en"))
            self._wait(self._submit())

        first, second = fake.call_args_list
        self.assertEqual(first.kwargs["source_language"], "vi")
        self.assertEqual(first.kwargs["target_language"], "en")
        self.assertEqual(second.kwargs["source_language"], "auto")

    def test_unsupported_or_identical_source_languages_are_refused(self):
        for form in ({"source_language": "zh"}, {"source_language": "../x"},
                     {"source_language": "vi", "target_language": "vi"}):
            with self.subTest(form=form):
                response = self.client.post(
                    "/api/jobs", headers=TOKEN,
                    files={"file": ("paper.pdf", PDF, "application/pdf")}, data=form)
                self.assertEqual(response.status_code, 400)

    def test_cancelling_an_unknown_job_is_not_found(self):
        response = self.client.post("/api/jobs/missing/cancel", headers=TOKEN)
        self.assertEqual(response.status_code, 404)

    def test_unknown_engines_and_models_are_refused(self):
        for form in (
            {"engine": "handoff"},
            {"engine": "bing"},
            {"engine": "google", "model": "translategemma:12b"},
            {"engine": "ollama", "model": "llama3:70b"},
        ):
            with self.subTest(form=form):
                response = self.client.post(
                    "/api/jobs",
                    headers=TOKEN,
                    files={"file": ("paper.pdf", PDF, "application/pdf")},
                    data=form,
                )
                self.assertEqual(response.status_code, 400)

    def test_capabilities_only_returns_public_profiles(self):
        response = self.client.get('/api/capabilities', headers=TOKEN)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['offline'])
        self.assertEqual([p['id'] for p in body['profiles']], ['fast','balanced','quality'])
        self.assertTrue(all(p['available'] for p in body['profiles']))
        for forbidden in ('ollama','translategemma','qwen','pull_command','base_url'):
            self.assertNotIn(forbidden, response.text.lower())

    def test_missing_data_is_neutral_and_not_downloaded(self):
        from pdf2zh.offline import OfflineError
        with mock.patch.object(offline_service.runtime, 'require', side_effect=OfflineError('LOCAL_DATA_MISSING')):
            body = self.client.get('/api/capabilities', headers=TOKEN).json()
        self.assertTrue(all(not p['available'] for p in body['profiles']))
        self.assertTrue(all(p['reason_code']=='LOCAL_DATA_MISSING' for p in body['profiles']))

    def test_old_engine_route_does_not_disclose_identity(self):
        response = self.client.get('/api/engines', headers=TOKEN)
        self.assertEqual(response.status_code, 410)
        self.assertNotIn('ollama', response.text.lower())

    def test_arbitrary_profile_is_rejected(self):
        response = self.client.post('/api/jobs', headers=TOKEN,
            files={'file':('paper.pdf',PDF,'application/pdf')}, data={'profile':'PRIVATE_MODEL'})
        self.assertIn(response.status_code, (400,503))
        self.assertNotIn('PRIVATE_MODEL', response.text)

    def test_other_local_pages_get_no_cors_access(self):
        """BUG-015: any localhost port used to be an allowed origin."""
        for origin in ("http://localhost:3000", "http://127.0.0.1:8089", "https://example.com"):
            with self.subTest(origin=origin):
                response = self.client.options('/api/capabilities', headers={
                    'Origin': origin, 'Access-Control-Request-Method': 'GET',
                    'Access-Control-Request-Headers': 'X-PDFTranslate-Token',
                })
                self.assertNotIn('access-control-allow-origin', response.headers)

    def test_the_public_dev_token_is_refused(self):
        self.assertNotEqual(backend.API_TOKEN, backend.DEV_TOKEN)
        response = self.client.get('/api/capabilities', headers={'X-PDFTranslate-Token': 'dev-token'})
        self.assertEqual(response.status_code, 401)

    def test_capabilities_needs_token(self):
        self.assertEqual(self.client.get('/api/capabilities').status_code,401)

    def test_engines_needs_the_api_token(self):
        self.assertEqual(self.client.get("/api/engines").status_code, 401)


if __name__ == "__main__":
    unittest.main()
