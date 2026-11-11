"""Public HTTPS requests with hostname TLS and a pinned, vetted destination."""
import base64
import http.client
import ipaddress
import json
import queue
import re
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from . import db, grants, limits, sessions
from .errors import SpacesError

TIMEOUT = 20
RESPONSE_BYTES = 5 * 1024 * 1024
_METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'}
_REDIRECTS = {301, 302, 303, 307, 308}
_STRIPPED = {'cookie', 'authorization', 'host', 'content-length', 'transfer-encoding',
             'connection', 'keep-alive', 'upgrade', 'te', 'trailer', 'accept-encoding'}


def _resolve_host(host, port, timeout):
    result = queue.Queue(maxsize=1)

    def resolve():
        try:
            answers = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            result.put([row[4][0] for row in answers])
        except OSError as exc:
            result.put(exc)

    # libc DNS has no deadline. A late answer is discarded and never opens a socket.
    threading.Thread(target=resolve, daemon=True).start()
    try:
        answers = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError() from exc
    if isinstance(answers, Exception):
        raise answers
    return answers


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip
        self._transport = None
        self._aborted = threading.Event()

    def connect(self):
        family = socket.AF_INET6 if ':' in self.ip else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        self._transport = raw
        try:
            if self._aborted.is_set():
                raise TimeoutError()
            raw.settimeout(self.timeout)
            raw.connect((self.ip, self.port))
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host, do_handshake_on_connect=False)
            self._transport = self.sock
            if self._aborted.is_set():
                raise TimeoutError()
            self.sock.do_handshake()
        except BaseException:
            self.close()
            raise

    def abort(self):
        self._aborted.set()
        transport = self._transport
        if transport is not None:
            try:
                transport.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            transport.close()

    def close(self):
        super().close()
        if self._transport is not None:
            self._transport.close()
            self._transport = None


_resolve = _resolve_host
_connection = _PinnedHTTPS


def _remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError()
    return seconds


def _blocked(reason):
    raise SpacesError('blocked', 'Internet destination is not allowed', reason=reason)


def _target(url):
    if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise SpacesError('invalid', 'Expected an HTTPS URL')
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() != 'https':
            _blocked('scheme')
        if not parts.hostname or parts.username is not None or parts.password is not None:
            raise ValueError()
        host = parts.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        if len(host) > 253 or '%' in host or '\\' in host:
            raise ValueError()
        if ':' not in host and not re.fullmatch(r'[a-z0-9_-]+(?:\.[a-z0-9_-]+)*', host):
            raise ValueError()
        port = parts.port if parts.port is not None else 443
    except (ValueError, UnicodeError) as exc:
        raise SpacesError('invalid', 'Malformed HTTPS URL') from exc
    if port not in (443, 8443):
        _blocked('port')
    authority = f'[{host}]' if ':' in host else host
    if port != 443:
        authority += f':{port}'
    path = quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
    return host, port, authority, path + ('?' + query if query else ''), urlunsplit(('https', authority, path, query, ''))


def _public(ip):
    if not ip.is_global or ip.is_reserved or ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.is_site_local or ip.teredo is not None or ip in ipaddress.ip_network('64:ff9b:1::/48'):
            return False
        if ip.ipv4_mapped is not None and not _public(ip.ipv4_mapped):
            return False
        if ip.sixtofour is not None and not _public(ip.sixtofour):
            return False
        if ip in ipaddress.ip_network('64:ff9b::/96') and not _public(ipaddress.IPv4Address(int(ip) & 0xffffffff)):
            return False
    return True


def _addresses(host, port, deadline):
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            literal = ipaddress.ip_address(socket.inet_aton(host))
        except OSError:
            literal = None
    answers = [str(literal)] if literal is not None else _resolve(host, port, _remaining(deadline))
    if not answers:
        raise OSError('No destination addresses')
    addresses = [ipaddress.ip_address(answer) for answer in answers]
    if any(not _public(ip) for ip in addresses):
        _blocked('private_address')
    return str(addresses[0])


