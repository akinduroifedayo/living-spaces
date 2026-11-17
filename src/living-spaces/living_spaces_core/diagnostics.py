from __future__ import annotations

import bisect
import re
from html.parser import HTMLParser
from typing import Callable, Mapping, NamedTuple
from urllib.parse import unquote, urljoin, urlsplit

ROOT = "https://space.invalid/"
REMOTE = re.compile(r"^(?:https?|wss?):|^//", re.I)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
REGEX_CONTEXT = re.compile(r"^(?:return|throw|case|typeof|void|delete|yield|await|=>|[=(:,;!&|?{\[])$")
WORD = re.compile(r"[\w$]")
CONSTRUCTORS = {"XMLHttpRequest", "WebSocket", "EventSource"}
CONTROL = {"if", "while", "for", "with"}
JS_TYPES = {"", "module", "application/ecmascript", "application/javascript", "application/x-ecmascript",
            "application/x-javascript", "text/ecmascript", "text/javascript", "text/javascript1.0",
            "text/javascript1.1", "text/javascript1.2", "text/javascript1.3", "text/javascript1.4",
            "text/javascript1.5", "text/jscript", "text/livescript", "text/x-ecmascript", "text/x-javascript"}
LOADING_RELS = {"stylesheet", "icon", "preload", "modulepreload", "prefetch", "manifest", "apple-touch-icon"}
SOURCE_ATTRS = {"script": "src", "img": "src", "source": "src", "audio": "src", "video": "src", "track": "src",
                "iframe": "src", "embed": "src", "input": "src", "object": "data"}
SVG_HREF = {"image", "use", "feimage"}
CSS_STRING = re.compile(r"""/\*.*?(?:\*/|$)|"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?""", re.S)
CSS_LOADS = re.compile(r"(?:url\(\s*|@import\s*)$", re.I)
CSS_IMPORT = re.compile(r"""@import\s+(?:url\(\s*)?(['"]?)([^'")\s;]+)\1""", re.I)
CSS_URL = re.compile(r"""url\(\s*(['"]?)([^'")]*?)\1\s*\)""", re.I)
MESSAGES = {
    "entry.missing": "Entry file {ref!r} is missing, so the Space cannot boot",
    "import.alias_target_missing": "manifest import {ref!r} points to missing file {target}",
    "import.unresolved": "import {ref!r} does not resolve to a project file ({target})",
    "import.bare_unmapped": "bare import {ref!r} is not in the manifest imports; add it to libraries or vendor the file",
    "asset.unresolved": "{ref!r} does not resolve to a project file ({target})",
    "net.direct_call": "direct network access with {ref} is blocked in the frame; use space.net.fetch(url, {{as}}) for public HTTPS",
    "net.remote_import": "remote import {ref!r} is blocked in the frame; vendor the file or add a bundled library",
    "net.remote_resource": "remote resource {ref!r} is blocked in the frame; add it as a project file or fetch it with space.net.fetch(url, {{as: 'bytes'}})",
    "library.file_unavailable": "Bundled file is not available yet: {ref}",
}


class Token(NamedTuple):
    text: str
    at: int


class Ref(NamedTuple):
    module: bool
    spec: str
    line: int
    column: int
    dynamic: bool = False


class Sink(NamedTuple):
    code: str
    ref: str
    line: int
    column: int


class Facts(NamedTuple):
    refs: tuple[Ref, ...]
    sinks: tuple[Sink, ...]


def diagnostic(code, path=None, line=None, column=None, ref=None, target=None):
    where = path if path is None or line is None else f"{path}:{line}:{column}"
    text = MESSAGES[code].format(ref=ref, target=target)
    return {"code": code, "path": path, "line": line, "column": column, "ref": ref, "target": target,
            "message": f"{where}: {text}. [{code}]" if where else f"{text}. [{code}]"}


