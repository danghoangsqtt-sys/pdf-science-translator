"""Assemble a fresh portable Windows application from verified local resources."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pdf2zh.offline import OfflinePack  # noqa: E402


def copy_tree(source: Path, destination: Path) -> None:
    patterns = ["__pycache__", "*.pyc", "*.optimized", ".git"]
    if source == ROOT / "webui/backend":
        patterns.append("data")
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*patterns))


def preflight(destination: Path, pack_root: Path) -> OfflinePack:
    """Validate every input before creating output or copying large resources."""
    destination = destination.resolve()
    pack_root = pack_root.resolve()
    if destination.exists():
        raise FileExistsError("Choose a new build directory; existing output is preserved")
    if destination == pack_root or destination.is_relative_to(pack_root):
        raise ValueError("Output must be separate from the input data")
    frontend = ROOT / "webui/frontend"
    required = [frontend / "dist/index.html", frontend / "dist-electron/main.cjs",
                frontend / "dist-electron/preload.mjs",
                frontend / "node_modules/electron/dist/electron.exe",
                ROOT / "LICENSE", ROOT / "THIRD_PARTY_NOTICES.md",
                ROOT / "pdf2zh/offline.py", ROOT / "webui/backend/main.py",
                ROOT / "scripts/translate_pdf.py"]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required local build input is missing: {path.relative_to(ROOT)}")
    pack = OfflinePack(pack_root)
    print("Verifying local data...", flush=True)
    pack.verify()
    # Leave working room for the OS and verification. No cleanup of existing builds.
    size = sum(path.stat().st_size for source in
               (pack_root, Path(sys.base_prefix), Path(sys.prefix) / "Lib/site-packages",
                frontend / "node_modules/electron/dist") for path in source.rglob("*") if path.is_file())
    ancestor = destination.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < size + 10 * 1024**3:
        raise OSError("Insufficient free disk space for a fresh build and reserve")
    return pack


def build(destination: Path, pack_root: Path) -> None:
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("Build with the repository Python 3.12 on Windows")
    destination = destination.resolve()
    pack = preflight(destination, pack_root)
    frontend = ROOT / "webui/frontend"
    for required in (frontend / "dist/index.html", frontend / "dist-electron/main.cjs",
                     frontend / "node_modules/electron/dist/electron.exe"):
        if not required.is_file():
            raise FileNotFoundError("Build frontend assets and install Electron first")
    destination.mkdir(parents=True)
    print("Copying application and Python 3.12...", flush=True)
    copy_tree(frontend / "node_modules/electron/dist", destination)
    (destination / "electron.exe").rename(destination / "PDFTranslate.exe")
    resources = destination / "resources"
    app = resources / "app"
    copy_tree(frontend / "dist", app / "dist")
    copy_tree(frontend / "dist-electron", app / "dist-electron")
    (app / "package.json").write_text(json.dumps({
        "name": "pdf-translate", "version": "0.3.0", "main": "dist-electron/main.cjs",
        "productName": "PDF Translate", "private": True,
    }), encoding="utf-8")
    copy_tree(Path(sys.base_prefix), resources / "python_runtime")
    copy_tree(Path(sys.prefix) / "Lib/site-packages", resources / "python_runtime/Lib/site-packages")
    for folder in ("pdf2zh", "webui/backend"):
        copy_tree(ROOT / folder, resources / folder)
    (resources / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/translate_pdf.py", resources / "scripts/translate_pdf.py")
    # The marker keeps cloud engines disabled even if the data directory is removed.
    (resources / "offline-edition.json").write_text('{"version":1}\n', encoding="utf-8")
    print("Copying verified local data...", flush=True)
    shutil.copytree(pack.root, resources / "offline-data")
    # Native GUI smoke checks resolve these two historical bundled asset locations.
    (resources / "app/assets").mkdir(parents=True, exist_ok=True)
    shutil.copy2(pack.asset("layout"), resources / "app/assets/doclayout.onnx")
    shutil.copy2(pack.asset("font"), resources / "app/assets/GoNotoKurrent-Regular.ttf")
    notices = resources / "legal"
    notices.mkdir()
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        path = ROOT / name
        shutil.copy2(path, notices / name)
    # Retain upstream notices that accompany the worker and the original model layers.
    for filename in ("LICENSE", "LICENSE.txt", "LICENSES.txt"):
        source = pack.asset("worker").parent / filename
        if source.is_file():
            shutil.copy2(source, notices / f"worker-{filename}")
    for index, path in enumerate(sorted((pack.root / "models/manifests").rglob("latest"))):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for layer in manifest["layers"]:
            if "license" in layer.get("mediaType", "").lower():
                blob = pack.root / "models/blobs" / layer["digest"].replace(":", "-")
                shutil.copy2(blob, notices / f"component-{index}-LICENSE.txt")
    if pack.available_profiles == {"fast"}:
        edition = ("Bản dành cho máy cấu hình yếu: chỉ có mức Nhanh.\n"
                   "Muốn dùng Cân bằng / Chất lượng cao, hãy dùng bản cho máy cấu hình mạnh.\n")
    else:
        edition = ("Bản dành cho máy cấu hình mạnh.\n"
                   "Chọn Nhanh / Cân bằng / Chất lượng cao; mặc định Cân bằng.\n")
    (destination / "HUONG-DAN.txt").write_text(
        "PDF Translate — Windows ngoại tuyến\n\n"
        "Mở PDFTranslate.exe. Giữ nguyên toàn bộ thư mục khi sao chép sang máy khác.\n"
        + edition +
        "Lần mở đầu cần thời gian kiểm tra dữ liệu. Không cần Internet hoặc cài công cụ AI riêng.\n"
        "Nếu thiếu dữ liệu, dùng lại bộ ứng dụng đầy đủ được cấp. Không tự tải qua mạng.\n"
        "PDF nguồn được giữ nguyên. Hãy đọc cảnh báo và đối chiếu bản dịch trước khi sử dụng.\n"
        "Đây là bản portable kiểm thử nội bộ, chưa ký số/phát hành.\n",
        encoding="utf-8-sig",
    )
    python = resources / "python_runtime/python.exe"
    env = dict(os.environ, PYTHONNOUSERSITE="1", PDF_TRANSLATE_OFFLINE="1")
    subprocess.run([str(python), "-s", "-m", "pip", "check"], env=env, cwd=resources, check=True)
    subprocess.run([str(python), "-s", "-c",
                    "import fitz, onnxruntime, tkinter; import pdf2zh.offline; import webui.backend.main; "
                    "assert pdf2zh.offline.active(); print('Portable dependencies ready')"],
                   env=env, cwd=resources, check=True)
    print(f"Portable Windows build ready: {destination}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.pack)
