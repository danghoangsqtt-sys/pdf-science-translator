"""Translation adapters for the preservation-focused PDF core."""

from __future__ import annotations

import functools
import html
import json
import logging
import os
import re
import threading
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import requests

from pdf2zh.cache import TranslationCache

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"</?b\d+>")
INTERNAL_PLACEHOLDER_PATTERN = re.compile(r"\{\s*v([\d\s]+)\}", re.IGNORECASE)
PAIRED_PLACEHOLDER_PATTERN = re.compile(r"<b(\d+)></b\1>")
STYLE_TAG_PATTERN = re.compile(r"<(/?)s([123])>", re.IGNORECASE)
DOMAIN_TERM_PATTERN = re.compile(r"</?t\d+>")
PAIRED_DOMAIN_TERM_PATTERN = re.compile(r"<t(\d+)></t\1>")
GLOSSARY_DIR = Path(__file__).resolve().parent / "glossaries"
# Domain names a caller may pass to translate_pdf(domain=...) / --domain. Kept
# as a frozenset (like translator.py's own TARGET_LANGUAGES-style constants)
# so an unknown domain fails at the CLI/API boundary, not deep inside a
# translation loop.
SUPPORTED_DOMAINS = frozenset({"natural_sciences", "technology", "medicine"})
COMMON_PUNCTUATION_MOJIBAKE = (
    ("\u00e2\u20ac\u201c", "\u2013"),  # UTF-8 en dash decoded as Windows-1252
    ("\u00e2\u20ac\u201d", "\u2014"),  # UTF-8 em dash decoded as Windows-1252
    ("\u00c2\u00a9", "\u00a9"),
    ("\u00c2\u00ae", "\u00ae"),
    ("\u00c2\u00b0", "\u00b0"),
    ("\u00c2\u00b1", "\u00b1"),
    ("\u00c2\u00b5", "\u00b5"),
)


class FormulaPlaceholderError(ValueError):
    """Raised when a translator damages or reorders protected formula tags."""


class SegmentTooLongError(ValueError):
    """Raised when a segment exceeds what the translation service accepts.

    Upstream truncates to the limit and returns the short answer as if it were
    the whole translation, so the tail of a long paragraph disappears with
    nothing said. A segment carrying formula or style markers is caught later
    by the marker check, but plain prose is silently cut in half. Refusing the
    segment keeps the source text and lets the caller say what happened.
    """


class TranslationServiceUnavailable(RuntimeError):
    """Raised when the engine cannot serve any request at all.

    Ollama not running, its model not downloaded, or a service refusing the
    machine outright: retrying one segment cannot help, and every later segment
    would fail the same way. The converter stops asking after the first one and
    the message, written for the user, travels up to the report.
    """


def remove_control_characters(value: str) -> str:
    """Remove control characters that cannot be emitted safely into PDF text."""
    return "".join(character for character in value if unicodedata.category(character)[0] != "C")


def repair_common_punctuation_mojibake(value: str) -> str:
    """Repair only unambiguous punctuation damaged while moving JSONL text."""
    for damaged, repaired in COMMON_PUNCTUATION_MOJIBAKE:
        value = value.replace(damaged, repaired)
    return value


def _decoded_as_windows_1252(value: str) -> str | None:
    """Return the UTF-8 text this string would be, if it is mojibake at all."""
    raw = bytearray()
    for character in value:
        try:
            raw += character.encode("cp1252")
        except UnicodeEncodeError:
            # cp1252 leaves 0x81, 0x8d, 0x8f, 0x90 and 0x9d undefined. A lenient
            # decoder passes those bytes through, so they arrive as C1 controls.
            if ord(character) >= 0x100:
                return None
            raw.append(ord(character))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def looks_like_mojibake(value: str) -> bool:
    """Report text that is UTF-8 read as Windows-1252, without repairing it.

    Searching for marker characters is wrong here: Â and Ã are ordinary
    Vietnamese letters, so PHÂN would be condemned. Re-encoding the whole
    string succeeds only when every character came from that one mistake, which
    real Vietnamese does not survive because its tone marks live outside
    Latin-1. Repairing is still refused: guessing a letter sequence is how a
    wrong word reaches the page looking correct.
    """
    decoded = _decoded_as_windows_1252(value)
    return decoded is not None and decoded != value


def has_unrepairable_mojibake(value: str) -> bool:
    """Damage that survives the punctuation repair, so whole letters are wrong.

    Testing the repaired text is not enough. Turning one damaged dash back into
    an en dash restores a byte that cannot begin a UTF-8 sequence, which hides
    the damaged letters standing around it; ten of the records that first
    exposed this defect were masked exactly that way. Compare what the record
    really said against what the safe repair managed to recover instead.
    """
    decoded = _decoded_as_windows_1252(value)
    return decoded is not None and decoded != repair_common_punctuation_mojibake(value)


NUMBER_ABBREVIATION_PATTERN = re.compile(r"(?<![A-Za-z])no\.(?=\s*\d)")


def normalise_number_abbreviation(text: str) -> str:
    """Capitalise the ``no.`` that means "number" so it is not read as "not".

    "ref. no. 305" came back as "ref. KHONG. 305": lowercase "no." mid-sentence
    reads as the negation, and every engine we can reach makes the same choice.
    The same string capitalised is unambiguous -- "No. 305" translates to
    "So 305" -- and capitalising an abbreviation that already stands for a
    proper noun changes nothing else about the sentence.

    Only ``no.`` directly in front of a number is touched, so ordinary prose
    ("there is no. Then...") is left alone.
    """
    return NUMBER_ABBREVIATION_PATTERN.sub("No.", text)