def _request_options(method, headers, body, as_):
    if not isinstance(method, str) or method.upper() not in _METHODS:
        raise SpacesError('invalid', 'Unsupported HTTP method')
    method = method.upper()
    if not isinstance(as_, str) or as_ not in ('text', 'json', 'bytes'):
        raise SpacesError('invalid', 'Response format must be text, json or bytes')
    if body is not None and not isinstance(body, (str, bytes)):
        raise SpacesError('invalid', 'Request body must be text or bytes')
    try:
        body = body.encode('utf-8') if isinstance(body, str) else body
    except UnicodeError as exc:
        raise SpacesError('invalid', 'Request body must be valid UTF-8') from exc
    limits.check(len(body or b''), limits.BRIDGE_BYTES, 'request body')
    if body is not None and method in ('GET', 'HEAD'):
        raise SpacesError('invalid', 'GET and HEAD do not accept a body')
    if headers is None:
        headers = {}
    limits.object_json(headers, limits.BRIDGE_BYTES, 'request headers')
    clean = {}
    for name, value in headers.items():
        if (not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) or not isinstance(value, str)
                or any(ord(c) < 32 or ord(c) == 127 or ord(c) > 255 for c in value)):
            raise SpacesError('invalid', 'Malformed HTTP header')
        lower = name.lower()
        if lower in _STRIPPED or lower.startswith(('proxy-', 'x-hermes')):
            continue
        clean[name] = value
    return method, clean, body


def _fetch_public(url, *, authorize, max_bytes, method='GET', headers=None, body=None, detail=None):
    deadline = time.monotonic() + TIMEOUT
    if detail is None:
        detail = {'host': '', 'status': None, 'bytes': 0}
    headers = headers or {}
    try:
        for hop in range(6):
            request_url = url
            authorize(request_url)
            host, port, authority, target, url = _target(url)
            detail['host'] = host
            ip = _addresses(host, port, deadline)
            authorize(request_url)
            conn = _connection(host, port, ip, _remaining(deadline))
            timer = threading.Timer(_remaining(deadline), conn.abort)
            timer.daemon = True
            response = None
            try:
                timer.start()
                authorize(request_url)
                conn.request(method, target, body=body, headers={**headers, 'Host': authority, 'Accept-Encoding': 'identity'})
                response = conn.getresponse()
                _remaining(deadline)
                detail['status'] = response.status
                if response.status in _REDIRECTS:
                    location = response.getheader('Location')
                    if hop == 5 or not location:
                        _blocked('redirect')
                    url = urljoin(request_url, location)
                    if (response.status == 303 and method != 'HEAD') or (response.status in (301, 302) and method == 'POST'):
                        method, body = 'GET', None
                        headers = {k: v for k, v in headers.items() if not k.lower().startswith('content-')}
                    continue
                response_headers = {k.lower(): v for k, v in response.getheaders()}
                content = bytearray()
                if method != 'HEAD':
                    while True:
                        _remaining(deadline)
                        chunk = response.read1(min(65536, max_bytes + 1 - len(content)))
                        if not chunk:
                            break
                        content.extend(chunk)
                        detail['bytes'] = len(content)
                        limits.check(len(content), max_bytes, 'response body')
                    if response.length not in (None, 0):
                        raise http.client.IncompleteRead(bytes(content), response.length)
                _remaining(deadline)
                authorize(request_url)
                result = {'status': response.status, 'url': url, 'headers': response_headers}
                return result, bytes(content)
            finally:
                timer.cancel()
                if response is not None:
                    response.close()
                conn.close()
    except (OSError, http.client.HTTPException) as exc:
        raise SpacesError('blocked', 'Internet request could not be completed', reason='network_error') from exc
    except (ValueError, UnicodeError) as exc:
        raise SpacesError('invalid', 'Malformed internet request') from exc


def fetch_for_agent(url, *, max_bytes):
    result, content = _fetch_public(url, authorize=lambda _url: None, max_bytes=max_bytes)
    if not 200 <= result['status'] < 300:
        raise SpacesError('blocked', f"Download returned HTTP {result['status']}", reason='http_status',
                          status=result['status'])
    return result, content


def fetch(sid, url, method='GET', headers=None, body=None, as_='text', session=None):
    def authorize(_url):
        if session is not None:
            sessions.require(sid, session)
        grants.check(sid, 'net')

    detail = {'host': '', 'status': None, 'bytes': 0}
    outcome = 'blocked'
    try:
        authorize(url)
        method, headers, body = _request_options(method, headers, body, as_)
        result, content = _fetch_public(url, authorize=authorize, max_bytes=RESPONSE_BYTES,
                                       method=method, headers=headers, body=body, detail=detail)
        mime = result['headers'].get('content-type', 'application/octet-stream').split(';', 1)[0].strip()
        if as_ == 'bytes':
            result.update(b64=base64.b64encode(content).decode('ascii'), mime=mime)
        elif as_ == 'json':
            try:
                result['json'] = json.loads(content)
                limits.dumps(result['json'])
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise SpacesError('invalid', 'Response is not valid JSON') from exc
        else:
            result['text'] = content.decode('utf-8', errors='replace')
        authorize(url)
        outcome = 'succeeded'
        return result
    except SpacesError as exc:
        outcome = exc.code
        raise
    finally:
        with db.write() as conn:
            grants._audit(conn, sid, 'app', 'net.fetch', 'net', outcome, detail)
