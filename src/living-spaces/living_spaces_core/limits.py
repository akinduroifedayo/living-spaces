"""Release-one resource limits and input primitives."""
import json
import re

from .errors import SpacesError

PROJECT_BYTES = 25 * 1024 * 1024
PROJECT_FILES = 600
FILE_BYTES = 8 * 1024 * 1024
DATA_BYTES = 256 * 1024
SOURCE_BYTES = 64 * 1024
RECORDS = 50_000
BATCH_OPS = 500
LOG_ENTRIES = 50
LOG_MESSAGE = 4000
LOG_HISTORY = 2000
BRIDGE_BYTES = 1024 * 1024
FEED_BYTES = 3 * 1024 * 1024
FEED_ENTRIES = 200
LIMITS = {
    "project_bytes": PROJECT_BYTES, "project_files": PROJECT_FILES,
    "file_bytes": FILE_BYTES, "data_bytes": DATA_BYTES, "source_bytes": SOURCE_BYTES,
    "records": RECORDS, "batch_ops": BATCH_OPS, "log_entries": LOG_ENTRIES,
    "log_message": LOG_MESSAGE, "log_history": LOG_HISTORY,
    "bridge_bytes": BRIDGE_BYTES, "feed_bytes": FEED_BYTES, "feed_entries": FEED_ENTRIES,
}


def check(actual, maximum, resource):
    if actual > maximum:
        raise SpacesError("limit", f"{resource} exceeds {maximum} (actual {actual})",
                          limit=maximum, actual=actual, resource=resource)


def dumps(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        encoded.encode("utf-8")
        return encoded
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise SpacesError("invalid", "Expected JSON-safe values") from exc


def object_json(value, maximum=None, resource="object"):
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise SpacesError("invalid", f"{resource} must be an object with string keys")
    encoded = dumps(value)
    if maximum is not None:
        check(len(encoded.encode("utf-8")), maximum, resource)
    return encoded


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise SpacesError("invalid", f"{name} must be an integer >= {minimum}")
    return value


def text(value, name, *, nonempty=True):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise SpacesError("invalid", f"{name} must be a {'nonempty ' if nonempty else ''}string")
    return value


def identifier(value, kind):
    patterns = {
        "space": r"[a-z0-9][a-z0-9-]{1,47}",
        "collection": r"(?:[a-z][a-z0-9_]{0,39}|_prefs)",
        "record": r"[A-Za-z0-9_.:-]{1,128}",
    }
    if not isinstance(value, str) or not re.fullmatch(patterns[kind], value):
        raise SpacesError("invalid", f"Invalid {kind} identifier")
    return value


def path(value):
    if (not isinstance(value, str) or len(value) > 200
            or not re.fullmatch(r"[A-Za-z0-9._/-]+", value)
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise SpacesError("invalid", "Invalid project path")
    return value
