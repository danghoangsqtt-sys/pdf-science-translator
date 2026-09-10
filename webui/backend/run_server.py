import os
import sys

# Ensure repository root is in sys.path so that scripts.translate_pdf
# and bundled pdf2zh packages are always imported reliably.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn

if __name__ == "__main__":
    # Single-user local desktop application: binds strictly to 127.0.0.1, port 8089
    uvicorn.run("webui.backend.main:app", host="127.0.0.1", port=8089, reload=False)