class BaseTranslator:
    """Cache-aware translator interface consumed by the PDF converter."""

    name = "base"
    lang_map: ClassVar[dict[str, str]] = {}
    # True when do_translate already retries what is worth retrying, so the
    # converter must not multiply its attempts by its own.
    handles_retries = False

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        **_: Any,
    ) -> None:
        self.lang_in = self.lang_map.get(lang_in.lower(), lang_in)
        self.lang_out = self.lang_map.get(lang_out.lower(), lang_out)
        self.model = model
        self.ignore_cache = ignore_cache
        self.cache = TranslationCache(
            self.name,
            {
                "lang_in": self.lang_in,
                "lang_out": self.lang_out,
                "model": model,
            },
        )

    def translate(self, text: str, ignore_cache: bool = False) -> str:
        """Translate text, consulting the persistent cache unless bypassed."""
        text = normalise_number_abbreviation(text)
        if not (self.ignore_cache or ignore_cache):
            cached = self.cache.get(text)
            if cached is not None:
                return cached
        translated = self.do_translate(text)
        if not (self.ignore_cache or ignore_cache):
            self.cache.set(text, translated)
        return translated

    def do_translate(self, text: str) -> str:
        """Translate one engine-sized text segment."""
        raise NotImplementedError

    def prefetch(self, texts: list[str]) -> None:
        """Optionally translate a page's segments together ahead of the
        per-segment calls. Engines without a batch API do nothing."""

    def get_rich_text_left_placeholder(self, identifier: int) -> str:
        return f"<b{identifier}>"

    def get_rich_text_right_placeholder(self, identifier: int) -> str:
        return f"</b{identifier}>"

    def get_formular_placeholder(self, identifier: int) -> str:
        return self.get_rich_text_left_placeholder(identifier) + self.get_rich_text_right_placeholder(identifier)


GOOGLE_BLOCKED_MESSAGE = (
    "Google đã tạm chặn máy này vì nhận quá nhiều yêu cầu dịch (lỗi 429 / trang "
    "xác minh CAPTCHA). Hãy dịch bằng bộ dịch Ngoại tuyến (Ollama) hoặc Azure, "
    "hoặc thử lại Google sau vài giờ."
)
GOOGLE_BLOCK_MARKERS = ("unusual traffic", "/sorry/", "captcha-form", "g-recaptcha")
GOOGLE_RESULT_PATTERN = re.compile(r'(?s)class="(?:t0|result-container)">(.*?)<')


def google_blocked(response: Any) -> bool:
    """Whether Google refused the machine rather than the text.

    The 26/10/2026 incident: once Google flags an IP it answers 429 or
    redirects to its /sorry CAPTCHA page, and does so for every request until
    the block lifts. Retrying each of thousands of segments only prolongs it.
    """
    if response.status_code == 429:
        return True
    if "/sorry" in str(getattr(response, "url", "") or ""):
        return True
    body = getattr(response, "text", "") or ""
    # A real result page echoes the source text, which may itself mention
    # "unusual traffic"; only a page without a result is read as a block.
    if GOOGLE_RESULT_PATTERN.search(body):
        return False
    lowered = body[:20000].lower()
    return any(marker in lowered for marker in GOOGLE_BLOCK_MARKERS)


class GoogleTranslator(BaseTranslator):
    """Translate through Google's mobile web endpoint without an API key."""

    name = "google"
    lang_map: ClassVar[dict[str, str]] = {"zh": "zh-CN"}

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            lang_in,
            lang_out,
            model,
            ignore_cache=ignore_cache,
            **kwargs,
        )
        self.session = requests.Session()
        self.endpoint = "https://translate.google.com/m"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            )
        }

    # The /m endpoint carries the text in the query string and rejects more
    # than this; it is the service's limit, not a preference.
    MAXIMUM_SEGMENT_CHARACTERS = 5000

    def do_translate(self, text: str) -> str:
        if len(text) > self.MAXIMUM_SEGMENT_CHARACTERS:
            raise SegmentTooLongError(
                f"segment of {len(text)} characters exceeds the "
                f"{self.MAXIMUM_SEGMENT_CHARACTERS} the service accepts"
            )
        response = self.session.get(
            self.endpoint,
            params={"tl": self.lang_out, "sl": self.lang_in, "q": text},
            headers=self.headers,
            timeout=30,
        )
        if google_blocked(response):
            raise TranslationServiceUnavailable(GOOGLE_BLOCKED_MESSAGE)
        if response.status_code == 400:
            raise RuntimeError("Google Translate rejected the text segment")
        response.raise_for_status()
        match = GOOGLE_RESULT_PATTERN.search(response.text)
        if match is None:
            raise RuntimeError("Google Translate response did not contain a translation result")
        return remove_control_characters(html.unescape(match.group(1)))


