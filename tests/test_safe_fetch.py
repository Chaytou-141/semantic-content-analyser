import gzip
import ipaddress
import json
import socket
import ssl
import subprocess
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from shutil import which

import pytest

from semantic_analyser.fetch_policy import Budget, FetchError, FetchLimits, FetchSession, normalize_url, public_address
from semantic_analyser.fetch_transport import PinnedConnector, ProcessResolver, SocketTransport, WireResponse, resolve_public
from semantic_analyser.robots_policy import parse_robots
from semantic_analyser.safe_fetch import SafeFetcher


class FakeDNS:
    def __init__(self, answers=None):
        self.answers = answers or [["8.8.8.8"]]
        self.calls = []

    def resolve(self, host, port, budget):
        self.calls.append((host, port))
        return self.answers[min(len(self.calls) - 1, len(self.answers) - 1)]


class FakeTransport:
    def __init__(self, routes=None):
        self.routes, self.calls = routes or {}, []

    def get(self, target, addresses, budget, decoded_limit):
        self.calls.append((target.url, addresses, time.monotonic()))
        status, body, extra = self.routes.get(target.request_target, (404, b"", {}))
        if len(body) > decoded_limit:
            raise FetchError("limit")
        budget.wire(len(body))
        budget.decoded(len(body))
        return WireResponse(status, {"content-type": "text/plain", **extra}, body, len(body))


def service(routes=None, answers=None, **limits):
    transport, dns = FakeTransport(routes), FakeDNS(answers)
    fetcher = SafeFetcher(FetchLimits(delay_seconds=0, **limits), dns, transport)
    return fetcher, fetcher.new_session("owner"), transport, dns


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://public.example/a", "gopher://public.example/", "http://user:pass@public.example/",
    "http://public.example:0/", "http://public.example:8080/", "https://public.example:80/", "http://public.example:443/",
    "http://127.0.0.1/", "http://127.1/", "http://2130706433/", "http://0x7f000001/", "http://0177.0.0.1/",
    "http://10.1.2.3/", "http://192.168.1.1/", "http://172.16.1.1/", "http://169.254.169.254/",
    "http://100.100.100.200/", "http://168.63.129.16/", "http://0.0.0.0/", "http://224.0.0.1/",
    "http://192.0.0.9/", "http://198.18.0.1/", "http://192.0.2.1/", "http://localhost/", "http://name.local/",
    "http://metadata.google.internal/", "http://[::1]/", "http://[::]/", "http://[fd00:ec2::254]/",
    "http://[fe80::1%25eth0]/", "http://[::ffff:8.8.8.8]/", "http://[64:ff9b::7f00:1]/",
    "http://[2002:7f00:1::]/", "http://[2001:db8::1]/", "http://[fec0::1]/",
    "http://public.example\\@127.0.0.1/", "http://public.example/\r\nHost:localhost",
    " http://public.example/", "http://public.example/%ZZ", "http://public.example/?access_token=private",
])
def test_unsafe_targets_never_reach_transport(url):
    fetcher, session, transport, _ = service()
    with pytest.raises(FetchError):
        fetcher.fetch(session, url, "owner")
    assert transport.calls == []


def test_normalization_and_public_literal_support():
    assert normalize_url("HTTPS://PUBLIC.Example.:443/café?q=ok#fragment").url == "https://public.example/caf%C3%A9?q=ok"
    assert public_address("8.8.8.8") == "8.8.8.8"
    assert public_address("2606:4700:4700::1111") == "2606:4700:4700::1111"
    fetcher, session, transport, dns = service({"/robots.txt": (404, b"", {}), "/": (200, b"public", {})})
    assert fetcher.fetch(session, "http://8.8.8.8/", "owner").body == b"public"
    assert dns.calls == []


@pytest.mark.parametrize("answers", [["8.8.8.8", "10.0.0.1"], ["8.8.8.8", "::1"], ["8.8.8.8", "64:ff9b::a00:1"], ["not-an-ip"]])
def test_all_dns_answers_checked_before_connect(answers):
    fetcher, session, transport, _ = service(answers=[answers])
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "blocked_destination" and transport.calls == []


