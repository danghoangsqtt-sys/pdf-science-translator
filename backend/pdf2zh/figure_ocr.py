"""OCR and selective label overlay for raster figures, charts, and image tables.

This module is strictly separate from ``pdf2zh.ocr`` (which handles full-page
scans). It only inspects raster images embedded inside layout ``figure`` (or
unmatched raster ``table``) regions, reuses the verified offline RapidOCR
recogniser, translates short natural-language labels while keeping every
number/tick/unit/symbol/abbreviation untouched, and overlays Unicode text onto
a copy of the image using PyMuPDF + OpenCV (no extra dependencies).

Any ambiguous region (low OCR confidence, non-uniform background, overflowing
translation, changed numbers, missing font) fails closed and keeps the original
pixels byte-for-byte.
"""

from __future__ import annotations

import logging
import math
import os
import re
from asyncio import CancelledError
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pymupdf

from pdf2zh.ocr import OcrLine, recognise_image
from pdf2zh.rules import FIGURE_WORDS, is_figure_natural_text
from pdf2zh.translator import (
    TranslationServiceUnavailable,
    markers_intact,
    numbers_intact,
    restore_number_notation,
)

logger = logging.getLogger(__name__)

# Thresholds locked in docs/brainstorm/session-2026-11-12.md (E3 / D4).
MIN_FIGURE_IMAGE_WIDTH = 150
MIN_FIGURE_IMAGE_HEIGHT = 80
MIN_OCR_CONFIDENCE = 0.85
MAX_LABEL_WORDS = 6
MAX_BG_CHANNEL_STD = 18.0
MIN_LABEL_PIXEL_HEIGHT = 9
MAX_LABEL_ANGLE_DEG = 8.0
MIN_FOREGROUND_CONTRAST = 35.0
MIN_OVERLAY_FONT_PX = 9.0
MIN_FONT_SCALE_RATIO = 0.50
VIETNAMESE_LINE_HEIGHT = 1.18

# Operators, arrows, set notation, or variable-index syntax indicate math/code.
_MATH_SYNTAX_RE = re.compile(
    r"[=≤≥≈≠±×÷·∑∫√∞∝∀∃∈∉⊆⊂⊇⊃→←↔^_<>]"
)
_NUMERIC_TOKEN_RE = re.compile(
    r"^[+\-−]?\d+(?:[.,:/]\d+)*(?:[eE][+\-]?\d+)?%?$"
)
_NUMBER_PREFIX_UNIT_RE = re.compile(
    r"^[+\-−]?\d+(?:[.,]\d+)?\s*[A-Za-z°µμ%/]+$"
)
_ABBREV_OR_CODE_RE = re.compile(
    r"^(?:[A-Z0-9][A-Z0-9\-/+._]{0,9}|[a-z][A-Z][A-Za-z0-9]*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*)$"
)
_REFERENCE_LABEL_RE = re.compile(
    r"^(?:fig(?:ure)?\.?|eq(?:uation)?\.?|tab(?:le)?\.?|sec(?:tion)?\.?)\s*\(?\d+[a-z]?\)?$",
    re.IGNORECASE,
)
_UNIT_TOKENS = frozenset(
    {
        "ms", "us", "ns", "hz", "khz", "mhz", "ghz", "kw", "mw", "gw",
        "kwh", "mwh", "gwh", "wh", "db", "px", "pt", "mm", "cm", "km",
        "kg", "mg", "ml", "gb", "mb", "kb", "tb", "fps", "rpm", "ppm",
        "bar", "pa", "kpa", "mpa", "mol", "rad", "deg", "sec", "min",
        "hr", "hrs", "yr", "yrs", "mv", "kv", "ma", "ka", "nm", "um",
        "relu", "gelu", "elu", "silu", "tanh", "lstm", "gru", "cnn",
        "rnn", "mlp", "gan", "vae", "mape", "rmse", "mae", "mse",
        "smape", "nmae", "nrmse", "auc", "roc", "iou", "fps", "cpu",
        "gpu", "tpu", "ram", "vram", "adam", "sgd", "lbfgs",
    }
)
_GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")


@dataclass(frozen=True)
class RasterFigureCandidate:
    """An embedded raster image that sits inside a page's figure/image-table area."""

    page_index: int
    xref: int
    bbox_pdf: tuple[float, float, float, float]
    width_px: int
    height_px: int


@dataclass(frozen=True)
class RasterLabelCandidate:
    """One OCR-detected label inside a raster figure eligible for overlay."""

    text: str
    bbox_px: tuple[float, float, float, float]
    confidence: float
    bg_rgb: tuple[int, int, int]
    fg_rgb: tuple[int, int, int]
    fit_box_px: tuple[float, float, float, float]
    source_height_px: float


@dataclass(frozen=True)
class FittedLabelOverlay:
    """A translated label sized and positioned inside its safe box."""

    source_text: str
    translated_text: str
    lines: tuple[str, ...]
    font_size_px: float
    erase_box_px: tuple[float, float, float, float]
    fit_box_px: tuple[float, float, float, float]
    bg_rgb: tuple[int, int, int]
    fg_rgb: tuple[int, int, int]