# English names TranslateGemma's prompt expects beside each code. A code with
# no entry is still sent, as its own name, rather than refused here.
LANGUAGE_NAMES = {
    "af": "Afrikaans", "ca": "Catalan", "cs": "Czech", "cy": "Welsh",
    "da": "Danish", "de": "German", "en": "English", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "fi": "Finnish", "fr": "French",
    "ga": "Irish", "gl": "Galician", "hr": "Croatian", "hu": "Hungarian",
    "id": "Indonesian", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "lt": "Lithuanian", "lv": "Latvian", "ms": "Malay",
    "mt": "Maltese", "nl": "Dutch", "no": "Norwegian", "pl": "Polish",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak",
    "sl": "Slovenian", "sq": "Albanian", "sv": "Swedish", "sw": "Swahili",
    "tl": "Tagalog", "tr": "Turkish", "vi": "Vietnamese", "zh": "Chinese",
}
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "translategemma:12b"
LIGHT_OLLAMA_MODEL = "translategemma:4b"


def ollama_base_url() -> str:
    """Where Ollama listens: our own setting, then Ollama's, then its default.

    ``OLLAMA_HOST`` is what the server itself reads, so it is often written
    without a scheme ("127.0.0.1:11434") or as the bind-all address, which a
    client cannot connect to.
    """
    value = (
        os.environ.get("PDF_TRANSLATE_OLLAMA_URL")
        or os.environ.get("OLLAMA_HOST")
        or DEFAULT_OLLAMA_URL
    ).strip()
    if "://" not in value:
        value = f"http://{value}"
    value = value.replace("://0.0.0.0", "://127.0.0.1").rstrip("/")
    if value.count(":") < 2:
        value += ":11434"
    return value


