from __future__ import annotations

import unittest

from pdf2zh.translator import BaseTranslator, markers_intact


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, text: str) -> str | None:
        return self.values.get(text)

    def set(self, text: str, translation: str) -> None:
        self.values[text] = translation


class FakeTranslator(BaseTranslator):
    def __init__(self, answer: str) -> None:
        self.ignore_cache = False
        self.cache = MemoryCache()
        self.answer = answer
        self.calls = 0

    def do_translate(self, text: str) -> str:
        self.calls += 1
        return self.answer


class SafeCacheTests(unittest.TestCase):
    def test_damaged_legacy_entry_is_ignored_and_replaced(self):
        source = "Let <b0></b0> be <s1>bold</s1>."
        translator = FakeTranslator("Gọi <b0></b0> là <s1>đậm</s1>.")
        translator.cache.set(source, "Gọi <b9></b9> là đậm.")

        result = translator.translate(source)

        self.assertEqual(result, translator.answer)
        self.assertEqual(translator.calls, 1)
        self.assertEqual(translator.cache.get(source), translator.answer)

    def test_damaged_engine_answer_never_enters_cache(self):
        source = "Let <b0></b0> be the loss."
        translator = FakeTranslator("Bản dịch làm mất công thức.")

        self.assertEqual(translator.translate(source), translator.answer)
        self.assertIsNone(translator.cache.get(source))

    def test_formula_style_and_domain_markers_are_all_checked(self):
        source = "<s1>A</s1> <b0></b0> <t0></t0>"
        self.assertTrue(markers_intact(source, "<t0></t0> <b0></b0> <s1>B</s1>"))
        for damaged in (
            "<s1>A</s1> <b1></b1> <t0></t0>",
            "A <b0></b0> <t0></t0>",
            "<s1>A</s1> <b0></b0> <t1></t1>",
            "<s1>A</s1> <b0></b0> <t0></t0><t9>",
        ):
            with self.subTest(damaged=damaged):
                self.assertFalse(markers_intact(source, damaged))


if __name__ == "__main__":
    unittest.main()