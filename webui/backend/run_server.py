import os
import sys

# Ensure repository root is in sys.path so that scripts.translate_pdf
# and bundled pdf2zh packages are always imported reliably.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _use_bundled_assets() -> None:
    """Point the engine at the packaged model/font so no download is needed.

    setdefault, so an explicit override still wins, and only when the file is actually present, so a dev checkout without
    app/assets/ populated falls through to the engine's own download logic
    unchanged instead of pointing at a path that doesn't exist.
    """
    assets = os.path.join(PROJECT_ROOT, "app", "assets")
    model = os.path.join(assets, "doclayout.onnx")
    font = os.path.join(assets, "GoNotoKurrent-Regular.ttf")
    if os.path.isfile(model):
        os.environ.setdefault("PDF_TRANSLATE_MODEL", model)
    if os.path.isfile(font):
        os.environ.setdefault("NOTO_FONT_PATH", font)


os.environ["PDF_TRANSLATE_OFFLINE"] = "1"
os.environ.setdefault("PDF_TRANSLATE_OFFLINE_PACK", os.path.join(PROJECT_ROOT, "offline-data"))
from pdf2zh.offline import install_network_guard

install_network_guard()
import logging
logging.disable(logging.CRITICAL)

import uvicorn

if __name__ == "__main__":
    # Single-user local desktop application: binds strictly to 127.0.0.1, port 8089
    uvicorn.run("webui.backend.main:app", host="127.0.0.1",
                port=int(os.environ.get("PDFTRANSLATE_API_PORT", "8089")),
                reload=False, access_log=False)