def ollama_model_name() -> str:
    return os.environ.get("PDF_TRANSLATE_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL


def _same_model(wanted: str, installed: str) -> bool:
    """Ollama lists ``name:tag``; a bare name means ``:latest``."""
    def full(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    return full(wanted.strip().lower()) == full(installed.strip().lower())


def ollama_pull_command(model: str) -> str:
    return f"ollama pull {model}"


def ollama_not_running_message(base_url: str) -> str:
    return (
        f"Không kết nối được Ollama tại {base_url}. Hãy cài Ollama từ "
        "https://ollama.com/download và mở ứng dụng Ollama, rồi dịch lại."
    )


def ollama_model_missing_message(model: str) -> str:
    return (
        f"Ollama đang chạy nhưng chưa tải mô hình {model}. "
        f"Mở cửa sổ dòng lệnh và chạy: {ollama_pull_command(model)}"
    )


@dataclass(frozen=True)
class OllamaStatus:
    """Whether the offline engine can translate right now, and if not, why."""

    state: str  # "ready", "not_running" or "model_missing"
    base_url: str
    model: str
    installed_models: tuple[str, ...] = ()
    message: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "ready"


def ollama_status(
    model: str | None = None,
    base_url: str | None = None,
    timeout: float = 3.0,
) -> OllamaStatus:
    """Ask Ollama which models it has, without loading any of them."""
    model = model or ollama_model_name()
    base_url = base_url or ollama_base_url()
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=timeout)
        response.raise_for_status()
        installed = tuple(
            str(entry.get("name", "")) for entry in response.json().get("models", [])
        )
    except (requests.RequestException, ValueError, AttributeError):
        return OllamaStatus(
            "not_running", base_url, model, message=ollama_not_running_message(base_url)
        )
    if not any(_same_model(model, name) for name in installed):
        return OllamaStatus(
            "model_missing",
            base_url,
            model,
            installed,
            ollama_model_missing_message(model),
        )
    return OllamaStatus("ready", base_url, model, installed, f"Ollama sẵn sàng với {model}.")


class OllamaTranslator(BaseTranslator):
    """Translate offline through a local Ollama server running TranslateGemma.

    The prompt is TranslateGemma's own, word for word: the model was trained on
    it, and it has no slot for a glossary, so domain terms keep travelling as
    masked ``<tN>`` placeholders the way they do for every other engine.
    """

    name = "ollama"
    # The converter's own retry is for flaky web endpoints. This one already
    # retries what is worth retrying, and a dead server must fail at once.
    handles_retries = True
    MAXIMUM_SEGMENT_CHARACTERS = 5000
    ATTEMPTS = 3
    BACKOFF_SECONDS = 2.0
    # A run of segments that all exhausted their attempts means the server is
    # wedged or far too slow for this machine, not that one paragraph is hard.
    CONSECUTIVE_FAILURE_LIMIT = 5

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            lang_in,
            lang_out,
            model or ollama_model_name(),
            ignore_cache=ignore_cache,
            **kwargs,
        )
        self.base_url = ollama_base_url()
        self.timeout = float(os.environ.get("PDF_TRANSLATE_OLLAMA_TIMEOUT", "180"))
        self.session = requests.Session()
        self._failure_lock = threading.Lock()
        self._consecutive_failures = 0

    def prompt(self, text: str) -> str:
        """TranslateGemma's documented prompt, including the two blank lines."""
        # "auto" has no meaning to the model; the documents this app sees are
        # overwhelmingly English, and --source-language overrides it.
        source_code = "en" if self.lang_in in ("", "auto") else self.lang_in
        source = LANGUAGE_NAMES.get(source_code, source_code)
        target = LANGUAGE_NAMES.get(self.lang_out, self.lang_out)
        return (
            f"You are a professional {source} ({source_code}) to {target} "
            f"({self.lang_out}) translator. Your goal is to accurately convey the "
            f"meaning and nuances of the original {source} text while adhering to "
            f"{target} grammar, vocabulary, and cultural sensitivities.\n"
            f"Produce only the {target} translation, without any additional "
            f"explanations or commentary. Please translate the following {source} "
            f"text into {target}:\n\n\n{text}"
        )

    def do_translate(self, text: str) -> str:
        if len(text) > self.MAXIMUM_SEGMENT_CHARACTERS:
            raise SegmentTooLongError(
                f"segment of {len(text)} characters exceeds the "
                f"{self.MAXIMUM_SEGMENT_CHARACTERS} sent in one request"
            )
        try:
            translated = self._translate_keeping_markers(text)
        except (TranslationServiceUnavailable, ImplausibleTranslationError):
            raise
        except Exception:
            with self._failure_lock:
                self._consecutive_failures += 1
                wedged = self._consecutive_failures >= self.CONSECUTIVE_FAILURE_LIMIT
            if wedged:
                raise TranslationServiceUnavailable(
                    f"Ollama tại {self.base_url} liên tục không trả lời "
                    f"({self.CONSECUTIVE_FAILURE_LIMIT} đoạn liền nhau lỗi). Máy có thể "
                    f"thiếu bộ nhớ GPU cho {self.model}; thử mô hình nhẹ hơn "
                    f"{LIGHT_OLLAMA_MODEL}."
                ) from None
            raise
        with self._failure_lock:
            self._consecutive_failures = 0
        return translated

    # Measured on the Inception Score excerpt with translategemma:12b: of 16
    # segments whose markers were lost at temperature 0, writing formulas as
    # "{0}" rescued 7, and two sampled retries of that form 2 more. Sampling
    # with the tag form rescued only 3. Every candidate still has to pass the
    # same marker check, so a rescue can never return a damaged formula.
    RESCUE_ATTEMPTS = ((0.0, None), (0.4, 1), (0.4, 2))

    def _translate_keeping_markers(self, text: str) -> str:
        """Translate; if markers were lost, retry in the forms the model keeps.

        Only segments whose first answer failed the marker check pay for the
        extra requests. When every attempt fails, the first answer is returned
        and the converter rejects it as before.
        """
        first = self._request_with_retries(text)
        if markers_intact(text, first) and plausible_length(text, first):
            return first
        braceable = (
            not markers_intact(text, first)
            and "<b" in text
            and not BRACED_NUMBER_PATTERN.search(text)
        )
        for temperature, seed in self.RESCUE_ATTEMPTS:
            if not braceable and temperature == 0.0:
                continue  # the tag form at temperature 0 is the answer we have
            try:
                if braceable:
                    candidate = unbrace_formula_tags(
                        self._request_with_retries(
                            brace_formula_tags(text), temperature, seed
                        ),
                        text,
                    )
                else:
                    candidate = self._request_with_retries(text, temperature, seed)
            except TranslationServiceUnavailable:
                raise
            except Exception:  # noqa: BLE001 - the first answer still stands
                break
            if markers_intact(text, candidate) and plausible_length(text, candidate):
                return candidate
        if not plausible_length(text, first):
            raise ImplausibleTranslationError(
                f"translation of {len(strip_markers(text))} characters came back as "
                f"{len(strip_markers(first))}; the model added text of its own"
            )
        return first

    def _request_with_retries(
        self, text: str, temperature: float = 0.0, seed: int | None = None
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(self.ATTEMPTS):
            if attempt:
                time.sleep(self.BACKOFF_SECONDS * 2 ** (attempt - 1))
            try:
                return self._request(text, temperature, seed)
            except (requests.Timeout, _RetryableOllamaError) as error:
                last_error = error
        assert last_error is not None
        raise last_error

    def _request(self, text: str, temperature: float = 0.0, seed: int | None = None) -> str:
        options: dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": 8192,
            # Room for Vietnamese to run longer than its source, while a
            # model that starts looping still stops.
            "num_predict": max(256, len(text)),
        }
        if seed is not None:
            options["seed"] = seed
        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": self.prompt(text),
                    "stream": False,
                    "keep_alive": "15m",
                    "options": options,
                },
                timeout=self.timeout,
            )
        except requests.ConnectionError as error:
            raise TranslationServiceUnavailable(
                ollama_not_running_message(self.base_url)
            ) from error
        if response.status_code == 404:
            raise TranslationServiceUnavailable(ollama_model_missing_message(self.model))
        if response.status_code >= 500:
            detail = response.text[:300].lower()
            if "memory" in detail:
                raise TranslationServiceUnavailable(
                    f"Không đủ bộ nhớ để chạy {self.model}. Hãy đóng bớt ứng dụng "
                    f"dùng GPU hoặc chọn mô hình nhẹ hơn {LIGHT_OLLAMA_MODEL}."
                )
            raise _RetryableOllamaError(f"Ollama returned HTTP {response.status_code}")
        response.raise_for_status()
        try:
            translated = str(response.json()["response"])
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError("Ollama response did not contain a translation") from error
        translated = close_lone_formula_tags(remove_control_characters(translated.strip()))
        translated = drop_added_final_period(text, translated)
        if "`" not in text:
            # The model quotes "{0}" as code; the source never had backticks.
            translated = translated.replace("`", "")
        if not translated:
            raise RuntimeError("Ollama returned an empty translation")
        return translated


TRAILING_TAGS_PATTERN = re.compile(r"(?:\s*</?[bst]\d+>)*\s*$")