def tokens(source: str) -> list[Token]:
    out: list[Token] = []
    frames: list = []
    parens: list[str] = []
    after_control = False
    at = 0

    def quoted(quote):
        nonlocal at
        start = at
        at += 1
        while at < len(source):
            if source[at] == "\\":
                at += 2
                continue
            at += 1
            if source[at - 1] == quote:
                break
        out.append(Token(source[start:at], start))

    while at < len(source):
        if frames and frames[-1][0] == "`":
            if source[at] == "\\":
                at += 2
            elif source[at] == "`":
                at += 1
                _, begin, head = frames.pop()
                out.append(Token(source[begin:at] if head is None else "`", at - 1))
            elif source.startswith("${", at):
                if frames[-1][2] is None:
                    frames[-1][2] = source[frames[-1][1] + 1:at]
                    out.append(Token("`" + frames[-1][2] + "${", frames[-1][1]))
                at += 2
                frames.append([0])
            else:
                at += 1
            continue
        start, char = at, source[at]
        control, after_control = after_control, False
        if char.isspace():
            at += 1
            after_control = control
        elif source.startswith("//", at):
            end = source.find("\n", at)
            at = len(source) if end < 0 else end
            after_control = control
        elif source.startswith("/*", at):
            end = source.find("*/", at + 2)
            at = len(source) if end < 0 else end + 2
            after_control = control
        elif char in "\"'":
            quoted(char)
        elif char == "`":
            at += 1
            frames.append(["`", start, None])
        elif char == "/" and (not out or control or REGEX_CONTEXT.match(out[-1].text)):
            at += 1
            in_class = False
            while at < len(source):
                if source[at] == "\\":
                    at += 2
                    continue
                at += 1
                if source[at - 1] == "[":
                    in_class = True
                elif source[at - 1] == "]":
                    in_class = False
                elif source[at - 1] == "/" and not in_class:
                    break
            while at < len(source) and source[at].isalpha():
                at += 1
            out.append(Token(source[start:at], start))
        elif char == "}" and frames and frames[-1][0] == 0:
            at += 1
            frames.pop()
        else:
            if frames:
                frames[-1][0] += (char == "{") - (char == "}")
            if char == "(":
                parens.append(out[-1].text if out and (len(out) < 2 or out[-2].text != ".") else "")
            elif char == ")":
                after_control = (parens.pop() if parens else "") in CONTROL
            if source.startswith("=>", at):
                at += 2
            elif WORD.match(char):
                while at < len(source) and WORD.match(source[at]):
                    at += 1
            else:
                at += 1
            out.append(Token(source[start:at], start))
    return out


def _string(token):
    return token.text[:1] in "\"'" and len(token.text) > 1


def _interpolated(token):
    return token.text[:1] == "`" and token.text.endswith("${") and len(token.text) > 2


def _constant(token):
    """A string literal, or a template literal with no ${} interpolation."""
    return _string(token) or (token.text[:1] == "`" and len(token.text) > 1 and not _interpolated(token))


def _head(token):
    return (token.text[1:-2] if _interpolated(token) else token.text[1:-1]).strip()


def _mediated(toks, i):
    """True only when fetch is called on an object named `net`: `space.net.fetch(`, `space?.net?.fetch(`,
    or a `net` alias of `space.net`. Every other receiver is diagnosed, because Q01 rounds 1-8 showed that
    each attempt to infer that some other `fetch(` is not a browser network call opened a false negative.
    """
    j = i - 1
    if j < 0 or toks[j].text != ".":
        return False
    j -= 1
    if j >= 0 and toks[j].text == "?":
        j -= 1
    if j >= 0 and toks[j].text == ")":
        j -= 1
    if j >= 1 and toks[j].text == "]" and toks[j - 1].text in ("'net'", '"net"'):
        return True
    return j >= 0 and toks[j].text == "net"


def _constant_at(toks, j, whole=True):
    """The constant string starting the expression at token j, looking through grouping parens.
    With whole=True (import specifiers) it must be the entire expression, so `'./' + name` is None.
    With whole=False (.src/.href) anything may follow: a remote prefix stays remote after
    concatenation, and a newline may end the statement by ASI."""
    opened = 0
    while 0 <= j < len(toks) and toks[j].text == "(":
        j, opened = j + 1, opened + 1
    if not (0 <= j < len(toks) and (_constant(toks[j]) or not whole and _interpolated(toks[j]))):
        return None
    if not whole:
        return toks[j]
    k = j + 1
    while opened and k < len(toks) and toks[k].text == ")":
        k, opened = k + 1, opened - 1
    end = toks[k].text if k < len(toks) else ";"
    return toks[j] if opened == 0 and end in (")", ",", ";", "}", "]") else None


