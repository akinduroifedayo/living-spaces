"""Supplemental survey probe, not a formal proof: parser and ingestion entry-count limits agree.

Use the same isolated-home setup as the maintained checks. No network is used. This probe exposes the current
501..1000-entry mismatch and verifies that the refused ingestion writes zero records. It is not part of run.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "checks"))
from harness import Violation, main, space


def check(core, home):
    from living_spaces_core import feeds, records
    observations = []
    for n in (499, 500, 501, 999, 1000, 1001):
        sid = space(core, f"Feed {n}")
        payload = ("<rss><channel>" + "".join(
            f"<item><guid>id-{i}</guid><title>T{i}</title></item>" for i in range(n)) + "</channel></rss>").encode()
        try:
            parsed = len(feeds.parse(payload))
        except core.SpacesError as exc:
            parsed = exc.to_dict()
        try:
            result = feeds.refresh_source(sid, {"id": "f", "url": "https://example.com/feed", "collection": "items"},
                                          actor="user", before_write=lambda: None, fetcher=lambda *_: payload)
        except core.SpacesError as exc:
            result = exc.to_dict()
        stored = records.query(sid, "items")["total"]
        if isinstance(result, dict) and "code" in result and stored:
            raise Violation(f"Refused feed of {n} entries left {stored} records: {result}")
        observations.append({"entries": n, "parsed": parsed, "result": result, "stored": stored})
    mismatch = [r["entries"] for r in observations if isinstance(r["parsed"], int) and r["stored"] != r["parsed"]]
    return {"observations": observations, "F4_mismatched_sizes": mismatch}


if __name__ == "__main__":
    main(check)