def drop_added_final_period(source: str, translated: str) -> str:
    """Remove the full stop the model puts after a heading that had none.

    translategemma turns "1. Introduction" into "1. Giới thiệu." and the title
    into a sentence. Only a single final period is removed, and only when the
    source ends without sentence punctuation; closing tags after it stay.
    """
    def body(text: str) -> str:
        return text[: TRAILING_TAGS_PATTERN.search(text).start()]

    source_body = body(source)
    if not source_body or source_body[-1] in ".!?:;…":
        return translated
    translated_body = body(translated)
    if not translated_body.endswith(".") or translated_body.endswith(".."):
        return translated
    return translated_body[:-1] + translated[len(translated_body):]


class ImplausibleTranslationError(RuntimeError):
    """The model answered with far more text than it was given.

    translategemma turned "...two desirable qualities of a generative model
    into a metric:" into a sentence with an invented acronym and an invented
    list. Nothing structural is wrong with such an answer, so the marker
    check passes it; only its length gives it away.
    """


MARKER_PATTERN = re.compile(r"</?[bst]\d+>")
# Vietnamese ran 1.1-1.5x the English character count on the measured
# excerpt; the invented answer ImplausibleTranslationError describes ran 1.94x.
# 1.6x plus a little room for short headings is past anything a faithful
# translation needed there.
PLAUSIBLE_LENGTH_RATIO = 1.6
PLAUSIBLE_LENGTH_SLACK = 20


def strip_markers(text: str) -> str:
    return MARKER_PATTERN.sub("", text)


def plausible_length(sent: str, translated: str) -> bool:
    source_length = len(strip_markers(sent))
    return len(strip_markers(translated)) <= (
        PLAUSIBLE_LENGTH_RATIO * source_length + PLAUSIBLE_LENGTH_SLACK
    )


BRACED_NUMBER_PATTERN = re.compile(r"\{(\d+)\}")


def brace_formula_tags(text: str) -> str:
    """``<b3></b3>`` -> ``{3}``: a spelling translategemma drops less often."""
    return PAIRED_PLACEHOLDER_PATTERN.sub(lambda match: f"{{{match.group(1)}}}", text)


def unbrace_formula_tags(translated: str, sent: str) -> str:
    """Turn ``{3}`` back into ``<b3></b3>``, for numbers the sent text used only."""
    numbers = set(PAIRED_PLACEHOLDER_PATTERN.findall(sent))

    def restore(match: re.Match) -> str:
        number = match.group(1)
        return f"<b{number}></b{number}>" if number in numbers else match.group(0)

    return BRACED_NUMBER_PATTERN.sub(restore, translated)


def markers_intact(sent: str, translated: str) -> bool:
    """The check the converter applies later: formula, style and term markers."""
    if placeholders(sent) != placeholders(translated):
        return False
    if PAIRED_DOMAIN_TERM_PATTERN.findall(sent) != PAIRED_DOMAIN_TERM_PATTERN.findall(
        translated
    ):
        return False
    try:
        validate_style_tags(sent, translated)
    except FormulaPlaceholderError:
        return False
    return True


LONE_FORMULA_TAG_PATTERN = re.compile(r"<b(\d+)\s*/?>")


def close_lone_formula_tags(text: str) -> str:
    """Complete a formula tag the model wrote as ``<b0>`` or ``<b0/>``.

    TranslateGemma sometimes drops the closing half of an empty pair. The
    opening half still marks the formula's position unambiguously, so the pair
    is completed - but only when no ``</bN>`` for that number appears anywhere;
    a tag that wraps words instead stays malformed and the segment is rejected
    by the usual placeholder check.
    """
    def complete(match: re.Match) -> str:
        identifier = match.group(1)
        following = text[match.end():]
        if following.startswith(f"</b{identifier}>") or f"</b{identifier}>" in text:
            return match.group(0)
        return f"<b{identifier}></b{identifier}>"

    return LONE_FORMULA_TAG_PATTERN.sub(complete, text)


class _RetryableOllamaError(RuntimeError):
    """A server-side hiccup worth another attempt."""


DEFAULT_AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_KEY_ENV = "AZURE_TRANSLATOR_KEY"
AZURE_REGION_ENV = "AZURE_TRANSLATOR_REGION"
AZURE_ENDPOINT_ENV = "AZURE_TRANSLATOR_ENDPOINT"
CONFIG_PATH_ENV = "PDF_TRANSLATE_CONFIG"


def user_config_path() -> Path:
    """Per-user settings file, outside any repository checkout."""
    configured = os.environ.get(CONFIG_PATH_ENV)
    if configured:
        return Path(configured).expanduser()
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PDFTranslate" / "engines.json"
    return Path.home() / ".config" / "pdftranslate" / "engines.json"


@dataclass(frozen=True)
class AzureSettings:
    key: str
    region: str | None
    endpoint: str
    source: str  # "environment" or the settings file path, never the key

    def __repr__(self) -> str:  # keep the key out of logs and tracebacks
        return (
            f"AzureSettings(region={self.region!r}, endpoint={self.endpoint!r}, "
            f"source={self.source!r})"
        )


