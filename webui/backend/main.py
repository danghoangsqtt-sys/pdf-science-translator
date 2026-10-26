from __future__ import annotations

import asyncio
import logging
import os
import secrets
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure repository root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from scripts.translate_pdf import DOMAINS, TARGET_LANGUAGES
from webui.backend.services.engine_service import (
    ENGINE_LABELS,
    allowed_ollama_models,
    describe_engines,
)
from webui.backend.services.job_service import FINISHED_WITH_RESULT, TranslationJobManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pdf_translate.backend")

API_TOKEN_HEADER = "X-PDFTranslate-Token"
API_TOKEN = os.environ.get("PDFTRANSLATE_API_TOKEN") or "dev-token"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MiB
DATA_DIR = Path(os.environ.get("PDFTRANSLATE_DATA_DIR") or (PROJECT_ROOT / "webui" / "backend" / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

job_manager = TranslationJobManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure job manager queue worker is running on app startup
    await job_manager.start()
    logger.info("PDF Translate backend started on 127.0.0.1 (Data dir: %s)", DATA_DIR)
    yield


app = FastAPI(title="PDF Translate Backend", lifespan=lifespan)

# Allow requests from local frontend (Electron / Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8089",
        "http://localhost:8089",
    ],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_api_token(token: str | None) -> None:
    if not token or not secrets.compare_digest(token, API_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên API không hợp lệ hoặc thiếu token xác thực.",
        )


async def _read_validated_upload(file: UploadFile, dest_path: Path, max_bytes: int = MAX_FILE_SIZE) -> None:
    """Stream an UploadFile to disk, enforcing the size cap and PDF magic bytes.

    FastAPI/Starlette already parsed the multipart body correctly (via
    python-multipart) before this is called - this only adds the app-specific
    checks: a hard size cap and a real content check instead of trusting the
    filename extension.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    first_chunk: bytes | None = None
    with dest_path.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            if first_chunk is None:
                first_chunk = chunk
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                out.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Dung lượng tệp vượt quá giới hạn cho phép ({max_bytes // (1024 * 1024)} MiB).",
                )
            out.write(chunk)

    if not first_chunk or not first_chunk.startswith(b"%PDF-"):
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tin không phải định dạng PDF hợp lệ (thiếu %PDF- magic bytes).",
        )


@app.get("/api/health")
async def health_check():
    """Health check endpoint. No authentication required."""
    return {"status": "ready"}


@app.get("/api/engines")
async def list_engines(
    model: str = "",
    x_pdftranslate_token: str | None = Header(default=None, alias=API_TOKEN_HEADER),
):
    """The engines on offer and whether Ollama can translate right now."""
    _require_api_token(x_pdftranslate_token)
    # Asks the local Ollama server over HTTP; keep it off the event loop.
    return await asyncio.to_thread(describe_engines, model or None)


@app.post("/api/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_translation_job(
    file: UploadFile = File(...),
    target_language: str = Form("vi"),
    domain: str = Form(""),
    engine: str = Form("ollama"),
    model: str = Form(""),
    x_pdftranslate_token: str | None = Header(default=None, alias=API_TOKEN_HEADER),
):
    """Receive PDF upload and enqueue a translation job."""
    _require_api_token(x_pdftranslate_token)

    if engine not in ENGINE_LABELS:
        supported_engines = ", ".join(ENGINE_LABELS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bộ dịch không được hỗ trợ: {engine!r}. Hỗ trợ: {supported_engines}",
        )
    model_value: str | None = model or None
    if model_value is not None and (
        engine != "ollama" or model_value not in allowed_ollama_models()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mô hình không được hỗ trợ cho bộ dịch {engine}: {model_value!r}",
        )

    # Reject rather than silently substitute: a client offering a language
    # this build cannot render (e.g. a non-Latin script) needs to see why
    # nothing happened, not get an unexplained Vietnamese result back.
    if target_language not in TARGET_LANGUAGES:
        supported = ", ".join(sorted(TARGET_LANGUAGES))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ngôn ngữ đích không được hỗ trợ: {target_language!r}. Hỗ trợ: {supported}",
        )

    # Empty string means "no domain selected" - the dropdown's default. Only
    # a non-empty value is validated/forwarded, same reject-don't-substitute
    # rule as target_language above.
    domain_value: str | None = domain or None
    if domain_value is not None and domain_value not in DOMAINS:
        supported_domains = ", ".join(sorted(DOMAINS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lĩnh vực không được hỗ trợ: {domain_value!r}. Hỗ trợ: {supported_domains}",
        )

    job_id = str(uuid.uuid4())
    upload_path = UPLOADS_DIR / f"{job_id}.pdf"
    job_output_dir = OUTPUTS_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    original_filename = file.filename or "document.pdf"
    try:
        await _read_validated_upload(file, upload_path, max_bytes=MAX_FILE_SIZE)
    except HTTPException:
        raise
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        logger.exception("Error reading upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lỗi khi đọc file tải lên: {exc}",
        )

    await job_manager.submit(
        job_id=job_id,
        original_filename=original_filename,
        upload_path=upload_path,
        output_dir=job_output_dir,
        target_language=target_language,
        domain=domain_value,
        engine=engine,
        model=model_value,
    )

    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    x_pdftranslate_token: str | None = Header(default=None, alias=API_TOKEN_HEADER),
):
    """Query the status and progress of a translation job."""
    _require_api_token(x_pdftranslate_token)
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tác vụ có mã {job_id}.",
        )
    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    x_pdftranslate_token: str | None = Header(default=None, alias=API_TOKEN_HEADER),
):
    """Stop a queued or running job. A running job stops before its next page."""
    _require_api_token(x_pdftranslate_token)
    job = job_manager.cancel(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tác vụ có mã {job_id}.",
        )
    return job.to_dict()


@app.get("/api/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    x_pdftranslate_token: str | None = Header(default=None, alias=API_TOKEN_HEADER),
):
    """Retrieve the translated PDF file upon completion."""
    _require_api_token(x_pdftranslate_token)
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tác vụ có mã {job_id}.",
        )

    if job.status not in FINISHED_WITH_RESULT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tác vụ chưa hoàn thành hoặc đã gặp lỗi.",
        )

    if not job.result_path or not job.result_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tệp kết quả trên máy chủ.",
        )

    stem = Path(job.original_filename).stem or "translated"
    filename = f"{stem}-{job.target_language}.pdf"
    return FileResponse(
        path=job.result_path,
        media_type="application/pdf",
        filename=filename,
    )
