"""Owned private worker; never reuse a user's independently configured AI service."""
from __future__ import annotations

import atexit
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import requests

from pdf2zh.offline import OfflineError, OfflinePack
from pdf2zh.runtime_policy import EffectivePolicy


def _kill_with_parent_job():
    """Return a Windows Job Object that kills its members when this process exits.

    The backend owns the local worker. If the backend is killed (app closed,
    Task Manager, crash), the handle closes with it and Windows ends the
    worker too, so no orphan keeps RAM/VRAM. Returns None where unsupported.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = ExtendedLimits()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return None
        return job, kernel32
    except (OSError, AttributeError):
        return None


class LocalRuntime:
    def __init__(self) -> None:
        self.pack: OfflinePack | None = None
        self.process: subprocess.Popen | None = None
        self.url = ""
        self.state = "LOCAL_PREPARING"
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._backend = "gpu"
        self._reuse_pack: OfflinePack | None = None
        self._registered = False
        self._process_lock = threading.RLock()
        self._job = _kill_with_parent_job()
        # Set whenever a _prepare run ends, ready or not; restart() waits on it.
        self._settled = threading.Event()

    def start(self) -> None:
        if self._thread is None:
            self._stop.clear()
            self._settled.clear()
            self._thread = threading.Thread(target=self._prepare, daemon=True)
            self._thread.start()
            if not self._registered:
                atexit.register(self.close)
                self._registered = True

    def _prepare(self) -> None:
        try:
            self._prepare_worker()
        finally:
            self._settled.set()

    def _prepare_worker(self) -> None:
        try:
            pack = self._reuse_pack
            self._reuse_pack = None
            if pack is None:
                root = Path(os.environ.get("PDF_TRANSLATE_OFFLINE_PACK", "offline-data"))
                pack = OfflinePack(root)
                data_dir = os.environ.get("PDFTRANSLATE_DATA_DIR")
                pack.verify(Path(data_dir) / "offline-verified.json" if data_dir else None)
            else:
                pack.unchanged()
            pack.configure()
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            self.url = f"http://127.0.0.1:{port}"
            env = dict(os.environ)
            env.update({
                "OLLAMA_HOST": f"127.0.0.1:{port}",
                "OLLAMA_MODELS": str(pack.root / "models"),
                "OLLAMA_NO_CLOUD": "1", "OLLAMA_REMOTES": "", "OLLAMA_NOHISTORY": "1",
                "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1",
                "OLLAMA_ORIGINS": self.url, "NO_PROXY": "*",
            })
            if self._backend == "cpu":
                env["CUDA_VISIBLE_DEVICES"] = ""
                env["GGML_VK_VISIBLE_DEVICES"] = ""
            else:
                env.pop("CUDA_VISIBLE_DEVICES", None)
                env.pop("GGML_VK_VISIBLE_DEVICES", None)
            self.process = subprocess.Popen(
                [str(pack.asset("worker")), "serve"], env=env, cwd=pack.root,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if self._job is not None:
                job, kernel32 = self._job
                # Children the worker starts later (model runners) join the job too.
                kernel32.AssignProcessToJobObject(job, int(self.process._handle))
            session = requests.Session()
            session.trust_env = False
            for _ in range(120):
                if self._stop.wait(0.25):
                    self._terminate_process()
                    return
                if self.process.poll() is not None:
                    raise OfflineError("LOCAL_RUNTIME_UNAVAILABLE")
                try:
                    reply = session.get(f"{self.url}/api/tags", timeout=1)
                    reply.raise_for_status()
                    names = {m["name"] for m in reply.json()["models"]}
                    needed = pack.installed_aliases()
                    if not needed.issubset(names):
                        raise OfflineError("LOCAL_DATA_INVALID")
                    self.pack = pack
                    os.environ["PDF_TRANSLATE_OLLAMA_URL"] = self.url
                    self.state = "ready"
                    return
                except requests.RequestException:
                    continue
            raise OfflineError("LOCAL_RUNTIME_UNAVAILABLE")
        except OfflineError as error:
            self.state = error.code
            self._terminate_process()
        except Exception:
            self.state = "LOCAL_RUNTIME_UNAVAILABLE"
            self._terminate_process()

    def require(self) -> OfflinePack:
        if self.state != "ready" or self.pack is None:
            raise OfflineError(self.state)
        if self.process is None or self.process.poll() is not None:
            self.state = "LOCAL_RUNTIME_UNAVAILABLE"
            raise OfflineError(self.state)
        self.pack.unchanged()
        return self.pack

    def close(self) -> None:
        self._stop.set()
        self._terminate_process()

    def _terminate_process(self) -> None:
        with self._process_lock:
            child = self.process
            self.process = None
        if child is not None and child.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            else:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()

    def restart(self, backend: str, timeout: float = 35) -> None:
        if backend not in ("gpu", "cpu"):
            raise OfflineError("PROFILE_UNAVAILABLE")
        if backend == self._backend and self.state == "ready":
            return
        self._stop.set()
        self._terminate_process()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)
            if thread.is_alive():
                # Starting a second _prepare now would race the first one for
                # self.process/self.pack and leave an orphan worker behind.
                self.state = "LOCAL_RUNTIME_UNAVAILABLE"
                raise OfflineError(self.state)
        self._thread = None
        self._reuse_pack = self.pack
        self.pack = None
        self.url = ""
        self.state = "LOCAL_PREPARING"
        self._backend = backend
        self.start()
        self._settled.wait(timeout)
        self.require()

    def probe(self, alias: str, policy: EffectivePolicy, timeout: float = 60) -> bool:
        """Load/test/unload one private alias on this owned worker only."""
        started = time.monotonic()
        self.restart(policy.backend, min(timeout, 35))
        pack = self.require()
        if alias not in pack.installed_aliases():
            raise OfflineError("PROFILE_UNAVAILABLE")
        marker = "<b0></b0>"
        prompt = (
            "You are a professional English (en) to Vietnamese (vi) translator. "
            "Your goal is to accurately convey the meaning and nuances of the original "
            "English text while adhering to Vietnamese grammar, vocabulary, and cultural "
            "sensitivities.\nProduce only the Vietnamese translation, without any additional "
            "explanations or commentary. Please translate the following English text into "
            f"Vietnamese:\n\n\nOffline readiness marker {marker}."
        )
        session = requests.Session()
        session.trust_env = False
        try:
            remaining = max(1.0, timeout - (time.monotonic() - started))
            reply = session.post(
                f"{self.url}/api/generate",
                json={
                    "model": alias,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": 0,
                    "options": {
                        "num_ctx": policy.context_tokens,
                        "num_batch": policy.batch_tokens,
                        "num_thread": policy.thread_count,
                        "num_predict": min(policy.output_tokens, 64),
                        "temperature": 0,
                    },
                },
                timeout=remaining,
            )
            reply.raise_for_status()
            data = reply.json()
            return data.get("done") is True and marker in str(data.get("response", ""))
        except (requests.RequestException, ValueError):
            return False


runtime = LocalRuntime()
