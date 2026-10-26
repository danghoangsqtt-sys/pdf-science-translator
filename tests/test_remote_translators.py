from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from pdf2zh import translator as translator_module
from pdf2zh.translator import (
    ENGINES,
    GOOGLE_BLOCKED_MESSAGE,
    AzureSettings,
    AzureTranslator,
    FormulaPlaceholderError,
    GoogleTranslator,
    SegmentTooLongError,
    TranslationServiceUnavailable,
    azure_settings,
    encode_formula_placeholders,
    google_blocked,
    restore_formula_placeholders,
)

SETTINGS = AzureSettings("secret-key", "southeastasia", "https://azure.example", "environment")


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: object = None,
        text: str = "",
        url: str = "https://translate.google.com/m",
        headers: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text or payload is None else json.dumps(payload)
        self.url = url
        self.headers = headers or {}

    def json(self) -> object:
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _azure_reply(*texts: str) -> FakeResponse:
    return FakeResponse(200, [{"translations": [{"text": text, "to": "vi"}]} for text in texts])


class GoogleBlockTests(unittest.TestCase):
    """The 26/10/2026 incident: a blocked IP must stop the run at once."""

    def setUp(self) -> None:
        self.translator = GoogleTranslator("en", "vi", ignore_cache=True)
        self.get = mock.Mock()
        self.translator.session.get = self.get

    def test_http_429_is_a_block(self):
        self.get.return_value = FakeResponse(429, text="Too Many Requests")
        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")
        self.assertEqual(str(caught.exception), GOOGLE_BLOCKED_MESSAGE)

    def test_a_redirect_to_the_sorry_page_is_a_block(self):
        self.get.return_value = FakeResponse(
            200, text="<html>…</html>", url="https://www.google.com/sorry/index?continue=x"
        )
        with self.assertRaises(TranslationServiceUnavailable):
            self.translator.translate("Hello")

    def test_a_captcha_page_is_a_block(self):
        self.get.return_value = FakeResponse(
            200,
            text="<p>Our systems have detected unusual traffic from your computer network.</p>"
            '<div class="g-recaptcha"></div>',
        )
        with self.assertRaises(TranslationServiceUnavailable):
            self.translator.translate("Hello")

    def test_the_message_is_vietnamese_and_names_the_alternatives(self):
        self.assertIn("Google đã tạm chặn máy này", GOOGLE_BLOCKED_MESSAGE)
        self.assertIn("Ollama", GOOGLE_BLOCKED_MESSAGE)
        self.assertIn("Azure", GOOGLE_BLOCKED_MESSAGE)

    def test_a_document_about_unusual_traffic_is_not_a_block(self):
        page = (
            '<div class="result-container">Lưu lượng bất thường trên mạng</div>'
            "<p>unusual traffic on the network</p>"
        )
        self.get.return_value = FakeResponse(200, text=page)
        self.assertFalse(google_blocked(self.get.return_value))
        self.assertEqual(
            self.translator.translate("unusual traffic on the network"),
            "Lưu lượng bất thường trên mạng",
        )

    def test_a_blocked_document_asks_google_once_not_per_segment(self):
        """Through the whole pipeline: one 429, then every segment is kept."""
        from tests.test_ollama_translator import EmptyLayoutModel, FONT_PATH, OllamaPipelineTests
        from pdf2zh.high_level import translate_stream

        get = mock.Mock(return_value=FakeResponse(429))
        with (
            mock.patch.object(requests.Session, "get", get),
            mock.patch("pdf2zh.high_level.download_remote_fonts", return_value=str(FONT_PATH)),
            mock.patch(
                "pdf2zh.high_level.output_style_font_paths", return_value={0: str(FONT_PATH)}
            ),
        ):
            _mono, _dual, report = translate_stream(
                OllamaPipelineTests._document(),
                lang_in="en",
                lang_out="vi",
                service="google",
                thread=4,
                model=EmptyLayoutModel(),
                create_dual=False,
                ignore_cache=True,
            )

        self.assertGreater(report.translatable_segments, 1)
        self.assertLessEqual(get.call_count, 4)  # at most one in flight per thread
        self.assertEqual(len(report.failures), report.translatable_segments)
        self.assertEqual(report.service_failure, GOOGLE_BLOCKED_MESSAGE)


class AzureSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / "engines.json"
        patcher = mock.patch.dict(
            os.environ, {"PDF_TRANSLATE_CONFIG": str(self.config)}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("AZURE_TRANSLATOR_KEY", "AZURE_TRANSLATOR_REGION", "AZURE_TRANSLATOR_ENDPOINT"):
            os.environ.pop(name, None)

    def test_nothing_configured_is_none(self):
        self.assertIsNone(azure_settings())

    def test_the_user_settings_file_is_read(self):
        self.config.write_text(
            json.dumps({"azure": {"key": "file-key", "region": "eastasia"}}), encoding="utf-8"
        )
        settings = azure_settings()
        self.assertEqual(settings.key, "file-key")
        self.assertEqual(settings.region, "eastasia")
        self.assertEqual(settings.endpoint, "https://api.cognitive.microsofttranslator.com")
        self.assertEqual(settings.source, str(self.config))

    def test_environment_variables_win_over_the_file(self):
        self.config.write_text(json.dumps({"azure": {"key": "file-key"}}), encoding="utf-8")
        with mock.patch.dict(
            os.environ,
            {"AZURE_TRANSLATOR_KEY": "env-key", "AZURE_TRANSLATOR_REGION": "westeurope"},
        ):
            settings = azure_settings()
        self.assertEqual((settings.key, settings.region, settings.source),
                         ("env-key", "westeurope", "environment"))

    def test_the_key_never_appears_in_the_settings_repr(self):
        self.assertNotIn("secret-key", repr(SETTINGS))

    def test_a_damaged_settings_file_is_treated_as_unconfigured(self):
        self.config.write_text("{not json", encoding="utf-8")
        self.assertIsNone(azure_settings())


class AzureTranslatorTests(unittest.TestCase):
    def setUp(self) -> None:
        sleep = mock.patch.object(translator_module.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)
        self.translator = AzureTranslator("en", "vi", ignore_cache=True, settings=SETTINGS)
        self.post = mock.Mock()
        self.translator.session.post = self.post

    def test_ollama_azure_and_google_are_registered(self):
        self.assertIs(ENGINES["azure"], AzureTranslator)

    def test_sends_html_with_key_region_and_languages(self):
        self.post.return_value = _azure_reply("Xin chào")

        self.assertEqual(self.translator.translate("Hello"), "Xin chào")

        call = self.post.call_args
        self.assertEqual(call.args[0], "https://azure.example/translate")
        self.assertEqual(
            call.kwargs["params"],
            {"api-version": "3.0", "to": "vi", "textType": "html", "from": "en"},
        )
        self.assertEqual(call.kwargs["headers"]["Ocp-Apim-Subscription-Key"], "secret-key")
        self.assertEqual(call.kwargs["headers"]["Ocp-Apim-Subscription-Region"], "southeastasia")
        self.assertEqual(call.kwargs["json"], [{"Text": "Hello"}])

    def test_auto_source_language_lets_azure_detect_it(self):
        translator = AzureTranslator("auto", "vi", ignore_cache=True, settings=SETTINGS)
        translator.session.post = self.post
        self.post.return_value = _azure_reply("Xin chào")
        translator.translate("Hello")
        self.assertNotIn("from", self.post.call_args.kwargs["params"])

    def test_prose_is_escaped_but_marker_tags_stay_tags(self):
        source = "If {v0} < <s1>5 & up</s1> then"
        self.post.return_value = _azure_reply("Nếu <b0></b0> &lt; <s1>5 &amp; trở lên</s1> thì")

        translated = self.translator.translate(encode_formula_placeholders(source))

        self.assertEqual(
            self.post.call_args.kwargs["json"],
            [{"Text": "If <b0></b0> &lt; <s1>5 &amp; up</s1> then"}],
        )
        self.assertEqual(
            restore_formula_placeholders(source, translated), "Nếu {v0} < <s1>5 & trở lên</s1> thì"
        )

    def test_a_dropped_formula_tag_still_rejects_the_segment(self):
        source = "Let {v0} be the loss."
        self.post.return_value = _azure_reply("Gọi là hàm mất mát.")
        translated = self.translator.translate(encode_formula_placeholders(source))
        with self.assertRaises(FormulaPlaceholderError):
            restore_formula_placeholders(source, translated)

    def test_a_page_is_sent_in_batches_within_the_service_limits(self):
        texts = [f"Segment {index} " + "x" * 98 for index in range(1200)]  # ~110 chars each

        batches = self.translator.batches(texts)

        self.assertTrue(all(len(batch) <= 1000 for batch in batches))
        self.assertTrue(all(sum(len(t) for t in batch) <= 50000 for batch in batches))
        self.assertEqual(sum(len(batch) for batch in batches), 1200)
        self.assertEqual([text for batch in batches for text in batch], texts)
        self.assertEqual(len(batches), 3)  # 50,000 characters is the binding limit

    def test_a_thousand_short_segments_split_on_the_element_limit(self):
        batches = self.translator.batches(["hi"] * 1500)
        self.assertEqual([len(batch) for batch in batches], [1000, 500])

    def test_prefetch_answers_each_segment_from_one_request(self):
        def reply(url, params, headers, json, timeout):
            return _azure_reply(*(f"VI:{item['Text']}" for item in json))

        self.post.side_effect = reply
        self.translator.prefetch(["one", "two", "one", "three"])
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual(
            [self.translator.translate(text) for text in ("one", "two", "three")],
            ["VI:one", "VI:two", "VI:three"],
        )
        self.assertEqual(self.post.call_count, 1)

    def test_a_failed_prefetch_leaves_segments_to_the_normal_path(self):
        self.post.side_effect = [requests.Timeout(), requests.Timeout(), requests.Timeout(),
                                 _azure_reply("Xin chào")]
        self.translator.prefetch(["Hello"])
        self.assertEqual(self.translator.translate("Hello"), "Xin chào")

    def test_an_invalid_key_is_unavailable_and_does_not_leak_the_key(self):
        self.post.return_value = FakeResponse(
            401, {"error": {"code": 401000, "message": "The request is not authorized"}}
        )
        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("secret-key", str(caught.exception))
        self.assertEqual(self.post.call_count, 1)

    def test_an_exhausted_free_quota_is_unavailable(self):
        self.post.return_value = FakeResponse(
            403, {"error": {"code": 403001, "message": "quota exceeded"}}
        )
        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")
        self.assertIn("hạn mức", str(caught.exception))

    def test_rate_limiting_is_retried_then_reported(self):
        self.post.side_effect = [FakeResponse(429, headers={"Retry-After": "3"}), _azure_reply("Xin chào")]
        self.assertEqual(self.translator.translate("Hello"), "Xin chào")
        self.assertIn(mock.call(3), self.sleep.call_args_list)

    def test_persistent_rate_limiting_stops_the_run(self):
        self.post.return_value = FakeResponse(429)
        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")
        self.assertIn("429", str(caught.exception))
        self.assertEqual(self.post.call_count, AzureTranslator.ATTEMPTS)

    def test_a_timeout_is_retried_with_backoff(self):
        self.post.side_effect = [requests.Timeout(), _azure_reply("Xin chào")]
        self.assertEqual(self.translator.translate("Hello"), "Xin chào")

    def test_no_connection_is_unavailable_after_retries(self):
        self.post.side_effect = requests.ConnectionError("offline")
        with self.assertRaises(TranslationServiceUnavailable) as caught:
            self.translator.translate("Hello")
        self.assertIn("Không kết nối được Azure", str(caught.exception))
        self.assertEqual(self.post.call_count, AzureTranslator.ATTEMPTS)

    def test_no_key_configured_is_unavailable_before_any_request(self):
        translator = AzureTranslator("en", "vi", ignore_cache=True, settings=None)
        translator.settings = None
        translator.session.post = self.post
        with self.assertRaises(TranslationServiceUnavailable) as caught:
            translator.translate("Hello")
        self.assertIn("AZURE_TRANSLATOR_KEY", str(caught.exception))
        self.post.assert_not_called()

    def test_an_over_long_segment_is_refused(self):
        with self.assertRaises(SegmentTooLongError):
            self.translator.translate("a" * 50001)
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
