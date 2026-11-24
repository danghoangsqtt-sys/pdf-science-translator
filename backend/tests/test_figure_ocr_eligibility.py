"""Unit tests for P11-T1: raster figure candidate selection, E3/D4 filtering, and color sampling."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import cv2
import numpy as np
import pymupdf

from pdf2zh.figure_ocr import (
    detect_raster_labels,
    extract_figure_image_candidates,
    is_raster_label_translatable,
    sample_label_colors,
    shared_outside_figure_xrefs,
)


def _encode_png(image_rgb: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
    assert ok
    return buf.tobytes()


def _fake_ocr_result(entries: list[tuple[tuple[float, float, float, float], str, float]]):
    boxes = []
    texts = []
    scores = []
    for (x0, y0, x1, y1), text, score in entries:
        boxes.append([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
        texts.append(text)
        scores.append(score)
    return SimpleNamespace(boxes=boxes, txts=texts, scores=scores)


class RasterFigureEligibilityTests(unittest.TestCase):
    def test_extract_candidates_respects_size_and_figure_bounds(self) -> None:
        large_img = np.full((120, 220, 3), 240, dtype=np.uint8)
        small_img = np.full((60, 100, 3), 240, dtype=np.uint8)
        outside_img = np.full((120, 220, 3), 200, dtype=np.uint8)

        with pymupdf.open() as doc:
            page = doc.new_page(width=595, height=842)
            page.insert_image(pymupdf.Rect(50, 100, 300, 250), stream=_encode_png(large_img))
            page.insert_image(pymupdf.Rect(320, 120, 420, 180), stream=_encode_png(small_img))
            page.insert_image(pymupdf.Rect(50, 500, 300, 650), stream=_encode_png(outside_img))

            candidates = extract_figure_image_candidates(
                page,
                figure_bounds=[(40, 90, 450, 270)],
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual((candidates[0].width_px, candidates[0].height_px), (220, 120))

    def test_shared_xref_outside_figure_is_excluded(self) -> None:
        logo = np.full((100, 200, 3), 230, dtype=np.uint8)
        png = _encode_png(logo)
        with pymupdf.open() as doc:
            doc.new_page(width=595, height=842)
            doc.new_page(width=595, height=842)
            xref = doc[0].insert_image(pymupdf.Rect(50, 100, 250, 200), stream=png)
            # Reuse the same image xref on page 2 (outside any figure).
            doc[1].insert_image(pymupdf.Rect(50, 20, 250, 120), xref=xref)

            shared = shared_outside_figure_xrefs(doc, {0: {xref}})

        self.assertIn(xref, shared)

    def test_d4_label_filter_rejects_numbers_units_symbols_and_acronyms(self) -> None:
        rejected = [
            "24",
            "0.5",
            "-10%",
            "1e-4",
            "100-200",
            "10 ms",
            "50 kW",
            "kW",
            "x_i",
            "f(s) <= f(x)",
            "N = 100",
            "MAPE",
            "RMSE",
            "ReLU",
            "LSTM",
            "Fig. 1",
            "Eq. (2)",
            "This label has far more than six prose words inside",
        ]
        for text in rejected:
            with self.subTest(rejected=text):
                self.assertFalse(is_raster_label_translatable(text))

    def test_d4_label_filter_accepts_flowchart_and_chart_labels(self) -> None:
        accepted = [
            "Initialization",
            "Mutation",
            "Crossover",
            "Selection",
            "Termination Condition",
            "Optimal Solution",
            "True",
            "False",
            "Yes/No",
            "Dense Layer (64)",
            "Input Data",
            "Multi-Head Attention",
            "N hour",
            "Real value",
            "Predicted value",
        ]
        for text in accepted:
            with self.subTest(accepted=text):
                self.assertTrue(is_raster_label_translatable(text))

    def test_sample_label_colors_accepts_uniform_light_and_dark_boxes(self) -> None:
        # Light blue box with dark text.
        light_img = np.full((120, 260, 3), (210, 230, 250), dtype=np.uint8)
        cv2.putText(light_img, "Init", (60, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 25, 30), 2)
        colors_light = sample_label_colors(light_img, (55, 45, 130, 80))
        self.assertIsNotNone(colors_light)
        bg_l, fg_l = colors_light
        self.assertLess(abs(bg_l[0] - 210) + abs(bg_l[1] - 230) + abs(bg_l[2] - 250), 10)
        self.assertLess(fg_l[0], 90)

        # Dark navy box with white text.
        dark_img = np.full((120, 260, 3), (25, 45, 85), dtype=np.uint8)
        cv2.putText(dark_img, "Init", (60, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (250, 250, 250), 2)
        colors_dark = sample_label_colors(dark_img, (55, 45, 130, 80))
        self.assertIsNotNone(colors_dark)
        bg_d, fg_d = colors_dark
        self.assertLess(bg_d[0], 45)
        self.assertGreater(fg_d[0], 180)

    def test_sample_label_colors_rejects_gradient_and_crossed_lines(self) -> None:
        # Strong horizontal gradient across the label ring.
        grad = np.zeros((120, 260, 3), dtype=np.uint8)
        for col in range(260):
            val = int(col * 255 / 259)
            grad[:, col] = (val, 255 - val, 128)
        cv2.putText(grad, "Label", (60, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
        self.assertIsNone(sample_label_colors(grad, (55, 45, 155, 80)))

        # High-contrast checkerboard/grid behind label.
        noisy = np.full((120, 260, 3), 255, dtype=np.uint8)
        noisy[::4, :] = (20, 20, 20)
        noisy[:, ::4] = (20, 20, 20)
        self.assertIsNone(sample_label_colors(noisy, (55, 45, 155, 80)))

    def test_detect_raster_labels_merges_multiline_box_and_counts_skips(self) -> None:
        img = np.full((180, 360, 3), 255, dtype=np.uint8)
        # Flowchart box with solid fill and black border.
        cv2.rectangle(img, (20, 20), (220, 100), (220, 238, 255), thickness=-1)
        cv2.rectangle(img, (20, 20), (220, 100), (0, 0, 0), thickness=2)
        cv2.putText(img, "Termination", (45, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (15, 15, 15), 2)
        cv2.putText(img, "Condition", (55, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (15, 15, 15), 2)
        # Axis tick on the right.
        cv2.putText(img, "0.5", (270, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (15, 15, 15), 2)

        def fake_ocr(_image: np.ndarray):
            return _fake_ocr_result(
                [
                    ((42, 34, 190, 56), "Termination", 0.96),
                    ((52, 64, 175, 86), "Condition", 0.94),
                    ((268, 42, 315, 64), "0.5", 0.98),
                    ((250, 120, 340, 145), "LowConf", 0.62),
                ]
            )

        candidates, skipped = detect_raster_labels(img, fake_ocr)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].text, "Termination Condition")
        self.assertGreaterEqual(skipped["low_confidence"], 1)
        self.assertGreaterEqual(skipped["non_prose_or_numeric"], 1)
        # Fit box stays strictly inside the black border (x0 >= 22, x1 <= 218).
        self.assertGreaterEqual(candidates[0].fit_box_px[0], 22.0)
        self.assertLessEqual(candidates[0].fit_box_px[2], 218.0)

    def test_chart_legend_rows_with_left_swatches_stay_separate_and_keep_swatches(self) -> None:
        img = np.full((120, 300, 3), 255, dtype=np.uint8)
        # Blue swatch + "real value", orange swatch + "predicted value" on white legend.
        cv2.line(img, (25, 34), (55, 34), (31, 119, 180), thickness=2)
        cv2.putText(img, "real value", (68, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1)
        cv2.line(img, (25, 62), (55, 62), (255, 127, 14), thickness=2)
        cv2.putText(img, "predicted value", (68, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 1)

        def fake_ocr(_image: np.ndarray):
            return _fake_ocr_result(
                [
                    ((66, 25, 165, 43), "real value", 0.99),
                    ((66, 53, 215, 71), "predicted value", 0.99),
                ]
            )

        candidates, _ = detect_raster_labels(img, fake_ocr)
        self.assertEqual([c.text for c in candidates], ["real value", "predicted value"])
        # Expansion leftward must stop cleanly to the right of the swatches (x > 55).
        for candidate in candidates:
            self.assertGreater(candidate.fit_box_px[0], 55.0)


if __name__ == "__main__":
    unittest.main()