def _js(source, position):
    toks = tokens(source)
    none = Token("", -1)
    get = lambda i: toks[i] if 0 <= i < len(toks) else none
    where = lambda token: position(token.at)
    refs, sinks = [], []
    for i, token in enumerate(toks):
        text, prev, nxt = token.text, get(i - 1), get(i + 1)
        if text in ("import", "export") and prev.text != ".":
            if text == "import" and nxt.text == "(":
                spec = _constant_at(toks, i + 2)
                if spec is not None:
                    refs.append(Ref(True, spec.text[1:-1], *where(spec), dynamic=True))
                continue
            if nxt.text == ".":
                continue
            spec = nxt if text == "import" and _string(nxt) else None
            j = i + 1
            while spec is None and j < len(toks) and toks[j].text not in (";", "import", "export"):
                if toks[j].text == "from" and _string(get(j + 1)):
                    spec = toks[j + 1]
                j += 1
            if spec is not None:
                refs.append(Ref(True, spec.text[1:-1], *where(spec)))
        elif text == "fetch" and nxt.text == "(" and prev.text != "function" and not _mediated(toks, i):
            sinks.append(Sink("net.direct_call", "fetch()", *where(token)))
        elif text in CONSTRUCTORS:
            sinks.append(Sink("net.direct_call", text, *where(token)))
        elif text == "sendBeacon" and nxt.text == "(" and prev.text != "function":
            sinks.append(Sink("net.direct_call", "sendBeacon()", *where(token)))
        elif text in ("src", "href") and prev.text == "." and nxt.text == "=" and get(i + 2).text != "=":
            spec = _constant_at(toks, i + 2, whole=False)
            if spec is not None and REMOTE.match(_head(spec)):
                sinks.append(Sink("net.remote_resource", _head(spec), *where(token)))
    return refs, sinks


def _blank(text):
    return re.sub(r"[^\n]", " ", text)


def _inert_css(source):
    out, tail, at = [], "", 0
    for match in CSS_STRING.finditer(source):
        between, token = source[at:match.start()], match.group(0)
        tail = re.sub(r"\s+", " ", tail + between)[-32:]
        if token.startswith("/*"):
            out += [between, _blank(token)]
            tail = re.sub(r"\s+", " ", tail + " ")[-32:]
        else:
            loads = CSS_LOADS.search(tail) is not None
            out += [between, token if loads else token[:1] + _blank(token[1:-1]) + token[-1:]]
            tail = (tail + "s")[-32:]
        at = match.end()
    return "".join(out) + source[at:]


def _css(source, position):
    source = _inert_css(source)
    refs, taken = [], []
    for match in CSS_IMPORT.finditer(source):
        refs.append(Ref(False, match.group(2), *position(match.start(2))))
        taken.append(match.span())
    k = 0
    for match in CSS_URL.finditer(source):
        while k < len(taken) and taken[k][1] <= match.start():
            k += 1
        if k == len(taken) or match.start() < taken[k][0]:
            refs.append(Ref(False, match.group(2).strip(), *position(match.start(2))))
    return refs, []


