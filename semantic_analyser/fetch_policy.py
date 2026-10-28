"""Conservative public-URL admission and finite fetch budgets (no network I/O)."""

import ipaddress
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit


MESSAGES = {
    "unsafe_url": (400, "Use a public HTTP or HTTPS URL without credentials or an unsafe port."),
    "blocked_destination": (400, "The destination is not permitted for website fetching."),
    "scope": (400, "The URL or redirect leaves the selected website. Start a separate website run."),
    "dns": (502, "The website address could not be resolved safely."),
    "timeout": (504, "The website request timed out."),
    "limit": (413, "The website response or fetch run exceeds the supported resource limits."),
    "invalid_response": (502, "The website returned an unsupported or malformed response."),
    "content": (415, "The website did not return supported public text content."),
    "inaccessible": (502, "The requested public content is unavailable or requires authentication."),
    "network": (502, "The website could not be reached securely."),
    "robots": (403, "The website's robots policy does not permit this request."),
    "robots_unavailable": (503, "The website's robots policy could not be checked. Try again later."),
    "busy": (429, "The website or fetch run is busy. Try again later."),
    "backoff": (429, "The website requested a pause. Try again later."),
    "capacity": (503, "Website fetching capacity is full. Try again later."),
    "owner": (403, "This fetch run is not available to this session."),
}


class FetchError(Exception):
    def __init__(self, code):
        self.code = code
        self.status, self.message = MESSAGES[code]
        super().__init__(self.message)


@dataclass(frozen=True)
class FetchLimits:
    dns_seconds: float = 3
    connect_seconds: float = 3
    read_seconds: float = 5
    total_seconds: float = 20
    run_seconds: float = 180
    redirects: int = 3
    robots_redirects: int = 5
    requests: int = 60
    encoded_bytes: int = 2 * 1024 * 1024
    decoded_bytes: int = 2 * 1024 * 1024
    header_bytes: int = 32 * 1024
    run_wire_bytes: int = 20 * 1024 * 1024
    run_decoded_bytes: int = 20 * 1024 * 1024
    robots_bytes: int = 512 * 1024
    robots_rules: int = 4096
    robots_match_steps: int = 200000
    delay_seconds: float = 1
    max_crawl_delay: float = 30
    robots_cache_seconds: float = 300
    site_states: int = 256
    site_state_seconds: float = 900

    def __post_init__(self):
        import math
        if any(not math.isfinite(float(v)) or v <= 0 for k, v in vars(self).items()
               if k not in {"redirects", "robots_redirects", "delay_seconds"}):
            raise ValueError("Fetch limits must be finite and positive.")
        if any(not math.isfinite(float(v)) or v < 0 for v in [self.redirects, self.robots_redirects, self.delay_seconds]):
            raise ValueError("Redirect/delay bounds must be finite and nonnegative.")


DENIED_NETWORKS = tuple(ipaddress.ip_network(n) for n in [
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24", "192.88.99.0/24", "192.168.0.0/16",
    "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
    "168.63.129.16/32",  # Azure platform virtual address; not a general public website.
    "::/96", "::ffff:0:0/96", "64:ff9b::/96", "64:ff9b:1::/48", "100::/64",
    "2001::/23", "2002::/16", "fc00::/7", "fe80::/10", "fec0::/10", "ff00::/8",
])


def public_address(value):
    try:
        if not isinstance(value, str) or "%" in value:
            raise ValueError("Scoped/non-string address")
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise FetchError("blocked_destination") from error
    if (not address.is_global or address.is_multicast or address.is_reserved or address.is_unspecified or
            any(address.version == net.version and address in net for net in DENIED_NETWORKS) or
            (address.version == 6 and address not in ipaddress.ip_network("2000::/3"))):
        raise FetchError("blocked_destination")
    return str(address)


@dataclass(frozen=True)
class Target:
    url: str
    scheme: str
    host: str
    port: int
    path: str
    query: str

    @property
    def authority(self):
        return f"[{self.host}]" if ":" in self.host else self.host

    @property
    def origin(self):
        return f"{self.scheme}://{self.authority}"

    @property
    def request_target(self):
        return self.path + ("?" + self.query if self.query else "")


