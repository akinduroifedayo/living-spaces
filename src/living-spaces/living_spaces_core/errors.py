"""The one error type the core raises (CONTRACTS.md §4). REST, tools and the bridge all serialize it."""
from __future__ import annotations

CODES = {
    "not_found": 404, "invalid": 400, "conflict": 409, "not_granted": 403, "session_invalid": 403,
    "limit": 413, "archived": 423, "blocked": 423, "ambiguous": 409, "incompatible": 409,
}


class SpacesError(Exception):
    def __init__(self, code: str, message: str, **extra):
        if code not in CODES:
            raise ValueError(f"unknown SpacesError code {code!r}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    @property
    def http_status(self) -> int:
        return CODES[self.code]

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}
