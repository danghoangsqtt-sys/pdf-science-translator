"""Public profile contract, with no engine names or raw diagnostics."""
from __future__ import annotations

from pdf2zh.offline import MESSAGES, PROFILES, OfflineError, ProcessingProfile, profile_for
from webui.backend.services.runtime_service import runtime


def capabilities() -> dict[str, object]:
    code: str | None = None
    pack = None
    try:
        pack = runtime.require()
    except OfflineError as error:
        code = error.code
    profile_set = getattr(pack, "available_profiles", None)
    available = set(profile_set) if isinstance(profile_set, (set, frozenset)) else set(PROFILES)
    if pack is None:
        available.clear()
    default_profile = "balanced" if "balanced" in available else "fast"
    return {
        "offline": True,
        "default_profile": default_profile,
        "profiles": [
            {"id": p.id, "label": p.label, "description": p.description,
             "available": code is None and p.id in available,
             "reason_code": code if code is not None or p.id in available else "PROFILE_UNAVAILABLE",
             "message": MESSAGES.get(
                 code if code is not None or p.id in available else "PROFILE_UNAVAILABLE",
                 "Sẵn sàng xử lý trên máy.",
             )}
            for p in PROFILES.values()
        ],
    }


def require_profile(value: str) -> ProcessingProfile:
    profile_for(value)
    return runtime.require().require_profile(value)


def public_failure(error: BaseException) -> tuple[str, str]:
    if isinstance(error, OfflineError):
        return error.code, str(error)
    return "PROCESSING_FAILED", MESSAGES["PROCESSING_FAILED"]
