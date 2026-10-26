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
    from fastapi.testclient import TestClient

    from webui.backend import main as backend
    from webui.backend.services import engine_service, job_service

TOKEN = {"X-PDFTranslate-Token": "dev-token"}
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
        self.assertTrue(warnings[0].startswith("Không kết nối được Ollama"))
        self.assertIn("Trang 3, 7 là ảnh quét", warnings[-1])


@unittest.skipUnless(HAS_FASTAPI, "webui backend dependencies are not installed")
class BackendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # One client for the class: the job queue belongs to the event loop
        # the app started on, as it does in the real single-loop server.
        cls.client = TestClient(backend.app)
        cls.client.__enter__()
        cls.addClassCleanup(cls.client.__exit__, None, None, None)

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
            job_id = self._submit(engine="ollama", model="translategemma:4b")
            body = self._wait(job_id)

        self.assertEqual(body["status"], "complete_with_warnings")
        self.assertEqual(body["engine"], "ollama")
        self.assertEqual(body["translated_ratio"], 0.4)
        self.assertEqual(body["segments"]["kept"]["formula"], 6)
        self.assertTrue(body["warnings"])
        self.assertEqual(fake.call_args.kwargs["engine"], "ollama")
        self.assertEqual(fake.call_args.kwargs["model"], "translategemma:4b")
        result = self.client.get(f"/api/jobs/{job_id}/result", headers=TOKEN)
        self.assertEqual(result.status_code, 200)

    def test_a_fully_translated_job_is_complete_without_warnings(self):
        fake = mock.Mock(side_effect=self._writes_output(10, {}))
        with mock.patch.object(job_service, "translate_pdf", fake):
            body = self._wait(self._submit())

        self.assertEqual(body["status"], "complete")
        self.assertEqual(body["translated_ratio"], 1.0)
        self.assertEqual(body["warnings"], [])
        self.assertEqual(fake.call_args.kwargs["engine"], "ollama")

    def test_nothing_translated_is_an_error_with_the_reason(self):
        """The 26/10/2026 incident: Google blocked the IP, the app said done."""
        fake = mock.Mock(side_effect=TranslationError("Google đã tạm chặn máy này."))
        with mock.patch.object(job_service, "translate_pdf", fake):
            job_id = self._submit(engine="google")
            body = self._wait(job_id)

        self.assertEqual(body["status"], "error")
        self.assertIn("Google", body["error"])
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

    def test_engines_lists_choices_and_ollama_state(self):
        from pdf2zh.translator import OllamaStatus

        status = OllamaStatus(
            "model_missing", "http://127.0.0.1:11434", "translategemma:12b",
            ("translategemma:4b",), "chưa tải",
        )
        with mock.patch.object(engine_service, "ollama_status", return_value=status):
            body = self.client.get("/api/engines", headers=TOKEN).json()

        self.assertEqual(body["default"], "ollama")
        self.assertEqual(
            [engine["id"] for engine in body["engines"]], ["ollama", "google"]
        )
        self.assertEqual(body["ollama"]["state"], "model_missing")
        self.assertEqual(body["ollama"]["pull_command"], "ollama pull translategemma:12b")
        self.assertEqual(body["ollama"]["installed_models"], ["translategemma:4b"])

    def test_a_stopped_server_on_a_machine_without_ollama_says_install_it(self):
        from pdf2zh.translator import OllamaStatus

        status = OllamaStatus("not_running", "http://127.0.0.1:11434", "translategemma:12b")
        with (
            mock.patch.object(engine_service, "ollama_status", return_value=status),
            mock.patch.object(engine_service, "ollama_installed", return_value=False),
        ):
            body = self.client.get("/api/engines", headers=TOKEN).json()

        self.assertEqual(body["ollama"]["state"], "not_installed")
        self.assertIn("ollama.com/download", body["ollama"]["message"])

    def test_engines_needs_the_api_token(self):
        self.assertEqual(self.client.get("/api/engines").status_code, 401)


if __name__ == "__main__":
    unittest.main()
