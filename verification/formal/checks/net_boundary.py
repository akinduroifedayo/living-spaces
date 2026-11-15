"""Internet boundary: generated URLs, DNS answers and redirect chains through real net._fetch_public.

Space code reaches the internet only through net.fetch -> _fetch_public (net.py:193-255). This check replaces
the two OS edges, name resolution (net._resolve) and the socket (net._connection), with fakes and drives the
real code with generated inputs: hosts written as names, dotted, decimal, hex, octal, short and IPv6 forms of
private and public addresses, DNS answers that mix private and public addresses, and up to four redirects.

Properties, judged by an independent deny list (not the code's own _public):
  VettedIpArgument   _connection is never passed loopback, private, link-local, CGNAT, multicast, reserved,
                     unspecified or broadcast space, including IPv4 embedded in IPv6 (mapped, NAT64, 6to4)
  ResolvedIpArgument the address passed to _connection is one the resolver returned for that hop's host
  PortAllowlist      _connection receives only port 443 or 8443 after URL validation
  CredentialsStay    Authorization and Cookie are never sent after a redirect to another host or port

The transport is faked in full, including _PinnedHTTPS. This does not check actual socket pinning, TLS certificate
validation or SNI. The properties describe arguments crossing that boundary, not real network connections.
"""
from __future__ import annotations

import ipaddress
import random
import socket

from harness import Violation, main

DENY = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
    "192.0.0.0/29", "192.168.0.0/16", "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4",
    "::/128", "::1/128", "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8")]
PRIVATE_V4 = ["127.0.0.1", "10.1.2.3", "172.16.9.9", "192.168.1.213", "169.254.169.254", "100.64.1.1",
              "0.0.0.0", "224.0.0.1", "255.255.255.255", "198.18.0.1"]
PUBLIC_V4 = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "151.101.1.69"]
PUBLIC_V6 = ["2606:4700:4700::1111", "2a00:1450:4001:80b::200e"]
PRIVATE_V6 = ["::1", "fe80::1", "fd00::5", "fec0::1", "ff02::1", "::"]


def embedded_v4(ip):
    if ip.version != 6:
        return None
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip in ipaddress.ip_network("64:ff9b::/96"):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip in ipaddress.ip_network("2002::/16"):
        return ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF)
    return None


def denied(ip):
    ip = ipaddress.ip_address(ip)
    inner = embedded_v4(ip)
    return any(ip in n for n in DENY if n.version == ip.version) or (inner is not None and denied(inner))


def spellings(v4):
    n = int(ipaddress.IPv4Address(v4))
    a, b, c, d = (int(x) for x in v4.split("."))
    return [v4, str(n), hex(n), f"0{a:o}.{b}.{c}.{d}", f"{a}.{(b << 16) | (c << 8) | d}", f"[::ffff:{v4}]",
            f"[64:ff9b::{a * 256 + b:x}:{c * 256 + d:x}]", f"[2002:{a * 256 + b:x}:{c * 256 + d:x}::1]", v4 + "."]


