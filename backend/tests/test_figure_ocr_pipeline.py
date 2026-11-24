"""End-to-end pipeline tests for P11-T3: raster figure OCR integration, switches, and reporting."""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import cv2
import numpy as np
import pymupdf

from pdf2zh.figure_ocr import resolve_figure_font_path
from pdf2zh.high_level import translate_stream
from pdf2zh.ocr import OcrUnavailableError
from pdf2zh.offline import PROFILES
from pdf2zh.translator import BaseTranslator
from scripts import translate_pdf


def _encode_png(image_rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
    assert ok
    return buf.tobytes()


def _decode_rgb(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert bgr is not None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _build_synthetic_diagram() -> np.ndarray:
    img = np.full((180, 360, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (20, 30), (220, 100), (220, 238, 255), thickness=-1)
    cv2.rectangle(img, (20, 30), (220, 100), (0, 0, 0), thickness=2)
    cv2.putText(img, "Initialization", (42, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (15, 20, 30), 2)
    # Axis tick "24" must stay untouched.
    cv2.putText(img, "24", (270, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 2)
    return img


def _build_synthetic_pdf(diagram_rgb: np.ndarray) -> bytes:
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            pymupdf.Point(50, 80),
            "This paragraph introduces the optimization flowchart below.",
            fontsize=11,
        )
        page.insert_image(pymupdf.Rect(50, 140, 410, 320), stream=_encode_png(diagram_rgb))
        return doc.tobytes()


class _FakeBox:
    def __init__(self, cls_id: int, xyxy: tuple[float, float, float, float]) -> None:
        self.cls = cls_id
        self.xyxy = np.array([list(xyxy)], dtype=float)


class _FakeLayoutModel:
    def predict(self, _image: np.ndarray, imgsz: int = 640):
        names = {0: "plain text", 1: "figure"}
        boxes = [
            _FakeBox(0, (40, 60, 520, 100)),
            _FakeBox(1, (45, 135, 420, 330)),
        ]
        return [SimpleNamespace(names=names, boxes=boxes)]


class _StubTranslator(BaseTranslator):
    name = "stub"

    def __init__(self, lang_in: str, lang_out: str, model=None, **kwargs) -> None:
        super().__init__(lang_in, lang_out, model=model, ignore_cache=True)

    def do_translate(self, text: str) -> str:
        mapping = {
            "This paragraph introduces the optimization flowchart below.": (
                "Đoạn này giới thiệu sơ đồ tối ưu hóa bên dưới."
            ),
            "Initialization": "Khởi tạo",
        }
        return mapping.get(text, f"VI:{text}")


def _fake_ocr(_image: np.ndarray):
    return SimpleNamespace(
        boxes=[
            [[38, 50, 205, 78], [205, 50], [205, 78], [38, 78]],  # fixed below
        ],
        txts=[],
        scores=[],
    )


def _diagram_ocr(_image: np.ndarray):
    return SimpleNamespace(
        boxes=[
            [[38, 48, 205, 78], [205, 48], [205, 78], [38, 78]][:0]
            or [[38, 48], [205, 48], [205, 78], [38, 78]],
            [[265, 48], [308, 48], [308, 78], [265, 78]],
        ],
        txts=["Initialization", "24"],
        scores=[0.96, 0.99],
    )


class RasterFigurePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        if resolve_figure_font_path() is None:
            self.skipTest("Bundled Unicode font not present in fresh clone")

    def test_profile_switches_disable_figure_ocr_on_fast_and_enable_on_balanced_quality(self) -> None:
        self.assertFalse(PROFILES["fast"].translate_figure_images)
        self.assertTrue(PROFILES["balanced"].translate_figure_images)
        self.assertTrue(PROFILES["quality"].translate_figure_images)

    def test_translate_stream_replaces_figure_image_and_reports_counts(self) -> None:
        diagram = _build_synthetic_diagram()
        raw_pdf = _build_synthetic_pdf(diagram)
        source_sha = hashlib.sha256(raw_pdf).hexdigest()

        with mock.patch.dict("pdf2zh.converter.ENGINES", {"google": _StubTranslator}):
            mono, _dual, report = translate_stream(
                raw_pdf,
                lang_in="en",
                lang_out="vi",
                service="google",
                thread=1,
                model=_FakeLayoutModel(),
                create_dual=False,
                ignore_cache=True,
                translate_figure_images=True,
                figure_ocr_engine=_diagram_ocr,
            )

        self.assertEqual(hashlib.sha256(raw_pdf).hexdigest(), source_sha)
        self.assertEqual(report.figure_labels_translated, 1)
        self.assertEqual(report.figure_labels_skipped, 1)
        self.assertEqual(report.figure_skip_reasons.get("non_prose_or_numeric"), 1)

        with pymupdf.open(stream=mono, filetype="pdf") as out_doc:
            self.assertEqual(out_doc.page_count, 1)
            self.assertIn("giới thiệu sơ đồ", out_doc[0].get_text("text"))
            images = out_doc[0].get_images(full=True)
            self.assertEqual(len(images), 1)
            extracted = out_doc.extract_image(images[0][0])
            rendered = _decode_rgb(extracted["image"])
            self.assertEqual(rendered.shape, diagram.shape)
            # Label interior changed, border and tick "24" untouched.
            self.assertFalse(np.array_equal(rendered[45:85, 35:210], diagram[45:85, 35:210]))
            np.testing.assert_array_equal(rendered[30:32, 20:221], diagram[30:32, 20:221])
            np.testing.assert_array_equal(rendered[40:85, 260:320], diagram[40:85, 260:320])

    def test_switch_off_and_scan_skip_leave_figure_bytes_untouched(self) -> None:
        diagram = _build_synthetic_diagram()
        raw_pdf = _build_synthetic_pdf(diagram)
        called = False

        def fail_if_called(_img):
            nonlocal called
            called = True
            return _diagram_ocr(_img)

        with mock.patch.dict("pdf2zh.converter.ENGINES", {"google": _StubTranslator}):
            mono_off, _, report_off = translate_stream(
                raw_pdf,
                lang_in="en",
                lang_out="vi",
                service="google",
                thread=1,
                model=_FakeLayoutModel(),
                create_dual=False,
                ignore_cache=True,
                translate_figure_images=False,
                figure_ocr_engine=fail_if_called,
            )
            mono_scan, _, report_scan = translate_stream(
                raw_pdf,
                lang_in="en",
                lang_out="vi",
                service="google",
                thread=1,
                model=_FakeLayoutModel(),
                create_dual=False,
                ignore_cache=True,
                skip_backing_pages={0},
                translate_figure_images=True,
                figure_ocr_engine=fail_if_called,
            )

        self.assertFalse(called)
        self.assertEqual(report_off.figure_labels_translated, 0)
        self.assertEqual(report_scan.figure_labels_translated, 0)
        for output_bytes in (mono_off, mono_scan):
            with pymupdf.open(stream=output_bytes, filetype="pdf") as out_doc:
                extracted = out_doc.extract_image(out_doc[0].get_images(full=True)[0][0])
                np.testing.assert_array_equal(_decode_rgb(extracted["image"]), diagram)

    def test_missing_rapidocr_fails_soft_without_breaking_text_translation(self) -> None:
        diagram = _build_synthetic_diagram()
        raw_pdf = _build_synthetic_pdf(diagram)

        with (
            mock.patch.dict("pdf2zh.converter.ENGINES", {"google": _StubTranslator}),
            mock.patch("pdf2zh.ocr.load_ocr_engine", side_effect=OcrUnavailableError("missing")),
        ):
            mono, _, report = translate_stream(
                raw_pdf,
                lang_in="en",
                lang_out="vi",
                service="google",
                thread=1,
                model=_FakeLayoutModel(),
                create_dual=False,
                ignore_cache=True,
                translate_figure_images=True,
            )

        self.assertEqual(report.figure_labels_translated, 0)
        with pymupdf.open(stream=mono, filetype="pdf") as out_doc:
            self.assertIn("giới thiệu sơ đồ", out_doc[0].get_text("text"))

    def test_cancellation_event_aborts_during_figure_pass(self) -> None:
        diagram = _build_synthetic_diagram()
        raw_pdf = _build_synthetic_pdf(diagram)
        cancel = threading.Event()

        class _CancellingTranslator(_StubTranslator):
            def do_translate(self, text: str) -> str:
                result = super().do_translate(text)
                # Trigger cancellation after prose finishes, right before figure pass.
                cancel.set()
                return result

        with (
            mock.patch.dict("pdf2zh.converter.ENGINES", {"google": _CancellingTranslator}),
            self.assertRaises(asyncio.CancelledError),
        ):
            translate_stream(
                raw_pdf,
                lang_in="en",
                lang_out="vi",
                service="google",
                thread=1,
                model=_FakeLayoutModel(),
                create_dual=False,
                ignore_cache=True,
                cancellation_event=cancel,
                translate_figure_images=True,
                figure_ocr_engine=_diagram_ocr,
            )

    def test_cli_no_figure_ocr_flag_propagates_to_translate_pdf(self) -> None:
        args = translate_pdf._parser().parse_args(
            ["sample.pdf", "--output-dir", "out", "--no-figure-ocr"]
        )
        self.assertTrue(args.no_figure_ocr)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.pdf"
            src.write_bytes(_build_synthetic_pdf(_build_synthetic_diagram()))
            out_dir = Path(tmp) / "out"
            captured: dict[str, object] = {}

            def fake_run(source, temp_output, *pos, **kw):
                captured.update(kw)
                (temp_output / f"{src.stem}-mono.pdf").write_bytes(src.read_bytes())
                return SimpleNamespace(
                    failures=[],
                    reasons={},
                    image_only_pages=set(),
                    translatable_segments=2,
                    service_failure=None,
                    figure_labels_translated=0,
                    figure_labels_skipped=0,
                )

            with (
                mock.patch.object(translate_pdf, "_run_engine", side_effect=fake_run),
                mock.patch.object(translate_pdf, "_require_core"),
            ):
                result = translate_pdf.translate_pdf(
                    src,
                    out_dir,
                    engine="google",
                    translate_figure_images=False,
                )

        self.assertIs(captured.get("translate_figure_images"), False)
        self.assertEqual(result.figure_labels_translated, 0)


if __name__ == "__main__":
    unittest.main()
