"""Prepare an offline data pack exclusively from existing local resources."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pdf2zh.offline import PROFILES, sha256  # noqa: E402
from pdf2zh.resource_pack import RUNTIME_REVISION  # noqa: E402

SOURCES = {
    "local-fast": ("translategemma", "4b"),
    "local-balanced": ("translategemma", "12b"),
    "local-quality": ("translategemma", "12b"),
    "local-rescue": ("qwen3.5", "9b"),
}
# The lite edition is for machines that cannot hold the 12B models: Nhanh only.
EDITION_PROFILES = {"full": tuple(PROFILES), "lite": ("fast",)}


def _aliases(profiles: tuple[str, ...]) -> list[str]:
    """Model aliases a profile set needs, its rescue fallback included."""
    names: list[str] = []
    for ident in profiles:
        for model in (PROFILES[ident].model, PROFILES[ident].fallback):
            if model and model.split(":", 1)[0] not in names:
                names.append(model.split(":", 1)[0])
    return names


def prepare(destination: Path, worker: Path, models: Path, ocr: Path, edition: str = "full") -> None:
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("Destination already exists; choose a new output directory")
    profiles = EDITION_PROFILES[edition]
    manifests = {}
    for alias in _aliases(profiles):
        name, tag = SOURCES[alias]
        source = models / "manifests" / "registry.ollama.ai" / "library" / name / tag
        manifests[alias] = json.loads(source.read_text(encoding="utf-8"))
    if not worker.is_file() or not (worker.parent / "lib").is_dir():
        raise FileNotFoundError("Local worker runtime is incomplete")
    destination.mkdir(parents=True)
    assets = {}

    def copy(source: Path, relative: str, key: str | None = None) -> None:
        target = destination / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if key:
            assets[key] = relative

    copy(worker, "worker/pdftranslate-worker.exe", "worker")
    shutil.copytree(worker.parent / "lib", destination / "worker" / "lib")
    copy(ROOT / "app/assets/doclayout.onnx", "assets/layout.onnx", "layout")
    copy(ROOT / "app/assets/GoNotoKurrent-Regular.ttf", "assets/text.ttf", "font")
    copy(ROOT / "app/fonts/BeVietnamPro-Regular.ttf", "assets/ocr-font.ttf", "ocr_font")
    copy(ROOT / "app/fonts/BeVietnamPro-OFL.txt", "assets/ocr-font-OFL.txt")
    for name in ("det_small", "rec_small", "det_medium", "rec_medium"):
        copy(ocr / f"PP-OCRv6_{name}.onnx", f"assets/ocr/PP-OCRv6_{name}.onnx", f"ocr_{name}")
    copy(ocr / "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
         "assets/ocr/ch_ppocr_mobile_v2.0_cls_mobile.onnx", "ocr_cls")
    model_files: dict[str, list[str]] = {}
    for alias, manifest in manifests.items():
        owned = model_files.setdefault(alias, [])
        for layer in [manifest["config"], *manifest["layers"]]:
            digest = layer["digest"]
            if not digest.startswith("sha256:") or len(digest) != 71:
                raise ValueError("Unsupported local model manifest")
            filename = digest.replace(":", "-")
            copy(models / "blobs" / filename, f"models/blobs/{filename}")
            owned.append(f"models/blobs/{filename}")
        relative = f"models/manifests/registry.ollama.ai/library/{alias}/latest"
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        owned.append(relative)
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            relative = path.relative_to(destination).as_posix()
            files[relative] = {"size": path.stat().st_size, "sha256": sha256(path)}
    if edition == "full":
        # Unchanged v1 layout: the format the shipped portable build was verified with.
        manifest = {
            "version": 1, "assets": assets, "files": files,
            "profiles": {ident: p.model for ident, p in PROFILES.items()},
        }
    else:
        profile_data = {}
        for ident in profiles:
            owned = []
            for alias in _aliases((ident,)):
                owned.extend(item for item in model_files[alias] if item not in owned)
            profile_data[ident] = {"model": PROFILES[ident].model, "files": owned}
        per_model = {item for owned in model_files.values() for item in owned}
        manifest = {
            "version": 2, "edition": edition,
            "compatibility": {"platform": "windows", "architecture": "amd64",
                              "runtime_revision": RUNTIME_REVISION},
            "assets": assets,
            "native": sorted(name for name in files if name.startswith("worker/")),
            "common": sorted(name for name in files if name not in per_model),
            "profiles": profile_data,
            "files": files,
        }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Offline data prepared: {len(files)} files, {sum(f['size'] for f in files.values())} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--models", type=Path, default=Path(os.environ.get("OLLAMA_MODELS", "models")))
    parser.add_argument("--ocr", type=Path, required=True)
    parser.add_argument("--edition", choices=sorted(EDITION_PROFILES), default="full",
                        help="full: Nhanh/Cân bằng/Chất lượng cao; lite: Nhanh only")
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.worker, arguments.models, arguments.ocr, arguments.edition)
