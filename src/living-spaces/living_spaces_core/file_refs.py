from __future__ import annotations

from contextlib import ExitStack
import fnmatch
import hashlib
import os
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from . import db, limits, net
from .errors import SpacesError

CACHE_SUBDIRS = (
    "cache/images", "cache/documents", "cache/screenshots", "cache/vision",
    "cache/video", "cache/videos", "cache/generated/images", "downloads/connectors",
    "images", "cache/scratch",
)
LEGACY_CACHE_SUBDIRS = (
    "image_cache", "document_cache", "browser_screenshots", "temp_vision_images",
    "temp_video_files", "video_cache",
)
DENIED_NAMES = (".env", ".env.*", ".envrc", "auth.json", ".credentials.json", "credentials.json", "*.key",
                ".netrc", "_netrc", ".npmrc", ".git-credentials", ".gitconfig", ".boto", ".pypirc") + tuple(
    stem + extension
    for stem in ("token", "tokens", ".token", ".tokens", "*[._-]token", "*[._-]tokens",
                 "secret", "secrets", ".secret", ".secrets", "*[._-]secret", "*[._-]secrets")
    for extension in ("", ".json", ".txt", ".yaml", ".yml", ".toml")
)
DENIED_DIRS = (".ssh", ".aws", ".docker", ".kube", ".gnupg", ".git", ".azure", ".gcloud",
               ".claude", ".codex", ".cursor", ".gemini", ".aider", ".continue", ".codeium",
               ".openclaw", ".pi", ".qwen", ".copilot", ".windsurf")
