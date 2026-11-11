"""Synthetic numeric HTTPS leaves for the real feed transport path."""
import io
import socket
from contextlib import ExitStack, contextmanager
from unittest.mock import Mock, patch

from living_spaces_core import net

PUBLIC = "93.184.216.34"


class Response:
    def __init__(self, body=b"", status=200, headers=None):
        self.status = status
        self.headers = headers or {}
        self.length = None
        self.stream = io.BytesIO(body)

    def getheader(self, name, default=None):
        return next((value for key, value in self.headers.items()
                     if key.lower() == name.lower()), default)

    def getheaders(self):
        return list(self.headers.items())

    def read1(self, size):
        return self.stream.read(size)

    def close(self):
        self.stream.close()


class PinnedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.connections = []
        self.requests = []
        self.events = []
        self.factory = Mock(side_effect=self.connect)

    def connect(self, host, port, ip, timeout):
        transport = self
        connection = (host, port, ip, timeout)
        self.connections.append(connection)
        self.events.append(("connect", connection))

        class Connection:
            def request(self, method, target, body=None, headers=None):
                self.sent = dict(host=host, method=method, target=target, body=body, headers=headers)
                transport.requests.append(self.sent)
                transport.events.append(("request", self.sent))

            def getresponse(self):
                response = transport.responses.pop(0)
                transport.events.append(("response", self.sent, response.status))
                return response

            def close(self):
                pass

            def abort(self):
                pass

        return Connection()

    @contextmanager
    def installed(self):
        with ExitStack() as stack:
            for name in ("connect", "connect_ex", "sendto"):
                stack.enter_context(patch.object(socket.socket, name, side_effect=AssertionError("Live socket forbidden")))
            for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "create_connection"):
                stack.enter_context(patch.object(socket, name, side_effect=AssertionError("Live network forbidden")))
            stack.enter_context(patch.object(net, "_resolve", return_value=[PUBLIC]))
            stack.enter_context(patch.object(net, "_connection", self.factory))
            yield self