def test_scoped_dns_and_operator_public_infrastructure_denies():
    fetcher, session, transport, _ = service(answers=[["8.8.8.8", "2001:4860:4860::8888%eth0"]])
    with pytest.raises(FetchError):
        fetcher.fetch(session, "http://public.example/", "owner")
    assert not transport.calls
    fetcher = SafeFetcher(FetchLimits(delay_seconds=0), FakeDNS(), FakeTransport(), denied_networks=["8.8.8.0/24"])
    with pytest.raises(FetchError) as error:
        fetcher.fetch(fetcher.new_session("owner"), "http://public.example/", "owner")
    assert error.value.code == "blocked_destination"


def test_rebinding_between_robots_and_content_is_rejected():
    fetcher, session, transport, dns = service(answers=[["8.8.8.8"], ["127.0.0.1"]])
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "blocked_destination"
    assert len(dns.calls) == 2 and len(transport.calls) == 1
    assert transport.calls[0][0].endswith("/robots.txt")


def test_every_wire_request_gets_its_own_validated_answer():
    fetcher, session, transport, dns = service({"/": (200, b"ok", {})}, [["8.8.8.8"], ["1.1.1.1"], ["9.9.9.9"]])
    fetcher.fetch(session, "http://public.example/", "owner")
    fetcher.fetch(session, "http://public.example/", "owner")
    assert [call[1] for call in transport.calls] == [("8.8.8.8",), ("1.1.1.1",), ("9.9.9.9",)]


@pytest.mark.parametrize("location", ["http://127.0.0.1/", "http://other.example/", "//evil.example/", "file:///secret", "http://public.example:8000/", "http://u:p@public.example/"])
def test_unsafe_redirects_not_followed(location):
    fetcher, session, transport, _ = service({"/": (302, b"", {"location": location})})
    with pytest.raises(FetchError):
        fetcher.fetch(session, "https://public.example/", "owner")
    assert len(transport.calls) == 2


def test_same_host_redirect_rechecks_policy_and_loop_limits():
    routes = {"/robots.txt": (200, b"User-agent: *\nDisallow: /private\n", {}), "/": (302, b"", {"location": "/private"})}
    fetcher, session, transport, _ = service(routes)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "robots" and len(transport.calls) == 2
    fetcher, session, transport, _ = service({"/": (302, b"", {"location": "/"})})
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "invalid_response"


@pytest.mark.parametrize("path", ["/allowed/../private", "/allowed/%2e%2e/private", "/allowed/.%2E/private"])
def test_dot_segments_cannot_bypass_robots(path):
    fetcher, session, transport, _ = service({"/robots.txt": (200, b"User-agent: *\nDisallow: /private", {})})
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example" + path, "owner")
    assert error.value.code == "robots" and len(transport.calls) == 1


@pytest.mark.parametrize("path", ["/allowed%2f..%2fprivate", "/a%5cb", "//private"])
def test_ambiguous_path_separators_are_rejected(path):
    with pytest.raises(FetchError):
        normalize_url("http://public.example" + path)


def test_redirect_cap_and_safe_upgrade():
    routes = {f"/{i}": (302, b"", {"location": f"/{i + 1}"}) for i in range(5)}
    fetcher, session, _, _ = service(routes, redirects=2)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/0", "owner")
    assert error.value.code == "limit"
    fetcher, session, transport, _ = service({"/": (302, b"", {"location": "https://public.example/final"}), "/final": (200, b"done", {})})
    assert fetcher.fetch(session, "http://public.example/", "owner").url == "https://public.example/final"
    fetcher, session, _, _ = service({"/": (302, b"", {"location": "http://public.example/end"})})
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "https://public.example/", "owner")
    assert error.value.code == "scope"


@pytest.mark.parametrize("status,code", [(401, "robots"), (403, "robots"), (429, "backoff"), (500, "robots_unavailable"), (503, "robots_unavailable")])
def test_robots_errors_fail_closed(status, code):
    fetcher, session, transport, _ = service({"/robots.txt": (status, b"", {})})
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == code and len(transport.calls) == 1


@pytest.mark.parametrize("path,allowed", [("/", True), ("/private", False), ("/private/open", True), ("/private/openX", False),
                                          ("/caf%C3%A9", False), ("/encoded/slash", True), ("/encoded%2Fslash", False), ("/file.PDF", False)])
