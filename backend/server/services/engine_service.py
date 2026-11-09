"""Which translation engines this machine can use right now, in the user's words."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from pdf2zh.translator import (
    AZURE_KEY_ENV,
    AZURE_REGION_ENV,
    DEFAULT_OLLAMA_MODEL,
    LIGHT_OLLAMA_MODEL,
    _same_model,
    ollama_model_name,
    ollama_pull_command,
    azure_not_configured_message,
    azure_settings,
    ollama_status,
    user_config_path,
)

DEFAULT_ENGINE = "ollama"
# Engines the app offers. "handoff" is an agent workflow, not a user choice.
ENGINE_LABELS = {
    "ollama": "Ngoại tuyến (Ollama)",
    "azure": "Azure",
    "google": "Google (dự phòng)",
}
OLLAMA_MODELS = (DEFAULT_OLLAMA_MODEL, LIGHT_OLLAMA_MODEL)
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"


def ollama_installed() -> bool:
    """Whether the Ollama program exists here, running or not."""
    if shutil.which("ollama"):
        return True
    local = os.environ.get("LOCALAPPDATA")
    candidates = [Path(local) / "Programs" / "Ollama" / "ollama.exe"] if local else []
    candidates += [
        Path("/Applications/Ollama.app"),
        Path("/usr/local/bin/ollama"),
        Path("/usr/bin/ollama"),
    ]
    return any(path.exists() for path in candidates)


def allowed_ollama_models() -> tuple[str, ...]:
    """The two TranslateGemma sizes, plus a model named in the environment."""
    configured = ollama_model_name()
    if configured in OLLAMA_MODELS:
        return OLLAMA_MODELS
    return (*OLLAMA_MODELS, configured)


def describe_ollama(model: str | None = None) -> dict[str, object]:
    """Ollama's state for the status line: ready, not installed, not running, no model."""
    status = ollama_status(model)
    installed_models = [
        name
        for name in allowed_ollama_models()
        if any(_same_model(name, installed) for installed in status.installed_models)
    ]
    state = status.state
    message = status.message
    if state == "not_running" and not ollama_installed():
        state = "not_installed"
        message = (
            "Chưa cài Ollama. Tải tại https://ollama.com/download, cài đặt và mở "
            f"Ollama, rồi chạy: {ollama_pull_command(status.model)}"
        )
    return {
        "state": state,
        "ready": status.ready,
        "model": status.model,
        "base_url": status.base_url,
        "message": message,
        "pull_command": ollama_pull_command(status.model),
        "download_url": OLLAMA_DOWNLOAD_URL,
        "models": list(allowed_ollama_models()),
        "installed_models": installed_models,
    }


def describe_azure() -> dict[str, object]:
    """Whether an Azure key is configured, and where from. Never the key."""
    settings = azure_settings()
    if settings is None:
        return {
            "configured": False,
            "region": None,
            "source": None,
            "message": azure_not_configured_message(),
            "key_env": AZURE_KEY_ENV,
            "region_env": AZURE_REGION_ENV,
            "config_path": str(user_config_path()),
        }
    source = "biến môi trường" if settings.source == "environment" else settings.source
    return {
        "configured": True,
        "region": settings.region,
        "source": settings.source,
        "message": f"Đã cấu hình khóa Azure (từ {source}).",
        "key_env": AZURE_KEY_ENV,
        "region_env": AZURE_REGION_ENV,
        "config_path": str(user_config_path()),
    }


def describe_engines(model: str | None = None) -> dict[str, object]:
    return {
        "default": DEFAULT_ENGINE,
        "engines": [
            {"id": engine, "label": label} for engine, label in ENGINE_LABELS.items()
        ],
        "ollama": describe_ollama(model),
        "azure": describe_azure(),
    }
