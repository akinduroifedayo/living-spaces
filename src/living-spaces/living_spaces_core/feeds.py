from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from . import db, limits, net
from .errors import SpacesError

MAX_BYTES = limits.FEED_BYTES
MAX_ENTRIES = limits.FEED_ENTRIES
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"


def source_host(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SpacesError("invalid", "Feed sources must use https without credentials")
    return parsed.hostname.lower()


def fetch(sid, url):
    from . import grants

    host = source_host(url)

    def authorize(request_url):
        if source_host(request_url) != host:
            raise SpacesError("not_granted", "Feed redirect changed host", capability="net")
        grants.check(sid, "net")

    response, body = net._fetch_public(url, authorize=authorize, max_bytes=MAX_BYTES)
    if not 200 <= response["status"] < 300:
        raise SpacesError("invalid", "Feed request failed", status=response["status"])
    authorize(url)
    return body


def _text(node, path):
    child = node.find(path)
    return "" if child is None else "".join(child.itertext()).strip()


def _timestamp(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            stamp = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp()


def parse(payload):
    size = len(payload.encode("utf-8")) if isinstance(payload, str) else len(payload)
    limits.check(size, MAX_BYTES, "feed bytes")
    # Removing NULs also catches declarations in UTF-16 and UTF-32 XML.
    guard = payload.replace(b"\x00", b"") if isinstance(payload, bytes) else payload
    pattern = br"<!\s*(?:DOCTYPE|ENTITY)\b" if isinstance(guard, bytes) else r"<!\s*(?:DOCTYPE|ENTITY)\b"
    if re.search(pattern, guard, re.IGNORECASE):
        raise SpacesError("invalid", "DOCTYPE and ENTITY declarations are forbidden in feeds")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SpacesError("invalid", f"Invalid feed XML: {exc}") from exc
    atom = root.tag == ATOM + "feed"
    if atom:
        entries = root.findall(ATOM + "entry")
    elif root.tag == "rss" and root.find("channel") is not None:
        entries = root.findall("channel/item")
    else:
        raise SpacesError("invalid", "Expected an RSS 2.0 or Atom feed")
    if len(entries) > MAX_ENTRIES:
        raise SpacesError("limit", f"Feed exceeds {MAX_ENTRIES} entries", limit=MAX_ENTRIES, actual=len(entries))
    mapped = []
    for entry in entries:
        if atom:
            links = entry.findall(ATOM + "link")
            link = next((item.get("href", "") for item in links if item.get("rel", "alternate") == "alternate"), "")
            identity = _text(entry, ATOM + "id") or link
            fields = {
                "title": _text(entry, ATOM + "title"),
                "summary": _text(entry, ATOM + "summary") or _text(entry, ATOM + "content"),
                "url": link,
                "authors": [name for author in entry.findall(ATOM + "author") if (name := _text(author, ATOM + "name"))],
                "published": _timestamp(_text(entry, ATOM + "published")),
                "updated": _timestamp(_text(entry, ATOM + "updated")),
            }
        else:
            link = _text(entry, "link")
            identity = _text(entry, "guid") or link
            fields = {
                "title": _text(entry, "title"), "summary": _text(entry, "description"), "url": link,
                "authors": ["".join(author.itertext()).strip() for author in entry.findall("author") + entry.findall(DC + "creator")],
                "published": _timestamp(_text(entry, "pubDate")),
                "updated": _timestamp(_text(entry, "updated") or _text(entry, DC + "date") or _text(entry, "pubDate")),
            }
        if not identity:
            raise SpacesError("invalid", "Feed entry needs an id or link")
        limits.object_json(fields, limits.SOURCE_BYTES, "record source")
        rid = "src_" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
        mapped.append((rid, fields))
    return mapped


def refresh_source(sid, source, *, actor, before_write, fetcher=None, counts=None):
    from . import grants, records

    source_host(source["url"])
    grants.check(sid, "net")
    entries = parse((fetcher or fetch)(sid, source["url"]))
    fetched_at = db.now()
    source_as_of = max((fields["updated"] or fetched_at for _, fields in entries), default=fetched_at)
    source_entries = [
        (rid, fields, {
            "handler": "feed", "source_id": source["id"], "url": source["url"],
            "fetched_at": fetched_at, "source_updated": fields["updated"],
        }) for rid, fields in entries
    ]
    before_write()
    grants.check(sid, "net")
    result = records.upsert_sources(sid, source["collection"], source_entries, actor=actor)
    if counts is None:
        counts = {"added": 0, "updated": 0, "unchanged": 0}
    for key in ("added", "updated", "unchanged"):
        counts[key] += result[key]
    return counts, source_as_of