def test_robots_matching_normalization_and_specificity(path, allowed):
    body = "User-agent: *\nDisallow: /private\nAllow: /private/open$\nDisallow: /café\nDisallow: /encoded%2fslash\nDisallow: /*.PDF$\n".encode()
    assert parse_robots(body, FetchLimits()).allows(path) is allowed


def test_robots_combines_specific_groups_allow_tie_and_bom():
    policy = parse_robots(b"\xef\xbb\xbfUser-agent: *\nDisallow: /\n\nUser-agent: semanticcontentanalyser\nDisallow: /a\n\nUser-agent: SemanticContentAnalyser\nAllow: /a\nDisallow: /b\n", FetchLimits())
    assert policy.allows("/a") and policy.allows("/elsewhere") and not policy.allows("/b")
    assert not parse_robots(b"User-agent: *\nDisallow: /%62\n", FetchLimits()).allows("/b")
    assert parse_robots(b"User-agent: SemanticContentAnalyser\nDisallow:\nUser-agent: *\nDisallow: /", FetchLimits()).allows("/anything")
    assert not parse_robots(b"User-agent: *\nDisallow: /a$b\nAllow: /a*b", FetchLimits()).allows("/a$b")


@pytest.mark.parametrize("gap", [b"\n", b"  \n", b"# explanation\n\n"])
def test_robots_blank_lines_do_not_drop_rules(gap):
    policy = parse_robots(b"User-agent: *\n" + gap + b"Disallow: /first\n" + gap + b"Disallow: /second\n", FetchLimits())
    assert not policy.allows("/first") and not policy.allows("/second")
    assert policy.allows("/other")


def test_robots_parser_and_matching_have_work_bounds():
    with pytest.raises(FetchError):
        parse_robots(b"\xff", FetchLimits())
    with pytest.raises(FetchError):
        parse_robots(b"User-agent: *\nDisallow: /" + b"x" * 9000, FetchLimits())
    with pytest.raises(FetchError):
        parse_robots(b"User-agent: *\nDisallow: /a\nDisallow: /b", FetchLimits(robots_rules=1))
    policy = parse_robots(b"User-agent: *\nDisallow: /*aaaaaaaaaaaaab$", FetchLimits())
    with pytest.raises(FetchError):
        policy.allows("/" + "a" * 500, match_steps=50)


def test_request_run_owner_and_site_state_limits():
    fetcher, session, transport, _ = service({"/": (200, b"ok", {})}, requests=3)
    for _ in range(2):
        fetcher.fetch(session, "http://public.example/", "owner")
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "limit" and len(transport.calls) == 3
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "someone-else")
    assert error.value.code == "owner"
    fetcher, session, _, _ = service({"/": (200, b"ok", {})}, site_states=1)
    fetcher.fetch(session, "http://public.example/", "owner")
    with pytest.raises(FetchError) as error:
        fetcher.fetch(fetcher.new_session("second"), "http://second.example/", "second")
    assert error.value.code == "capacity"


def test_run_byte_and_lifetime_limits():
    fetcher, session, _, _ = service({"/": (200, b"body", {})}, run_decoded_bytes=3)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "limit"
    session.started = -100000
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "timeout"


def test_delay_and_crawl_delay_apply_before_content():
    fetcher, session, transport, _ = service({"/robots.txt": (200, b"User-agent: *\nCrawl-delay: 0.08", {}), "/": (200, b"ok", {})})
    fetcher.fetch(session, "http://public.example/", "owner")
    assert transport.calls[1][2] - transport.calls[0][2] >= .075


def test_retry_after_is_respected_without_retrying():
    fetcher, session, transport, _ = service({"/": (429, b"", {"retry-after": "120"})})
    with pytest.raises(FetchError):
        fetcher.fetch(session, "http://public.example/", "owner")
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "backoff" and len(transport.calls) == 2