def azure_settings() -> AzureSettings | None:
    """The Azure Translator key, region and endpoint, or None if not configured.

    Environment variables win over the per-user settings file
    (``{"azure": {"key": ..., "region": ..., "endpoint": ...}}``). Neither is
    ever inside the repository.
    """
    key = os.environ.get(AZURE_KEY_ENV, "").strip()
    if key:
        return AzureSettings(
            key,
            os.environ.get(AZURE_REGION_ENV, "").strip() or None,
            (os.environ.get(AZURE_ENDPOINT_ENV) or DEFAULT_AZURE_ENDPOINT).rstrip("/"),
            "environment",
        )
    path = user_config_path()
    try:
        with path.open(encoding="utf-8") as stream:
            section = json.load(stream).get("azure") or {}
    except (OSError, ValueError, AttributeError):
        return None
    key = str(section.get("key") or "").strip()
    if not key:
        return None
    return AzureSettings(
        key,
        str(section.get("region") or "").strip() or None,
        str(section.get("endpoint") or DEFAULT_AZURE_ENDPOINT).rstrip("/"),
        str(path),
    )


def azure_not_configured_message() -> str:
    return (
        "Chưa cấu hình khóa Azure Translator. Đặt biến môi trường "
        f"{AZURE_KEY_ENV} và {AZURE_REGION_ENV}, hoặc tạo tệp {user_config_path()} "
        'với nội dung {"azure": {"key": "...", "region": "..."}}.'
    )


# Markers the converter puts into a segment, which Azure must treat as markup.
AZURE_MARKUP_PATTERN = re.compile(r"</?[bst]\d+>")


def _escape_for_azure(text: str) -> str:
    """Escape prose for textType=html while leaving the marker tags as tags."""
    parts: list[str] = []
    position = 0
    for match in AZURE_MARKUP_PATTERN.finditer(text):
        parts.append(html.escape(text[position:match.start()], quote=False))
        parts.append(match.group(0))
        position = match.end()
    parts.append(html.escape(text[position:], quote=False))
    return "".join(parts)


class AzureTranslator(BaseTranslator):
    """Azure Translator Text API v3, with the user's own key.

    Segments go as HTML so formula and style markers come back as tags rather
    than translated words. A page's segments are sent together in batches
    within the service's limits (``prefetch``), then served one at a time.
    """

    name = "azure"
    lang_map: ClassVar[dict[str, str]] = {"zh": "zh-Hans", "no": "nb", "tl": "fil"}
    handles_retries = True
    MAXIMUM_ELEMENTS = 1000
    MAXIMUM_REQUEST_CHARACTERS = 50000
    ATTEMPTS = 3
    BACKOFF_SECONDS = 2.0

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        settings: AzureSettings | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(lang_in, lang_out, model, ignore_cache=ignore_cache, **kwargs)
        self.settings = settings or azure_settings()
        self.session = requests.Session()
        self._prefetched: dict[str, str] = {}
        self._prefetch_lock = threading.Lock()

    def prefetch(self, texts: list[str]) -> None:
        """Translate a page's segments in as few requests as the limits allow.

        Best effort: a batch that fails is left for the per-segment path,
        which raises and reports the same error against each segment.
        """
        wanted: list[str] = []
        seen: set[str] = set()
        for text in texts:
            text = normalise_number_abbreviation(text)
            if text in seen or len(_escape_for_azure(text)) > self.MAXIMUM_REQUEST_CHARACTERS:
                continue
            seen.add(text)
            if not self.ignore_cache and self.cache.get(text) is not None:
                continue
            wanted.append(text)
        for batch in self.batches(wanted):
            try:
                translations = self._request(batch)
            except Exception as error:  # noqa: BLE001 - the per-segment path reports it
                logger.debug("Azure batch of %d segments failed: %s", len(batch), error)
                return
            with self._prefetch_lock:
                self._prefetched.update(zip(batch, translations))

    def batches(self, texts: list[str]) -> list[list[str]]:
        """Split into requests of at most 1,000 elements and 50,000 characters."""
        batches: list[list[str]] = []
        current: list[str] = []
        size = 0
        for text in texts:
            length = len(_escape_for_azure(text))
            if current and (
                len(current) >= self.MAXIMUM_ELEMENTS
                or size + length > self.MAXIMUM_REQUEST_CHARACTERS
            ):
                batches.append(current)
                current, size = [], 0
            current.append(text)
            size += length
        if current:
            batches.append(current)
        return batches

    def do_translate(self, text: str) -> str:
        if len(_escape_for_azure(text)) > self.MAXIMUM_REQUEST_CHARACTERS:
            raise SegmentTooLongError(
                f"segment of {len(text)} characters exceeds the "
                f"{self.MAXIMUM_REQUEST_CHARACTERS} the service accepts"
            )
        with self._prefetch_lock:
            prefetched = self._prefetched.pop(text, None)
        if prefetched is not None:
            return prefetched
        return self._request([text])[0]

    def _request(self, texts: list[str]) -> list[str]:
        if self.settings is None:
            raise TranslationServiceUnavailable(azure_not_configured_message())
        params: dict[str, str] = {
            "api-version": "3.0",
            "to": self.lang_out,
            "textType": "html",
        }
        if self.lang_in and self.lang_in != "auto":
            params["from"] = self.lang_in
        headers = {
            "Ocp-Apim-Subscription-Key": self.settings.key,
            "Content-Type": "application/json; charset=UTF-8",
        }
        if self.settings.region:
            headers["Ocp-Apim-Subscription-Region"] = self.settings.region
        body = [{"Text": _escape_for_azure(text)} for text in texts]

        last_error: Exception | None = None
        for attempt in range(self.ATTEMPTS):
            if attempt:
                time.sleep(self.BACKOFF_SECONDS * 2 ** (attempt - 1))
            try:
                response = self.session.post(
                    f"{self.settings.endpoint}/translate",
                    params=params,
                    headers=headers,
                    json=body,
                    timeout=30,
                )
            except requests.ConnectionError as error:
                last_error = error
                continue
            except requests.Timeout as error:
                last_error = error
                continue
            if response.status_code == 200:
                return self._parse(response, len(texts))
            detail = _azure_error_detail(response)
            if response.status_code == 401:
                raise TranslationServiceUnavailable(
                    "Azure từ chối khóa dịch (lỗi 401). Kiểm tra lại khóa "
                    f"{AZURE_KEY_ENV} và vùng {AZURE_REGION_ENV}. {detail}".strip()
                )
            if response.status_code == 403:
                raise TranslationServiceUnavailable(
                    "Azure không cho phép yêu cầu này (lỗi 403) – thường do đã dùng "
                    f"hết hạn mức miễn phí hoặc sai vùng. {detail}".strip()
                )
            if response.status_code == 400:
                raise RuntimeError(f"Azure rejected the request: {detail}")
            last_error = RuntimeError(f"Azure returned HTTP {response.status_code}: {detail}")
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    time.sleep(min(int(retry_after), 60))
        if isinstance(last_error, requests.ConnectionError):
            raise TranslationServiceUnavailable(
                f"Không kết nối được Azure Translator tại {self.settings.endpoint}. "
                "Kiểm tra kết nối Internet."
            ) from last_error
        if isinstance(last_error, RuntimeError) and "HTTP 429" in str(last_error):
            raise TranslationServiceUnavailable(
                "Azure đang giới hạn tốc độ (lỗi 429): gói miễn phí cho 2 triệu ký tự "
                "mỗi giờ. Hãy thử lại sau ít phút hoặc dùng bộ dịch Ngoại tuyến (Ollama)."
            ) from last_error
        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse(response: Any, expected: int) -> list[str]:
        try:
            results = response.json()
            texts = [str(item["translations"][0]["text"]) for item in results]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Azure response did not contain translations") from error
        if len(texts) != expected:
            raise RuntimeError(
                f"Azure returned {len(texts)} translations for {expected} segments"
            )
        return [remove_control_characters(html.unescape(text)) for text in texts]


