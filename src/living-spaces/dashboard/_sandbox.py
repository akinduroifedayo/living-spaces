from pathlib import Path


def trusted_document() -> dict:
    document = (Path(__file__).resolve().parent.parent / "guest" / "space-host.html").read_text(encoding="utf-8")
    if not document.strip():
        raise ValueError("The packaged sandbox document is empty")
    root = Path(__file__).resolve().parent.parent / "guest"
    variants = {key: (root / filename).read_text(encoding="utf-8") for key, filename in (
        ("partition_off", "partition-off.html"), ("partition_https", "partition-https.html"))}
    if any(not value.strip() for value in variants.values()):
        raise ValueError("A packaged partition document is empty")
    return {"format": 2, "shell_srcdoc": document, **variants}
