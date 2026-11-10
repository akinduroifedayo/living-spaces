"""Attacker listener: logs every TCP accept, HTTP request and UDP datagram. Any line in canary.log = traffic reached it."""
import socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
LOG = sys.argv[1]
def log(s):
    with open(LOG, "a") as f: f.write(f"{time.strftime('%H:%M:%S')} {s}\n")
class H(BaseHTTPRequestHandler):
    def _hit(self): log(f"HTTP {self.command} {self.path}"); self.send_response(200); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers(); self.wfile.write(b"ok")
    do_GET = do_POST = do_OPTIONS = _hit
    def log_message(self, *a): pass
class S(ThreadingHTTPServer):
    def get_request(self):
        conn, addr = super().get_request(); log(f"TCP accept from {addr}"); return conn, addr
def udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 47802))
    while True:
        d, a = s.recvfrom(2048); log(f"UDP {len(d)}B from {a}")
threading.Thread(target=udp, daemon=True).start()
S(("127.0.0.1", 47801), H).serve_forever()