def _azure_error_detail(response: Any) -> str:
    """Azure's own error message, which never contains the key."""
    try:
        error = response.json().get("error", {})
        return f"({error.get('code', '')}: {error.get('message', '')})"
    except (ValueError, AttributeError):
        return ""


def placeholders(text: str) -> list[str]:
    """Return the formula placeholder tags in order, e.g. ['<b0>', '</b0>']."""
    return PLACEHOLDER_PATTERN.findall(text)


def encode_formula_placeholders(text: str) -> str:
    """Turn converter-internal ``{vN}`` markers into translator-safe tag pairs."""
    return INTERNAL_PLACEHOLDER_PATTERN.sub(
        lambda match: f"<b{int(match.group(1).replace(' ', ''))}></b{int(match.group(1).replace(' ', ''))}>",
        text,
    )


def restore_formula_placeholders(source: str, translated: str) -> str:
    """Validate translator output and restore its tags to converter markers."""
    encoded_source = encode_formula_placeholders(source)
    if placeholders(encoded_source) != placeholders(translated):
        raise FormulaPlaceholderError("formula placeholders changed during translation")
    validate_style_tags(encoded_source, translated)
    restored = PAIRED_PLACEHOLDER_PATTERN.sub(
        lambda match: f"{{v{match.group(1)}}}", translated
    )
    if PLACEHOLDER_PATTERN.search(restored):
        raise FormulaPlaceholderError("formula placeholder pair is malformed")
    return restored


@functools.lru_cache(maxsize=len(SUPPORTED_DOMAINS))
def load_domain_glossary(domain: str) -> dict[str, str]:
    """Load the English -> Vietnamese preferred-term table for one domain.

    Cached: the table is read from disk once per domain per process, not once
    per segment. An unknown domain returns an empty table rather than raising,
    so a caller that already validated ``domain in SUPPORTED_DOMAINS`` (the
    CLI/API boundary) never has to catch an exception here too.
    """
    if domain not in SUPPORTED_DOMAINS:
        return {}
    path = GLOSSARY_DIR / f"{domain}.json"
    try:
        with path.open(encoding="utf-8") as stream:
            table = json.load(stream)
    except (OSError, ValueError):
        logger.warning("Could not load domain glossary %r from %s", domain, path)
        return {}
    return {str(term): str(preferred) for term, preferred in table.items()}


def mask_domain_terms(text: str, glossary: dict[str, str]) -> tuple[str, list[str]]:
    """Replace glossary term occurrences with ``<tN></tN>`` placeholders.

    Matches whole words/phrases only (case-insensitive), longest term first so
    a multi-word entry such as "boundary condition" is not cut short by a
    shorter entry it happens to contain. Returns the masked text and the
    preferred Vietnamese translation for each placeholder, in the order the
    placeholders appear - restore_domain_terms uses that order, not a second
    dictionary lookup, so it never depends on glossary contents at restore time.
    """
    if not glossary:
        return text, []
    terms_by_length = sorted(glossary, key=len, reverse=True)
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(term) for term in terms_by_length) + r")\b",
        re.IGNORECASE,
    )
    lookup = {term.lower(): preferred for term, preferred in glossary.items()}
    preferred_in_order: list[str] = []

    def substitute(match: re.Match) -> str:
        index = len(preferred_in_order)
        preferred_in_order.append(lookup[match.group(0).lower()])
        return f"<t{index}></t{index}>"

    masked = pattern.sub(substitute, text)
    return masked, preferred_in_order


