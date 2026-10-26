from __future__ import annotations

import argparse
import tempfile
from collections import Counter
import unittest
from pathlib import Path
from unittest import mock

from pdf2zh.high_level import TranslationReport
from scripts import translate_pdf

MODEL = "translategemma:12b"

class FailureReportingTests(unittest.TestCase):
    def test_an_over_long_segment_is_reported_as_its_own_reason(self):
        """Truncating it silently loses the tail; saying so lets the user act.

        It is neither a fit failure nor a dead connection, and telling the user
        their network is down would send them to check the wrong thing.
        """
        lines = translate_pdf._describe_failures(Counter({"SegmentTooLongError": 2}))
        self.assertEqual(len(lines), 1)
        self.assertIn("2 segments", lines[0])
        self.assertIn("longer than the translation service accepts", lines[0])

    def test_each_kind_of_failure_gets_its_own_line(self):
        lines = translate_pdf._describe_failures(
            Counter(
                {
                    "SegmentTooLongError": 1,
                    "FormulaPlaceholderError": 1,
                    "single line needs less than 50% font size": 1,
                    "ConnectionError": 1,
                }
            )
        )
        self.assertEqual(len(lines), 4)
        self.assertEqual(
            sum("translation engine failed" in line for line in lines), 1
        )


class PageCountAdvisoryTests(unittest.TestCase):
    def test_a_document_at_or_under_the_limit_gets_no_advisory(self):
        self.assertIsNone(
            translate_pdf.page_count_advisory(translate_pdf.PAGE_COUNT_ADVISORY_LIMIT)
        )
        self.assertIsNone(translate_pdf.page_count_advisory(1))

    def test_a_document_past_the_limit_names_its_own_page_count(self):
        over = translate_pdf.PAGE_COUNT_ADVISORY_LIMIT + 1
        advisory = translate_pdf.page_count_advisory(over)
        self.assertIsNotNone(advisory)
        self.assertIn(str(over), advisory)
        self.assertIn("--pages", advisory)

    def test_peeking_a_missing_file_never_raises(self):
        self.assertIsNone(translate_pdf._peek_page_count(Path("does-not-exist.pdf")))


class TranslatePdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name).resolve()
        self.source = self.root / "guide.pdf"
        self.source.write_bytes(b"%PDF-1.7\nsource")
        self.output = self.root / "output"
        # The default engine asks the local Ollama server first; these tests
        # run the converter as a mock, so no server is consulted.
        ollama = mock.patch.object(
            translate_pdf, "_require_ollama", side_effect=lambda model: model or MODEL
        )
        ollama.start()
        self.addCleanup(ollama.stop)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    @staticmethod
    def _engine_side_effect(source, temp_output, *_args):
        (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(
            b"%PDF-1.7\ntranslated"
        )
        # The real runner hands back what the core could not translate, and why.
        return TranslationReport(translatable_segments=12)

    @mock.patch.object(translate_pdf, "_require_core")
    @mock.patch.object(translate_pdf, "_run_engine")
    def test_copies_the_core_result_to_a_stable_vietnamese_name(self, run, _core):
        run.side_effect = self._engine_side_effect

        result = translate_pdf.translate_pdf(self.source, self.output)

        self.assertEqual(result.path, self.output / "guide-vi.pdf")
        self.assertEqual(result.untranslated, 0)
        self.assertEqual(result.path.read_bytes(), b"%PDF-1.7\ntranslated")
        run.assert_called_once_with(
            self.source, mock.ANY, "vi", "auto", None,
            translate_pdf.DEFAULT_OLLAMA_THREADS, False, f"ollama:{MODEL}", {}, None,
        )

    @mock.patch.object(translate_pdf, "_require_core")
    @mock.patch.object(translate_pdf, "_run_engine")
    def test_refuses_to_replace_output_without_authorization(self, run, _core):
        self.output.mkdir()
        existing = self.output / "guide-vi.pdf"
        existing.write_bytes(b"existing")

        with self.assertRaisesRegex(translate_pdf.TranslationError, "already exists"):
            translate_pdf.translate_pdf(self.source, self.output)

        run.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"existing")

    @mock.patch.object(translate_pdf, "_require_core")
    def test_rejects_a_non_pdf_payload(self, _core):
        invalid = self.root / "fake.pdf"
        invalid.write_text("not a PDF", encoding="utf-8")

        with self.assertRaisesRegex(translate_pdf.TranslationError, "PDF header"):
            translate_pdf.translate_pdf(invalid, self.output)

    def test_validates_and_converts_page_ranges(self):
        self.assertEqual(translate_pdf._page_selection("1,3-5"), "1,3-5")
        self.assertEqual(translate_pdf._pages_to_indices("1,3-5"), [0, 2, 3, 4])
        with self.assertRaises(argparse.ArgumentTypeError):
            translate_pdf._page_selection("5-3")

    def test_ocr_profile_is_opt_in_at_the_cli_boundary(self):
        args = translate_pdf._parser().parse_args(
            ["guide.pdf", "--output-dir", "out", "--ocr", "standard"]
        )
        self.assertEqual(args.ocr, "standard")
        self.assertEqual(
            translate_pdf._parser().parse_args(["guide.pdf", "--output-dir", "out"]).ocr,
            "off",
        )

    def test_requires_the_bundled_core_instead_of_the_pypi_wheel(self):
        translate_pdf._require_core()

        import pdf2zh

        self.assertTrue(
            Path(pdf2zh.__file__).resolve().is_relative_to(translate_pdf.BUNDLED_CORE)
        )

    def test_engine_contract_forwards_language_engine_and_handoff_files(self):
        fake_model = object()
        with (
            mock.patch(
                "pdf2zh.doclayout.OnnxModel.load_available",
                return_value=fake_model,
            ),
            mock.patch(
                "pdf2zh.high_level.translate",
                return_value=[("translated.pdf", "")],
            ) as core_translate,
        ):
            translate_pdf._run_engine(
                self.source,
                self.output,
                "fr",
                "en",
                "2-3",
                1,
                True,
                "handoff",
                {"segments_in": "table.jsonl"},
            )

        core_translate.assert_called_once_with(
            files=[str(self.source)],
            output=str(self.output),
            pages=[1, 2],
            lang_in="en",
            lang_out="fr",
            service="handoff",
            thread=1,
            model=fake_model,
            envs={"segments_in": "table.jsonl"},
            callback=None,
            ignore_cache=True,
        )

    def test_reports_segments_the_engine_could_not_translate(self):
        def partial(source, temp_output, *_args):
            (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(b"%PDF-1.7\n")
            return TranslationReport(
                failures=["a"] * 7,
                reasons=Counter({"ConnectionError": 7}),
                translatable_segments=40,
            )

        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine", side_effect=partial),
        ):
            result = translate_pdf.translate_pdf(self.source, self.output)

        # A document that lost some segments must still be delivered, and say so.
        self.assertEqual(result.path, self.output / "guide-vi.pdf")
        self.assertEqual(result.untranslated, 7)
        self.assertEqual(result.total_segments, 40)
        self.assertEqual(result.translated_segments, 33)
        self.assertAlmostEqual(result.translated_ratio, 33 / 40)
        self.assertEqual(result.engine, "ollama")
        self.assertEqual(result.model, MODEL)

    def test_kept_segments_are_counted_by_what_the_user_would_do(self):
        def partial(source, temp_output, *_args):
            (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(b"%PDF-1.7\n")
            return TranslationReport(
                failures=["a"] * 9,
                reasons=Counter({
                    "TranslationServiceUnavailable": 2,
                    "ReadTimeout": 1,
                    "FormulaPlaceholderError": 3,
                    "table cell cannot fit at 50% font size": 2,
                    "SegmentTooLongError": 1,
                }),
                translatable_segments=20,
            )

        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine", side_effect=partial),
        ):
            result = translate_pdf.translate_pdf(self.source, self.output)

        self.assertEqual(
            result.kept_by_reason,
            {"service": 3, "formula": 3, "fit": 2, "too_long": 1},
        )

    def test_nothing_translated_is_an_error_not_a_finished_file(self):
        """The 26/10/2026 IP block: a source copy was reported as complete."""
        def blocked(source, temp_output, *_args):
            (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(b"%PDF-1.7\n")
            return TranslationReport(
                failures=["a"] * 12,
                reasons=Counter({"TranslationServiceUnavailable": 12}),
                translatable_segments=12,
                service_failure="Không kết nối được Ollama tại http://127.0.0.1:11434.",
            )

        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine", side_effect=blocked),
        ):
            with self.assertRaisesRegex(translate_pdf.TranslationError, "Không kết nối"):
                translate_pdf.translate_pdf(self.source, self.output)

        self.assertFalse((self.output / "guide-vi.pdf").exists())

    def test_nothing_translated_without_a_service_message_names_the_causes(self):
        def unfit(source, temp_output, *_args):
            (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(b"%PDF-1.7\n")
            return TranslationReport(
                failures=["a"] * 2,
                reasons=Counter({"FormulaPlaceholderError": 2}),
                translatable_segments=2,
            )

        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine", side_effect=unfit),
        ):
            with self.assertRaisesRegex(translate_pdf.TranslationError, "formula markers"):
                translate_pdf.translate_pdf(self.source, self.output)

    def test_ollama_is_checked_before_any_page_is_read(self):
        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(
                translate_pdf,
                "_require_ollama",
                side_effect=translate_pdf.TranslationError("chưa tải mô hình"),
            ),
            mock.patch.object(translate_pdf, "_run_engine") as run,
        ):
            with self.assertRaisesRegex(translate_pdf.TranslationError, "chưa tải"):
                translate_pdf.translate_pdf(self.source, self.output)
        run.assert_not_called()

    def test_azure_without_a_key_is_refused_before_any_page_is_read(self):
        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch("pdf2zh.translator.azure_settings", return_value=None),
            mock.patch.object(translate_pdf, "_run_engine") as run,
        ):
            with self.assertRaisesRegex(translate_pdf.TranslationError, "AZURE_TRANSLATOR_KEY"):
                translate_pdf.translate_pdf(self.source, self.output, engine="azure")
        run.assert_not_called()

    def test_each_engine_gets_its_own_default_thread_count(self):
        for engine, threads in (
            ("ollama", translate_pdf.DEFAULT_OLLAMA_THREADS),
            ("google", translate_pdf.DEFAULT_THREADS),
        ):
            with (
                self.subTest(engine=engine),
                mock.patch.object(translate_pdf, "_require_core"),
                mock.patch.object(translate_pdf, "_run_engine") as run,
            ):
                run.side_effect = self._engine_side_effect
                translate_pdf.translate_pdf(
                    self.source, self.output, engine=engine, overwrite=True
                )
                self.assertEqual(run.call_args.args[5], threads)
                self.assertEqual(run.call_args.args[7].split(":")[0], engine)
        self.assertLessEqual(translate_pdf.DEFAULT_OLLAMA_THREADS, 2)

    def test_the_default_engine_is_the_offline_one(self):
        args = translate_pdf._parser().parse_args([str(self.source), "--output-dir", "out"])
        self.assertEqual(args.engine, "ollama")
        self.assertIsNone(args.threads)

    def test_model_applies_only_to_ollama(self):
        args = translate_pdf._parser().parse_args(
            [str(self.source), "--output-dir", "out", "--engine", "google",
             "--model", "translategemma:4b"]
        )
        with self.assertRaisesRegex(translate_pdf.TranslationError, "--model"):
            translate_pdf._validate_arguments(args)

    def test_refuses_a_document_with_no_extractable_text(self):
        """An image-only scan must not be handed over as a finished translation."""
        def scanned(source, temp_output, *_args):
            (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(b"%PDF")
            return TranslationReport(
                image_only_pages={0, 1, 2, 3}, translatable_segments=0, pages_processed=4
            )

        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine", side_effect=scanned),
        ):
            with self.assertRaises(translate_pdf.TranslationError) as caught:
                translate_pdf.translate_pdf(self.source, self.output)

        message = str(caught.exception)
        self.assertIn("image-only", message)
        self.assertIn("OCR", message)
        # Nothing may be written: a file on disk is what made this look like success.
        self.assertFalse((self.output / "guide-vi.pdf").exists())

    def test_reports_image_only_pages_of_a_mixed_document(self):
        def mixed(source, temp_output, *_args):
            (Path(temp_output) / f"{Path(source).stem}-mono.pdf").write_bytes(b"%PDF")
            return TranslationReport(image_only_pages={2, 6}, translatable_segments=30)

        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine", side_effect=mixed),
        ):
            result = translate_pdf.translate_pdf(self.source, self.output)

        # Delivered, because the rest of it translated, but the gaps are named.
        self.assertEqual(result.path, self.output / "guide-vi.pdf")
        self.assertEqual(result.image_only_pages, (2, 6))

    def test_layout_failures_are_not_reported_as_a_network_problem(self):
        """The bug this guards: every skipped segment blamed the translation service."""
        lines = translate_pdf._describe_failures(
            Counter({"single line needs less than 50% font size": 5})
        )

        self.assertEqual(len(lines), 1)
        self.assertIn("did not fit", lines[0])
        for wrong in ("service", "engine failed", "reach"):
            self.assertNotIn(wrong, lines[0])

    def test_damaged_formula_markers_are_reported_as_their_own_cause(self):
        lines = translate_pdf._describe_failures(Counter({"FormulaPlaceholderError": 1}))

        self.assertEqual(len(lines), 1)
        self.assertIn("formula", lines[0])
        self.assertTrue(lines[0].startswith("1 segment "), lines[0])

    def test_each_cause_is_reported_separately(self):
        lines = translate_pdf._describe_failures(
            Counter({
                "table cell cannot fit at 50% font size": 2,
                "rotated text needs less than 50% font size": 1,
                "FormulaPlaceholderError": 4,
                "ConnectionError": 3,
            })
        )

        self.assertEqual(len(lines), 3)
        joined = " | ".join(lines)
        self.assertIn("3 segments", joined)
        self.assertIn("4 segments", joined)
        self.assertIn("ConnectionError x3", joined)

    def test_target_language_is_limited_to_latin_script(self):
        self.assertEqual(translate_pdf._target_language("FR"), "fr")
        for rejected in ("zh", "ja", "ko", "ar", "he", "th", "hi"):
            with self.subTest(language=rejected):
                with self.assertRaises(argparse.ArgumentTypeError):
                    translate_pdf._target_language(rejected)

    def test_output_name_follows_the_target_language(self):
        with (
            mock.patch.object(translate_pdf, "_require_core"),
            mock.patch.object(translate_pdf, "_run_engine") as run,
        ):
            run.side_effect = self._engine_side_effect
            result = translate_pdf.translate_pdf(
                self.source, self.output, target_language="fr"
            )
        self.assertEqual(result.path, self.output / "guide-fr.pdf")

    def test_handoff_flags_are_rejected_for_the_google_engine(self):
        args = translate_pdf._parser().parse_args(
            [str(self.source), "--output-dir", str(self.output), "--segments", "t.jsonl"]
        )
        with self.assertRaisesRegex(translate_pdf.TranslationError, "require --engine handoff"):
            translate_pdf._validate_arguments(args)

    def test_handoff_engine_requires_a_segments_file(self):
        args = translate_pdf._parser().parse_args(
            [str(self.source), "--output-dir", str(self.output), "--engine", "handoff"]
        )
        with self.assertRaisesRegex(translate_pdf.TranslationError, "needs --segments"):
            translate_pdf._validate_arguments(args)

    def test_output_dir_is_optional_only_when_emitting_segments(self):
        emit = translate_pdf._parser().parse_args(
            [str(self.source), "--engine", "handoff", "--emit-segments", "m.jsonl"]
        )
        translate_pdf._validate_arguments(emit)

        bare = translate_pdf._parser().parse_args([str(self.source)])
        with self.assertRaisesRegex(translate_pdf.TranslationError, "--output-dir is required"):
            translate_pdf._validate_arguments(bare)


if __name__ == "__main__":
    unittest.main()
