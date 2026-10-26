from __future__ import annotations

import os
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pymupdf
import requests

from pdf2zh import translator as translator_module
from pdf2zh.translator import (
    ENGINES,
    FormulaPlaceholderError,
    OllamaTranslator,
    SegmentTooLongError,
    TranslationServiceUnavailable,
    encode_formula_placeholders,
    ollama_base_url,
    ollama_status,
    restore_formula_placeholders,
)

FONT_PATH = Path(__file__).resolve().parents[1] / "app" / "fonts" / "BeVietnamPro-Regular.ttf"


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: object = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _reply(translation: str) -> FakeResponse:
    return FakeResponse(200, {"response": translation, "done": True})


class EmptyLayoutModel:
    def predict(self, _image: np.ndarray, imgsz: int) -> list[SimpleNamespace]:
        return [SimpleNamespace(boxes=[], names={})]


class OllamaSettingsTests(unittest.TestCase):
    def test_the_server_address_accepts_what_ollama_itself_reads(self):
        cases = {
            "127.0.0.1:11434": "http://127.0.0.1:11434",
            "0.0.0.0": "http://127.0.0.1:11434",
            "http://gpu-box:8080/": "http://gpu-box:8080",
        }
        for value, expected in cases.items():
            with self.subTest(value=value), mock.patch.dict(
                os.environ, {"OLLAMA_HOST": value}, clear=False
            ):
                os.environ.pop("PDF_TRANSLATE_OLLAMA_URL", None)
                self.assertEqual(ollama_base_url(), expected)

    def test_ollama_is_a_registered_engine(self):
        self.assertIs(ENGINES["ollama"], OllamaTranslator)


class OllamaStatusTests(unittest.TestCase):
    def test_a_server_that_does_not_answer_is_reported_as_not_running(self):
        with mock.patch.object(
            translator_module.requests, "get", side_effect=requests.ConnectionError()
        ):
            status = ollama_status("translategemma:12b", "http://127.0.0.1:11434")
        self.assertEqual(status.state, "not_running")
        self.assertFalse(status.ready)
        self.assertIn("ollama.com/download", status.message)

    def test_a_model_not_yet_pulled_names_the_command_that_fetches_it(self):
        tags = FakeResponse(200, {"models": [{"name": "qwen3.5:9b"}]})
        with mock.patch.object(translator_module.requests, "get", return_value=tags):
            status = ollama_status("translategemma:12b", "http://127.0.0.1:11434")
        self.assertEqual(status.state, "model_missing")
        self.assertIn("ollama pull translategemma:12b", status.message)
        self.assertEqual(status.installed_models, ("qwen3.5:9b",))

    def test_a_bare_model_name_means_its_latest_tag(self):
        tags = FakeResponse(200, {"models": [{"name": "translategemma:latest"}]})
        with mock.patch.object(translator_module.requests, "get", return_value=tags):
            status = ollama_status("translategemma", "http://127.0.0.1:11434")
        self.assertTrue(status.ready)


