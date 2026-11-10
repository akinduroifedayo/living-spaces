from pathlib import Path


def trusted_document() -> dict:
    document = (Path(__file__).resolve().parent.parent / "guest" / "space-host.html").read_text(encoding="utf-8")
    if not document.strip():
        raise ValueError("The packaged sandbox document is empty")
    return {"format": 1, "shell_srcdoc": document}