def literal(host):
    """What getaddrinfo answers for a numeric host, as the OS would."""
    try:
        return str(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        try:
            return socket.inet_ntoa(socket.inet_aton(host.rstrip(".")))
        except OSError:
            return None


class World:
    def __init__(self, rng):
        self.rng = rng
        self.dns = {}
        self.connections = []
        self.opened = []
        self.redirects = []
        self.next_location = []
        self.resolved = {}

    def resolve(self, host, port, timeout):
        lit = literal(host)
        if lit:
            answers = [lit]
        else:
            answers = self.dns.setdefault(host, self.rng.sample(PUBLIC_V4 + PUBLIC_V6 + PRIVATE_V4 + PRIVATE_V6,
                                                                self.rng.randint(1, 3)))
        self.resolved.setdefault(host, set()).update(answers)
        return list(answers)

    def connection(self, host, port, ip, timeout):
        self.opened.append((host, port, ip))
        world = self

        class Response:
            def __init__(self, status, location):
                self.status, self.location, self.length = status, location, None

            def getheader(self, name):
                return self.location if name == "Location" else None

            def getheaders(self):
                return [("Content-Type", "text/plain")]

            def read1(self, n):
                return b""

            def close(self):
                pass

        class Conn:
            def request(self, method, target, body=None, headers=None):
                world.connections.append((host, port, ip, dict(headers or {})))

            def getresponse(self):
                if world.redirects:
                    return Response(world.redirects.pop(0), world.next_location.pop(0))
                return Response(200, None)

            def abort(self):
                pass

            def close(self):
                pass

        return Conn()


def url_for(rng):
    kind = rng.random()
    if kind < 0.45:
        host = rng.choice(spellings(rng.choice(PRIVATE_V4 + PUBLIC_V4)))
    elif kind < 0.6:
        host = f"[{rng.choice(PRIVATE_V6 + PUBLIC_V6)}]"
    else:
        host = rng.choice(["example.com", "api.example.com", "Evil.Example.", "xn--bcher-kva.example", "metadata.internal"])
    port = rng.choice(["", "", ":443", ":8443", ":80", ":22"])
    scheme = rng.choice(["https", "https", "https", "http", "HTTPS"])
    return f"{scheme}://{host}{port}/p?q=1"


def check(core, home):
    from living_spaces_core import net, SpacesError
    stats = {"scenarios": 0, "connections": 0, "blocked": 0, "invalid": 0, "cross_host_hops": 0}
    for seed in range(20000):
        rng = random.Random(seed)
        world = World(rng)
        hops = rng.randint(0, 4)
        world.redirects = [rng.choice([301, 302, 303, 307, 308]) for _ in range(hops)]
        world.next_location = [url_for(rng) if rng.random() < 0.8 else "/relative/next" for _ in range(hops)]
        start = url_for(rng)
        net._resolve, net._connection = world.resolve, world.connection
        try:
            net._fetch_public(start, authorize=lambda _url: None, max_bytes=1024,
                              headers={"Authorization": "Bearer secret", "Cookie": "sid=1"})
        except SpacesError as exc:
            stats["blocked" if exc.code == "blocked" else "invalid"] += 1
        stats["scenarios"] += 1
        story = f"start {start}, redirects {list(zip(world.redirects, world.next_location))}, DNS {world.dns}"
        for host, port, ip in world.opened:
            if denied(ip) or any(denied(a) for a in world.resolved.get(host, ())):
                raise Violation(f"VettedIpArgument: passed {ip} for {host!r} with an unsafe address in its DNS answers. {story}")
            if ip not in world.resolved.get(host, set()) | {literal(host)}:
                raise Violation(f"ResolvedIpArgument: passed {ip}, which the resolver did not return for {host!r}. {story}")
            if port not in (443, 8443):
                raise Violation(f"PortAllowlist: passed port {port}. {story}")
        first = None
        crossed = False
        for host, port, ip, headers in world.connections:
            stats["connections"] += 1
            if denied(ip):
                raise Violation(f"VettedIpArgument: passed {ip} for host {host!r}. {story}. requests {world.connections}")
            if ip not in world.resolved.get(host, set()) | {literal(host)}:
                raise Violation(f"ResolvedIpArgument: passed {ip}, which no resolver answer for {host!r} gave. {story}")
            if port not in (443, 8443):
                raise Violation(f"PortAllowlist: passed port {port}. {story}")
            first = first or (host, port)
            crossed = crossed or (host, port) != first
            stats["cross_host_hops"] += crossed
            if crossed and ({"Authorization", "Cookie"} & set(headers)):
                raise Violation(f"CredentialsStay: sent {sorted({'Authorization', 'Cookie'} & set(headers))} to "
                                f"{host}:{port} after a redirect away from {first[0]}:{first[1]}. {story}")
    return stats


if __name__ == "__main__":
    main(check)
