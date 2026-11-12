"""Preservation rules that distinguish the Code4Life PDF translation core."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

FORMULA_FONT_PATTERN = re.compile(
    r"(CM[^R]|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|"
    r"stmary|.*Mono|.*Code|.*Sym|.*Math|.*Typewriter|Cousine|Consolas|Menlo|"
    r"Monaco|Inconsolata|Source.?Code|Fira.?Code|DejaVu.?Sans.?Mono|"
    r"Liberation.?Mono|Courier)"
)

MATH_OPERATOR_PATTERN = re.compile(
    r"[=≤≥≈≠±×÷·∑∫√∞∝+*/^]"
)
PROSE_WORD_PATTERN = re.compile(r"[a-z]{3,}")
MATH_FUNCTION_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:sin|cos|tan|cot|sec|csc|log|ln|exp|min|max|lim|det|mod)(?![A-Za-z])",
    re.IGNORECASE,
)
STACKED_TOKEN_PATTERN = re.compile(
    r"[A-Za-z\u0370-\u03ff][A-Za-z\u0370-\u03ff0-9%]*"
)

BULLET_CHARACTERS = frozenset(
    ("•", "■", "□", "▪", "▸", "▹", "►", "▶", "●", "○", "◆", "◇", "★", "☆", "‣", "⬤")
)

PRIVATE_USE_BULLETS = frozenset(("\uf0b7", "\uf0d8", "\uf0fc"))

LANGUAGE_LINE_HEIGHT = {
    "zh-cn": 1.4,
    "zh-tw": 1.4,
    "zh-hans": 1.4,
    "zh-hant": 1.4,
    "zh": 1.4,
    "ja": 1.1,
    "ko": 1.2,
    "en": 1.2,
    "ar": 1.0,
    "ru": 0.8,
    "uk": 0.8,
    "ta": 0.8,
    "vi": 1.2,
}

# Measured ink extents, not preferences: see min_line_height_for_language.
DEFAULT_MIN_LINE_HEIGHT = 0.95
LANGUAGE_MIN_LINE_HEIGHT = {
    "vi": 1.10,
}


@dataclass(frozen=True)
class PreservationDecision:
    """A page classification whose layout must remain untouched."""

    kind: str
    detail: str


@dataclass(frozen=True)
class TableTextCluster:
    """A visual text group inside a table cell, separated from codes/units."""

    bbox: tuple[float, float, float, float]
    text: str
    words: tuple[Sequence[Any], ...]


def is_formula_font(font_name: str) -> bool:
    """Return whether a font name marks formula or code text."""
    return FORMULA_FONT_PATTERN.match(font_name) is not None


def is_bullet_character(text: str, font_name: str | bytes = "") -> bool:
    """Recognize Unicode bullets and common Symbol/Wingdings PUA bullets."""
    if text in BULLET_CHARACTERS:
        return True
    if isinstance(font_name, bytes):
        font_name = font_name.decode(errors="ignore")
    return (
        text in PRIVATE_USE_BULLETS
        and re.search(
            r"wingdings|webdings|symbol|dingbats", font_name, re.IGNORECASE
        )
        is not None
    )


def line_height_for_language(language: str) -> float:
    """Return the translation line-height multiplier for a target language."""
    return LANGUAGE_LINE_HEIGHT.get(language.lower(), 1.1)


def min_line_height_for_language(language: str) -> float:
    """Return the tightest leading that still keeps two lines from touching.

    A paragraph that grew in translation used to buy room by crushing its
    leading to 0.75, which is below the ink of the glyphs being drawn. Measured
    by rendering every letter in the output font and reading the real ink
    extent, in em above and below the baseline:

        English lowercase   0.695 up + 0.210 down = 0.905
        Vietnamese          0.890 up + 0.210 down = 1.100

    Stacked tone marks (e-circumflex-acute, o-horn-grave) reach far higher than
    a plain ascender, so Vietnamese needs more room than English rather than
    less. Below these values the lines overlap no matter what else is right.
    """
    return LANGUAGE_MIN_LINE_HEIGHT.get(language.lower(), DEFAULT_MIN_LINE_HEIGHT)


def _rect(value: Sequence[Any]) -> tuple[float, float, float, float] | None:
    if len(value) < 4:
        return None
    try:
        return tuple(float(item) for item in value[:4])
    except (TypeError, ValueError):
        return None


def _inside_any(
    rectangle: tuple[float, float, float, float],
    regions: Iterable[Sequence[Any]],
) -> bool:
    x0, y0, x1, y1 = rectangle
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for region in regions:
        bounds = _rect(region)
        if bounds is None:
            continue
        rx0, ry0, rx1, ry1 = bounds
        if rx0 <= cx <= rx1 and ry0 <= cy <= ry1:
            return True
    return False


def formula_regions(
    blocks: Iterable[Sequence[Any]],
    words: Iterable[Sequence[Any]],
    *,
    stacked_exclusions: Iterable[Sequence[Any]] = (),
) -> list[tuple[float, float, float, float]]:
    """Return ordinary-font regions whose exact mathematical layout must survive.

    The layout model catches dedicated formula fonts well, but technical PDFs
    often typeset equations in the same font as their prose. Operator-heavy
    blocks without prose words are equations. A second geometry rule catches an
    inline stacked fraction such as F1/b0 even when it sits inside a prose block.
    """
    protected: list[tuple[float, float, float, float]] = []
    for block in blocks:
        bounds = _rect(block)
        if bounds is None or len(block) < 5:
            continue
        compact = " ".join(str(block[4]).split())
        prose_candidate = MATH_FUNCTION_PATTERN.sub("", compact)
        if (
            compact
            and MATH_OPERATOR_PATTERN.search(compact)
            and PROSE_WORD_PATTERN.search(prose_candidate) is None
        ):
            protected.append(bounds)

    candidates = list(words)
    exclusions = tuple(stacked_exclusions)
    for index, upper in enumerate(candidates):
        upper_bounds = _rect(upper)
        if upper_bounds is None or len(upper) < 8:
            continue
        upper_text = str(upper[4])
        if (
            len(upper_text) > 4
            or STACKED_TOKEN_PATTERN.fullmatch(upper_text) is None
            or not any(character.isdigit() for character in upper_text)
            or _inside_any(upper_bounds, exclusions)
        ):
            continue
        ux0, uy0, ux1, uy1 = upper_bounds
        for lower in candidates[index + 1 :]:
            lower_bounds = _rect(lower)
            if lower_bounds is None or len(lower) < 8:
                continue
            if upper[5] != lower[5] or upper[6] == lower[6]:
                continue
            lower_text = str(lower[4])
            if (
                len(lower_text) > 4
                or STACKED_TOKEN_PATTERN.fullmatch(lower_text) is None
                or not any(character.isdigit() for character in lower_text)
                or _inside_any(lower_bounds, exclusions)
            ):
                continue
            lx0, ly0, lx1, ly1 = lower_bounds
            overlap = max(0.0, min(ux1, lx1) - max(ux0, lx0))
            smaller_width = min(ux1 - ux0, lx1 - lx0)
            centre_gap = abs((uy0 + uy1) / 2 - (ly0 + ly1) / 2)
            max_height = max(uy1 - uy0, ly1 - ly0)
            if (
                smaller_width > 0
                and overlap / smaller_width >= 0.6
                and 2 < centre_gap <= 1.5 * max_height
            ):
                protected.append(
                    (
                        min(ux0, lx0),
                        min(uy0, ly0),
                        max(ux1, lx1),
                        max(uy1, ly1),
                    )
                )
    return protected


def matching_table_cells(
    model_bounds: Sequence[Any],
    tables: Iterable[Any],
    *,
    minimum_overlap: float = 0.5,
) -> list[tuple[float, float, float, float]]:
    """Return cells from the table whose area covers a model table detection.

    The model is the gate: PyMuPDF cell detection only enables translation when
    it can explain at least half of that already-recognised table. Unmatched
    tables keep the old, fully protected behaviour.
    """
    model = _rect(model_bounds)
    if model is None:
        return []
    mx0, my0, mx1, my1 = model
    model_area = max(0.0, mx1 - mx0) * max(0.0, my1 - my0)
    if model_area <= 0:
        return []

    best: Any = None
    best_overlap = 0.0
    for table in tables:
        bounds = _rect(getattr(table, "bbox", ()))
        if bounds is None:
            continue
        tx0, ty0, tx1, ty1 = bounds
        intersection = max(0.0, min(mx1, tx1) - max(mx0, tx0)) * max(
            0.0, min(my1, ty1) - max(my0, ty0)
        )
        overlap = intersection / model_area
        if overlap > best_overlap:
            best, best_overlap = table, overlap
    if best is None or best_overlap < minimum_overlap:
        return []

    cells: list[tuple[float, float, float, float]] = []
    for cell in getattr(best, "cells", ()):
        bounds = _rect(cell)
        if bounds is None:
            continue
        x0, y0, x1, y1 = bounds
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if mx0 <= cx <= mx1 and my0 <= cy <= my1 and bounds not in cells:
            cells.append(bounds)
    return cells


def should_translate_table_cell(text: str) -> bool:
    """Return whether a cell contains natural-language text rather than codes.

    Product identifiers and numeric cells are safer left as original PDF glyphs.
    Natural-language labels in the supported source documents contain lowercase
    letters, including Unicode lowercase letters outside English.
    """
    value = " ".join(text.split())
    if not value:
        return False

    def natural_token(token: str) -> bool:
        token = token.strip("()[]{}:;,\"'“”")
        letters = "".join(character for character in token if character.isalpha())
        if token.lower() in {"dry", "wet"}:
            return True
        if token.lower() in {"max", "min"}:
            return False
        if re.search(r"[\u0370-\u03ff]", token):
            return False
        if len(letters) <= 2:
            return False
        if letters.isupper():
            return False
        if (
            any(character.isdigit() for character in token)
            or re.search(r"[a-z][A-Z]", token)
            or sum(character.isupper() for character in letters) >= 2
            or re.search(r"[%._/·]", token)
        ):
            return False
        if len(letters) <= 3 and letters[:1].isupper():
            return False
        return any(character.islower() for character in letters)

    return any(natural_token(token) for token in value.split())


def cluster_table_words(
    words: Iterable[Sequence[Any]],
    cell: Sequence[Any],
) -> list[TableTextCluster]:
    """Split a visually merged table cell into prose and code-like x clusters.

    Some PDFs omit the rule between a description and its abbreviation column,
    so PyMuPDF returns both as one cell. Normal word spaces are small; the jump
    to a right-aligned code is much larger. X-overlap across wrapped lines keeps
    multi-line descriptions together.
    """
    bounds = _rect(cell)
    items = [word for word in words if _rect(word) is not None and len(word) >= 5]
    if bounds is None or not items:
        return []

    heights = [max(0.1, float(word[3]) - float(word[1])) for word in items]
    gap_limit = max(3.0, median(heights) * 0.6)
    groups: list[list[Sequence[Any]]] = []
    group_bounds: list[list[float]] = []
    for word in sorted(items, key=lambda item: (float(item[0]), float(item[1]))):
        x0, y0, x1, y1 = (float(value) for value in word[:4])
        matches = [
            index
            for index, current in enumerate(group_bounds)
            if x0 <= current[2] + gap_limit and x1 >= current[0] - gap_limit
        ]
        if not matches:
            groups.append([word])
            group_bounds.append([x0, y0, x1, y1])
            continue
        target = matches[0]
        groups[target].append(word)
        current = group_bounds[target]
        current[:] = [
            min(current[0], x0),
            min(current[1], y0),
            max(current[2], x1),
            max(current[3], y1),
        ]
        for extra in reversed(matches[1:]):
            groups[target].extend(groups.pop(extra))
            other = group_bounds.pop(extra)
            current[:] = [
                min(current[0], other[0]),
                min(current[1], other[1]),
                max(current[2], other[2]),
                max(current[3], other[3]),
            ]

    ordered = sorted(zip(groups, group_bounds), key=lambda item: item[1][0])
    cx0, cy0, cx1, cy1 = bounds
    result: list[TableTextCluster] = []
    for index, (group, group_box) in enumerate(ordered):
        left = cx0 if index == 0 else (ordered[index - 1][1][2] + group_box[0]) / 2
        right = cx1 if index + 1 == len(ordered) else (
            group_box[2] + ordered[index + 1][1][0]
        ) / 2
        text = " ".join(
            str(word[4])
            for word in sorted(
                group,
                key=lambda item: (
                    int(item[5]) if len(item) > 5 else 0,
                    int(item[6]) if len(item) > 6 else 0,
                    int(item[7]) if len(item) > 7 else 0,
                ),
            )
        )
        result.append(
            TableTextCluster(
                (max(cx0, left), cy0, min(cx1, right), cy1),
                text,
                tuple(group),
            )
        )
    return result


def drawing_shape(drawing: Mapping[str, Any]) -> tuple[float, float, float, float, bool] | None:
    """Reduce a PyMuPDF ``get_drawings()`` entry to its box and squareness.

    Rectangles, quads and paths built only from horizontal/vertical lines and
    corner curves (rounded boxes, cylinders) count as rectangular; any slanted
    line (a diamond, an arrow head) does not.
    """
    rect = drawing.get("rect")
    if rect is None:
        return None
    bounds = _rect(tuple(rect))
    if bounds is None:
        return None
    items = list(drawing.get("items", ()))
    # An open polyline (a connector between boxes) has a bounding box too, and
    # a label beside it is not inside it.
    closed = (
        bool(drawing.get("closePath"))
        or drawing.get("type") in ("f", "fs")
        or any(item and item[0] in ("re", "qu") for item in items)
    )
    if not closed:
        return None
    rectangular = True
    for item in items:
        if not item:
            continue
        if item[0] == "l" and len(item) >= 3:
            (ax, ay), (bx, by) = (item[1][0], item[1][1]), (item[2][0], item[2][1])
            if abs(ax - bx) > 0.5 and abs(ay - by) > 0.5:
                rectangular = False
                break
        elif item[0] == "qu" and len(item) >= 2:
            # A quad drawn as a diamond is still a quad; only an axis-aligned
            # one is a box.
            try:
                ul, ur, ll = item[1][0], item[1][1], item[1][2]
                tilted = abs(ul[1] - ur[1]) > 0.5 or abs(ul[0] - ll[0]) > 0.5
            except (TypeError, IndexError):
                tilted = True
            if tilted:
                rectangular = False
                break
    return (*bounds, rectangular)


def _path_polygons(drawing: Mapping[str, Any]) -> list[list[tuple[float, float]]]:
    """Return the closed subpaths of a drawing as point lists (curves as chords)."""
    polygons: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []

    def point(value: Any) -> tuple[float, float]:
        return (float(value[0]), float(value[1]))

    def flush() -> None:
        if len(current) >= 3:
            polygons.append(list(current))
        current.clear()

    for item in drawing.get("items", ()):
        if not item:
            continue
        kind = item[0]
        try:
            if kind == "re":
                flush()
                x0, y0, x1, y1 = (float(value) for value in tuple(item[1])[:4])
                polygons.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
            elif kind == "qu":
                flush()
                quad = item[1]
                polygons.append(
                    [point(quad[0]), point(quad[1]), point(quad[3]), point(quad[2])]
                )
            elif kind in ("l", "c"):
                start, end = point(item[1]), point(item[-1])
                if current and (
                    abs(current[-1][0] - start[0]) > 0.01
                    or abs(current[-1][1] - start[1]) > 0.01
                ):
                    flush()
                if not current:
                    current.append(start)
                if kind == "c":
                    current.extend((point(item[2]), point(item[3])))
                current.append(end)
        except (TypeError, IndexError, ValueError):
            return []
    flush()
    return polygons


def _inside_polygon(polygon: Sequence[tuple[float, float]], x: float, y: float) -> bool:
    inside = False
    count = len(polygon)
    for index in range(count):
        ax, ay = polygon[index]
        bx, by = polygon[(index + 1) % count]
        if (ay > y) != (by > y):
            crossing = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < crossing:
                inside = not inside
    return inside


def occluded_glyphs(
    traces: Iterable[Mapping[str, Any]],
    drawings: Iterable[Mapping[str, Any]],
) -> list[tuple[float, float, float, float, str]]:
    """Return glyphs a later opaque fill paints over, so the reader never sees.

    Diagram tools leave stray text under the shapes drawn after it (a "Z" under
    a box, a "No" under a diamond). Re-drawing text after the page's graphics
    would reveal it, and grouping it with the visible label would garble that
    label. ``traces`` are PyMuPDF ``get_texttrace()`` spans and ``drawings``
    ``get_drawings()`` entries, both in top-left coordinates with ``seqno``.
    The result is per glyph: (x0, y0, x1, y1, character).
    """
    fills = []
    for drawing in drawings:
        if drawing.get("fill") is None or drawing.get("type") not in ("f", "fs"):
            continue
        opacity = drawing.get("fill_opacity")
        if opacity is not None and float(opacity) < 0.99:
            continue
        rect = _rect(tuple(drawing.get("rect") or ()))
        if rect is None:
            continue
        polygons = _path_polygons(drawing)
        if polygons:
            fills.append((int(drawing.get("seqno", -1)), rect, polygons))
    if not fills:
        return []
    hidden: list[tuple[float, float, float, float, str]] = []
    for trace in traces:
        sequence = int(trace.get("seqno", -1))
        if trace.get("type") == 3:
            continue
        later = [fill for fill in fills if fill[0] > sequence]
        if not later:
            continue
        for character in trace.get("chars", ()):
            try:
                code, bbox = int(character[0]), _rect(tuple(character[3]))
            except (TypeError, IndexError, ValueError):
                continue
            if bbox is None:
                continue
            cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
            for _, rect, polygons in later:
                if not _centre_inside(rect, (cx, cy)):
                    continue
                # Every corner, not only the centre, so a glyph at a shape's
                # edge (still partly visible) is kept.
                corners = (
                    (bbox[0] + 0.5, bbox[1] + 0.5),
                    (bbox[2] - 0.5, bbox[1] + 0.5),
                    (bbox[0] + 0.5, bbox[3] - 0.5),
                    (bbox[2] - 0.5, bbox[3] - 0.5),
                )
                if all(
                    any(_inside_polygon(polygon, px, py) for polygon in polygons)
                    for px, py in corners
                ):
                    hidden.append((*bbox, chr(code)))
                    break
    return hidden


def visible_words(
    words: Iterable[Sequence[Any]],
    hidden: Sequence[tuple[float, float, float, float, str]],
) -> list[Sequence[Any]]:
    """Drop words whose glyphs are mostly painted over (see occluded_glyphs)."""
    if not hidden:
        return list(words)
    result = []
    for word in words:
        bounds = _rect(word)
        if bounds is None:
            result.append(word)
            continue
        covered = 0.0
        for gx0, gy0, gx1, gy1, _ in hidden:
            overlap_x = min(bounds[2], gx1) - max(bounds[0], gx0)
            overlap_y = min(bounds[3], gy1) - max(bounds[1], gy0)
            if overlap_x > 0 and overlap_y > 0:
                covered += overlap_x
        if covered < 0.5 * max(0.1, bounds[2] - bounds[0]):
            result.append(word)
    return result


@dataclass(frozen=True)
class FigureLabel:
    """A short text label drawn inside a vector figure.

    ``bounds`` is the room the translation may use. ``enclosed`` says it came
    from the drawn shape around the label (a flowchart box), so the label is
    centred in it; otherwise it is the label's own extent, widened only into
    empty space on both sides equally.
    """

    bounds: tuple[float, float, float, float]
    text: str
    words: tuple[Sequence[Any], ...]
    enclosed: bool
    # False for a line of a left-aligned list (a description beside a
    # timeline): it keeps its left edge and grows only to the right.
    centred: bool = True


# Short words that flowcharts use as whole labels ("Yes"/"No" on decision
# branches). The table-cell predicate keeps capitalised three-letter tokens as
# source because in tables they are mostly codes and units.
FIGURE_WORDS = frozenset(
    {"yes", "no", "end", "start", "stop", "new", "old", "true", "false", "out", "input", "output"}
)


def _figure_line_translatable(text: str) -> bool:
    value = " ".join(text.split())
    if value.strip(".:?!").lower() in FIGURE_WORDS:
        return True
    return should_translate_table_cell(value)


def _contains(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
    tolerance: float = 1.0,
) -> bool:
    return (
        outer[0] <= inner[0] + tolerance
        and outer[1] <= inner[1] + tolerance
        and outer[2] >= inner[2] - tolerance
        and outer[3] >= inner[3] - tolerance
    )


def _centre_inside(
    rectangle: tuple[float, float, float, float],
    point: tuple[float, float],
) -> bool:
    return rectangle[0] <= point[0] <= rectangle[2] and rectangle[1] <= point[1] <= rectangle[3]


def figure_labels(
    words: Iterable[Sequence[Any]],
    figure: Sequence[Any],
    shapes: Iterable[Sequence[Any]] = (),
) -> list[FigureLabel]:
    """Group the words of a vector figure into translatable labels.

    Words are PyMuPDF ``get_text("words")`` tuples and ``figure``/``shapes`` are
    rectangles in the same top-left coordinates. Only labels that read as
    natural language are returned: axis ticks, variables, units and codes stay
    as source glyphs together with every line, arrow and fill of the figure.
    A label whose words overlap each other (an icon glyph printed over a word)
    is left alone rather than guessed at.
    """
    area = _rect(figure)
    if area is None:
        return []
    fx0, fy0, fx1, fy1 = area
    figure_area = max(0.0, fx1 - fx0) * max(0.0, fy1 - fy0)
    items = []
    for word in words:
        bounds = _rect(word)
        if bounds is None or len(word) < 5:
            continue
        centre = ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
        if _centre_inside(area, centre):
            items.append((bounds, word))
    if not items:
        return []

    # A shape is (x0, y0, x1, y1[, rectangular]). Its full box decides which
    # words belong together; the room it lends a translation is the whole box
    # only when it is axis-aligned. A diamond or ellipse lends the rectangle
    # inscribed in it, roughly the middle half each way.
    outers: list[tuple[float, float, float, float]] = []
    rooms: list[tuple[float, float, float, float]] = []
    for shape in shapes:
        bounds = _rect(shape)
        if bounds is None:
            continue
        sx0, sy0, sx1, sy1 = bounds
        if sx1 - sx0 < 4 or sy1 - sy0 < 4:
            continue
        if (sx1 - sx0) * (sy1 - sy0) > 0.5 * figure_area:
            continue
        rectangular = bool(shape[4]) if len(shape) > 4 else True
        room = bounds
        if not rectangular:
            qx, qy = (sx1 - sx0) / 4, (sy1 - sy0) / 4
            room = (sx0 + qx, sy0 + qy, sx1 - qx, sy1 - qy)
        outers.append(bounds)
        rooms.append(room)

    def holder(box: Sequence[float]) -> int | None:
        inner = (box[0], box[1], box[2], box[3])
        candidates = [
            index for index, shape in enumerate(outers) if _contains(shape, inner)
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda index: (outers[index][2] - outers[index][0])
            * (outers[index][3] - outers[index][1]),
        )

    # Words -> lines: same baseline band, a word space apart, same shape.
    # Columns in a figure can sit closer than a word space in prose, so the
    # gap is half the line height and a shape boundary always separates.
    lines: list[dict[str, Any]] = []
    for bounds, word in sorted(items, key=lambda item: (item[0][0], item[0][1])):
        x0, y0, x1, y1 = bounds
        height = max(0.1, y1 - y0)
        centre_y = (y0 + y1) / 2
        word_holder = holder(bounds)
        target = None
        for line in lines:
            line_height = max(0.1, line["box"][3] - line["box"][1])
            line_centre = (line["box"][1] + line["box"][3]) / 2
            if abs(centre_y - line_centre) > 0.4 * max(height, line_height):
                continue
            if line["holder"] != word_holder:
                continue
            gap = x0 - line["box"][2]
            if gap <= 0.5 * max(height, line_height):
                target = line
                break
        if target is None:
            lines.append(
                {
                    "box": [x0, y0, x1, y1],
                    "words": [word],
                    "overlap": False,
                    "holder": word_holder,
                }
            )
            continue
        if x0 < target["box"][2] - 0.5:
            target["overlap"] = True
        target["words"].append(word)
        box = target["box"]
        box[:] = [min(box[0], x0), min(box[1], y0), max(box[2], x1), max(box[3], y1)]

    # Lines -> labels: stacked lines of a similar size that overlap
    # horizontally and sit in the same drawn shape form one multi-line label.
    lines.sort(key=lambda line: (line["box"][1], line["box"][0]))
    labels: list[dict[str, Any]] = []
    for line in lines:
        x0, y0, x1, y1 = line["box"]
        height = max(0.1, y1 - y0)
        target = None
        for label in labels:
            last = label["lines"][-1]["box"]
            last_height = max(0.1, last[3] - last[1])
            gap = y0 - last[3]
            overlap = min(x1, last[2]) - max(x0, last[0])
            # Outside any shape, lines that share a left edge and each start
            # with a capital are list items, not one wrapped phrase.
            first_word = min(line["words"], key=lambda item: float(item[0]))
            list_item = (
                line["holder"] is None
                and abs(x0 - last[0]) <= 0.5 * height
                and str(first_word[4])[:1].isupper()
            )
            if (
                label["holder"] == line["holder"]
                and not list_item
                and -0.3 * height <= gap <= 0.6 * height
                and overlap > 0.3 * min(x1 - x0, last[2] - last[0])
                and max(height, last_height) <= 1.3 * min(height, last_height)
            ):
                target = label
                break
        if target is None:
            labels.append({"lines": [line], "holder": line["holder"]})
        else:
            target["lines"].append(line)

    all_centres = [
        ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2, id(word))
        for bounds, word in items
    ]
    label_boxes = []
    for label in labels:
        boxes = [line["box"] for line in label["lines"]]
        label_boxes.append(
            (
                min(box[0] for box in boxes),
                min(box[1] for box in boxes),
                max(box[2] for box in boxes),
                max(box[3] for box in boxes),
            )
        )

    result: list[FigureLabel] = []
    for index, label in enumerate(labels):
        if any(line["overlap"] for line in label["lines"]):
            continue
        # A line of names or codes inside a label ("Word2vec (NPLM), NLPS"
        # above its description) stays as source glyphs: such lines are where
        # unusual punctuation lives, and a re-drawn copy can only get it wrong.
        # The remaining lines must be contiguous, or the translation would be
        # fitted over the line left in place.
        flags = [
            _figure_line_translatable(
                " ".join(
                    str(item[4])
                    for item in sorted(line["words"], key=lambda item: float(item[0]))
                )
            )
            for line in label["lines"]
        ]
        if not any(flags):
            continue
        first, last = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
        if not all(flags[first:last + 1]):
            continue
        kept = label["lines"][first:last + 1]
        label_words = tuple(
            word
            for line in kept
            for word in sorted(line["words"], key=lambda item: float(item[0]))
        )
        text = " ".join(str(word[4]) for word in label_words)
        own = {id(word) for word in label_words}
        lx0 = min(line["box"][0] for line in kept)
        ly0 = min(line["box"][1] for line in kept)
        lx1 = max(line["box"][2] for line in kept)
        ly1 = max(line["box"][3] for line in kept)
        height = max(0.1, max(line["box"][3] - line["box"][1] for line in kept))
        # A shape still holding a line left in place is not this label's to
        # use: the centre test below sees that line's words and declines.
        owner = holder((lx0, ly0, lx1, ly1))
        shape = rooms[owner] if owner is not None else None
        if (
            shape is not None
            and _contains(shape, (lx0, ly0, lx1, ly1))
            and not any(
                _centre_inside(outers[owner], (cx, cy))
                for cx, cy, identity in all_centres
                if identity not in own
            )
        ):
            inset = max(1.0, 0.15 * height)
            bounds = (
                min(lx0, shape[0] + inset),
                min(ly0, shape[1] + 0.5),
                max(lx1, shape[2] - inset),
                max(ly1, shape[3] - 0.5),
            )
            result.append(FigureLabel(bounds, text, label_words, True))
            continue

        # No shape of its own: widen equally into free space on both sides.
        free_left = lx0 - fx0
        free_right = fx1 - lx1
        for other_index, other in enumerate(label_boxes):
            if other_index == index:
                continue
            if other[3] < ly0 or other[1] > ly1:
                continue
            if other[2] <= lx0:
                free_left = min(free_left, lx0 - other[2])
            elif other[0] >= lx1:
                free_right = min(free_right, other[0] - lx1)
        for shape_box in outers:
            if shape_box[3] < ly0 or shape_box[1] > ly1:
                continue
            for edge in (shape_box[0], shape_box[2]):
                if edge <= lx0:
                    free_left = min(free_left, lx0 - edge)
                elif edge >= lx1:
                    free_right = min(free_right, edge - lx1)
        # A label lined up on its left edge with another free label directly
        # above or below is part of a list and keeps that edge.
        left_aligned = any(
            other_index != index
            and labels[other_index]["holder"] is None
            and abs(other[0] - lx0) <= 0.5 * height
            and (0 <= ly0 - other[3] <= 1.5 * height or 0 <= other[1] - ly1 <= 1.5 * height)
            for other_index, other in enumerate(label_boxes)
        )
        if left_aligned:
            grow = max(0.0, min(free_right - 2.0, 0.5 * (lx1 - lx0)))
            result.append(
                FigureLabel(
                    (lx0, ly0 - 0.5, lx1 + grow, ly1 + 0.5),
                    text,
                    label_words,
                    False,
                    centred=False,
                )
            )
            continue
        widen = max(0.0, min(free_left - 2.0, free_right - 2.0, 0.3 * (lx1 - lx0)))
        result.append(
            FigureLabel(
                (lx0 - widen, ly0 - 0.5, lx1 + widen, ly1 + 0.5),
                text,
                label_words,
                False,
            )
        )
    return result


def page_has_image(blocks: Iterable[Mapping[str, Any]]) -> bool:
    """Return whether the page draws any raster image at all.

    is_scanned_page asks whether one image covers half the page, which is the
    right question for backing rectangles but the wrong one for deciding a page
    held nothing to translate: scanners routinely emit a page as dozens of
    tiles, none of them large on its own. A page with no text and no image is
    simply blank, and saying so would be noise.
    """
    return any(block.get("type") == 1 for block in blocks)


def is_scanned_page(blocks: Iterable[Mapping[str, Any]], page_area: float) -> bool:
    """Return whether a rendered image covers more than half of the page."""
    if page_area <= 0:
        return False
    for block in blocks:
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not isinstance(bbox, (tuple, list)) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = (float(value) for value in bbox)
        if max(0.0, x1 - x0) * max(0.0, y1 - y0) > page_area * 0.5:
            return True
    return False


# "Surname, I." or "van den Oord, A." at the start of a bibliography entry, as
# ICML/NeurIPS/ACL styles print them: authors first, the year bare, not in
# parentheses ("..., 2017."), so the "(2017)" signal below never fires.
REFERENCE_ENTRY_START = re.compile(
    r"^(?:\[\d{1,3}\]\s*|\d{1,3}\.\s+)?"
    r"(?:(?:van|von|der|den|de|da|di|du|le|la|del)\s+)*"
    r"[A-Z][A-Za-zÀ-ɏ'’-]+(?:\s[A-Z][A-Za-zÀ-ɏ'’-]+)?,\s"
    r"[A-Z]\.(?:\s?-?[A-Z]\.)*"
    r"(?=[,\s]|$)"
)
BARE_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")


def looks_like_reference_entry(text: str) -> bool:
    """A bibliography entry: authors as "Surname, I." first, and a year.

    Such entries must keep their source text: translating them turns
    "Chollet, F. et al." into "Chollet, F. và các tác giả khác" and mixes
    Vietnamese into titles and venues the reader has to look up in English.
    Prose that mentions an author starts with a word, not "Surname, I.".
    """
    text = text.strip()
    return bool(REFERENCE_ENTRY_START.match(text)) and bool(BARE_YEAR.search(text))


REFERENCE_HEADER = re.compile(
    r"[\xad]?(references?|bibliography|suggested\s+reading|further\s+reading|works?\s+cited)",
    re.IGNORECASE,
)
NUMBERED_ENTRY_START = re.compile(r"^(?:\[\d{1,3}\]|\d{1,3}\.\s)")


def prose_precedes_references(lines: Sequence[str]) -> bool:
    """Whether a References heading follows real prose on the same page.

    The last page of a two-column paper often ends its conclusion and
    acknowledgement in the left column before the bibliography starts. Its
    32 entries satisfied the whole-page reference test and the prose above
    them was never translated. Such a page is left to the converter, which
    keeps each entry by itself (looks_like_reference_entry).
    """
    for index, line in enumerate(lines):
        if REFERENCE_HEADER.fullmatch(line):
            prose = [
                earlier
                for earlier in lines[:index]
                if len(earlier) >= 30
                and not NUMBERED_ENTRY_START.match(earlier)
                and not REFERENCE_ENTRY_START.match(earlier)
            ]
            return len(prose) >= 6
    return False


def bibliography_rects(
    lines: Sequence[tuple[str, Sequence[float]]],
) -> list[tuple[float, float, float, float]]:
    """Boxes of the bibliography on a page where prose comes first.

    ``lines`` are (text, PyMuPDF bbox) in reading order. Everything after the
    References heading that sits below it in its column, or in a column wholly
    to its right, is the list itself. Protecting that area keeps every entry
    exactly as typeset: reflowing an untranslated entry lost its hanging
    indent and ran "[16] ... (2012) [17] Cao, T." together as one paragraph.
    The heading itself is translated. One box per column, not one per line:
    the glyphs of a wrapped line ("cessed February 6, 2024]") fell into the
    gaps between line boxes and were sent for translation on their own.
    """
    for index, (text, heading) in enumerate(lines):
        if not REFERENCE_HEADER.fullmatch(text.strip()):
            continue
        hx0, hy0, hx1, _ = heading[:4]
        centre = (hx0 + hx1) / 2
        below: list[Sequence[float]] = []
        right: list[Sequence[float]] = []
        for _, bbox in lines[index + 1:]:
            x0, y0, x1, _ = bbox[:4]
            if x0 <= centre <= x1 and y0 >= hy0:
                below.append(bbox)
            elif x0 > hx1:
                right.append(bbox)
        return [
            (
                min(b[0] for b in group),
                min(b[1] for b in group),
                max(b[2] for b in group),
                max(b[3] for b in group),
            )
            for group in (below, right)
            if group
        ]
    return []


FORMULA_PLACEHOLDER = re.compile(r"\{v\d+\}")
SEGMENT_WORD = re.compile(r"[^\W\d_]+(?:\.[^\W\d_]+)*\.?")


def looks_like_formula_line(text: str) -> bool:
    """A segment that is a formula with a few connecting words, not a sentence.

    "For objective function f: X ⊆ ℝⁿ → ℝ where X ≠ ∅ find s ∈ X s.t.
    f(s) ≤ f(x) ∀x ∈ X where f(s) ≠ −∞" reaches the converter as a dozen
    formula placeholders strung together by "for", "where", "find" and the
    punctuation between them. A model given that rewrites the structure,
    turning "f(s) ≤ f(x)" into "s, ≤ f, x", and every marker still checks out.
    Such a line keeps its source text. A sentence that merely contains
    formulas has half again as many words as placeholders, or a run of more than three
    words between two of them, and is translated as before.
    """
    placeholders = FORMULA_PLACEHOLDER.findall(text)
    if len(placeholders) < 4:
        return False
    runs = [len(SEGMENT_WORD.findall(piece)) for piece in FORMULA_PLACEHOLDER.split(text)]
    return max(runs) <= 3 and sum(runs) <= 1.5 * len(placeholders)


def classify_preserved_page(page_text: str) -> PreservationDecision | None:
    """Classify pages whose number-heavy structure must not be reflowed."""
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return None

    toc_score = 0
    standalone_nums = 0
    spaced_page_nums = 0
    emspace_page_nums = 0
    for line in lines:
        if (
            re.search(r"\.{5,}", line)
            or re.search(r"(\.\s){4,}", line)
            or re.search(r"[\x08\ufffd\u2500-\u257f]{3,}", line)
        ):
            toc_score += 3
        elif re.search(r"[\x08\ufffd\u2500-\u257f]+\s*\d{1,4}\s*$", line):
            toc_score += 2
        elif re.search(r"\S\s{5,}\d{1,4}\s*$", line):
            spaced_page_nums += 1
        elif re.fullmatch(r"\d{1,4}", line):
            standalone_nums += 1

        if re.search(r"[\u2002\u2003]+\s*\d{1,4}\s*$", line) or re.search(
            r"[\u2002\u2003]+\s*[ivxlcdm]+\s*$", line, re.IGNORECASE
        ):
            emspace_page_nums += 1

    has_contents_header = any(
        re.fullmatch(r"(table\s+of\s+)?contents?", line, re.IGNORECASE)
        for line in lines[:5]
    )
    if has_contents_header:
        toc_score += 5
    if spaced_page_nums >= 5:
        toc_score += spaced_page_nums
    if emspace_page_nums >= 5:
        toc_score += emspace_page_nums
    if standalone_nums >= 8 and toc_score > 0:
        toc_score += standalone_nums
    if len(lines) >= 15 and standalone_nums >= 10 and standalone_nums / len(lines) > 0.3:
        toc_score += standalone_nums
    if len(lines) >= 15:
        lines_ending_num = sum(
            1 for line in lines if re.search(r"\S\s+\d{1,4}\s*$", line)
        )
        if lines_ending_num / len(lines) > 0.8:
            toc_score += lines_ending_num
    if toc_score >= 8:
        return PreservationDecision("TOC", f"score={toc_score}")

    index_comma_numbers = sum(
        1 for line in lines if re.search(r",\s*\d{1,4}", line)
    )
    if len(lines) >= 20 and index_comma_numbers / len(lines) > 0.4:
        return PreservationDecision(
            "INDEX", f"comma_num={index_comma_numbers}/{len(lines)}"
        )
    if re.fullmatch(r"index", lines[0], re.IGNORECASE):
        return PreservationDecision("INDEX", "header")

    has_nomenclature_header = any(
        re.fullmatch(
            r"(nomenclature|list\s+of\s+symbols|symbols?\s+and\s+abbreviations?|"
            r"glossary|notation)s?",
            line,
            re.IGNORECASE,
        )
        for line in lines[:5]
    )
    if has_nomenclature_header and len(lines) >= 10:
        symbol_definition_pairs = sum(
            1
            for index in range(len(lines) - 1)
            if len(lines[index]) <= 15
            and len(lines[index + 1]) > 5
            and not lines[index].isdigit()
        )
        if symbol_definition_pairs / len(lines) > 0.3:
            return PreservationDecision(
                "NOMENCLATURE",
                f"pairs={symbol_definition_pairs}/{len(lines)}",
            )

    has_reference_header = any(
        re.fullmatch(
            r"[\xad]?(references?|bibliography|suggested\s+reading|further\s+reading|"
            r"works?\s+cited)",
            line,
            re.IGNORECASE,
        )
        for line in lines[:10]
    )
    numbered_refs = sum(1 for line in lines if re.match(r"^\d{1,3}\.\s", line))
    author_year_refs = sum(
        1 for line in lines if re.match(r"^[A-Z][a-z]+,?\s.*\(\d{4}\)", line)
    )
    bracketed_refs = sum(1 for line in lines if re.match(r"^\[\d{1,3}\]", line))
    # Authors-first entries with a bare year; one line per entry start.
    author_initial_refs = sum(1 for line in lines if REFERENCE_ENTRY_START.match(line))
    bare_year_lines = sum(1 for line in lines if BARE_YEAR.search(line))
    year_parentheses = sum(1 for line in lines if re.search(r"\(\d{4}\)", line))
    isbn_doi = sum(
        1
        for line in lines
        if re.search(r"ISBN|ISSN|doi\.org|https?://", line, re.IGNORECASE)
    )
    all_refs = numbered_refs + author_year_refs + bracketed_refs
    reference_signals = all_refs + year_parentheses + isbn_doi
    if prose_precedes_references(lines):
        # Prose first, then the bibliography: entries are kept one by one.
        return None
    if has_reference_header and reference_signals >= 5:
        return PreservationDecision(
            "REFERENCES",
            f"header, refs={all_refs}, years={year_parentheses}, isbn_doi={isbn_doi}",
        )
    if len(lines) >= 10 and all_refs >= 5 and year_parentheses + isbn_doi >= 3:
        return PreservationDecision(
            "REFERENCES",
            f"refs={all_refs}, years={year_parentheses}, isbn_doi={isbn_doi}",
        )
    # A continuation page of an authors-first bibliography: no header, years
    # bare. Entries wrap, so a year often sits on a later line than the
    # authors; the Inception Score paper's page 7 had 29 entry starts and 25
    # lines with a year.
    if (
        len(lines) >= 10
        and author_initial_refs >= 8
        and bare_year_lines >= 0.6 * author_initial_refs
        and author_initial_refs / len(lines) >= 0.15
    ):
        return PreservationDecision(
            "REFERENCES",
            f"author_initial={author_initial_refs}/{len(lines)}, bare_years={bare_year_lines}",
        )
    return None