def test_site_concurrency_is_shared_across_owners():
    fetcher, first, transport, _ = service({"/": (200, b"ok", {})})
    entered, release = threading.Event(), threading.Event()
    original = transport.get

    def blocked(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)

    transport.get = blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fetcher.fetch, first, "http://public.example/", "owner")
        assert entered.wait(2)
        try:
            with pytest.raises(FetchError) as error:
                fetcher.fetch(fetcher.new_session("second"), "http://public.example/", "second")
            assert error.value.code == "busy"
        finally:
            release.set()
        assert future.result().body == b"ok"


def test_default_connector_uses_numeric_sockaddr_and_detects_peer_mismatch(monkeypatch):
    records = []

    class Sock:
        def settimeout(self, timeout):
            assert 0 < timeout <= 3

        def connect(self, address):
            records.append(address)

        def getpeername(self):
            return ("8.8.8.8", 80)

        def close(self):
            records.append("closed")

    monkeypatch.setattr(socket, "socket", lambda *args: Sock())
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Independent DNS resolution"))
    budget = Budget(FetchSession("owner", FetchLimits()))
    sock = PinnedConnector().connect(normalize_url("http://public.example/"), ("8.8.8.8",), budget)
    assert records[0] == ("8.8.8.8", 80)
    monkeypatch.setattr(Sock, "getpeername", lambda self: ("10.0.0.1", 80))
    with pytest.raises(FetchError) as error:
        PinnedConnector().connect(normalize_url("http://public.example/"), ("8.8.8.8",), budget)
    assert error.value.code == "blocked_destination" and "10.0.0.1" not in str(error.value)


def test_ipv6_numeric_dial_and_tls_server_name(monkeypatch):
    address = "2606:4700:4700::1111"
    records = []

    class Sock:
        def settimeout(self, timeout):
            pass

        def connect(self, value):
            records.append(value)

        def getpeername(self):
            return (address, 443, 0, 0)

        def close(self):
            pass

    class Context:
        check_hostname, verify_mode = True, ssl.CERT_REQUIRED

        def wrap_socket(self, sock, server_hostname):
            records.append(server_hostname)
            return sock

    monkeypatch.setattr(socket, "socket", lambda family, kind: Sock() if family == socket.AF_INET6 else pytest.fail("Wrong IP family"))
    PinnedConnector(Context).connect(normalize_url("https://public.example/"), (address,), Budget(FetchSession("owner", FetchLimits())))
    assert records == [(address, 443, 0, 0), "public.example"]


def test_connector_rejects_private_address_even_when_called_directly(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *args: pytest.fail("Must reject before creating a socket"))
    with pytest.raises(FetchError):
        PinnedConnector().connect(normalize_url("http://public.example/"), ("127.0.0.1",), Budget(FetchSession("owner", FetchLimits())))


def test_connection_timeout_and_tls_handshake_timeout(monkeypatch):
    original = socket.socket

    class TimedOut:
        def settimeout(self, seconds):
            assert seconds <= .1

        def connect(self, address):
            raise TimeoutError()

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", lambda *args: TimedOut())
    with pytest.raises(FetchError) as error:
        PinnedConnector().connect(normalize_url("http://public.example/"), ("8.8.8.8",), Budget(FetchSession("owner", FetchLimits(connect_seconds=.1))))
    assert error.value.code == "timeout"
    monkeypatch.setattr(socket, "socket", original)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def silent_peer():
        conn, _ = listener.accept()
        with conn:
            time.sleep(.2)

    thread = threading.Thread(target=silent_peer, daemon=True)
    thread.start()
    stub = type("Fixture", (), {"server_address": listener.getsockname()})()
    try:
        with pytest.raises(FetchError) as error:
            FixtureConnector(stub).connect(normalize_url("https://public.example/"), ("8.8.8.8",), Budget(FetchSession("owner", FetchLimits(connect_seconds=.05))))
        assert error.value.code == "timeout"
    finally:
        listener.close()
        thread.join(timeout=1)