class OllamaTranslatorTests(unittest.TestCase):
    def setUp(self) -> None:
        sleep = mock.patch.object(translator_module.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        self.translator = OllamaTranslator(
            "en", "vi", "translategemma:12b", ignore_cache=True
        )
        self.translator.base_url = "http://127.0.0.1:11434"
        self.post = mock.Mock()
        self.translator.session.post = self.post

    def test_uses_translategemma_prompt_with_both_language_codes(self):
        self.post.return_value = _reply("  Xin chào thế giới  \n")

        self.assertEqual(self.translator.translate("Hello world"), "Xin chào thế giới")

        url = self.post.call_args.args[0]
        body = self.post.call_args.kwargs["json"]
        self.assertEqual(url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(body["model"], "translategemma:12b")
        self.assertFalse(body["stream"])
        self.assertEqual(body["options"]["temperature"], 0)
        prompt = body["prompt"]
        self.assertTrue(
            prompt.startswith(
                "You are a professional English (en) to Vietnamese (vi) translator."
            )
        )
        self.assertIn("Produce only the Vietnamese translation", prompt)
        # The model card insists on two blank lines before the text.
        self.assertTrue(prompt.endswith(":\n\n\nHello world"))

    def test_auto_source_language_is_sent_as_english(self):
        translator = OllamaTranslator("auto", "vi", ignore_cache=True)
        self.assertIn("English (en) to Vietnamese (vi)", translator.prompt("x"))

    def test_formula_tags_that_survive_are_restored(self):
        source = "Let {v0} be the loss and {v1} its gradient."
        encoded = encode_formula_placeholders(source)
        self.post.return_value = _reply("Gọi <b0></b0> là hàm mất mát và <b1></b1> là gradient.")

        translated = self.translator.translate(encoded)

        self.assertEqual(
            restore_formula_placeholders(source, translated),
            "Gọi {v0} là hàm mất mát và {v1} là gradient.",
        )

    def test_a_dropped_formula_tag_rejects_the_translation(self):
        source = "Let {v0} be the loss and {v1} its gradient."
        self.post.return_value = _reply("Gọi <b0></b0> là hàm mất mát và gradient của nó.")

        translated = self.translator.translate(encode_formula_placeholders(source))

        with self.assertRaises(FormulaPlaceholderError):
            restore_formula_placeholders(source, translated)

    def test_a_formula_tag_missing_its_closing_half_is_completed(self):
        """Seen from translategemma:12b on 'Equation {v0} shows ...'."""
        source = "Equation {v0} shows the bound {v1}."
        self.post.return_value = _reply("Phương trình <b0> cho thấy giới hạn <b1></b1>.")

        translated = self.translator.translate(encode_formula_placeholders(source))

        self.assertEqual(
            restore_formula_placeholders(source, translated),
            "Phương trình {v0} cho thấy giới hạn {v1}.",
        )

    def test_a_heading_does_not_gain_a_full_stop(self):
        cases = {
            ("1. Introduction", "1. Giới thiệu."): "1. Giới thiệu",
            ("<s1>Abstract</s1>", "<s1>Tóm tắt.</s1>"): "<s1>Tóm tắt</s1>",
            ("Results hold.", "Kết quả đúng."): "Kết quả đúng.",
            ("Wait for it", "Hãy chờ..."): "Hãy chờ...",
            ("the bound {v0}", "giới hạn <b0></b0>."): "giới hạn <b0></b0>",
        }
        for (source, reply), expected in cases.items():
            with self.subTest(source=source):
                self.post.return_value = _reply(reply)
                self.assertEqual(
                    self.translator.translate(encode_formula_placeholders(source)), expected
                )

    def test_a_formula_tag_wrapping_words_is_not_repaired(self):
        source = "Equation {v0} shows the bound."
        self.post.return_value = _reply("Phương trình <b0>cho thấy</b0> giới hạn.")

        translated = self.translator.translate(encode_formula_placeholders(source))

        with self.assertRaises(FormulaPlaceholderError):
            restore_formula_placeholders(source, translated)

    def test_a_dropped_style_run_keeps_the_segment_in_the_source(self):
        """Seen from translategemma:12b; losing bold silently is a regression."""
        source = "Higher scores indicate <s1>better</s1> quality."
        self.post.return_value = _reply("Điểm cao hơn cho thấy chất lượng tốt hơn.")

        translated = self.translator.translate(source)

        with self.assertRaises(FormulaPlaceholderError):
            restore_formula_placeholders(source, translated)

    def test_a_server_that_is_not_running_is_unavailable_at_once(self):
        self.post.side_effect = requests.ConnectionError("refused")

        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")

        self.assertEqual(self.post.call_count, 1)
        self.assertIn("Không kết nối được Ollama", str(caught.exception))

    def test_a_missing_model_is_unavailable_and_says_how_to_pull_it(self):
        self.post.return_value = FakeResponse(404, text='{"error":"model not found"}')

        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")

        self.assertIn("ollama pull translategemma:12b", str(caught.exception))

    def test_running_out_of_memory_suggests_the_lighter_model(self):
        self.post.return_value = FakeResponse(
            500, text='{"error":"model requires more system memory"}'
        )

        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")

        self.assertIn("translategemma:4b", str(caught.exception))

    def test_a_timeout_is_retried_with_backoff_then_reported(self):
        self.post.side_effect = [requests.Timeout(), requests.Timeout(), _reply("Xin chào")]

        self.assertEqual(self.translator.translate("Hello"), "Xin chào")
        self.assertEqual(self.post.call_count, OllamaTranslator.ATTEMPTS)
        delays = [call.args[0] for call in translator_module.time.sleep.call_args_list]
        self.assertEqual(delays, [2.0, 4.0])

    def test_a_segment_that_keeps_timing_out_fails_alone(self):
        self.post.side_effect = requests.Timeout()

        with self.assertRaises(requests.Timeout):
            self.translator.translate("Hello")

    def test_a_run_of_failed_segments_means_the_server_is_wedged(self):
        self.post.side_effect = requests.Timeout()
        for _ in range(OllamaTranslator.CONSECUTIVE_FAILURE_LIMIT - 1):
            with self.assertRaises(requests.Timeout):
                self.translator.translate("Hello")

        with self.assertRaises(TranslationServiceUnavailable):
            self.translator.translate("Hello")

    def test_one_success_resets_the_failure_run(self):
        self.post.side_effect = requests.Timeout()
        for _ in range(OllamaTranslator.CONSECUTIVE_FAILURE_LIMIT - 1):
            with self.assertRaises(requests.Timeout):
                self.translator.translate("Hello")
        self.post.side_effect = None
        self.post.return_value = _reply("Xin chào")
        self.translator.translate("Hello")
        self.post.side_effect = requests.Timeout()

        with self.assertRaises(requests.Timeout):
            self.translator.translate("Hello")

    def test_an_empty_answer_is_a_failure_not_a_blank_translation(self):
        self.post.return_value = _reply("   ")

        with self.assertRaises(RuntimeError):
            self.translator.translate("Hello")

    def test_an_over_long_segment_is_refused_without_a_request(self):
        with self.assertRaises(SegmentTooLongError):
            self.translator.translate("a" * 5001)
        self.post.assert_not_called()


class OllamaPipelineTests(unittest.TestCase):
    """The converter stops asking a dead server and says why, once."""

    @staticmethod
    def _document() -> bytes:
        document = pymupdf.open()
        page = document.new_page(width=300, height=300)
        for index, y in enumerate((40, 90, 140, 190)):
            page.insert_text((20, y), f"Paragraph number {index} explains the method.", fontsize=9)
        stream = document.tobytes()
        document.close()
        return stream

    def _translate(self, post: mock.Mock):
        from pdf2zh.high_level import translate_stream

        with (
            mock.patch.object(requests.Session, "post", post),
            mock.patch.object(translator_module.time, "sleep"),
            mock.patch(
                "pdf2zh.high_level.download_remote_fonts", return_value=str(FONT_PATH)
            ),
            mock.patch(
                "pdf2zh.high_level.output_style_font_paths",
                return_value={0: str(FONT_PATH)},
            ),
        ):
            _mono, _dual, report = translate_stream(
                self._document(),
                lang_in="en",
                lang_out="vi",
                service="ollama:translategemma:12b",
                thread=1,
                model=EmptyLayoutModel(),
                create_dual=False,
                ignore_cache=True,
            )
        return report

    def test_a_stopped_server_is_asked_once_and_reported_for_every_segment(self):
        post = mock.Mock(side_effect=requests.ConnectionError("refused"))

        report = self._translate(post)

        self.assertEqual(post.call_count, 1)
        self.assertGreater(report.translatable_segments, 0)
        self.assertEqual(len(report.failures), report.translatable_segments)
        self.assertEqual(
            report.reasons,
            Counter({"TranslationServiceUnavailable": report.translatable_segments}),
        )
        self.assertIn("Không kết nối được Ollama", report.service_failure)

    def test_a_working_server_translates_every_segment(self):
        post = mock.Mock(return_value=_reply("Đoạn văn giải thích phương pháp."))

        report = self._translate(post)

        self.assertGreater(report.translatable_segments, 0)
        self.assertEqual(report.failures, [])
        self.assertIsNone(report.service_failure)


if __name__ == "__main__":
    unittest.main()
