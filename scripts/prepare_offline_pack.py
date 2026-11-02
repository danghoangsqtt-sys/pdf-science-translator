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

SOURCES = {
    "local-fast": ("translategemma", "4b"),
    "local-balanced": ("translategemma", "12b"),
    "local-quality": ("translategemma", "12b"),
    "local-rescue": ("qwen3.5", "9b"),
}


def prepare(destination: Path, worker: Path, models: Path, ocr: Path) -> None:
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("Destination already exists; choose a new output directory")
    manifests = {}
    for alias, (name, tag) in SOURCES.items():
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
    for alias, manifest in manifests.items():
        for layer in [manifest["config"], *manifest["layers"]]:
            digest = layer["digest"]
            if not digest.startswith("sha256:") or len(digest) != 71:
                raise ValueError("Unsupported local model manifest")
            filename = digest.replace(":", "-")
            copy(models / "blobs" / filename, f"models/blobs/{filename}")
        relative = f"models/manifests/registry.ollama.ai/library/{alias}/latest"
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            relative = path.relative_to(destination).as_posix()
            files[relative] = {"size": path.stat().st_size, "sha256": sha256(path)}
    manifest = {
        "version": 1, "assets": assets, "files": files,
        "profiles": {ident: p.model for ident, p in PROFILES.items()},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Offline data prepared: {len(files)} files, {sum(f['size'] for f in files.values())} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--models", type=Path, default=Path(os.environ.get("OLLAMA_MODELS", "models")))
    parser.add_argument("--ocr", type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.worker, arguments.models, arguments.ocr)