DENIED_STORES = tuple(tuple(path.lower().split("/")) for path in (
    ".config/gh", ".config/gcloud", ".config/git", ".config/google-chrome", ".config/chromium",
    ".config/opencode", ".local/share/opencode",
    ".config/BraveSoftware", ".config/microsoft-edge", ".mozilla/firefox",
    "Library/Keychains", "Library/Safari", "Library/Application Support/Google/Chrome",
    "Library/Application Support/Chromium", "Library/Application Support/BraveSoftware",
    "Library/Application Support/Microsoft Edge", "Library/Application Support/Firefox",
    "AppData/Local/Google/Chrome", "AppData/Local/Microsoft/Edge", "AppData/Roaming/Mozilla/Firefox",
    "AppData/Roaming/gcloud", "AppData/Roaming/gnupg",
))
_HAS_SECURE_OPEN = (os.open in os.supports_dir_fd
                    and all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY")))
PROVENANCE_URL_CHARS = 512


def _real(path) -> Path:
    return Path(os.path.realpath(path))


def _roots():
    home = Path(os.path.abspath(db.hermes_home()))
    real_home = _real(home)
    roots = []
    for subdir in (*CACHE_SUBDIRS, *LEGACY_CACHE_SUBDIRS):
        root, resolved = home / subdir, real_home / subdir
        # A cache symlink must not redefine the allowlist's boundary.
        if _real(root) != resolved:
            continue
        if subdir in LEGACY_CACHE_SUBDIRS:
            try:
                if not root.is_dir() or next(root.iterdir(), None) is None:
                    continue
            except OSError:
                continue
        roots.extend((root, resolved))
    return roots


def _hermes_homes():
    homes = {Path(os.path.abspath(db.hermes_home())), Path.home() / ".hermes"}
    homes.update(_real(home) for home in tuple(homes))
    for home in tuple(homes):
        if home.parent.name == "profiles":
            homes.add(home.parent.parent)
    return homes


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _denied(path: Path, cache_roots) -> bool:
    # TMPDIR never grants access to the rest of any Hermes home or its profiles.
    if (any(_within(path, home) for home in _hermes_homes())
            and not any(_within(path, root) for root in cache_roots)):
        return True
    parts = tuple(part.lower() for part in path.parts)
    if any(part in DENIED_DIRS for part in parts):
        return True
    if any(parts[i:i + len(store)] == store for store in DENIED_STORES for i in range(len(parts))):
        return True
    if any(fnmatch.fnmatchcase(path.name.lower(), pattern) for pattern in DENIED_NAMES):
        return True
    store = _real(db.db_path())
    return path in (store, store.with_name(store.name + "-wal"), store.with_name(store.name + "-shm"))


def _check_size(size, maximum):
    limits.check(size, limits.FILE_BYTES, "file bytes")
    limits.check(size, maximum, "available project bytes")


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_path(raw: str, *, max_bytes=None) -> bytes:
    if not isinstance(raw, str) or not raw or "\x00" in raw or not os.path.isabs(raw):
        raise SpacesError("invalid", "from_path must be an absolute local path")
    if ".." in Path(raw).parts:
        raise SpacesError("blocked", "from_path cannot contain parent traversal", reason="outside_roots")
    original = Path(raw)
    resolved = _real(raw)
    cache_roots = _roots()
    if _denied(original, cache_roots) or _denied(resolved, cache_roots):
        raise SpacesError("blocked", "from_path points at a credential or Spaces store file", reason="denied_path")
    roots = list(cache_roots)
    temp = Path(os.path.abspath(tempfile.gettempdir()))
    real_temp = _real(temp)
    if not any(_within(_real(home), real_temp) for home in (*_hermes_homes(), Path.home())):
        roots.extend((temp, real_temp))
    if (not any(_within(original, root) for root in roots)
            or not any(_within(resolved, root) for root in roots)):
        raise SpacesError("blocked", "from_path must be inside a supported Hermes media/download cache or temp folder; "
                          "stage authorized files with native tools first", reason="outside_roots")
    if not _HAS_SECURE_OPEN:
        raise SpacesError("blocked", "Local imports require descriptor-relative no-follow and nonblocking opens",
                          reason="unsupported_platform")
    maximum = limits.FILE_BYTES if max_bytes is None else min(max_bytes, limits.FILE_BYTES)
    try:
        expected = os.stat(resolved, follow_symlinks=False)
        with ExitStack() as handles:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
            directory = os.open(resolved.anchor, flags | os.O_DIRECTORY)
            handles.callback(os.close, directory)
            for part in resolved.parts[1:-1]:
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                handles.callback(os.close, directory)
            leaf = os.open(resolved.name, flags, dir_fd=directory)
            handles.callback(os.close, leaf)
            info = os.fstat(leaf)
            if not stat.S_ISREG(info.st_mode):
                raise SpacesError("invalid", "from_path must be a regular file")
            _check_size(info.st_size, maximum)
            if _identity(info) != _identity(expected):
                raise SpacesError("invalid", "from_path changed while being imported")
            content = bytearray()
            while True:
                chunk = os.read(leaf, min(65536, maximum + 1 - len(content)))
                if not chunk:
                    break
                _check_size(len(content) + len(chunk), maximum)
                content.extend(chunk)
            after = os.fstat(leaf)
            _check_size(after.st_size, maximum)
            if _identity(after) != _identity(info) or after.st_size != len(content):
                raise SpacesError("invalid", "from_path changed while being imported")
            return bytes(content)
    except OSError:
        raise SpacesError("invalid", "from_path does not exist, changed or cannot be read safely") from None


def _url_note(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parts.port is not None:
            host += f":{parts.port}"
        clean = urlunsplit((parts.scheme, host, "", "", ""))
    except ValueError:
        return "[unavailable URL]"
    return clean[:PROVENANCE_URL_CHARS]


def fetch_url(url: str, *, max_bytes=None):
    if not isinstance(url, str):
        raise SpacesError("invalid", "from_url must be an HTTPS URL")
    maximum = limits.FILE_BYTES if max_bytes is None else min(max_bytes, limits.FILE_BYTES)
    result, content = net.fetch_for_agent(url, max_bytes=maximum)
    source, final = _url_note(url), _url_note(result["url"])
    origin = final if source == final else f"{source} to {final}"
    return content, f"{origin} sha256:{hashlib.sha256(content).hexdigest()}"