def normalize_url(url):
    try:
        if (not isinstance(url, str) or len(url) > 2048 or not url or
                any(c.isspace() or ord(c) < 33 or 127 <= ord(c) <= 159 for c in url) or "\\" in url or
                re.search(r"%(?![0-9a-fA-F]{2})", url)):
            raise ValueError("Bad URL syntax")
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or parts.username is not None or parts.password is not None:
            raise ValueError("Unsupported scheme or credentials")
        scheme = parts.scheme.lower()
        port = parts.port if parts.port is not None else (443 if scheme == "https" else 80)
        if port != (443 if scheme == "https" else 80):
            raise ValueError("Unsupported port")
        host = (parts.hostname or "").rstrip(".")
        if not host or "%" in host:
            raise ValueError("Missing/scoped host")
        try:
            host = str(ipaddress.ip_address(host))
        except ValueError:
            host = host.encode("idna").decode("ascii").lower()
            if len(host) > 253 or "." not in host or re.fullmatch(r"[0-9.]+", host) or host.startswith("0x"):
                raise ValueError("Ambiguous host")
            if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
                raise ValueError("Invalid host label")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".home.arpa")):
            raise FetchError("blocked_destination")
        credentials = {"token", "access_token", "api_key", "apikey", "password", "authorization", "auth", "signature", "x-amz-signature", "x-amz-credential"}
        if any(key.lower() in credentials for key, _ in parse_qsl(parts.query, max_num_fields=100)):
            raise ValueError("Credential query")
        raw_path = parts.path or "/"
        if re.search(r"%(?:2f|5c)", raw_path, re.IGNORECASE) or "//" in raw_path:
            raise ValueError("Ambiguous path separators")
        unreserved = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
        raw_path = re.sub(r"%([0-9a-fA-F]{2})", lambda m: chr(int(m[1], 16)) if chr(int(m[1], 16)) in unreserved else "%" + m[1].upper(), raw_path)
        trailing = raw_path.endswith(("/", "/.", "/.."))
        segments = []
        for segment in raw_path.split("/"):
            if segment == ".":
                continue
            if segment == "..":
                if segments:
                    segments.pop()
            else:
                segments.append(segment)
        raw_path = "/" + "/".join(segments).lstrip("/")
        if trailing and not raw_path.endswith("/"):
            raw_path += "/"
        path = quote(raw_path, safe="/%:@!$&'()*+,;=-._~")
        query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
        authority = f"[{host}]" if ":" in host else host
        normalized = urlunsplit((scheme, authority, path, query, ""))
        if len(normalized) > 2048:
            raise ValueError("Encoded URL too long")
        return Target(normalized, scheme, host, port, path, query)
    except FetchError:
        raise
    except (ValueError, UnicodeError) as error:
        raise FetchError("unsafe_url") from error


@dataclass
class FetchSession:
    owner: str
    limits: FetchLimits
    started: float = field(default_factory=time.monotonic)
    host: str | None = None
    requests: int = 0
    wire_bytes: int = 0
    decoded_bytes: int = 0
    robots: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


class Budget:
    def __init__(self, session, control=None):
        self.session, self.limits, self.control = session, session.limits, control
        self.end = min(time.monotonic() + self.limits.total_seconds, session.started + self.limits.run_seconds,
                       control.end if control else float("inf"))

    def check(self):
        if self.control:
            self.control.check()
        if time.monotonic() >= self.end:
            raise FetchError("timeout")

    def remaining(self, bound):
        self.check()
        return min(bound, max(.001, self.end - time.monotonic()))

    def request(self):
        self.check()
        if self.session.requests >= self.limits.requests:
            raise FetchError("limit")
        self.session.requests += 1

    def wire(self, size):
        self.session.wire_bytes += size
        if self.session.wire_bytes > self.limits.run_wire_bytes:
            raise FetchError("limit")
        self.check()

    def decoded(self, size):
        self.session.decoded_bytes += size
        if self.session.decoded_bytes > self.limits.run_decoded_bytes:
            raise FetchError("limit")
        self.check()
