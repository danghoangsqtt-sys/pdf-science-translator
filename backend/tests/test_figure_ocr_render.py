"""Unit tests for P11-T2: number-preserving label translation and Unicode overlay rendering."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from pdf2zh.figure_ocr import (
    process_figure_image,
    resolve_figure_font_path,
    translate_raster_label,
)


def _encode_png(image_rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
    assert ok
    return buf.tobytes()


def _decode_rgb(png_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert bgr is not None
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _fake_ocr_result(entries: list[tuple[tuple[float, float, float, float], str, float]]):
    return SimpleNamespace(
        boxes=[[[x0, y0], [x1, y0], [x1, y1], [x0, y1]] for (x0, y0, x1, y1), _, _ in entries],
        txts=[text for _, text, _ in entries],
        scores=[score for _, _, score in entries],
    )


class _DictTranslator:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def translate(self, text: str) -> str:
        return self.mapping.get(text, text)


class RasterFigureRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.font_path = resolve_figure_font_path()
        if self.font_path is None:
            self.skipTest("Bundled Unicode font not present in fresh clone")

    def test_translate_raster_label_preserves_numbers_and_refuses_changes(self) -> None:
        good = _DictTranslator({"Dense Layer (64)": "Lớp dày đặc (64)"})
        out, reason = translate_raster_label("Dense Layer (64)", good)
        self.assertEqual(out, "Lớp dày đặc (64)")
        self.assertIsNone(reason)

        # Separator localization is restored automatically.
        sep = _DictTranslator({"Step 0.5": "Bước 0,5"})
        out_sep, reason_sep = translate_raster_label("Step 0.5", sep)
        self.assertEqual(out_sep, "Bước 0.5")
        self.assertIsNone(reason_sep)

        # Dropping or spelling out a number is refused.
        bad = _DictTranslator({"Dense Layer (64)": "Lớp dày đặc (sáu mươi tư)"})
        out_bad, reason_bad = translate_raster_label("Dense Layer (64)", bad)
        self.assertIsNone(out_bad)
        self.assertEqual(reason_bad, "numbers_changed")

    def test_overlay_renders_vietnamese_preserves_border_and_untouched_ticks(self) -> None:
        img = np.full((220, 440, 3), 255, dtype=np.uint8)
        # Box 1: light blue fill, black border, "Initialization".
        cv2.rectangle(img, (20, 20), (240, 90), (220, 238, 255), thickness=-1)
        cv2.rectangle(img, (20, 20), (240, 90), (0, 0, 0), thickness=2)
        cv2.putText(img, "Initialization", (48, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (15, 20, 30), 2)

        # Box 2: mixed label with number "(64)" where translator drops the number -> must keep source!
        cv2.rectangle(img, (20, 120), (240, 190), (235, 248, 225), thickness=-1)
        cv2.rectangle(img, (20, 120), (240, 190), (0, 0, 0), thickness=2)
        cv2.putText(img, "Dense (64)", (52, 162), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (15, 20, 30), 2)

        # Axis tick on the right: "0.5" -> must never be touched!
        cv2.putText(img, "0.5", (320, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)

        def fake_ocr(_image: np.ndarray):
            return _fake_ocr_result(
                [
                    ((44, 40, 215, 68), "Initialization", 0.97),
                    ((48, 140, 205, 168), "Dense (64)", 0.96),
                    ((316, 86, 365, 115), "0.5", 0.99),
                ]
            )

        translator = _DictTranslator(
            {
                "Initialization": "Khởi tạo",
                "Dense (64)": "Lớp dày đặc",  # missing 64 -> refused!
            }
        )

        patch = process_figure_image(
            xref=76,
            image_bytes=_encode_png(img),
            ocr_engine=fake_ocr,
            translator=translator,
            font_path=self.font_path,
        )

        self.assertEqual(patch.translated_count, 1)
        self.assertEqual(patch.skipped_reasons.get("numbers_changed"), 1)
        self.assertEqual(patch.skipped_reasons.get("non_prose_or_numeric"), 1)
        self.assertIsNotNone(patch.png_bytes)

        rendered = _decode_rgb(patch.png_bytes)
        self.assertEqual(rendered.shape, img.shape)

        # Box 1 interior changed (Vietnamese drawn) and still contains dark ink pixels.
        box1_before = img[35:75, 40:220]
        box1_after = rendered[35:75, 40:220]
        self.assertFalse(np.array_equal(box1_before, box1_after))
        ink_count = int(np.count_nonzero(np.linalg.norm(box1_after.astype(float) - (220, 238, 255), axis=2) > 40))
        self.assertGreater(ink_count, 40)

        # Box 1 black border pixels stay completely intact!
        np.testing.assert_array_equal(rendered[20:22, 20:241], img[20:22, 20:241])
        np.testing.assert_array_equal(rendered[89:91, 20:241], img[89:91, 20:241])

        # Box 2 (rejected for dropped number) and axis tick "0.5" stay pixel-identical!
        np.testing.assert_array_equal(rendered[120:191, 20:241], img[120:191, 20:241])
        np.testing.assert_array_equal(rendered[80:125, 305:380], img[80:125, 305:380])

    def test_overflowing_translation_is_skipped_and_image_stays_unmodified(self) -> None:
        img = np.full((120, 240, 3), 255, dtype=np.uint8)
        # Very tight box around "True".
        cv2.rectangle(img, (80, 42), (138, 68), (240, 240, 240), thickness=-1)
        cv2.rectangle(img, (80, 42), (138, 68), (0, 0, 0), thickness=2)
        cv2.putText(img, "True", (88, 61), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)

        def fake_ocr(_image: np.ndarray):
            return _fake_ocr_result([((86, 46, 132, 63), "True", 0.96)])

        # Translation far too wide to fit inside the 54x24 box at >= 9px.
        translator = _DictTranslator({"True": "Điều kiện thỏa mãn hoàn toàn"})
        patch = process_figure_image(
            xref=12,
            image_bytes=_encode_png(img),
            ocr_engine=fake_ocr,
            translator=translator,
            font_path=self.font_path,
        )

        self.assertIsNone(patch.png_bytes)
        self.assertEqual(patch.translated_count, 0)
        self.assertEqual(patch.skipped_reasons.get("fit_overflow"), 1)


if __name__ == "__main__":
    unittest.main()