@dataclass(frozen=True)
class FigureImagePatch:
    """Result of processing a single embedded raster figure image."""

    xref: int
    png_bytes: bytes | None
    translated_count: int = 0
    skipped_count: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class FigureOcrSummary:
    """Aggregated counts across all raster figures in a document."""

    images_processed: int = 0
    images_modified: int = 0
    labels_translated: int = 0
    labels_skipped: int = 0
    skipped_by_reason: Counter[str] = field(default_factory=Counter)


def _rect_overlap_ratio(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> float:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    inner_area = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if inner_area <= 0:
        return 0.0
    dx = max(0.0, min(ix1, ox1) - max(ix0, ox0))
    dy = max(0.0, min(iy1, oy1) - max(iy0, oy0))
    return (dx * dy) / inner_area


def _centre_inside(
    rect: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
) -> bool:
    cx = (rect[0] + rect[2]) / 2.0
    cy = (rect[1] + rect[3]) / 2.0
    return region[0] <= cx <= region[2] and region[1] <= cy <= region[3]


def extract_figure_image_candidates(
    page: pymupdf.Page,
    figure_bounds: Sequence[Sequence[float]],
    unmatched_table_bounds: Sequence[Sequence[float]] = (),
) -> list[RasterFigureCandidate]:
    """Return embedded raster images >= 150x80 px lying inside figure regions."""
    regions = [
        (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        for b in (*figure_bounds, *unmatched_table_bounds)
        if len(b) >= 4
    ]
    if not regions:
        return []

    page_index = int(getattr(page, "number", 0))
    candidates: list[RasterFigureCandidate] = []
    seen_xrefs: set[int] = set()
    for info in page.get_images(full=True):
        xref = int(info[0])
        if xref in seen_xrefs:
            continue
        width_px = int(info[2])
        height_px = int(info[3])
        if width_px < MIN_FIGURE_IMAGE_WIDTH or height_px < MIN_FIGURE_IMAGE_HEIGHT:
            continue
        rects = page.get_image_rects(xref)
        matched_rect: tuple[float, float, float, float] | None = None
        for rect in rects:
            box = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
            if any(
                _rect_overlap_ratio(box, region) >= 0.5 or _centre_inside(box, region)
                for region in regions
            ):
                matched_rect = box
                break
        if matched_rect is not None:
            seen_xrefs.add(xref)
            candidates.append(
                RasterFigureCandidate(
                    page_index=page_index,
                    xref=xref,
                    bbox_pdf=matched_rect,
                    width_px=width_px,
                    height_px=height_px,
                )
            )
    return candidates


def shared_outside_figure_xrefs(
    doc: pymupdf.Document,
    figure_xrefs_by_page: dict[int, set[int]],
) -> set[int]:
    """Identify xrefs also drawn on pages/areas outside approved figure candidates.

    Replacing a shared XObject (for example a repeated header or decorative
    banner) would alter pages outside the target figure, so shared xrefs stay
    untouched.
    """
    all_candidates = {xref for xrefs in figure_xrefs_by_page.values() for xref in xrefs}
    if not all_candidates:
        return set()
    usage_pages: dict[int, set[int]] = {xref: set() for xref in all_candidates}
    for pageno in range(doc.page_count):
        page = doc[pageno]
        for info in page.get_images(full=True):
            xref = int(info[0])
            if xref in usage_pages:
                usage_pages[xref].add(pageno)
    shared: set[int] = set()
    for xref, pages in usage_pages.items():
        approved_pages = {
            pageno for pageno, xrefs in figure_xrefs_by_page.items() if xref in xrefs
        }
        if pages - approved_pages:
            shared.add(xref)
    return shared


def _clean_token_for_check(token: str) -> str:
    return token.strip("()[]{}:;.,?!\"'“”‘’")


def _token_is_numeric_or_unit(token: str) -> bool:
    stripped = _clean_token_for_check(token)
    if not stripped:
        return True
    if _NUMERIC_TOKEN_RE.match(stripped):
        return True
    if _NUMBER_PREFIX_UNIT_RE.match(stripped):
        return True
    if stripped.lower() in _UNIT_TOKENS:
        return True
    if _GREEK_RE.search(stripped):
        return True
    if len(stripped) == 1 and stripped.isalpha():
        return True
    return False


def is_raster_label_translatable(text: str) -> bool:
    """Apply E3 + D4 rules to decide if an OCR label should be translated.

    Allows short natural-language labels (<= 6 words) from flowcharts, charts,
    and raster tables — including mixed labels such as ``Dense Layer (64)`` or
    ``N hour``. Refuses pure numbers, axis ticks, units, math expressions,
    variables, and standalone acronyms/codes (``MAPE``, ``ReLU``, ``x_i``).
    """
    value = " ".join(text.split())
    if not value:
        return False
    if _MATH_SYNTAX_RE.search(value):
        return False
    if _REFERENCE_LABEL_RE.match(value):
        return False

    words = value.split()
    if len(words) > MAX_LABEL_WORDS:
        return False

    # Flowchart single words or slash pairs ("True", "False", "Yes/No").
    bare = value.strip(".:?!").lower()
    if bare in FIGURE_WORDS:
        return True
    if "/" in bare:
        parts = [part.strip() for part in bare.split("/") if part.strip()]
        if parts and all(part in FIGURE_WORDS for part in parts):
            return True

    # If every token is numeric, a unit, a single variable, or an acronym/code, keep source.
    non_numeric_tokens: list[str] = []
    for token in words:
        if _token_is_numeric_or_unit(token):
            continue
        cleaned = _clean_token_for_check(token)
        if not cleaned:
            continue
        # Reject camel-case/all-caps acronyms unless they are known flowchart words.
        if cleaned.lower() in FIGURE_WORDS:
            non_numeric_tokens.append(cleaned)
            continue
        if _ABBREV_OR_CODE_RE.match(cleaned) and not cleaned.islower():
            continue
        if cleaned.lower() in _UNIT_TOKENS:
            continue
        non_numeric_tokens.append(cleaned)

    if not non_numeric_tokens:
        return False

    # Require at least one natural prose word on the cleaned text.
    prose_fragment = " ".join(non_numeric_tokens)
    if is_figure_natural_text(prose_fragment):
        return True

    # Allow hyphenated natural words such as "Multi-Head" when parts are real words.
    for token in non_numeric_tokens:
        if "-" in token:
            parts = [part for part in token.split("-") if part]
            if parts and any(is_figure_natural_text(part) for part in parts):
                return True
    return False


def _line_angle_degrees(line: OcrLine) -> float:
    first, second = line.polygon[0], line.polygon[1]
    angle = abs(math.degrees(math.atan2(second[1] - first[1], second[0] - first[0])))
    if angle > 180.0:
        angle = 360.0 - angle
    return min(angle, abs(180.0 - angle))


def sample_label_colors(
    image_rgb: np.ndarray,
    bbox_px: tuple[float, float, float, float],
    *,
    max_bg_std: float = MAX_BG_CHANNEL_STD,
) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    """Estimate (bg_rgb, fg_rgb) around a label; return None if background is non-uniform."""
    height, width = image_rgb.shape[:2]
    x0 = max(0, int(math.floor(bbox_px[0])))
    y0 = max(0, int(math.floor(bbox_px[1])))
    x1 = min(width, int(math.ceil(bbox_px[2])))
    y1 = min(height, int(math.ceil(bbox_px[3])))
    box_w = x1 - x0
    box_h = y1 - y0
    if box_w < 6 or box_h < MIN_LABEL_PIXEL_HEIGHT:
        return None

    margin = max(2, min(4, int(round(box_h * 0.15))))
    ox0 = max(0, x0 - margin)
    oy0 = max(0, y0 - margin)
    ox1 = min(width, x1 + margin)
    oy1 = min(height, y1 + margin)

    patch = image_rgb[oy0:oy1, ox0:ox1]
    ring_mask = np.ones((oy1 - oy0, ox1 - ox0), dtype=bool)
    ring_mask[(y0 - oy0):(y1 - oy0), (x0 - ox0):(x1 - ox0)] = False
    ring_pixels = patch[ring_mask].astype(np.float32)
    if ring_pixels.shape[0] < 16:
        return None

    # Allow up to 15% outlier pixels (e.g. a box border touching one tight edge)
    # while still rejecting gradients, grids, photos, and plot curves.
    bg_vec = np.median(ring_pixels, axis=0)
    ring_dists = np.linalg.norm(ring_pixels - bg_vec, axis=1)
    cutoff = float(np.percentile(ring_dists, 85))
    core_ring = ring_pixels[ring_dists <= cutoff]
    if core_ring.shape[0] < 12:
        return None

    channel_std = np.std(core_ring, axis=0)
    if float(np.max(channel_std)) > max_bg_std or float(np.percentile(ring_dists, 80)) > max_bg_std * 1.35:
        return None

    bg_vec = np.median(core_ring, axis=0)
    bg_rgb = (int(round(bg_vec[0])), int(round(bg_vec[1])), int(round(bg_vec[2])))

    inner = image_rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    distances = np.linalg.norm(inner - bg_vec, axis=1)
    max_dist = float(np.max(distances)) if distances.size else 0.0
    if max_dist < MIN_FOREGROUND_CONTRAST:
        return None

    threshold = max(MIN_FOREGROUND_CONTRAST * 0.8, 0.5 * max_dist)
    ink_pixels = inner[distances >= threshold]
    if ink_pixels.shape[0] < 6:
        return None

    fg_vec = np.median(ink_pixels, axis=0)
    if float(np.linalg.norm(fg_vec - bg_vec)) < MIN_FOREGROUND_CONTRAST:
        return None
    fg_rgb = (int(round(fg_vec[0])), int(round(fg_vec[1])), int(round(fg_vec[2])))
    return bg_rgb, fg_rgb


def _expand_uniform_fit_box(
    image_rgb: np.ndarray,
    bbox_px: tuple[float, float, float, float],
    bg_rgb: tuple[int, int, int],
    other_boxes: Sequence[tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    """Expand a label box horizontally/vertically inside its uniform fill only.

    Stops 2 px before any border/stroke/plot line and never crosses another OCR
    box, giving translated Vietnamese text room inside its own flowchart box.
    """
    height, width = image_rgb.shape[:2]
    x0, y0, x1, y1 = bbox_px
    ix0 = max(0, int(math.floor(x0)))
    iy0 = max(0, int(math.floor(y0)))
    ix1 = min(width, int(math.ceil(x1)))
    iy1 = min(height, int(math.ceil(y1)))
    box_w = max(1, ix1 - ix0)
    box_h = max(1, iy1 - iy0)

    bg_vec = np.array(bg_rgb, dtype=np.float32)
    color_tol = max(24.0, 1.5 * MAX_BG_CHANNEL_STD)
    max_horiz = min(int(box_w * 0.6), 80)
    max_vert = min(int(box_h * 0.35), 14)

    # Hard obstacle bounds from sibling OCR boxes on the same horizontal/vertical band.
    left_limit = max(0, ix0 - max_horiz)
    right_limit = min(width, ix1 + max_horiz)
    top_limit = max(0, iy0 - max_vert)
    bottom_limit = min(height, iy1 + max_vert)

    for ox0, oy0, ox1, oy1 in other_boxes:
        if oy1 >= iy0 and oy0 <= iy1:
            if ox1 <= ix0:
                left_limit = max(left_limit, int(math.ceil(ox1)) + 2)
            elif ox0 >= ix1:
                right_limit = min(right_limit, int(math.floor(ox0)) - 2)
        if ox1 >= ix0 and ox0 <= ix1:
            if oy1 <= iy0:
                top_limit = max(top_limit, int(math.ceil(oy1)) + 2)
            elif oy0 >= iy1:
                bottom_limit = min(bottom_limit, int(math.floor(oy0)) - 2)

    def _col_is_bg(col_x: int, cy0: int, cy1: int) -> bool:
        strip = image_rgb[cy0:cy1, col_x, :].astype(np.float32)
        if strip.size == 0:
            return False
        dists = np.linalg.norm(strip - bg_vec, axis=1)
        # Require every pixel in the column to match bg so thin legend swatches,
        # axis ticks, or connector arrows immediately halt expansion.
        return float(np.max(dists)) <= color_tol

    def _row_is_bg(row_y: int, cx0: int, cx1: int) -> bool:
        strip = image_rgb[row_y, cx0:cx1, :].astype(np.float32)
        if strip.size == 0:
            return False
        dists = np.linalg.norm(strip - bg_vec, axis=1)
        return float(np.max(dists)) <= color_tol

    new_x0 = ix0
    for cx in range(ix0 - 1, left_limit - 1, -1):
        if not _col_is_bg(cx, iy0, iy1):
            break
        new_x0 = cx
    if new_x0 < ix0:
        new_x0 = min(ix0, new_x0 + 2)

    new_x1 = ix1
    for cx in range(ix1, right_limit):
        if not _col_is_bg(cx, iy0, iy1):
            break
        new_x1 = cx + 1
    if new_x1 > ix1:
        new_x1 = max(ix1, new_x1 - 2)

    new_y0 = iy0
    for cy in range(iy0 - 1, top_limit - 1, -1):
        if not _row_is_bg(cy, new_x0, new_x1):
            break
        new_y0 = cy
    if new_y0 < iy0:
        new_y0 = min(iy0, new_y0 + 1)

    new_y1 = iy1
    for cy in range(iy1, bottom_limit):
        if not _row_is_bg(cy, new_x0, new_x1):
            break
        new_y1 = cy + 1
    if new_y1 > iy1:
        new_y1 = max(iy1, new_y1 - 1)

    return float(new_x0), float(new_y0), float(new_x1), float(new_y1)


def _strip_is_uniform_bg(
    image_rgb: np.ndarray,
    upper_box: tuple[float, float, float, float],
    lower_box: tuple[float, float, float, float],
    bg_rgb: tuple[int, int, int],
) -> bool:
    """Return True if no border line separates two vertically stacked OCR lines."""
    height, width = image_rgb.shape[:2]
    gy0 = max(0, int(math.floor(upper_box[3])))
    gy1 = min(height, int(math.ceil(lower_box[1])))
    if gy1 <= gy0:
        return True
    gx0 = max(0, int(math.floor(max(upper_box[0], lower_box[0]))))
    gx1 = min(width, int(math.ceil(min(upper_box[2], lower_box[2]))))
    if gx1 <= gx0:
        return False
    strip = image_rgb[gy0:gy1, gx0:gx1].reshape(-1, 3).astype(np.float32)
    bg_vec = np.array(bg_rgb, dtype=np.float32)
    dists = np.linalg.norm(strip - bg_vec, axis=1)
    return float(np.percentile(dists, 90)) <= max(26.0, 1.5 * MAX_BG_CHANNEL_STD)


def _has_left_swatch(
    image_rgb: np.ndarray,
    bbox_px: tuple[float, float, float, float],
    bg_rgb: tuple[int, int, int],
) -> bool:
    """Detect a chart-legend line swatch or bullet immediately left of a label.

    A vertical box border runs continuously across the top and bottom edges of
    the strip, whereas a horizontal legend swatch or marker sits inside the
    middle band with background above and below it.
    """
    height, width = image_rgb.shape[:2]
    x0, y0, _, y1 = bbox_px
    bh = max(1.0, y1 - y0)
    sx1 = max(0, int(math.floor(x0)) - 2)
    sx0 = max(0, int(math.floor(x0 - 1.8 * bh)))
    sy0 = max(0, int(math.floor(y0)))
    sy1 = min(height, int(math.ceil(y1)))
    if sx1 - sx0 < 4 or sy1 - sy0 < 5:
        return False
    patch = image_rgb[sy0:sy1, sx0:sx1].astype(np.float32)
    bg_vec = np.array(bg_rgb, dtype=np.float32)
    ink = np.linalg.norm(patch - bg_vec, axis=2) >= MIN_FOREGROUND_CONTRAST
    # Exclude columns that are continuous vertical strokes (e.g. a box border).
    vertical_stroke_cols = np.mean(ink, axis=0) >= 0.75
    if np.any(vertical_stroke_cols):
        # Keep only pixels strictly to the right of any enclosing box border.
        border_right = int(np.max(np.flatnonzero(vertical_stroke_cols))) + 1
        ink = ink[:, border_right:]
        if ink.shape[1] < 3:
            return False
    row_has_ink = np.any(ink, axis=1)
    if row_has_ink[0] and row_has_ink[-1]:
        return False
    return int(np.count_nonzero(ink)) >= 4


def _merge_stacked_ocr_lines(
    image_rgb: np.ndarray,
    lines: Sequence[OcrLine],
) -> list[tuple[OcrLine, tuple[int, int, int], tuple[int, int, int], float]]:
    """Group multi-line labels sharing one uniform box before eligibility checks."""
    ordered = sorted(lines, key=lambda item: (item.bbox[1], item.bbox[0]))
    groups: list[dict[str, Any]] = []
    for line in ordered:
        colors = sample_label_colors(image_rgb, line.bbox)
        if colors is None:
            groups.append({"lines": [line], "colors": None})
            continue
        bg_rgb, fg_rgb = colors
        lx0, ly0, lx1, ly1 = line.bbox
        lh = max(1.0, ly1 - ly0)
        lw = max(1.0, lx1 - lx0)

        merged = False
        for group in reversed(groups):
            if group["colors"] is None:
                continue
            prev = group["lines"][-1]
            px0, py0, px1, py1 = prev.bbox
            ph = max(1.0, py1 - py0)
            pw = max(1.0, px1 - px0)
            gap = ly0 - py1
            overlap_x = min(lx1, px1) - max(lx0, px0)
            prev_bg, _ = group["colors"]
            bg_dist = math.dist(bg_rgb, prev_bg)
            combined_words = len(" ".join(item.text for item in group["lines"]).split()) + len(
                line.text.split()
            )
            # Keep separate chart-legend rows apart: each carries its own left
            # swatch (coloured line/marker) or forms a left-aligned list on white.
            legend_rows = _has_left_swatch(image_rgb, prev.bbox, prev_bg) and _has_left_swatch(
                image_rgb, line.bbox, bg_rgb
            )
            left_aligned_uncentred = (
                abs(lx0 - px0) <= 0.25 * max(lh, ph)
                and abs(((lx0 + lx1) / 2.0) - ((px0 + px1) / 2.0)) > 0.35 * max(lh, ph)
                and min(bg_rgb) >= 240
            )
            if (
                not legend_rows
                and not left_aligned_uncentred
                and combined_words <= MAX_LABEL_WORDS
                and bg_dist <= 22.0
                and max(lh, ph) <= 1.35 * min(lh, ph)
                and -0.2 * lh <= gap <= 0.65 * max(lh, ph)
                and overlap_x >= 0.3 * min(lw, pw)
                and _strip_is_uniform_bg(image_rgb, prev.bbox, line.bbox, prev_bg)
            ):
                group["lines"].append(line)
                merged = True
                break
        if not merged:
            groups.append({"lines": [line], "colors": (bg_rgb, fg_rgb)})

    results: list[tuple[OcrLine, tuple[int, int, int], tuple[int, int, int], float]] = []
    for group in groups:
        if group["colors"] is None:
            continue
        items: list[OcrLine] = group["lines"]
        x0 = min(item.bbox[0] for item in items)
        y0 = min(item.bbox[1] for item in items)
        x1 = max(item.bbox[2] for item in items)
        y1 = max(item.bbox[3] for item in items)
        text = " ".join(item.text.strip() for item in items)
        conf = min(item.confidence for item in items)
        avg_line_h = float(np.median([item.bbox[3] - item.bbox[1] for item in items]))
        bg_rgb, fg_rgb = group["colors"]
        combined_line = OcrLine(
            text=text,
            polygon=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
            confidence=conf,
        )
        results.append((combined_line, bg_rgb, fg_rgb, avg_line_h))
    return results


def detect_raster_labels(
    image_rgb: np.ndarray,
    ocr_engine: Callable[[np.ndarray], Any],
    *,
    min_confidence: float = MIN_OCR_CONFIDENCE,
) -> tuple[list[RasterLabelCandidate], Counter[str]]:
    """Run OCR on a raster figure and return only E3/D4-eligible labels + skip counts."""
    skipped: Counter[str] = Counter()
    raw_lines = recognise_image(ocr_engine, image_rgb)
    if not raw_lines:
        return [], skipped

    passing_lines: list[OcrLine] = []
    all_raw_boxes: list[tuple[float, float, float, float]] = []
    for line in raw_lines:
        all_raw_boxes.append(line.bbox)
        bx0, by0, bx1, by1 = line.bbox
        if line.confidence < min_confidence:
            skipped["low_confidence"] += 1
            continue
        if (by1 - by0) < MIN_LABEL_PIXEL_HEIGHT:
            skipped["too_small"] += 1
            continue
        if _line_angle_degrees(line) > MAX_LABEL_ANGLE_DEG:
            skipped["rotated"] += 1
            continue
        passing_lines.append(line)

    if not passing_lines:
        return [], skipped

    # Track lines rejected specifically for non-uniform backgrounds.
    uniform_lines: list[OcrLine] = []
    for line in passing_lines:
        if sample_label_colors(image_rgb, line.bbox) is None:
            skipped["non_uniform_bg"] += 1
        else:
            uniform_lines.append(line)

    grouped = _merge_stacked_ocr_lines(image_rgb, uniform_lines)
    candidates: list[RasterLabelCandidate] = []
    for combined, bg_rgb, fg_rgb, line_height in grouped:
        if not is_raster_label_translatable(combined.text):
            skipped["non_prose_or_numeric"] += 1
            continue
        other_boxes = [
            box for box in all_raw_boxes
            if not (
                box[0] >= combined.bbox[0] - 1.0
                and box[1] >= combined.bbox[1] - 1.0
                and box[2] <= combined.bbox[2] + 1.0
                and box[3] <= combined.bbox[3] + 1.0
            )
        ]
        fit_box = _expand_uniform_fit_box(image_rgb, combined.bbox, bg_rgb, other_boxes)
        candidates.append(
            RasterLabelCandidate(
                text=combined.text,
                bbox_px=combined.bbox,
                confidence=combined.confidence,
                bg_rgb=bg_rgb,
                fg_rgb=fg_rgb,
                fit_box_px=fit_box,
                source_height_px=line_height,
            )
        )
    return candidates, skipped


def resolve_figure_font_path(font_path: str | Path | None = None) -> Path | None:
    """Resolve an embedded Unicode TrueType font for Vietnamese raster overlays."""
    candidates: list[Path] = []
    if font_path is not None:
        candidates.append(Path(font_path))
    env_font = os.environ.get("PDF_TRANSLATE_OCR_FONT", "").strip()
    if env_font:
        candidates.append(Path(env_font))
    backend_root = Path(__file__).resolve().parents[1]
    candidates.extend(
        [
            backend_root / "app" / "fonts" / "BeVietnamPro-Regular.ttf",
            backend_root / "app" / "assets" / "GoNotoKurrent-Regular.ttf",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _clean_short_translation(source: str, translated: str) -> str:
    value = " ".join(translated.split()).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("`", '"', "'"):
        value = value[1:-1].strip()
    if value.endswith(".") and not source.rstrip().endswith("."):
        value = value[:-1].rstrip()
    return value


def translate_raster_label(
    text: str,
    translator: Any,
) -> tuple[str | None, str | None]:
    """Translate one short figure label, refusing changed numbers or implausible replies."""
    try:
        raw = translator.translate(text)
    except TranslationServiceUnavailable:
        raise
    except Exception as error:
        logger.debug("Figure label translation skipped for %r: %s", text, error)
        return None, "translation_failed"

    if not isinstance(raw, str) or not raw.strip():
        return None, "translation_failed"

    cleaned = _clean_short_translation(text, raw)
    cleaned = restore_number_notation(text, cleaned)
    if not cleaned:
        return None, "translation_failed"
    if cleaned.casefold() == text.casefold():
        return None, "unchanged"
    if not markers_intact(text, cleaned):
        return None, "markers_changed"
    if not numbers_intact(text, cleaned):
        return None, "numbers_changed"
    max_len = max(int(len(text) * 2.5) + 12, 48)
    if len(cleaned) > max_len:
        return None, "implausible"
    return cleaned, None


def _candidate_line_splits(text: str) -> list[tuple[str, ...]]:
    words = text.split()
    splits: list[tuple[str, ...]] = [(text,)]
    if len(words) < 2:
        return splits
    best_two: tuple[str, str] | None = None
    best_score = float("inf")
    for idx in range(1, len(words)):
        left = " ".join(words[:idx])
        right = " ".join(words[idx:])
        score = max(len(left), len(right))
        if score < best_score:
            best_score = score
            best_two = (left, right)
    if best_two is not None:
        splits.append(best_two)
    return splits


def fit_label_layout(
    text: str,
    fit_box_px: tuple[float, float, float, float],
    source_height_px: float,
    font: pymupdf.Font,
) -> tuple[tuple[str, ...], float] | None:
    """Find the largest readable font size (1 or 2 lines) that fits inside fit_box_px."""
    box_w = fit_box_px[2] - fit_box_px[0]
    box_h = fit_box_px[3] - fit_box_px[1]
    if box_w < 8.0 or box_h < MIN_OVERLAY_FONT_PX:
        return None

    min_size = max(MIN_OVERLAY_FONT_PX, source_height_px * MIN_FONT_SCALE_RATIO)
    max_size = max(min_size, min(source_height_px * 1.05, box_h * 0.92))
    usable_w = max(4.0, box_w - 2.0)

    def _max_size_for(lines: tuple[str, ...]) -> float | None:
        size = max_size
        while size >= min_size - 1e-6:
            line_h = size * VIETNAMESE_LINE_HEIGHT
            total_h = line_h * len(lines)
            if total_h <= box_h + 1.0:
                widths = [float(font.text_length(line, fontsize=size)) for line in lines]
                if max(widths) <= usable_w:
                    return round(size, 2)
            size -= 0.5
        return None

    splits = _candidate_line_splits(text)
    single_size = _max_size_for(splits[0])
    two_size = _max_size_for(splits[1]) if len(splits) > 1 else None

    if single_size is None and two_size is None:
        return None
    if single_size is not None and two_size is not None:
        if single_size >= two_size * 0.85:
            return splits[0], single_size
        return splits[1], two_size
    if single_size is not None:
        return splits[0], single_size
    return splits[1], two_size


def render_translated_figure_image(
    image_rgb: np.ndarray,
    overlays: Sequence[FittedLabelOverlay],
    font_path: Path,
) -> bytes:
    """Paint uniform background boxes and crisp Unicode labels onto an RGB image copy."""
    canvas = image_rgb.copy()
    height, width = canvas.shape[:2]

    for overlay in overlays:
        ex0 = max(0, int(math.floor(overlay.erase_box_px[0])))
        ey0 = max(0, int(math.floor(overlay.erase_box_px[1])))
        ex1 = min(width, int(math.ceil(overlay.erase_box_px[2])))
        ey1 = min(height, int(math.ceil(overlay.erase_box_px[3])))
        canvas[ey0:ey1, ex0:ex1] = overlay.bg_rgb

    ok, encoded = cv2.imencode(".png", cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("Could not encode base figure image to PNG")
    base_png = encoded.tobytes()

    font = pymupdf.Font(fontfile=str(font_path))
    ascender = float(getattr(font, "ascender", 0.85))
    descender = float(getattr(font, "descender", -0.22))

    with pymupdf.open() as temp_doc:
        page = temp_doc.new_page(width=float(width), height=float(height))
        page.insert_image(pymupdf.Rect(0.0, 0.0, float(width), float(height)), stream=base_png)
        page.insert_font(fontname="figfont", fontfile=str(font_path))

        for overlay in overlays:
            fx0, fy0, fx1, fy1 = overlay.fit_box_px
            fs = overlay.font_size_px
            line_h = fs * VIETNAMESE_LINE_HEIGHT
            block_h = line_h * len(overlay.lines)
            top_y = fy0 + max(0.0, (fy1 - fy0 - block_h) / 2.0)
            baseline_offset = (line_h + fs * (ascender + descender)) / 2.0
            color = (
                overlay.fg_rgb[0] / 255.0,
                overlay.fg_rgb[1] / 255.0,
                overlay.fg_rgb[2] / 255.0,
            )
            for line_index, text_line in enumerate(overlay.lines):
                line_w = float(font.text_length(text_line, fontsize=fs))
                tx = fx0 + max(0.0, (fx1 - fx0 - line_w) / 2.0)
                ty = top_y + line_index * line_h + baseline_offset
                page.insert_text(
                    pymupdf.Point(tx, ty),
                    text_line,
                    fontname="figfont",
                    fontsize=fs,
                    color=color,
                )

        pix = page.get_pixmap(dpi=72, alpha=False)
        return pix.tobytes("png")


def _decode_image_rgb(image_bytes: bytes) -> np.ndarray | None:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        return None
    if decoded.ndim == 2:
        return cv2.cvtColor(decoded, cv2.COLOR_GRAY2RGB)
    if decoded.ndim == 3 and decoded.shape[2] == 3:
        return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    if decoded.ndim == 3 and decoded.shape[2] == 4:
        alpha = decoded[:, :, 3]
        # Skip images with significant semi-transparency to avoid breaking masks.
        if int(np.count_nonzero(alpha < 250)) > 0.05 * alpha.size:
            return None
        return cv2.cvtColor(decoded[:, :, :3], cv2.COLOR_BGR2RGB)
    return None


def process_figure_image(
    xref: int,
    image_bytes: bytes,
    ocr_engine: Callable[[np.ndarray], Any],
    translator: Any,
    *,
    font_path: str | Path | None = None,
    min_confidence: float = MIN_OCR_CONFIDENCE,
) -> FigureImagePatch:
    """Run the full E3/D4 pipeline on one raster figure image.

    Returns ``png_bytes=None`` whenever no label safely translates and fits,
    leaving the embedded PDF image untouched.
    """
    resolved_font = resolve_figure_font_path(font_path)
    if resolved_font is None:
        return FigureImagePatch(xref=xref, png_bytes=None, skipped_reasons={"missing_font": 1})

    image_rgb = _decode_image_rgb(image_bytes)
    if image_rgb is None:
        return FigureImagePatch(xref=xref, png_bytes=None, skipped_reasons={"unsupported_image": 1})

    height, width = image_rgb.shape[:2]
    if width < MIN_FIGURE_IMAGE_WIDTH or height < MIN_FIGURE_IMAGE_HEIGHT:
        return FigureImagePatch(xref=xref, png_bytes=None, skipped_reasons={"image_too_small": 1})

    candidates, skipped = detect_raster_labels(
        image_rgb, ocr_engine, min_confidence=min_confidence
    )
    if not candidates:
        return FigureImagePatch(
            xref=xref,
            png_bytes=None,
            translated_count=0,
            skipped_count=sum(skipped.values()),
            skipped_reasons=dict(skipped),
        )

    font = pymupdf.Font(fontfile=str(resolved_font))
    overlays: list[FittedLabelOverlay] = []
    for candidate in candidates:
        translated, reason = translate_raster_label(candidate.text, translator)
        if translated is None:
            skipped[reason or "translation_failed"] += 1
            continue
        fitted = fit_label_layout(
            translated,
            candidate.fit_box_px,
            candidate.source_height_px,
            font,
        )
        if fitted is None:
            skipped["fit_overflow"] += 1
            continue
        lines, font_size_px = fitted
        # Erase tight around the original text (padded 1 px for anti-aliased rims),
        # clamped strictly inside fit_box_px so box borders stay intact.
        ex0 = max(candidate.fit_box_px[0], candidate.bbox_px[0] - 1.0)
        ey0 = max(candidate.fit_box_px[1], candidate.bbox_px[1] - 1.0)
        ex1 = min(candidate.fit_box_px[2], candidate.bbox_px[2] + 1.0)
        ey1 = min(candidate.fit_box_px[3], candidate.bbox_px[3] + 1.0)
        overlays.append(
            FittedLabelOverlay(
                source_text=candidate.text,
                translated_text=translated,
                lines=lines,
                font_size_px=font_size_px,
                erase_box_px=(ex0, ey0, ex1, ey1),
                fit_box_px=candidate.fit_box_px,
                bg_rgb=candidate.bg_rgb,
                fg_rgb=candidate.fg_rgb,
            )
        )

    if not overlays:
        return FigureImagePatch(
            xref=xref,
            png_bytes=None,
            translated_count=0,
            skipped_count=sum(skipped.values()),
            skipped_reasons=dict(skipped),
        )

    png_bytes = render_translated_figure_image(image_rgb, overlays, resolved_font)
    return FigureImagePatch(
        xref=xref,
        png_bytes=png_bytes,
        translated_count=len(overlays),
        skipped_count=sum(skipped.values()),
        skipped_reasons=dict(skipped),
    )


def _replace_image_xref(doc: pymupdf.Document, xref: int, png_bytes: bytes) -> None:
    """Replace an image XObject in place without mutating target page resources or contents."""
    scratch_page = doc.new_page(width=1.0, height=1.0)
    try:
        new_xref = scratch_page.insert_image(scratch_page.rect, stream=png_bytes)
        doc.xref_copy(new_xref, xref)
    finally:
        doc.delete_page(scratch_page.number)


def translate_document_figure_images(
    doc: pymupdf.Document,
    figure_bounds_by_page: dict[int, Sequence[Sequence[float]]],
    *,
    ocr_engine: Callable[[np.ndarray], Any],
    translator: Any,
    unmatched_table_bounds_by_page: dict[int, Sequence[Sequence[float]]] | None = None,
    preextracted_candidates: dict[int, list[RasterFigureCandidate]] | None = None,
    skip_pages: Iterable[int] = (),
    font_path: str | Path | None = None,
    cancellation_event: Any = None,
) -> FigureOcrSummary:
    """Replace eligible raster figure images in ``doc`` in place; never touches source file."""
    summary = FigureOcrSummary()
    skip_set = set(skip_pages)
    unmatched_tables = unmatched_table_bounds_by_page or {}

    candidates_by_page: dict[int, list[RasterFigureCandidate]] = {}
    figure_xrefs_by_page: dict[int, set[int]] = {}
    if preextracted_candidates is not None:
        for pageno, candidates in preextracted_candidates.items():
            if pageno in skip_set or pageno < 0 or pageno >= doc.page_count:
                continue
            if candidates:
                candidates_by_page[pageno] = list(candidates)
                figure_xrefs_by_page[pageno] = {item.xref for item in candidates}
    else:
        all_pages = sorted(set(figure_bounds_by_page) | set(unmatched_tables))
        for pageno in all_pages:
            if pageno in skip_set or pageno < 0 or pageno >= doc.page_count:
                continue
            page = doc[pageno]
            candidates = extract_figure_image_candidates(
                page,
                figure_bounds_by_page.get(pageno, ()),
                unmatched_table_bounds=unmatched_tables.get(pageno, ()),
            )
            if candidates:
                candidates_by_page[pageno] = candidates
                figure_xrefs_by_page[pageno] = {item.xref for item in candidates}

    if not candidates_by_page:
        return summary

    shared_xrefs = shared_outside_figure_xrefs(doc, figure_xrefs_by_page)
    processed_xrefs: set[int] = set()

    for pageno in sorted(candidates_by_page):
        if cancellation_event is not None and cancellation_event.is_set():
            raise CancelledError("task cancelled")
        page = doc[pageno]
        for candidate in candidates_by_page[pageno]:
            if cancellation_event is not None and cancellation_event.is_set():
                raise CancelledError("task cancelled")
            if candidate.xref in shared_xrefs or candidate.xref in processed_xrefs:
                continue
            processed_xrefs.add(candidate.xref)
            extracted = doc.extract_image(candidate.xref)
            if not extracted or not extracted.get("image"):
                continue
            summary.images_processed += 1
            try:
                patch = process_figure_image(
                    candidate.xref,
                    extracted["image"],
                    ocr_engine,
                    translator,
                    font_path=font_path,
                )
            except TranslationServiceUnavailable:
                logger.warning("Stopping raster figure translation: translation service unavailable")
                return summary
            summary.labels_translated += patch.translated_count
            summary.labels_skipped += patch.skipped_count
            summary.skipped_by_reason.update(patch.skipped_reasons)
            if patch.png_bytes is not None:
                _replace_image_xref(doc, candidate.xref, patch.png_bytes)
                summary.images_modified += 1
    return summary
