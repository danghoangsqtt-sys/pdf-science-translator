"""Numbers in a translation are written exactly as the source writes them (BUG-023).

arXiv 2307.15299v5 with translategemma:12b: "there are 96,432 rows" came back
as "có 96.432 dòng", "reshaped from a 3D to a 2D tensor" as "từ một tensor ba
chiều thành một tensor hai chiều", and the "1st" of an author line vanished.
Markers and length were intact, so every check passed.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from pdf2zh import translator as translator_module
from pdf2zh.cache import clean_test_db, init_test_db
from pdf2zh.translator import (
    NumbersChangedError,
    OllamaTranslator,
    numbers_intact,
    restore_number_notation,
)


def _reply(translation: str):
    return mock.Mock(status_code=200, json=mock.Mock(
        return_value={"response": translation, "done": True}))


class NumberNotationTests(unittest.TestCase):
    def test_localised_separators_are_put_back(self):
        cases = {
            ("In total, there are 96,432 rows", "Tổng cộng có 96.432 dòng"):
                "Tổng cộng có 96,432 dòng",
            ("96,432 rows", "96 432 dòng"): "96,432 dòng",
            ("a learning rate of 0.1 and 0.0001", "tốc độ học 0,1 và 0,0001"):
                "tốc độ học 0.1 và 0.0001",
        }
        for (sent, answer), expected in cases.items():
            with self.subTest(sent=sent):
                restored = restore_number_notation(sent, answer)
                self.assertEqual(restored, expected)
                self.assertTrue(numbers_intact(sent, restored))

    def test_spelled_out_or_dropped_numbers_are_refused(self):
        for sent, answer in (
            ("reshaped from a 3D to a 2D tensor", "từ một tensor ba chiều thành hai chiều"),
            ("1st Anuvab Sen", "Anuvab Sen"),
            ("24 nodes", "hai mươi bốn nút"),
        ):
            with self.subTest(sent=sent):
                self.assertFalse(numbers_intact(sent, restore_number_notation(sent, answer)))

    def test_faithful_translations_pass(self):
        for sent, answer in (
            ("until July 14th, 2023", "đến ngày 14 tháng 7 năm 2023"),
            ("pp. 1735-1780 (1997) [21]", "tr. 1735-1780 (1997) [21]"),
            ("Suppose <b6></b6> has 24 nodes", "Giả sử <b6></b6> có 24 nút"),
            ("Figure 3 below", "Hình 3 dưới đây"),
            ("No numbers here", "Không có số"),
        ):
            with self.subTest(sent=sent):
                self.assertTrue(numbers_intact(sent, answer))

    def test_marker_numbers_are_not_counted(self):
        self.assertTrue(numbers_intact("Let <b12></b12> be x", "Gọi <b12></b12> là x"))


class OllamaNumberRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        for patcher in (
            mock.patch.object(translator_module.time, "sleep"),
            mock.patch.dict(os.environ, {"PDF_TRANSLATE_OLLAMA_FALLBACK_MODEL": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.translator = OllamaTranslator("en", "vi", "translategemma:12b", ignore_cache=True)
        self.translator.base_url = "http://127.0.0.1:11434"
        self.post = mock.Mock()
        self.translator.session.post = self.post

    def test_a_sampled_retry_that_keeps_the_numbers_is_used(self):
        sent = "It is reshaped from a 3D to a 2D tensor."
        self.post.side_effect = [
            _reply("Nó được chuyển từ tensor ba chiều thành tensor hai chiều."),
            _reply("Nó được chuyển từ tensor 3D thành tensor 2D."),
        ]
        self.assertEqual(self.translator.translate(sent),
                         "Nó được chuyển từ tensor 3D thành tensor 2D.")

    def test_a_segment_whose_numbers_never_survive_is_refused(self):
        sent = "It is reshaped from a 3D to a 2D tensor."
        self.post.return_value = _reply("Nó được chuyển từ tensor ba chiều thành hai chiều.")
        with self.assertRaisesRegex(NumbersChangedError, "2, 3"):
            self.translator.translate(sent)

    def test_a_localised_thousands_separator_needs_no_retry(self):
        self.post.return_value = _reply("Tổng cộng có 96.432 dòng.")
        self.assertEqual(self.translator.translate("In total, there are 96,432 rows."),
                         "Tổng cộng có 96,432 dòng.")
        self.assertEqual(self.post.call_count, 1)


class NumberCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_db = init_test_db()
        self.addCleanup(clean_test_db, self.test_db)
        for patcher in (
            mock.patch.object(translator_module.time, "sleep"),
            mock.patch.dict(os.environ, {"PDF_TRANSLATE_OLLAMA_FALLBACK_MODEL": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _translator(self) -> OllamaTranslator:
        translator = OllamaTranslator("en", "vi", "translategemma:12b")
        translator.base_url = "http://127.0.0.1:11434"
        translator.session.post = mock.Mock()
        return translator

    def test_an_answer_that_lost_a_number_is_never_cached(self):
        sent = "The output layer contains 24 nodes."
        first = self._translator()
        first.session.post.return_value = _reply("Lớp đầu ra chứa hai mươi bốn nút.")
        with self.assertRaises(NumbersChangedError):
            first.translate(sent)
        self.assertIsNone(first.cache.get(sent))

    def test_a_cached_localised_answer_is_served_in_source_notation(self):
        sent = "In total, there are 96,432 rows."
        old = self._translator()
        old.cache.set(sent, "Tổng cộng có 96.432 dòng.")  # cached before this check
        served = self._translator()
        self.assertEqual(served.translate(sent), "Tổng cộng có 96,432 dòng.")
        served.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
