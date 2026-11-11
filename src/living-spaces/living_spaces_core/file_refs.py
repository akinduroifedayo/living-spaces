"""Agent-side file references: copy a local file or a public HTTPS download into a Space as bytes."""
from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
import tempfile
from pathlib import Path

from . import db, limits, net
from .errors import SpacesError

DENIED_NAMES = (".env", ".env.*", "auth.json", "*token*", "*secret*", "*.key")
DENIED_DIRS = (".ssh",)


def _real(path) -> Path:
    return Path(os.path.realpath(path))


def _roots():
    return [_real(db.hermes_home()), _real(tempfile.gettempdir()), _real(Path.home())]


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _denied(path: Path) -> bool:
    if any(part in DENIED_DIRS for part in path.parts):
        return True
    name = path.name.lower()
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in DENIED_NAMES):
        return True
    store = _real(db.db_path())
    return path in (store, store.with_name(store.name + "-wal"), store.with_name(store.name + "-shm"))


def read_path(raw: str) -> bytes:
    if not isinstance(raw, str) or not raw or "\x00" in raw or not os.path.isabs(raw):
        raise SpacesError("invalid", "from_path must be an absolute local path")
    resolved = _real(raw)
    if _denied(Path(os.path.normpath(raw))) or _denied(resolved):
        raise SpacesError("blocked", "from_path points at a credential or Spaces store file", reason="denied_path")
    if not any(_within(resolved, root) for root in _roots()):
        raise SpacesError("blocked", "from_path must be inside the Hermes home, the temp folder or your home folder",
                          reason="outside_roots")
    try:
        info = os.stat(resolved)
    except OSError:
        raise SpacesError("invalid", "from_path does not exist or cannot be read") from None
    if not stat.S_ISREG(info.st_mode):
        raise SpacesError("invalid", "from_path must be a regular file")
    limits.check(info.st_size, limits.FILE_BYTES, "file bytes")
    try:
        with open(resolved, "rb") as handle:
            content = handle.read(limits.FILE_BYTES + 1)
    except OSError:
        raise SpacesError("invalid", "from_path cannot be read") from None
    limits.check(len(content), limits.FILE_BYTES, "file bytes")
    return content


def fetch_url(url: str):
    """Return (bytes, provenance note). The bot is acting, so no Space `net` grant applies."""
    if not isinstance(url, str):
        raise SpacesError("invalid", "from_url must be an HTTPS URL")
    result, content = net.fetch_for_agent(url, max_bytes=limits.FILE_BYTES)
    return content, f"{result['url']} sha256:{hashlib.sha256(content).hexdigest()}"
