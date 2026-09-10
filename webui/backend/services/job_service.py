from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from scripts.translate_pdf import translate_pdf

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "complete", "error"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TranslationJob:
    job_id: str
    original_filename: str
    upload_path: Path
    output_dir: Path
    target_language: str
    domain: str | None = None
    status: JobStatus = "queued"
    progress: dict[str, int] = field(default_factory=lambda: {"done": 0, "total": 0})
    error: str | None = None
    result_path: Path | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
        }


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
    ) -> TranslationJob:
        await self.start()
        job = TranslationJob(
            job_id=job_id,
            original_filename=original_filename,
            upload_path=upload_path,
            output_dir=output_dir,
            target_language=target_language,
            domain=domain,
        )
        self._jobs[job_id] = job
        await self._queue.put(job_id)
        return job

    def get(self, job_id: str) -> TranslationJob | None:
        return self._jobs.get(job_id)

    async def _worker(self) -> None:
        logger.info("Translation single-worker queue started.")
        while True:
            job_id = await self._queue.get()
            try:
                job = self._jobs.get(job_id)
                if job is None:
                    continue
                await self._run_job(job)
            except Exception as exc:
                logger.exception("Unexpected error in worker loop for job %s: %s", job_id, exc)
            finally:
                self._queue.task_done()

    async def _run_job(self, job: TranslationJob) -> None:
        job.status = "running"
        job.updated_at = _utc_now()
        logger.info("Starting translation job %s (target=%s, file=%s)", job.job_id, job.target_language, job.original_filename)

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
                overwrite=True,
                on_progress=on_progress,
            )

            if translation.path and translation.path.is_file():
                job.result_path = translation.path
                job.status = "complete"
                job.updated_at = _utc_now()
                logger.info("Job %s completed successfully: %s", job.job_id, job.result_path)
            else:
                job.status = "error"
                job.error = "Không tìm thấy file PDF kết quả sau khi dịch."
                job.updated_at = _utc_now()
                logger.error("Job %s finished without output path.", job.job_id)
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            job.updated_at = _utc_now()
            logger.exception("Job %s failed: %s", job.job_id, exc)
