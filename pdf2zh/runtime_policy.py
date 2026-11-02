"""Stable per-job resource policy candidates for the offline runtime."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

POLICY_REVISION = 1
GIB = 1024**3


@dataclass(frozen=True)
class ResourceSnapshot:
    ram_total_bytes: int | None
    ram_available_bytes: int | None
    vram_total_bytes: int | None
    vram_free_bytes: int | None
    logical_processors: int | None


@dataclass(frozen=True)
class EffectivePolicy:
    profile: str
    backend: str
    context_tokens: int
    batch_tokens: int
    thread_count: int
    output_tokens: int
    resource_class: str
    pack_revision: str
    revision: int = POLICY_REVISION

    def __post_init__(self) -> None:
        if self.profile not in ("fast", "balanced", "quality"):
            raise ValueError("profile")
        if self.backend not in ("gpu", "cpu"):
            raise ValueError("backend")
        if self.context_tokens not in (2048, 4096):
            raise ValueError("context")
        if not 1 <= self.thread_count <= 16 or not 1 <= self.batch_tokens <= 256:
            raise ValueError("runtime limits")
        if not 128 <= self.output_tokens < self.context_tokens:
            raise ValueError("output limit")
        if not self.pack_revision or len(self.pack_revision) > 128:
            raise ValueError("pack revision")

    def stable_key(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def _resource_class(snapshot: ResourceSnapshot) -> str:
    ram = 0 if snapshot.ram_total_bytes is None else snapshot.ram_total_bytes // GIB
    vram = 0 if snapshot.vram_total_bytes is None else snapshot.vram_total_bytes // GIB
    ram_band = 24 if ram >= 24 else 16 if ram >= 16 else 8 if ram >= 8 else 0
    vram_band = 12 if vram >= 12 else 8 if vram >= 8 else 4 if vram >= 4 else 0
    return f"ram{ram_band}-vram{vram_band}"


def candidate_policies(profile: str, snapshot: ResourceSnapshot,
                       pack_revision: str) -> tuple[EffectivePolicy, ...]:
    """Return at most two conservative policies to prove, never a readiness claim."""
    if profile not in ("fast", "balanced", "quality"):
        raise ValueError("profile")
    threads = max(1, min(snapshot.logical_processors or 4, 8))
    resource_class = _resource_class(snapshot)
    candidates: list[EffectivePolicy] = []
    vram_total = snapshot.vram_total_bytes
    vram_free = snapshot.vram_free_bytes
    ram_total = snapshot.ram_total_bytes
    ram_free = snapshot.ram_available_bytes

    if (vram_total is not None and vram_total >= 8 * GIB
            and (vram_free is None or vram_free >= 4 * GIB)):
        candidates.append(EffectivePolicy(
            profile, "gpu", 4096, 128, threads, 1024, resource_class, pack_revision,
        ))
    minimum_total = 4 * GIB if profile == "fast" else 8 * GIB if profile == "balanced" else 10 * GIB
    if (vram_total is not None and vram_total >= minimum_total
            and (vram_free is None or vram_free >= 5 * GIB // 2)):
        candidates.append(EffectivePolicy(
            profile, "gpu", 2048, 64, threads, 640, resource_class, pack_revision,
        ))
    if (profile == "fast" and ram_total is not None and ram_total >= 16 * GIB
            and (ram_free is None or ram_free >= 6 * GIB)):
        candidates.append(EffectivePolicy(
            profile, "cpu", 2048, 32, min(threads, 6), 512, resource_class, pack_revision,
        ))
    unique: list[EffectivePolicy] = []
    for candidate in candidates:
        if candidate.stable_key() not in {item.stable_key() for item in unique}:
            unique.append(candidate)
    return tuple(unique[:2])
