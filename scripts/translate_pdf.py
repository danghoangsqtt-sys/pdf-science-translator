#!/usr/bin/env python3
"""Translate one text-based PDF while preserving its layout and formulas."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from pdf2zh.high_level import TranslationReport

SKILL_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_CORE = (SKILL_ROOT / "pdf2zh").resolve()
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

CORE_VERSION = "1.9.11"
RULESET = "code4life-preservation-v1"
DEFAULT_TARGET_LANGUAGE = "vi"

# Latin-script targets the bundled GoNotoKurrent font renders correctly. Scripts
# needing CJK glyphs, right-to-left runs, or complex shaping are refused rather
# than emitted as blank boxes or reordered text.
TARGET_LANGUAGES = frozenset(
    {
        "af", "ca", "cs", "cy", "da", "de", "en", "es", "et", "eu", "fi", "fr",
        "ga", "gl", "hr", "hu", "id", "is", "it", "lt", "lv", "ms", "mt", "nl",
        "no", "pl", "pt", "ro", "sk", "sl", "sq", "sv", "sw", "tl", "tr", "vi",
    }
)

# Ollama runs on this machine and needs no account; Google's free web endpoint
# blocks an IP that sends it a whole book, so it is a fallback, not the default.
ENGINES = ("ollama", "google", "handoff")
DEFAULT_ENGINE = "ollama"
OCR_MODES = ("off", "standard", "enhanced")
# Mirrors pdf2zh.translator.SUPPORTED_DOMAINS as a plain tuple, the same way
# ENGINES/OCR_MODES above duplicate pdf2zh values instead of importing the
# heavy core before _require_core() has validated the environment.
DOMAINS = ("natural_sciences", "technology", "medicine")

# Measured on an eight-page sample: 2 threads 48s, 4 threads 30s, 8 threads 27s,
# 12 threads 29s. Past four, the layout pass rather than the network is the floor,
# and more concurrency only raises the odds of the service throttling a long run.
DEFAULT_THREADS = 4
# One GPU serves Ollama's requests largely one after another: two keep it busy
# while the converter prepares the next segment, and four only queue up and
# risk running a 12 GB card out of memory.
DEFAULT_OLLAMA_THREADS = 2
MAX_THREADS = 8


def default_threads(engine: str) -> int:
    return DEFAULT_OLLAMA_THREADS if engine == "ollama" else DEFAULT_THREADS

# Short articles and single-chapter documents up to this length have been
# translated clean in regression benchmarking (8, 22, 36 pages, Google
# engine). Longer documents are a supported use case, not rejected here, but
# a 144-page survey PDF in that same benchmark hit a crash and a silent
# formula-adjacent text-splitting defect that a shorter run never exercised,
# so past this length the odds of hitting an edge case the fit/placeholder
# gates do not yet fully cover go up. This is a nudge toward the workflow
# agent-knowledge/validation.md already recommends - validate a --pages
# range first - not a hard limit.
PAGE_COUNT_ADVISORY_LIMIT = 50


def page_count_advisory(page_count: int) -> str | None:
    """Return a validation nudge for a document past PAGE_COUNT_ADVISORY_LIMIT."""
    if page_count <= PAGE_COUNT_ADVISORY_LIMIT:
        return None
    return (
        f"{page_count} pages is beyond the length this build has been checked "
        f"against directly (clean up to {PAGE_COUNT_ADVISORY_LIMIT} pages). "
        "Consider validating a --pages range first, then translate the whole "
        "document, and review formula- and table-dense pages in the result."
    )


class TranslationError(RuntimeError):
    """Raised when input validation or the translation engine fails."""


class TranslationCancelled(TranslationError):
    """Raised when the caller's cancel event stopped the run between pages.

    Nothing is written: the half-made output lives only in the temporary
    directory, which is removed on the way out.
    """


class Translation(NamedTuple):
    """Where the translated file landed, and how much of it stayed in the source language."""

    path: Path | None
    untranslated: int = 0
    reasons: Mapping[str, int] = MappingProxyType({})
    image_only_pages: tuple[int, ...] = ()
    ocr_pages: tuple[int, ...] = ()
    ocr_profile: str = "off"
    ocr_warnings: tuple[str, ...] = ()
    # Segments the engine was asked for; untranslated is the part of these
    # that stayed in the source language.
    total_segments: int = 0
    engine: str = ""
    model: str | None = None
    # Set when the engine stopped answering altogether, in words for the user.
    service_failure: str | None = None

    @property
    def translated_segments(self) -> int:
        return max(0, self.total_segments - self.untranslated)

    @property
    def translated_ratio(self) -> float:
        """Share of translatable segments that came back translated, 0..1."""
        if self.total_segments <= 0:
            return 0.0
        return self.translated_segments / self.total_segments

    @property
    def kept_by_reason(self) -> dict[str, int]:
        return classify_failures(self.reasons)


# record_translation_failure passes up either an exception class name or one of
# the converter's fit rules. Reporting them as one sentence sent users to check
# a network that was never the problem, so they are separated here.
_FIT_MARKERS = ("font size", "cannot fit")
_FORMULA_REASON = "FormulaPlaceholderError"
_TOO_LONG_REASON = "SegmentTooLongError"


def _count_of_segments(count: int) -> str:
    return f"{count} segment" if count == 1 else f"{count} segments"


def _is_fit_reason(reason: str) -> bool:
    return any(marker in reason for marker in _FIT_MARKERS)


def classify_failures(reasons: Mapping[str, int]) -> dict[str, int]:
    """Count kept-source segments by what the user would do about them.

    ``service``: the engine failed or was unreachable; ``formula``: the
    translation damaged formula or style markers; ``fit``: the translation did
    not fit its region at the smallest allowed size; ``too_long``: the
    paragraph was longer than one request may carry.
    """
    fit = sum(count for reason, count in reasons.items() if _is_fit_reason(reason))
    formula = reasons.get(_FORMULA_REASON, 0)
    too_long = reasons.get(_TOO_LONG_REASON, 0)
    service = sum(reasons.values()) - fit - formula - too_long
    return {"service": service, "formula": formula, "fit": fit, "too_long": too_long}


def _describe_failures(reasons: Mapping[str, int]) -> list[str]:
    """Turn raw skip reasons into lines that say what the user can do."""
    is_fit = _is_fit_reason
    fit = sum(count for reason, count in reasons.items() if is_fit(reason))
    formula = reasons.get(_FORMULA_REASON, 0)
    too_long = reasons.get(_TOO_LONG_REASON, 0)
    engine = {
        reason: count
        for reason, count in reasons.items()
        if reason not in (_FORMULA_REASON, _TOO_LONG_REASON) and not is_fit(reason)
    }

    lines: list[str] = []
    if fit:
        lines.append(
            f"{_count_of_segments(fit)} stayed in the source language because the "
            "translation did not fit the original line at the smallest allowed size"
        )
    if formula:
        lines.append(
            f"{_count_of_segments(formula)} stayed in the source language because the "
            "translation came back with damaged formula markers"
        )
    if too_long:
        lines.append(
            f"{_count_of_segments(too_long)} stayed in the source language because the "
            "paragraph was longer than the translation service accepts in one request"
        )
    if engine:
        names = ", ".join(f"{name} x{count}" for name, count in sorted(engine.items()))
        lines.append(
            f"{_count_of_segments(sum(engine.values()))} stayed in the source language "
            f"because the translation engine failed ({names})"
        )
    return lines


def _positive_threads(value: str) -> int:
    threads = int(value)
    if not 1 <= threads <= MAX_THREADS:
        raise argparse.ArgumentTypeError(f"threads must be between 1 and {MAX_THREADS}")
    return threads


def _page_selection(value: str) -> str:
    if not re.fullmatch(r"[1-9]\d*(?:-[1-9]\d*)?(?:,[1-9]\d*(?:-[1-9]\d*)?)*", value):
        raise argparse.ArgumentTypeError("pages must use one-based ranges such as 1,3-5")
    for item in value.split(","):
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            if start > end:
                raise argparse.ArgumentTypeError("page range start must not exceed its end")
    return value


def _source_language(value: str) -> str:
    if value == "auto" or re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?", value):
        return value
    raise argparse.ArgumentTypeError("source language must be 'auto' or a Google language code")


def _target_language(value: str) -> str:
    language = value.lower()
    if language not in TARGET_LANGUAGES:
        supported = ", ".join(sorted(TARGET_LANGUAGES))
        raise argparse.ArgumentTypeError(
            f"unsupported target language {value!r}. The bundled font covers Latin-script "
            f"targets only, so CJK, right-to-left, and complex-shaping scripts would render "
            f"as blank boxes or reordered text. Supported: {supported}"
        )
    return language


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate one text-based PDF while preserving layout and formulas."
    )
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--target-language", default=DEFAULT_TARGET_LANGUAGE, type=_target_language
    )
    parser.add_argument("--source-language", default="auto", type=_source_language)
    parser.add_argument("--pages", type=_page_selection)
    parser.add_argument(
        "--threads",
        default=None,
        type=_positive_threads,
        help=f"default {DEFAULT_OLLAMA_THREADS} for ollama, {DEFAULT_THREADS} otherwise",
    )
    parser.add_argument("--engine", default=DEFAULT_ENGINE, choices=ENGINES)
    parser.add_argument(
        "--model",
        default=None,
        help="ollama engine: model name (default translategemma:12b, "
        "or PDF_TRANSLATE_OLLAMA_MODEL)",
    )
    parser.add_argument(
        "--ocr",
        default="off",
        choices=OCR_MODES,
        help="experimental local OCR for image-only pages",
    )
    parser.add_argument(
        "--segments",
        type=Path,
        help='handoff engine: JSONL of {"src","dst"} records to translate from',
    )
    parser.add_argument(
        "--emit-segments",
        type=Path,
        help="handoff engine: write the segments left untranslated here, as JSONL",
    )
    parser.add_argument("--ignore-cache", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--domain",
        default=None,
        choices=DOMAINS,
        help="force preferred terminology for a subject domain over the engine's own wording",
    )
    return parser


def _validate_arguments(args: argparse.Namespace) -> None:
    if args.output_dir is None and args.emit_segments is None:
        raise TranslationError("--output-dir is required unless --emit-segments is given")
    if args.engine == "handoff":
        if args.segments is None and args.emit_segments is None:
            raise TranslationError("--engine handoff needs --segments, --emit-segments, or both")
    elif args.segments is not None or args.emit_segments is not None:
        raise TranslationError("--segments and --emit-segments require --engine handoff")
    if args.model is not None and args.engine != "ollama":
        raise TranslationError("--model applies only to --engine ollama")


def _require_core() -> None:
    try:
        import pdf2zh
        importlib.import_module("pdf2zh.doclayout")
        # high_level pulls in the native stack - pikepdf/qpdf, PyMuPDF, onnx.
        # Without it a broken install slipped past this check and surfaced as a
        # raw ImportError from the engine, once per file in the queue, instead
        # of one actionable message before any work started.
        importlib.import_module("pdf2zh.high_level")
    except ImportError as error:
        requirements = SKILL_ROOT / "requirements.txt"
        install = f'"{sys.executable}" -m pip install -r "{requirements}"'
        raise TranslationError(f"PDF core dependencies are missing. Run: {install}") from error
    if pdf2zh.__version__ != CORE_VERSION:
        raise TranslationError(
            f"Expected bundled PDF core {CORE_VERSION}, found {pdf2zh.__version__}"
        )
    if getattr(pdf2zh, "__ruleset__", None) != RULESET:
        raise TranslationError("Bundled PDF core does not expose the required preservation ruleset")
    # A packaged build has no pip environment for a PyPI wheel to shadow the core,
    # and its module paths point inside the extraction directory rather than here.
    if getattr(sys, "frozen", False):
        return
    module_path = Path(pdf2zh.__file__).resolve()
    if not module_path.is_relative_to(BUNDLED_CORE):
        raise TranslationError(f"Refusing external PDF core: {module_path}")


def _require_ollama(model: str | None) -> str:
    """Fail before any page is read when the offline engine cannot answer."""
    from pdf2zh.translator import ollama_status

    status = ollama_status(model)
    if not status.ready:
        raise TranslationError(status.message)
    return status.model


def _peek_page_count(path: Path) -> int | None:
    """Best-effort page count read before translation starts.

    A nicer heads-up is never worth failing the run over, so any error here
    is swallowed the same way app/gui.py's count_pages already does.
    """
    try:
        import fitz

        with fitz.open(path) as document:
            return document.page_count
    except Exception:  # noqa: BLE001
        return None


def _validate_input(path: Path) -> Path:
    source = path.expanduser().resolve()
    if not source.is_file():
        raise TranslationError(f"Input PDF does not exist: {source}")
    if source.suffix.lower() != ".pdf":
        raise TranslationError(f"Input must have a .pdf extension: {source}")
    with source.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise TranslationError(f"Input does not contain a PDF header: {source}")
    return source


def _describe(error: BaseException) -> str:
    """Flatten an exception chain into one line.

    The core wraps every failure in a generic "Failed to translate <path>", so
    reporting only str(error) hides the reason the document actually failed.
    """
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip()
        parts.append(f"{type(current).__name__}: {message}" if message else type(current).__name__)
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)


def _pages_to_indices(pages: str | None) -> list[int] | None:
    if pages is None:
        return None
    indices: list[int] = []
    for item in pages.split(","):
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            indices.extend(range(start - 1, end))
        else:
            indices.append(int(item) - 1)
    return indices


def _segment_envs(segments: Path | None, emit_segments: Path | None) -> dict[str, str]:
    """Resolve the handoff file paths that the translator reads through `envs`."""
    envs: dict[str, str] = {}
    if segments is not None:
        source = segments.expanduser().resolve()
        if not source.is_file():
            raise TranslationError(f"Segments file does not exist: {source}")
        envs["segments_in"] = str(source)
    if emit_segments is not None:
        emitted = emit_segments.expanduser().resolve()
        emitted.parent.mkdir(parents=True, exist_ok=True)
        envs["segments_out"] = str(emitted)
    return envs


_LAYOUT_MODEL: dict[str | None, object] = {}
# The desktop app warms the model on a background thread while the user is still
# picking files, so two threads really can arrive here at once. On a first run
# onnxruntime serialises a 71 MB optimised graph next to the model, and two of
# those writing the same path would race over a file the next run has to trust.
_LAYOUT_MODEL_LOCK = threading.Lock()


def _layout_model(bundled_path: str | None) -> object:
    """Return the layout model, loading it at most once per process.

    Building the inference session takes about a second and a half, which a
    batch of files would otherwise pay for every single document.
    """
    with _LAYOUT_MODEL_LOCK:
        if bundled_path not in _LAYOUT_MODEL:
            from pdf2zh.doclayout import OnnxModel

            _LAYOUT_MODEL[bundled_path] = (
                OnnxModel(bundled_path) if bundled_path else OnnxModel.load_available()
            )
        return _LAYOUT_MODEL[bundled_path]


def load_layout_model() -> object:
    """Build the inference session, raising if the native stack is unusable.

    The packaged smoke test calls this: onnxruntime and its model are the
    heaviest thing a frozen build has to load, and a bundle that cannot do it
    is broken for every document, not just the first.
    """
    return _layout_model(os.environ.get("PDF_TRANSLATE_MODEL"))


def preload_layout_model() -> None:
    """Build the inference session ahead of the first translation.

    Safe to call from any thread and any number of times; it never raises,
    because a failed warm-up only means the first translation pays the cost
    it used to pay anyway.
    """
    try:
        load_layout_model()
    except Exception:  # noqa: BLE001 - a warm-up failure must stay invisible
        pass


def _run_engine(
    source: Path,
    temp_output: Path,
    target_language: str,
    source_language: str,
    pages: str | None,
    threads: int,
    ignore_cache: bool,
    engine: str,
    envs: dict[str, str],
    on_progress: Callable[[int, int], None] | None = None,
    skip_backing_pages: set[int] | None = None,
    ocr_regions_by_page: dict | None = None,
    domain: str | None = None,
    cancel_event: object | None = None,
) -> "TranslationReport":
    """Run the core and return what it could not translate, and why."""
    from pdf2zh.high_level import translate

    # A packaged build ships the layout model so the first run needs no network.
    model = _layout_model(os.environ.get("PDF_TRANSLATE_MODEL"))

    # The core reports progress by handing its tqdm bar to a callback.
    callback = None
    if on_progress is not None:
        def callback(progress: object) -> None:
            on_progress(getattr(progress, "n", 0), getattr(progress, "total", 0) or 0)

    arguments = dict(
        files=[str(source)],
        output=str(temp_output),
        pages=_pages_to_indices(pages),
        lang_in=source_language,
        lang_out=target_language,
        service=engine,
        thread=threads,
        model=model,
        envs=envs,
        callback=callback,
        ignore_cache=ignore_cache,
    )
    if skip_backing_pages:
        arguments["skip_backing_pages"] = skip_backing_pages
    if ocr_regions_by_page:
        arguments["ocr_regions_by_page"] = ocr_regions_by_page
    if domain:
        arguments["domain"] = domain
    if cancel_event is not None:
        # The core checks it before each page; anything with is_set() will do.
        arguments["cancellation_event"] = cancel_event
    result = translate(**arguments)
    if len(result) != 1:
        raise TranslationError("PDF core did not report one translated result")
    return result[0][1]


def translate_pdf(
    input_pdf: Path,
    output_dir: Path | None,
    *,
    target_language: str = DEFAULT_TARGET_LANGUAGE,
    source_language: str = "auto",
    pages: str | None = None,
    threads: int | None = None,
    ignore_cache: bool = False,
    overwrite: bool = False,
    engine: str = DEFAULT_ENGINE,
    model: str | None = None,
    segments: Path | None = None,
    emit_segments: Path | None = None,
    ocr: str = "off",
    domain: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event: object | None = None,
) -> Translation:
    """Translate one PDF, reporting any segments the engine could not translate."""
    _require_core()
    if ocr not in OCR_MODES:
        raise TranslationError(f"Unsupported OCR mode: {ocr}")
    if domain is not None and domain not in DOMAINS:
        supported = ", ".join(sorted(DOMAINS))
        raise TranslationError(f"Unsupported domain: {domain!r}. Supported: {supported}")
    if engine not in ENGINES:
        raise TranslationError(f"Unsupported engine: {engine!r}")
    if threads is None:
        threads = default_threads(engine)
    source = _validate_input(input_pdf)
    envs = _segment_envs(segments, emit_segments)
    destination: Path | None = None
    destination_dir: Path | None = None
    if output_dir is not None:
        destination_dir = output_dir.expanduser().resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{source.stem}-{target_language}.pdf"
        if destination.exists() and not overwrite:
            raise TranslationError(
                f"Output already exists: {destination}. "
                "Pass --overwrite only with replacement authorization."
            )
    if engine == "ollama":
        model = _require_ollama(model)
    service = f"{engine}:{model}" if model else engine

    with tempfile.TemporaryDirectory(prefix="pdf-translate-", dir=destination_dir) as temp:
        temp_output = Path(temp)
        processing_source = source
        ocr_preparation = None
        if ocr != "off":
            try:
                from pdf2zh.ocr import OcrUnavailableError, prepare_ocr_pdf

                ocr_preparation = prepare_ocr_pdf(
                    source,
                    temp_output / f"{source.stem}-ocr-sidecar.pdf",
                    mode=ocr,
                    pages=_pages_to_indices(pages),
                    layout_model=_layout_model(os.environ.get("PDF_TRANSLATE_MODEL")),
                )
                processing_source = ocr_preparation.sidecar
            except OcrUnavailableError as error:
                requirements = SKILL_ROOT / "requirements-ocr.txt"
                install = f'"{sys.executable}" -m pip install -r "{requirements}"'
                raise TranslationError(f"OCR is unavailable: {error} Run: {install}") from error
            except Exception as error:
                raise TranslationError(f"OCR preparation failed: {_describe(error)}") from error
        try:
            engine_arguments = {}
            if ocr_preparation and ocr_preparation.pages:
                engine_arguments["skip_backing_pages"] = set(ocr_preparation.pages)
                engine_arguments["ocr_regions_by_page"] = (
                    ocr_preparation.reflow_regions_by_page
                )
            if domain:
                engine_arguments["domain"] = domain
            if cancel_event is not None:
                if cancel_event.is_set():
                    raise TranslationCancelled("Đã hủy tác vụ dịch.")
                engine_arguments["cancel_event"] = cancel_event
            report = _run_engine(
                processing_source,
                temp_output,
                target_language,
                source_language,
                pages,
                threads,
                ignore_cache,
                service,
                envs,
                on_progress,
                **engine_arguments,
            )
        except TranslationError:
            raise
        except asyncio.CancelledError as error:
            raise TranslationCancelled("Đã hủy tác vụ dịch.") from error
        except Exception as error:
            raise TranslationError(f"PDF translation core failed: {_describe(error)}") from error

        # Nothing was translatable, so the engine produced a copy of the source
        # with no translated text in it. Handing that over as a finished
        # translation is the one outcome the preservation rules forbid outright:
        # say what the document actually needs instead. The message carries the
        # words app/errors.py matches for E-PDF-03.
        if report.translatable_segments == 0:
            if ocr != "off":
                details = "; ".join(ocr_preparation.warnings) if ocr_preparation else ""
                suffix = f" ({details})" if details else ""
                raise TranslationError(
                    f"OCR found no text that could be translated safely in {source.name}{suffix}"
                )
            raise TranslationError(
                f"No text could be extracted from {source.name}: the selected pages are "
                "image-only scans. This tool does not perform OCR, so run OCR on the "
                "PDF first and translate the result."
            )

        untranslated = len(report.failures)
        service_failure = getattr(report, "service_failure", None)
        total = report.translatable_segments
        # Every segment stayed in the source language: the file would be a copy
        # of the source handed over as a translation, which is what the IP
        # block on 26/10/2026 produced while the app said it had finished.
        if destination is not None and untranslated >= total:
            if service_failure:
                raise TranslationError(service_failure)
            causes = "; ".join(_describe_failures(report.reasons))
            raise TranslationError(
                f"Không dịch được đoạn nào trong {source.name}"
                + (f": {causes}" if causes else "")
            )
        details = {
            "total_segments": total,
            "engine": engine,
            "model": model,
            "service_failure": service_failure,
        }
        image_only = tuple(sorted(report.image_only_pages))
        ocr_pages = ocr_preparation.pages if ocr_preparation else ()
        ocr_warnings = ocr_preparation.warnings if ocr_preparation else ()
        if destination is None:
            return Translation(
                None,
                untranslated,
                report.reasons,
                image_only,
                ocr_pages,
                ocr,
                ocr_warnings,
                **details,
            )

        generated = temp_output / f"{source.stem}-mono.pdf"
        if not generated.is_file():
            candidates = sorted(temp_output.glob("*-mono.pdf"))
            if len(candidates) != 1:
                names = ", ".join(path.name for path in temp_output.iterdir()) or "no files"
                raise TranslationError(f"Engine did not produce one translated PDF; found: {names}")
            generated = candidates[0]

        if ocr_preparation and ocr_preparation.cleaned_images:
            from pdf2zh.ocr import replace_ocr_page_images

            cleaned_output = temp_output / f"{source.stem}-ocr-cleaned.pdf"
            try:
                replace_ocr_page_images(
                    generated,
                    cleaned_output,
                    ocr_preparation.cleaned_images,
                )
            except Exception as error:
                raise TranslationError(
                    f"Could not install the cleaned OCR background: {_describe(error)}"
                ) from error
            generated = cleaned_output

        staged = destination_dir / f".{destination.name}.tmp"
        try:
            shutil.copyfile(generated, staged)
            staged.replace(destination)
        finally:
            staged.unlink(missing_ok=True)

    return Translation(
        destination,
        untranslated,
        report.reasons,
        image_only,
        ocr_pages,
        ocr,
        ocr_warnings,
        **details,
    )


def _use_utf8_output() -> None:
    """Print Vietnamese paths on a legacy console codepage instead of crashing.

    Windows terminals still default to cp1252, which cannot encode Vietnamese, so
    a path like D:\\Tai lieu\\sach-vi.pdf would raise after the work was done.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _use_utf8_output()
    args = _parser().parse_args(argv)
    try:
        _validate_arguments(args)
        if args.pages is None:
            page_count = _peek_page_count(args.input_pdf)
            if page_count is not None:
                advisory = page_count_advisory(page_count)
                if advisory is not None:
                    print(f"notice: {advisory}")
        result = translate_pdf(
            args.input_pdf,
            args.output_dir,
            target_language=args.target_language,
            source_language=args.source_language,
            pages=args.pages,
            threads=args.threads,
            ignore_cache=args.ignore_cache,
            overwrite=args.overwrite,
            engine=args.engine,
            model=args.model,
            segments=args.segments,
            emit_segments=args.emit_segments,
            ocr=args.ocr,
            domain=args.domain,
        )
    except TranslationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if result.path is not None:
        print(f"Translated PDF: {result.path}")
    if result.total_segments:
        engine = f"{result.engine}:{result.model}" if result.model else result.engine
        print(
            f"Translated {result.translated_segments}/{result.total_segments} segments "
            f"({result.translated_ratio:.0%}) with {engine}"
        )
    if result.service_failure:
        print(f"warning: {result.service_failure}", file=sys.stderr)
    if result.ocr_pages:
        numbers = ", ".join(str(page + 1) for page in result.ocr_pages)
        print(f"OCR ({result.ocr_profile}): pages {numbers}")
    for warning in result.ocr_warnings:
        print(f"warning: OCR {warning}", file=sys.stderr)
    if result.image_only_pages:
        numbers = ", ".join(str(page + 1) for page in result.image_only_pages)
        print(
            f"warning: page {numbers} is an image-only scan and was left untranslated; "
            "this tool has no OCR"
            if len(result.image_only_pages) == 1
            else f"warning: pages {numbers} are image-only scans and were left "
            "untranslated; this tool has no OCR",
            file=sys.stderr,
        )
    for line in _describe_failures(result.reasons):
        print(f"warning: {line}", file=sys.stderr)
    if args.emit_segments is not None:
        emitted = args.emit_segments.expanduser().resolve()
        pending = sum(1 for line in emitted.open(encoding="utf-8") if line.strip())
        print(f"Segments left untranslated: {pending} -> {emitted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
