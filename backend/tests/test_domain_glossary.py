from __future__ import annotations

import unittest

from pdf2zh.translator import (
    SUPPORTED_DOMAINS,
    load_domain_glossary,
    mask_domain_terms,
    restore_domain_terms,
)
from scripts.translate_pdf import DOMAINS


class DomainConstantsAgreeTests(unittest.TestCase):
    def test_cli_domain_list_matches_the_core_supported_set(self):
        """scripts/translate_pdf.py duplicates SUPPORTED_DOMAINS as a plain
        tuple (the same pattern ENGINES/OCR_MODES already use, to avoid
        importing the heavy core before _require_core() runs). If the two
        ever drift, --domain would offer a choice the core silently ignores."""
        self.assertEqual(set(DOMAINS), SUPPORTED_DOMAINS)


class LoadDomainGlossaryTests(unittest.TestCase):
    def test_every_supported_domain_has_a_non_empty_table(self):
        for domain in SUPPORTED_DOMAINS:
            with self.subTest(domain=domain):
                table = load_domain_glossary(domain)
                self.assertTrue(table)
                for term, preferred in table.items():
                    self.assertIsInstance(term, str)
                    self.assertIsInstance(preferred, str)
                    self.assertTrue(term.strip())
                    self.assertTrue(preferred.strip())

    def test_an_unknown_domain_returns_an_empty_table_not_an_error(self):
        self.assertEqual(load_domain_glossary("astrology"), {})


class MaskDomainTermsTests(unittest.TestCase):
    glossary = {"conduction": "dẫn nhiệt", "boundary condition": "điều kiện biên"}

    def test_a_term_in_the_middle_of_a_sentence_is_masked(self):
        text = "Conduction occurs when two objects touch directly."
        masked, preferred = mask_domain_terms(text, self.glossary)
        self.assertEqual(masked, "<t0></t0> occurs when two objects touch directly.")
        self.assertEqual(preferred, ["dẫn nhiệt"])

    def test_matching_is_case_insensitive_but_preserves_surrounding_text(self):
        masked, preferred = mask_domain_terms("Heat CONDUCTION is fast.", self.glossary)
        self.assertEqual(masked, "Heat <t0></t0> is fast.")
        self.assertEqual(preferred, ["dẫn nhiệt"])

    def test_a_multi_word_term_is_matched_as_one_unit(self):
        masked, preferred = mask_domain_terms(
            "Apply the correct boundary condition here.", self.glossary
        )
        self.assertEqual(masked, "Apply the correct <t0></t0> here.")
        self.assertEqual(preferred, ["điều kiện biên"])

    def test_word_boundaries_are_respected(self):
        """"conduction" must not match inside "semiconduction" or similar."""
        masked, preferred = mask_domain_terms("Semiconduction is unrelated.", self.glossary)
        self.assertEqual(masked, "Semiconduction is unrelated.")
        self.assertEqual(preferred, [])

    def test_an_empty_glossary_is_a_no_op(self):
        text = "Conduction occurs here."
        self.assertEqual(mask_domain_terms(text, {}), (text, []))

    def test_placeholder_indices_follow_appearance_order(self):
        text = "Boundary condition matters more than conduction here."
        masked, preferred = mask_domain_terms(text, self.glossary)
        self.assertEqual(masked, "<t0></t0> matters more than <t1></t1> here.")
        self.assertEqual(preferred, ["điều kiện biên", "dẫn nhiệt"])


class RestoreDomainTermsTests(unittest.TestCase):
    def test_no_placeholders_requested_returns_the_text_unchanged(self):
        self.assertEqual(restore_domain_terms("Xảy ra khi hai vật chạm nhau.", []), "Xảy ra khi hai vật chạm nhau.")

    def test_a_surviving_placeholder_is_replaced_with_the_preferred_term(self):
        translated = "<t0></t0> xảy ra khi hai vật chạm nhau."
        restored = restore_domain_terms(translated, ["dẫn nhiệt"])
        self.assertEqual(restored, "dẫn nhiệt xảy ra khi hai vật chạm nhau.")

    def test_reordered_placeholders_are_rejected_not_silently_swapped(self):
        """Google put term 1 before term 0 - restoring positionally would
        silently swap which Vietnamese term lands where. Must refuse instead."""
        translated = "<t1></t1> ảnh hưởng nhiều hơn <t0></t0>."
        self.assertIsNone(restore_domain_terms(translated, ["điều kiện biên", "dẫn nhiệt"]))

    def test_a_dropped_placeholder_is_rejected(self):
        translated = "Chỉ còn một thuật ngữ <t0></t0> ở đây."
        self.assertIsNone(restore_domain_terms(translated, ["dẫn nhiệt", "điều kiện biên"]))

    def test_a_malformed_unpaired_tag_is_rejected_not_leaked(self):
        translated = "<t0>dẫn nhiệt xảy ra ở đây."
        self.assertIsNone(restore_domain_terms(translated, ["dẫn nhiệt"]))

    def test_the_restored_text_never_contains_a_raw_placeholder_tag(self):
        translated = "<t0></t0> xảy ra khi hai vật chạm nhau."
        restored = restore_domain_terms(translated, ["dẫn nhiệt"])
        self.assertNotIn("<t0>", restored)
        self.assertNotIn("</t0>", restored)


if __name__ == "__main__":
    unittest.main()
