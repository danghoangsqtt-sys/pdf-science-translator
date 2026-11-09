"""Fail-closed policy and private asset contract for the Windows offline edition."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pdf2zh.resource_pack import PackContract, parse_contract, valid_relative_path

MESSAGES = {
    "INVALID_REQUEST": "Yêu cầu không hợp lệ. Hãy kiểm tra tài liệu và các lựa chọn.",
    "LOCAL_DATA_MISSING": "Chưa có đủ dữ liệu cục bộ. Hãy bổ sung gói dữ liệu ngoại tuyến.",
    "LOCAL_DATA_INVALID": "Gói dữ liệu cục bộ không hợp lệ. Hãy dùng lại gói được cấp.",
    "LOCAL_PREPARING": "Đang chuẩn bị bộ xử lý cục bộ. Vui lòng chờ.",
    "LOCAL_RUNTIME_UNAVAILABLE": "Bộ xử lý cục bộ chưa sẵn sàng. Hãy khởi động lại ứng dụng.",
    "LOCAL_BUSY": "Bộ xử lý cục bộ đang bận. Hãy thử kiểm tra lại sau.",
    "LOCAL_CHECK_CANCELLED": "Đã dừng kiểm tra cấu hình máy.",
    "LOCAL_CHECK_TIMEOUT": "Kiểm tra cấu hình máy chưa hoàn tất trong thời gian cho phép.",
    "PROFILE_UNAVAILABLE": "Mức xử lý này chưa sẵn sàng trên máy.",
    "OFFLINE_POLICY": "Thao tác không được hỗ trợ trong bản ngoại tuyến.",
    "PROCESSING_FAILED": "Không thể xử lý tài liệu. Tệp nguồn được giữ nguyên.",
}


class OfflineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code if code in MESSAGES else "PROCESSING_FAILED"
        super().__init__(f"{MESSAGES[self.code]} Mã hỗ trợ: {self.code}.")


@dataclass(frozen=True)
class ProcessingProfile:
    id: str
    label: str
    description: str
    model: str
    retries: int
    rescues: int
    fallback: str | None


PROFILES = {
    "fast": ProcessingProfile("fast", "Nhanh", "Ưu tiên tốc độ, ít tài nguyên.",
                              "local-fast:latest", 1, 0, None),
    "balanced": ProcessingProfile("balanced", "Cân bằng", "Cân bằng thời gian và độ đầy đủ.",
                                  "local-balanced:latest", 2, 1, None),
    "quality": ProcessingProfile("quality", "Chất lượng cao", "Xử lý kỹ hơn, có thể chậm hơn.",
                                 "local-quality:latest", 3, 3, "local-rescue:latest"),
}


def active() -> bool:
    return (os.environ.get("PDF_TRANSLATE_OFFLINE") == "1"
            or (Path(__file__).resolve().parents[1] / "offline-edition.json").is_file())


def profile_for(value: str) -> ProcessingProfile:
    try:
        return PROFILES[value]
    except KeyError:
        raise OfflineError("PROFILE_UNAVAILABLE") from None


def loopback(host: str | bytes | None) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(str(host).split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def install_network_guard() -> None:
    """Block Python DNS/TCP/UDP egress; worker has a separate local-only policy."""
    if getattr(socket, "_pdftranslate_offline", False):
        return
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_addrinfo = socket.getaddrinfo

    def check(sock: socket.socket, address: Any) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            if not isinstance(address, tuple) or not loopback(address[0]):
                raise OfflineError("OFFLINE_POLICY")

    def connect(sock: socket.socket, address: Any) -> Any:
        check(sock, address)
        return original_connect(sock, address)

    def connect_ex(sock: socket.socket, address: Any) -> Any:
        check(sock, address)
        return original_connect_ex(sock, address)

    def sendto(sock: socket.socket, *args: Any) -> Any:
        check(sock, args[-1])
        return original_sendto(sock, *args)

    def addrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host is not None and not loopback(host):
            raise OfflineError("OFFLINE_POLICY")
        return original_addrinfo("127.0.0.1" if host == "localhost" else host,
                                 port, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    socket.getaddrinfo = addrinfo
    socket._pdftranslate_offline = True
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class OfflinePack:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        try:
            manifest = self.root / "manifest.json"
            if not manifest.is_file():
                raise OfflineError("LOCAL_DATA_MISSING")
            if manifest.stat().st_size > 4 * 1024 * 1024:
                raise OfflineError("LOCAL_DATA_INVALID")
            self.data = json.loads(manifest.read_text(encoding="utf-8"))
            self.contract: PackContract = parse_contract(
                self.data, {ident: profile.model for ident, profile in PROFILES.items()}
            )
            self.signatures: dict[str, tuple[int, int]] = {}
            # Files already hashed on an earlier launch: relative -> (size, mtime_ns, sha256).
            self._trusted: dict[str, tuple[int, int, str]] = {}
            self.available_profiles: set[str] = set()
            self.profile_errors: dict[str, str] = {}
        except OfflineError:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise OfflineError("LOCAL_DATA_INVALID") from None

    def path(self, relative: str) -> Path:
        if not valid_relative_path(relative):
            raise OfflineError("LOCAL_DATA_INVALID")
        unresolved = self.root / relative
        candidate = unresolved.resolve()
        if unresolved.is_symlink() or not candidate.is_relative_to(self.root):
            raise OfflineError("LOCAL_DATA_INVALID")
        if not candidate.is_file():
            raise OfflineError("LOCAL_DATA_MISSING")
        return candidate

    def asset(self, name: str) -> Path:
        try:
            relative = self.data["assets"][name]
            if relative not in self.data["files"]:
                raise OfflineError("LOCAL_DATA_INVALID")
            return self.path(relative)
        except (KeyError, TypeError):
            raise OfflineError("LOCAL_DATA_INVALID") from None

    def _verify_files(self, relatives: set[str] | frozenset[str]) -> None:
        verified: dict[str, tuple[int, int]] = {}
        for relative in relatives:
            expected = self.data["files"][relative]
            path = self.path(relative)
            stat = path.stat()
            if stat.st_size != expected["size"]:
                raise OfflineError("LOCAL_DATA_INVALID")
            # Hashing ~20 GB on every launch took minutes. A file whose size and
            # modification time match the earlier full hash is trusted; any
            # change to it is hashed again.
            if self._trusted.get(relative) != (stat.st_size, stat.st_mtime_ns, expected["sha256"]):
                if sha256(path) != expected["sha256"]:
                    raise OfflineError("LOCAL_DATA_INVALID")
            verified[relative] = (stat.st_size, stat.st_mtime_ns)
        self.signatures.update(verified)

    @staticmethod
    def _aliases(ident: str) -> set[str]:
        profile = PROFILES[ident]
        return {profile.model} | ({profile.fallback} if profile.fallback else set())

    def _verify_profile_models(self, ident: str) -> None:
        allowed = self.contract.profiles[ident] | self.contract.common
        for alias in self._aliases(ident):
            name, tag = alias.split(":", 1)
            relative = f"models/manifests/registry.ollama.ai/library/{name}/{tag}"
            if relative not in allowed or relative not in self.signatures:
                raise OfflineError("LOCAL_DATA_INVALID")
            model = json.loads(self.path(relative).read_text(encoding="utf-8"))
            for layer in [model["config"], *model["layers"]]:
                digest = layer["digest"]
                if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
                    raise OfflineError("LOCAL_DATA_INVALID")
                blob = f"models/blobs/{digest.replace(':', '-')}"
                if blob not in allowed or blob not in self.signatures:
                    raise OfflineError("LOCAL_DATA_INVALID")

    def _cache_key(self) -> str:
        return f"{self.root}|{sha256(self.root / 'manifest.json')}"

    def _load_cache(self, cache: Path | None) -> None:
        self._trusted = {}
        if cache is None:
            return
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("key") == self._cache_key():
                self._trusted = {k: (int(v[0]), int(v[1]), str(v[2])) for k, v in data["files"].items()}
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
            self._trusted = {}

    def _save_cache(self, cache: Path | None) -> None:
        if cache is None:
            return
        files = {relative: [size, mtime, self.data["files"][relative]["sha256"]]
                 for relative, (size, mtime) in self.signatures.items()}
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_suffix(".tmp")
            temporary.write_text(json.dumps({"key": self._cache_key(), "files": files}), encoding="utf-8")
            os.replace(temporary, cache)
        except OSError:
            pass

    def verify(self, cache: Path | None = None) -> None:
        """Check every file against the manifest; `cache` remembers files already hashed."""
        self._load_cache(cache)
        self._verify(cache)

    def _verify(self, cache: Path | None) -> None:
        try:
            self._verify_files(self.contract.common)
            for asset in ("layout", "font", "ocr_font", "worker", "ocr_det_small", "ocr_rec_small",
                          "ocr_det_medium", "ocr_rec_medium", "ocr_cls"):
                self.asset(asset)
            self.available_profiles.clear()
            self.profile_errors.clear()
            for ident, resources in self.contract.profiles.items():
                try:
                    self._verify_files(resources)
                    self._verify_profile_models(ident)
                    self.available_profiles.add(ident)
                except OfflineError as error:
                    if self.contract.version == 1:
                        raise
                    self.profile_errors[ident] = error.code
            if not self.available_profiles:
                raise OfflineError("LOCAL_DATA_INVALID")
            self._save_cache(cache)
        except OfflineError:
            raise
        except (KeyError, TypeError, OSError, ValueError):
            raise OfflineError("LOCAL_DATA_INVALID") from None

    def unchanged(self) -> None:
        try:
            for relative, signature in self.signatures.items():
                stat = self.path(relative).stat()
                if (stat.st_size, stat.st_mtime_ns) != signature:
                    raise OfflineError("LOCAL_DATA_INVALID")
        except OSError:
            raise OfflineError("LOCAL_DATA_INVALID") from None

    def configure(self) -> None:
        os.environ["PDF_TRANSLATE_DATA_REVISION"] = sha256(self.root / "manifest.json")
        os.environ["PDF_TRANSLATE_MODEL"] = str(self.asset("layout"))
        os.environ["NOTO_FONT_PATH"] = str(self.asset("font"))
        os.environ["PDF_TRANSLATE_OCR_FONT"] = str(self.asset("ocr_font"))
        os.environ["PDF_TRANSLATE_OCR_ASSET_DIR"] = str(self.asset("ocr_cls").parent)

    def require_profile(self, ident: str) -> ProcessingProfile:
        if ident not in self.available_profiles:
            raise OfflineError("PROFILE_UNAVAILABLE")
        return profile_for(ident)

    def installed_aliases(self) -> set[str]:
        return set().union(*(self._aliases(ident) for ident in self.available_profiles))


def enforce_engine(engine: str, model: str | None) -> None:
    if active():
        allowed = {p.model for p in PROFILES.values()}
        if engine != "ollama" or model not in allowed:
            raise OfflineError("OFFLINE_POLICY")
