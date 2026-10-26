from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from scripts.translate_pdf import Translation, TranslationCancelled, translate_pdf

logger = logging.getLogger(__name__)

JobStatus = Literal[
    "queued", "running", "complete", "complete_with_warnings", "cancelled", "error"
]
# Statuses whose result file may be downloaded.
FINISHED_WITH_RESULT = ("complete", "complete_with_warnings")
# Below this share of translated text the result is still delivered, but the
# status itself says it is mostly untranslated, not only a warning beside it.
WARNING_RATIO = 0.5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pages(numbers: tuple[int, ...]) -> str:
    return ", ".join(str(page + 1) for page in numbers)


def translation_warnings(translation: Translation) -> list[str]:
    """What the user should know about a delivered translation, in Vietnamese.

    The reason travels with each count: a formula the model mangled and an
    engine that stopped answering need the user to do different things.
    """
    warnings: list[str] = []
    if translation.service_failure:
        warnings.append(translation.service_failure)
    kept = translation.kept_by_reason
    if kept.get("service"):
        warnings.append(
            f"{kept['service']} đoạn giữ nguyên bản gốc vì bộ dịch gặp lỗi."
        )
    if kept.get("formula"):
        warnings.append(
            f"{kept['formula']} đoạn giữ nguyên bản gốc vì bản dịch làm mất ký hiệu "
            "công thức hoặc định dạng in đậm/nghiêng."
        )
    if kept.get("fit"):
        warnings.append(
            f"{kept['fit']} đoạn giữ nguyên bản gốc vì bản dịch không vừa vùng chữ gốc."
        )
    if kept.get("too_long"):
        warnings.append(
            f"{kept['too_long']} đoạn quá dài để gửi một lần nên giữ nguyên bản gốc."
        )
    if translation.image_only_pages:
        warnings.append(
            f"Trang {_pages(translation.image_only_pages)} là ảnh quét, chưa được dịch."
        )
    warnings.extend(f"OCR: {warning}" for warning in translation.ocr_warnings)
    return warnings


def finished_status(translation: Translation) -> JobStatus:
    if translation.total_segments and translation.translated_ratio < WARNING_RATIO:
        return "complete_with_warnings"
    return "complete"


@dataclass
class TranslationJob:
    job_id: str
    original_filename: str
    upload_path: Path
    output_dir: Path
    target_language: str
    domain: str | None = None
    engine: str = "ollama"
    model: str | None = None
    status: JobStatus = "queued"
    progress: dict[str, int] = field(default_factory=lambda: {"done": 0, "total": 0})
    error: str | None = None
    result_path: Path | None = None
    translated_ratio: float | None = None
    segments: dict[str, object] | None = None
    warnings: list[str] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "engine": self.engine,
            "model": self.model,
            "translated_ratio": self.translated_ratio,
            "segments": self.segments,
            "warnings": self.warnings,
        }

    def record(self, translation: Translation) -> None:
        self.model = translation.model or self.model
        self.translated_ratio = round(translation.translated_ratio, 4)
        self.segments = {
            "total": translation.total_segments,
            "translated": translation.translated_segments,
            "kept": translation.kept_by_reason,
        }
        self.warnings = translation_warnings(translation)


class TranslationJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, TranslationJob] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(
                self._worker(), name="translation-job-worker"
            )

    async def submit(
        self,
        *,
        job_id: str,
        original_filename: str,
        upload_path: Path,
        output_dir: Path,
        target_language: str,
        domain: str | None = None,
        engine: str = "ollama",
        model: str | None = None,
    ) -> TranslationJob:
        await self.start()
        job = TranslationJob(
            job_id=job_id,
            original_filename=original_filename,
            upload_path=upload_path,
            output_dir=output_dir,
            target_language=target_language,
            domain=domain,
            engine=engine,
            model=model,
        )
        self._jobs[job_id] = job
        await self._queue.put(job_id)
        return job

    def get(self, job_id: str) -> TranslationJob | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> TranslationJob | None:
        """Ask a job to stop. A queued job never starts; a running one stops
        before its next page, and no output file is written."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.status in ("queued", "running"):
            job.cancel_event.set()
            if job.status == "queued":
                job.status = "cancelled"
                job.updated_at = _utc_now()
        return job

    async def _worker(self) -> None:
        logger.info("Translation single-worker queue started.")
        while True:
            job_id = await self._queue.get()
            try:
                job = self._jobs.get(job_id)
                if job is None or job.status == "cancelled":
                    continue
                await self._run_job(job)
            except Exception as exc:
                logger.exception("Unexpected error in worker loop for job %s: %s", job_id, exc)
            finally:
                self._queue.task_done()

    async def _run_job(self, job: TranslationJob) -> None:
        job.status = "running"
        job.updated_at = _utc_now()
        logger.info(
            "Starting translation job %s (target=%s, engine=%s, file=%s)",
            job.job_id, job.target_language, job.engine, job.original_filename,
        )

        def on_progress(done: int, total: int) -> None:
            job.progress = {"done": int(done), "total": int(total)}
            job.updated_at = _utc_now()

        try:
            translation = await asyncio.to_thread(
                translate_pdf,
                input_pdf=job.upload_path,
                output_dir=job.output_dir,
                target_language=job.target_language,
                domain=job.domain,
                engine=job.engine,
                model=job.model,
                overwrite=True,
                on_progress=on_progress,
                cancel_event=job.cancel_event,
            )
        except TranslationCancelled:
            job.status = "cancelled"
            job.updated_at = _utc_now()
            logger.info("Job %s cancelled.", job.job_id)
            return
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            job.updated_at = _utc_now()
            logger.exception("Job %s failed: %s", job.job_id, exc)
            return

        job.record(translation)
        if translation.path and translation.path.is_file():
            job.result_path = translation.path
            job.status = finished_status(translation)
            logger.info(
                "Job %s finished (%s, %.0f%% translated): %s",
                job.job_id, job.status, 100 * translation.translated_ratio, job.result_path,
            )
        else:
            job.status = "error"
            job.error = "Không tìm thấy file PDF kết quả sau khi dịch."
            logger.error("Job %s finished without output path.", job.job_id)
        job.updated_at = _utc_now()