def restore_domain_terms(translated: str, preferred_in_order: list[str]) -> str | None:
    """Substitute ``<tN></tN>`` placeholders with their glossary translations.

    Returns None - never a string containing a raw ``<tN>``/``</tN>`` tag or a
    dropped/reordered term - if the placeholders did not survive translation
    exactly as sent (right count, right order, properly paired). The caller
    is expected to re-translate the unmasked original text in that case,
    the same "prefer a safe fallback over a damaged result" rule the formula
    placeholder check above already enforces.
    """
    if not preferred_in_order:
        return translated
    matches = PAIRED_DOMAIN_TERM_PATTERN.findall(translated)
    if [int(index) for index in matches] != list(range(len(preferred_in_order))):
        return None

    def substitute(match: re.Match) -> str:
        return preferred_in_order[int(match.group(1))]

    restored = PAIRED_DOMAIN_TERM_PATTERN.sub(substitute, translated)
    if DOMAIN_TERM_PATTERN.search(restored):
        return None
    return restored


def _style_tag_counts(text: str) -> Counter[str]:
    """Return balanced style-pair counts, allowing complete pairs to reorder."""
    stack: list[str] = []
    pairs: Counter[str] = Counter()
    for match in STYLE_TAG_PATTERN.finditer(text):
        closing, identifier = match.groups()
        if not closing:
            stack.append(identifier)
            continue
        if not stack or stack[-1] != identifier:
            raise FormulaPlaceholderError("style tags are malformed or cross-nested")
        stack.pop()
        pairs[identifier] += 1
    if stack:
        raise FormulaPlaceholderError("style tags are not closed")
    return pairs


def validate_style_tags(source: str, translated: str) -> None:
    """Require the same balanced bold/italic runs after translation."""
    if _style_tag_counts(source) != _style_tag_counts(translated):
        raise FormulaPlaceholderError("style tags changed during translation")


def load_segment_table(path: str | None) -> dict[str, str]:
    """Load a source-to-translation table from a JSONL file of {"src", "dst"} records.

    Entries whose translation dropped or reordered a formula placeholder are
    skipped, so the next pass re-emits them instead of silently losing a formula.
    """
    if not path:
        return {}
    table: dict[str, str] = {}
    with open(path, encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                source, translation = record["src"], record["dst"]
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(
                    f"{path} line {number}: expected a JSON object with 'src' and 'dst'"
                ) from error
            if not isinstance(source, str) or not isinstance(translation, str):
                raise ValueError(f"{path} line {number}: 'src' and 'dst' must be strings")
            if not translation:
                continue
            if has_unrepairable_mojibake(translation):
                logger.warning(
                    "%s line %d: 'dst' is UTF-8 text decoded as Windows-1252; "
                    "segment left untranslated",
                    path,
                    number,
                )
                continue
            # Old converter versions emitted {vN}; normalise those records so
            # existing handoff files remain usable with the documented tags.
            source = encode_formula_placeholders(repair_common_punctuation_mojibake(source))
            translation = encode_formula_placeholders(
                repair_common_punctuation_mojibake(translation)
            )
            if placeholders(source) != placeholders(translation):
                logger.warning(
                    "%s line %d: formula placeholders differ between src and dst; "
                    "segment left untranslated",
                    path,
                    number,
                )
                continue
            try:
                validate_style_tags(source, translation)
            except FormulaPlaceholderError:
                logger.warning(
                    "%s line %d: style tags differ between src and dst; "
                    "segment left untranslated",
                    path,
                    number,
                )
                continue
            table[source] = translation
    return table


class HandoffTranslator(BaseTranslator):
    """Translate from a table produced outside the pipeline, such as by an agent.

    Two passes: the first runs with no table and records every segment it could
    not translate, the caller fills those in, and the second runs with the filled
    table to emit the real document.
    """

    name = "handoff"

    def __init__(
        self,
        lang_in: str,
        lang_out: str,
        model: str | None = None,
        *,
        ignore_cache: bool = False,
        envs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        # Misses fall through untranslated, so the shared cache must never see them
        # or "translation == original" is memoised for every later run.
        super().__init__(lang_in, lang_out, model, ignore_cache=True, **kwargs)
        envs = envs or {}
        self.table = load_segment_table(envs.get("segments_in"))
        self.misses_path = envs.get("segments_out")
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        if self.misses_path:
            open(self.misses_path, "w", encoding="utf-8").close()

    def do_translate(self, text: str) -> str:
        translation = self.table.get(text)
        if translation is not None:
            return translation
        self._record_miss(text)
        return text

    def _record_miss(self, text: str) -> None:
        """Append one untranslated segment, deduplicated, for the caller to fill in."""
        if not self.misses_path:
            return
        with self._lock:
            if text in self._seen:
                return
            self._seen.add(text)
            with open(self.misses_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps({"src": text}, ensure_ascii=False) + "\n")


ENGINES: dict[str, type[BaseTranslator]] = {
    engine.name: engine
    for engine in (OllamaTranslator, AzureTranslator, GoogleTranslator, HandoffTranslator)
}
