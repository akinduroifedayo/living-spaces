"""Fake TURN server on UDP 47804: answers Allocate with 401 + realm/nonce so a client retries with USERNAME,
then logs the USERNAME attribute. Proves whether data placed in ICE config leaves the sandbox."""
import socket
import struct
import sys
import time

LOG = sys.argv[1]
MAGIC = 0x2112A442


def log(s):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {s}\n")


def attrs(body):
    out, i = {}, 0
    while i + 4 <= len(body):
        t, n = struct.unpack("!HH", body[i:i + 4])
        out[t] = body[i + 4:i + 4 + n]
        i += 4 + n + (-n % 4)
    return out


def attr(t, v):
    return struct.pack("!HH", t, len(v)) + v + b"\0" * (-len(v) % 4)


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 47804))
while True:
    data, addr = s.recvfrom(4096)
    if len(data) < 20:
        continue
    mtype, mlen, magic = struct.unpack("!HHI", data[:8])
    tid = data[8:20]
    a = attrs(data[20:20 + mlen])
    user = a.get(0x0006)
    log(f"STUN type=0x{mtype:04x} from {addr} username={user.decode(errors='replace') if user else None}")
    if mtype == 0x0003 and not user:
        body = attr(0x0009, struct.pack("!HBB", 0, 4, 1) + b"Unauthorized") + attr(0x0014, b"spike") + attr(0x0015, b"nonce123")
        s.sendto(struct.pack("!HHI", 0x0113, len(body), MAGIC) + tid + body, addr)