def test_dns_process_numeric_success_and_stall_termination(monkeypatch):
    import semantic_analyser.fetch_transport as module
    budget = Budget(FetchSession("owner", FetchLimits()))
    assert ProcessResolver().resolve("127.0.0.1", 80, budget) == ["127.0.0.1"]  # Numeric: no DNS network access.
    monkeypatch.setattr(module, "DNS_CODE", "import time; time.sleep(30)")
    spawned = []
    original = subprocess.Popen

    def remember(*args, **kwargs):
        child = original(*args, **kwargs)
        spawned.append(child)
        return child

    monkeypatch.setattr(module.subprocess, "Popen", remember)
    start = time.monotonic()
    with pytest.raises(FetchError) as error:
        ProcessResolver().resolve("ignored.example", 80, Budget(FetchSession("owner", FetchLimits(dns_seconds=.1))))
    assert error.value.code == "timeout" and time.monotonic() - start < 2
    assert spawned[0].poll() is not None


@pytest.fixture
def local_server():
    class Server(ThreadingHTTPServer):
        daemon_threads = True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.server.seen.append((self.path, dict(self.headers)))
            action = self.server.routes.get(self.path)
            if action:
                try:
                    action(self)
                except (OSError, ssl.SSLError):
                    pass
                return
            body = b"User-agent: *\nAllow: /\n" if self.path == "/robots.txt" else b"<html>Local fixture content</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain" if self.path == "/robots.txt" else "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = Server(("127.0.0.1", 0), Handler)
    server.routes, server.seen = {}, []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


class FixtureConnector(PinnedConnector):
    """TEST-ONLY logical-public -> loopback mapping, never a production allow flag.

    Address admission is unchanged. Default numeric dialing/peer checks are tested
    separately above. This adapter exercises real local HTTP/TLS parser behaviour.
    """
    def __init__(self, server, context_factory=ssl.create_default_context):
        super().__init__(context_factory)
        self.server = server

    def _dial(self, address, port, timeout):
        assert public_address(address) == address
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(self.server.server_address)
        return sock

    def _verify_peer(self, sock, address):
        assert sock.getpeername()[0] == "127.0.0.1"


def real_service(server, **limits):
    value = SafeFetcher(FetchLimits(delay_seconds=0, **limits), FakeDNS(), SocketTransport(FixtureConnector(server)))
    return value, value.new_session("owner")


def raw_response(payload):
    return lambda handler: handler.connection.sendall(payload)