class _Html(HTMLParser):
    def __init__(self, lines):
        super().__init__(convert_charrefs=False)
        self.lines, self.refs, self.sinks, self.script = lines, [], [], None

    def position(self, line, column):
        start = self.lines[line - 1]
        return lambda offset: _shift(self.lines, start + column, offset)

    def handle_starttag(self, tag, attrs):
        here = self.getpos()
        values = {name: value or "" for name, value in attrs}
        found = []
        if tag in SOURCE_ATTRS and SOURCE_ATTRS[tag] in values:
            found.append(values[SOURCE_ATTRS[tag]])
        if tag in ("img", "source") and values.get("srcset"):
            found += [part.split()[0] for part in values["srcset"].split(",") if part.split()]
        if tag == "link" and set(values.get("rel", "").lower().split()) & LOADING_RELS and "href" in values:
            found.append(values["href"])
        if tag in SVG_HREF:
            found += [values[name] for name in ("href", "xlink:href") if name in values]
        self.refs += [Ref(False, spec, here[0], here[1] + 1) for spec in found]
        for name, value in values.items():
            if name.startswith("on") and value:
                self.sinks += [Sink(s.code, s.ref, here[0], here[1] + 1) for s in _js(value, lambda offset: (here[0], here[1] + 1))[1]]
        if values.get("style"):
            refs, _ = _css(values["style"], lambda offset: (here[0], here[1] + 1))
            self.refs += refs
        kind = values.get("type", "").split(";")[0].strip().lower()
        if tag == "script" and "src" not in values and kind in JS_TYPES:
            self.script = ("module" if kind == "module" else "classic")
        elif tag == "style":
            self.script = "style"

    def handle_endtag(self, tag):
        self.script = None

    def handle_data(self, data):
        if self.script is None:
            return
        position = self.position(*self.getpos())
        refs, sinks = (_css if self.script == "style" else _js)(data, position)
        self.refs += refs
        self.sinks += sinks


def _line_starts(source):
    return [0] + [m.end() for m in re.finditer("\n", source)]


def _shift(starts, base, offset):
    index = base + offset
    line = bisect.bisect_right(starts, index)
    return line, index - starts[line - 1] + 1


def scan(path: str, source: str) -> Facts:
    starts = _line_starts(source)
    position = lambda offset: _shift(starts, 0, offset)
    ext = path.rsplit(".", 1)[-1].lower()
    if ext in ("js", "mjs"):
        refs, sinks = _js(source, position)
    elif ext == "css":
        refs, sinks = _css(source, position)
    elif ext in ("html", "htm", "svg"):
        parser = _Html(starts)
        parser.feed(source)
        parser.close()
        refs, sinks = parser.refs, parser.sinks
    else:
        refs, sinks = [], []
    return Facts(tuple(refs), tuple(sinks))


_FACTS: dict[tuple[str, str], Facts] = {}


def _facts(path, sha, load):
    key = (path.rsplit(".", 1)[-1].lower(), sha)
    if key not in _FACTS:
        if len(_FACTS) >= 512:
            _FACTS.clear()
        _FACTS[key] = scan(path, load(sha).decode("utf-8", errors="replace"))
    return _FACTS[key]


def resolve(base: str, spec: str) -> str:
    return unquote(urlsplit(urljoin(ROOT + base, spec)).path).lstrip("/")


def diagnose(manifest: Mapping, blob_shas: Mapping[str, str], load: Callable[[str], bytes]) -> list[dict]:
    imports = manifest.get("imports") or {}
    found = []
    if manifest["entry"] not in blob_shas:
        found.append(diagnostic("entry.missing", "space.json", ref=manifest["entry"]))
    for name, target in imports.items():
        if target not in blob_shas:
            found.append(diagnostic("import.alias_target_missing", "space.json", ref=name, target=target))
    for path, sha in blob_shas.items():
        if path.rsplit(".", 1)[-1].lower() not in ("js", "mjs", "css", "html", "htm", "svg"):
            continue
        facts = _facts(path, sha, load)
        found += [diagnostic(s.code, path, s.line, s.column, s.ref) for s in facts.sinks]
        for ref in facts.refs:
            spec = ref.spec.strip()
            where = (path, ref.line, ref.column, spec)
            if REMOTE.match(spec):
                found.append(diagnostic("net.remote_import" if ref.module else "net.remote_resource", *where))
            elif not spec or spec.startswith("#") or SCHEME.match(spec):
                continue
            elif ref.module and not spec.startswith((".", "/")):
                if spec not in imports:
                    found.append(diagnostic("import.bare_unmapped", *where))
            elif resolve(path, spec) not in blob_shas:
                found.append(diagnostic("import.unresolved" if ref.module else "asset.unresolved", *where,
                                        target=resolve(path, spec)))
    return sorted(found, key=lambda d: (d["path"] != "space.json", d["path"] or "", d["line"] or 0,
                                        d["column"] or 0, d["code"]))
