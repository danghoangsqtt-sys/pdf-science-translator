"""Strict, versioned schema helpers for local offline resource packs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping

REQUIRED_ASSETS = (
    "layout", "font", "ocr_font", "worker", "ocr_det_small", "ocr_rec_small",
    "ocr_det_medium", "ocr_rec_medium", "ocr_cls",
)
RUNTIME_REVISION = 1


@dataclass(frozen=True)
class PackContract:
    version: int
    common: frozenset[str]
    profiles: Mapping[str, frozenset[str]]
    models: Mapping[str, str]


def valid_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in ("", ".", "..") for part in path.parts)


def _path_list(value: object, files: set[str]) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("resource list")
    paths = frozenset(value)
    if len(paths) != len(value) or not all(valid_relative_path(path) for path in paths):
        raise ValueError("resource paths")
    if not paths.issubset(files):
        raise ValueError("resource not declared")
    return paths


def parse_contract(data: Any, allowed_models: Mapping[str, str]) -> PackContract:
    if not isinstance(data, dict) or data.get("version") not in (1, 2):
        raise ValueError("manifest version")
    entries = data.get("files")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("files")
    files = set(entries)
    for relative, expected in entries.items():
        if not valid_relative_path(relative) or not isinstance(expected, dict):
            raise ValueError("file entry")
        size, digest = expected.get("size"), expected.get("sha256")
        if not isinstance(size, int) or size < 0:
            raise ValueError("file size")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest.lower())):
            raise ValueError("file digest")
    assets = data.get("assets")
    if not isinstance(assets, dict) or any(name not in assets for name in REQUIRED_ASSETS):
        raise ValueError("assets")
    if not all(valid_relative_path(path) and path in files for path in assets.values()):
        raise ValueError("asset path")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("profiles")
    if data["version"] == 1:
        if set(profiles) != set(allowed_models):
            raise ValueError("v1 profiles")
        if any(profiles[ident] != allowed_models[ident] for ident in allowed_models):
            raise ValueError("v1 model")
        return PackContract(1, frozenset(files),
                            {ident: frozenset(files) for ident in profiles}, dict(profiles))

    compatibility = data.get("compatibility")
    if (not isinstance(compatibility, dict)
            or compatibility.get("platform") != "windows"
            or compatibility.get("architecture") != "amd64"
            or compatibility.get("runtime_revision") != RUNTIME_REVISION):
        raise ValueError("compatibility")
    if data.get("edition") not in ("lite", "full"):
        raise ValueError("edition")
    if not set(profiles).issubset(allowed_models):
        raise ValueError("unknown profile")
    common = _path_list(data.get("common"), files)
    if not set(assets.values()).issubset(common):
        raise ValueError("assets must be common")
    native = _path_list(data.get("native"), files)
    if not native.issubset(common) or assets["worker"] not in native:
        raise ValueError("native runtime")
    profile_files: dict[str, frozenset[str]] = {}
    models: dict[str, str] = {}
    covered = set(common)
    for ident, details in profiles.items():
        if not isinstance(details, dict) or details.get("model") != allowed_models[ident]:
            raise ValueError("profile model")
        resources = _path_list(details.get("files"), files)
        profile_files[ident] = resources
        models[ident] = details["model"]
        covered.update(resources)
    if covered != files:
        raise ValueError("orphan resources")
    if data["edition"] == "lite" and set(profiles) != {"fast"}:
        raise ValueError("lite profile set")
    return PackContract(2, common, profile_files, models)
