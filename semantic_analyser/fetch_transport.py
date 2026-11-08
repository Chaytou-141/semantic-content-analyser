"""Pinned HTTP/1.x transport. No proxy, cookie jar, auth or automatic redirects."""

import http.client
import io
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import zlib
from dataclasses import dataclass

from .fetch_policy import FetchError, public_address

USER_AGENT = "SemanticContentAnalyser/0.1"
MEDIA_TYPES = {"text/html", "application/xhtml+xml", "text/plain", "application/json",
               "application/xml", "text/xml", "application/rss+xml", "application/atom+xml"}
DNS_CODE = """import json,socket,sys
rows=socket.getaddrinfo(sys.argv[1],int(sys.argv[2]),family=socket.AF_UNSPEC,type=socket.SOCK_STREAM)
addresses=list(dict.fromkeys(row[4][0] for row in rows))
if not addresses or len(addresses)>64: raise SystemExit(2)
print(json.dumps(addresses))
"""


class ProcessResolver:
    """Killable OS resolver: a stuck getaddrinfo never strands a parent thread."""
    def resolve(self, host, port, budget):
        process = None
        try:
            budget.check()
            process = subprocess.Popen([sys.executable, "-I", "-S", "-c", DNS_CODE, host, str(port)],
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       env={key: os.environ[key] for key in ["SystemRoot", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"] if key in os.environ},
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            output, _ = process.communicate(timeout=budget.remaining(budget.limits.dns_seconds))
            budget.check()
            if process.returncode or len(output) > 8192:
                raise FetchError("dns")
            values = json.loads(output)
            if not isinstance(values, list) or not 1 <= len(values) <= 64 or any(not isinstance(x, str) for x in values):
                raise FetchError("dns")
            return values
        except subprocess.TimeoutExpired as error:
            raise FetchError("timeout") from error
        except (OSError, ValueError, UnicodeError) as error:
            raise FetchError("dns") from error
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=1)


def resolve_public(target, resolver, budget, denied_networks=()):
    try:
        ipaddress.ip_address(target.host)
        values = [target.host]
    except ValueError:
        values = resolver.resolve(target.host, target.port, budget)
    # Validate the COMPLETE answer set before trying even its first public address.
    if not values or len(values) > 64:
        raise FetchError("dns")
    addresses = tuple(dict.fromkeys(public_address(value) for value in values))
    if any(ipaddress.ip_address(address).version == network.version and ipaddress.ip_address(address) in network
           for address in addresses for network in denied_networks):
        raise FetchError("blocked_destination")
    return addresses


class PinnedConnector:
    def __init__(self, context_factory=ssl.create_default_context):
        self.context_factory = context_factory

    def _dial(self, address, port, timeout):
        parsed = ipaddress.ip_address(address)
        sock = socket.socket(socket.AF_INET6 if parsed.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(timeout)
            # Canonical numeric sockaddr; no create_connection/getaddrinfo or proxy.
            sock.connect((address, port, 0, 0) if parsed.version == 6 else (address, port))
            return sock
        except BaseException:
            sock.close()
            raise

    def _verify_peer(self, sock, address):
        if public_address(sock.getpeername()[0]) != address:
            raise FetchError("blocked_destination")

    def connect(self, target, addresses, budget):
        connect_end = time.monotonic() + budget.remaining(budget.limits.connect_seconds)
        for address in addresses:
            address = public_address(address)
            sock = None
            try:
                remaining = min(connect_end - time.monotonic(), budget.remaining(budget.limits.connect_seconds))
                if remaining <= 0:
                    raise FetchError("timeout")
                sock = self._dial(address, target.port, remaining)
                self._verify_peer(sock, address)
                if target.scheme == "https":
                    context = self.context_factory()
                    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
                        raise FetchError("network")
                    if time.monotonic() >= connect_end:
                        raise FetchError("timeout")
                    sock.settimeout(min(max(.001, connect_end - time.monotonic()), budget.remaining(budget.limits.connect_seconds)))
                    sock = context.wrap_socket(sock, server_hostname=target.host)
                    self._verify_peer(sock, address)
                budget.check()
                return sock
            except FetchError:
                if sock:
                    sock.close()
                raise
            except TimeoutError as error:
                if sock:
                    sock.close()
                raise FetchError("timeout") from error
            except (OSError, ssl.SSLError) as error:
                if sock:
                    sock.close()
                if time.monotonic() >= connect_end:
                    raise FetchError("timeout") from error
        raise FetchError("network")


class DeadlineReader(io.RawIOBase):
    def __init__(self, sock, budget):
        super().__init__()
        self.sock, self.budget = sock, budget
        self.header_phase = True
        self.capture = bytearray()
        self.wire_count = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        self.sock.settimeout(self.budget.remaining(self.budget.limits.read_seconds))
        allowance = min(self.budget.limits.encoded_bytes + self.budget.limits.header_bytes - self.wire_count,
                        self.budget.limits.run_wire_bytes - self.budget.session.wire_bytes)
        if self.header_phase:
            allowance = min(allowance, self.budget.limits.header_bytes - len(self.capture))
        # At most one detection byte beyond a limit, never an unbounded recv/read.
        data = self.sock.recv(min(len(buffer), 8192, max(1, allowance + 1)))
        self.wire_count += len(data)
        self.budget.wire(len(data))
        if self.wire_count > self.budget.limits.encoded_bytes + self.budget.limits.header_bytes:
            raise FetchError("limit")
        if self.header_phase:
            self.capture.extend(data)
            if len(self.capture) > self.budget.limits.header_bytes:
                raise FetchError("limit")
        buffer[:len(data)] = data
        return len(data)


class ResponseSocket:
    def __init__(self, reader):
        self.reader = reader

    def makefile(self, mode):
        return io.BufferedReader(self.reader, buffer_size=8192)


@dataclass(frozen=True)
class WireResponse:
    status: int
    headers: dict
    body: bytes
    encoded_bytes: int


def validate_headers(response, captured):
    head, separator, _ = bytes(captured).partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    if not separator or not re.fullmatch(rb"HTTP/1\.[01] [1-5][0-9][0-9](?: [^\r\n]*)?", lines[0]):
        raise FetchError("invalid_response")
    if any(c < 32 or c == 127 for c in lines[0]):
        raise FetchError("invalid_response")
    if int(lines[0].split()[1]) != response.status:
        raise FetchError("invalid_response")  # Deliberately reject interim-response chains.
    for line in lines[1:]:
        name, colon, value = line.partition(b":")
        if not colon or not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) or any(c < 32 and c != 9 or c == 127 for c in value):
            raise FetchError("invalid_response")
    for key in ["content-length", "transfer-encoding", "content-encoding", "content-type", "location", "retry-after", "x-wp-totalpages"]:
        if len(response.headers.get_all(key, [])) > 1:
            raise FetchError("invalid_response")
    headers = {key: response.headers.get(key, "").strip() for key in
               ["content-length", "transfer-encoding", "content-encoding", "content-type", "location", "retry-after", "cache-control", "x-wp-totalpages"]}
    length, transfer = headers["content-length"], headers["transfer-encoding"].lower()
    headers["cache-control"] = ",".join(response.headers.get_all("cache-control", []))
    if ((response.headers.get_all("content-length") and not re.fullmatch(r"[0-9]{1,10}", length)) or
            (response.headers.get_all("transfer-encoding") and transfer != "chunked") or (length and transfer)):
        raise FetchError("invalid_response")
    return headers


class SocketTransport:
    def __init__(self, connector=None):
        self.connector = connector or PinnedConnector()

    def get(self, target, addresses, budget, decoded_limit):
        sock, response = None, None
        try:
            sock = self.connector.connect(target, addresses, budget)
            request = (f"GET {target.request_target} HTTP/1.1\r\nHost: {target.authority}\r\n"
                       f"User-Agent: {USER_AGENT}\r\nAccept: text/html, application/json, application/xml, text/plain, */*;q=0.1\r\n"
                       "Accept-Encoding: gzip, deflate\r\nConnection: close\r\n\r\n")
            sock.settimeout(budget.remaining(budget.limits.connect_seconds))
            sock.sendall(request.encode("ascii"))
            reader = DeadlineReader(sock, budget)
            response = http.client.HTTPResponse(ResponseSocket(reader))
            response.begin()
            headers = validate_headers(response, reader.capture)
            reader.header_phase = False
            if response.status not in {200, 204}:
                return WireResponse(response.status, headers, b"", 0)
            if response.status == 204:
                return WireResponse(response.status, headers, b"", 0)
            content_type = headers["content-type"].split(";", 1)[0].strip().lower()
            if content_type not in MEDIA_TYPES:
                raise FetchError("content")
            length = int(headers["content-length"]) if headers["content-length"] else None
            if length is not None and length > budget.limits.encoded_bytes:
                raise FetchError("limit")
            encoding = headers["content-encoding"].lower()
            if encoding not in {"", "identity", "gzip", "deflate"}:
                raise FetchError("content")
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS) if encoding in {"gzip", "deflate"} else None
            chunks, encoded, decoded = [], 0, 0

            def append(data):
                nonlocal decoded
                decoded += len(data)
                budget.decoded(len(data))  # Failed/oversized responses also consume the run budget.
                if decoded > decoded_limit:
                    raise FetchError("limit")
                chunks.append(data)

            while True:
                budget.check()
                data = response.read1(8192)
                if not data:
                    break
                encoded += len(data)
                if encoded > budget.limits.encoded_bytes:
                    raise FetchError("limit")
                if decoder:
                    while data:
                        old = data
                        append(decoder.decompress(data, decoded_limit - decoded + 1))
                        data = decoder.unconsumed_tail
                        if decoder.unused_data or (data == old and data):
                            raise FetchError("invalid_response")
                else:
                    append(data)
            if length is not None and encoded != length:
                raise FetchError("invalid_response")
            if decoder:
                append(decoder.decompress(b"", decoded_limit - decoded + 1))
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise FetchError("invalid_response")
            return WireResponse(response.status, headers, b"".join(chunks), encoded)
        except FetchError:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise FetchError("timeout") from error
        except (http.client.HTTPException, ValueError, zlib.error) as error:
            raise FetchError("invalid_response") from error
        except OSError as error:
            raise FetchError("network") from error
        finally:
            if response:
                response.close()
            if sock:
                sock.close()