def test_local_http_does_not_forward_cookies_auth_or_proxy_environment(local_server, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1")
    fetcher, session = real_service(local_server)
    assert fetcher.fetch(session, "http://public.example/article", "owner").body.startswith(b"<html>")
    for path, headers in local_server.seen:
        assert headers["Host"] == "public.example"
        assert not {key.lower() for key in headers} & {"cookie", "authorization", "proxy-authorization"}


@pytest.mark.parametrize("wire,code", [
    (b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\nx", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nContent-Length: -1\r\n\r\n", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nContent-Length:\r\n\r\n", "invalid_response"),
    (b"HTTP/1.1 200 \x00\r\nContent-Type: text/plain\r\n\r\nx", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 1\r\n\r\nx", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n folded: bad\r\n\r\nx", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nMissing colon\r\n\r\nx", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 20\r\n\r\nshort", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\nZZ\r\nx\r\n0\r\n\r\n", "invalid_response"),
    (b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 1\r\n\r\nx", "content"),
    (b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Encoding: br\r\nContent-Length: 1\r\n\r\nx", "content"),
    (b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n", "inaccessible"),
    (b"HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 0\r\n\r\n", "inaccessible"),
    (b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1\r\n\r\nx", "invalid_response"),
])
def test_malformed_or_inaccessible_local_responses(local_server, wire, code):
    local_server.routes["/bad"] = raw_response(wire)
    fetcher, session = real_service(local_server)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/bad", "owner")
    assert error.value.code == code


def test_compression_limits_and_truncation(local_server):
    bomb = gzip.compress(b"a" * (4 * 1024 * 1024))
    header = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Encoding: gzip\r\nContent-Length: "
    local_server.routes["/bomb"] = raw_response(header + str(len(bomb)).encode() + b"\r\n\r\n" + bomb)
    fetcher, session = real_service(local_server, decoded_bytes=1024)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/bomb", "owner")
    assert error.value.code == "limit"
    for name, body in [("good", gzip.compress(b"hello")), ("truncated", gzip.compress(b"hello")[:-4]), ("members", gzip.compress(b"hello") * 2)]:
        local_server.routes["/" + name] = raw_response(header + str(len(body)).encode() + b"\r\n\r\n" + body)
    assert fetcher.fetch(session, "http://public.example/good", "owner").body == b"hello"
    for path in ["truncated", "members"]:
        with pytest.raises(FetchError) as error:
            fetcher.fetch(session, "http://public.example/" + path, "owner")
        assert error.value.code == "invalid_response"
    deflated = zlib.compress(b"deflate text")
    local_server.routes["/deflate"] = raw_response(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Encoding: deflate\r\nContent-Length: " + str(len(deflated)).encode() + b"\r\n\r\n" + deflated)
    assert fetcher.fetch(session, "http://public.example/deflate", "owner").body == b"deflate text"


def test_header_encoded_chunked_and_run_wire_limits(local_server):
    local_server.routes["/headers"] = raw_response(b"HTTP/1.1 200 OK\r\nX-Long: " + b"a" * 40000 + b"\r\n\r\n")
    local_server.routes["/length"] = raw_response(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 9999999\r\n\r\n")
    body = b"1\r\nx\r\n" * 100 + b"0\r\n\r\n"
    local_server.routes["/chunked"] = raw_response(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n" + body)
    fetcher, session = real_service(local_server, encoded_bytes=50)
    for path in ["headers", "length", "chunked"]:
        with pytest.raises(FetchError) as error:
            fetcher.fetch(session, "http://public.example/" + path, "owner")
        assert error.value.code == "limit"
    fetcher, session = real_service(local_server, run_wire_bytes=100)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/", "owner")
    assert error.value.code == "limit"


@pytest.mark.parametrize("headers", [True, False])
def test_total_deadline_stops_slowloris_and_slow_body(local_server, headers):
    def slow(handler):
        if not headers:
            handler.connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 100\r\n\r\n")
        for value in (b"HTTP/1.1 200 OK\r\nX-Slow: " if headers else b"x" * 100):
            handler.connection.sendall(bytes([value]))
            time.sleep(.025)
    local_server.routes["/slow"] = slow
    fetcher, session = real_service(local_server, total_seconds=.2, read_seconds=.1)
    start = time.monotonic()
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/slow", "owner")
    assert error.value.code == "timeout" and time.monotonic() - start < 1.5


def test_read_inactivity_timeout(local_server):
    def stalled(handler):
        handler.connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 1\r\n\r\n")
        time.sleep(.3)
    local_server.routes["/stall"] = stalled
    fetcher, session = real_service(local_server, total_seconds=1, read_seconds=.05)
    with pytest.raises(FetchError) as error:
        fetcher.fetch(session, "http://public.example/stall", "owner")
    assert error.value.code == "timeout"


def test_real_local_tls_checks_certificate_and_hostname(local_server, tmp_path):
    openssl = which("openssl") or ("C:/Program Files/Git/usr/bin/openssl.exe" if Path("C:/Program Files/Git/usr/bin/openssl.exe").exists() else None)
    if not openssl:
        pytest.skip("Local TLS fixture requires existing openssl executable")
    key, cert = tmp_path / "ephemeral.key", tmp_path / "ephemeral.crt"
    generated = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                                "-days", "1", "-subj", "/CN=public.example", "-addext", "subjectAltName=DNS:public.example"],
                               capture_output=True, timeout=20)
    assert generated.returncode == 0, "Could not generate isolated ephemeral TLS fixture"
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert, key)
    local_server.socket = server_context.wrap_socket(local_server.socket, server_side=True)
    trusted = lambda: ssl.create_default_context(cafile=str(cert))
    fetcher = SafeFetcher(FetchLimits(delay_seconds=0), FakeDNS(), SocketTransport(FixtureConnector(local_server, trusted)))
    assert fetcher.fetch(fetcher.new_session("owner"), "https://public.example/", "owner").status == 200
    with pytest.raises(FetchError) as error:
        fetcher.fetch(fetcher.new_session("other"), "https://wrong.example/", "other")
    assert error.value.code == "network"
    untrusted, session = real_service(local_server)
    with pytest.raises(FetchError) as error:
        untrusted.fetch(session, "https://public.example/", "owner")
    assert error.value.code == "network"
