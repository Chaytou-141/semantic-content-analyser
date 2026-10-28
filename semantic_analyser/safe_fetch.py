"""Owner-bound fetching foundation; no discovery, extraction or analysis imports."""

import email.utils
import hashlib
import ipaddress
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from urllib.parse import urljoin

from .fetch_policy import Budget, FetchError, FetchLimits, FetchSession, normalize_url
from .fetch_transport import ProcessResolver, SocketTransport, resolve_public
from .robots_policy import RobotsPolicy, parse_robots


@dataclass
class SiteState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    next_start: float = 0
    touched: float = field(default_factory=time.monotonic)


class SiteGate:
    def __init__(self, limits):
        self.limits, self.states, self.lock = limits, {}, threading.Lock()

    @contextmanager
    def enter(self, host, delay, budget):
        with self.lock:
            now = time.monotonic()
            for key, old in list(self.states.items()):
                if not old.lock.locked() and old.next_start <= now and now - old.touched >= self.limits.site_state_seconds:
                    del self.states[key]
            if host not in self.states:
                if len(self.states) >= self.limits.site_states:
                    raise FetchError("capacity")
                self.states[host] = SiteState()
            state = self.states[host]
            if not state.lock.acquire(blocking=False):
                raise FetchError("busy")
        try:
            if state.next_start:
                state.next_start = max(state.next_start, state.touched + max(delay, self.limits.delay_seconds))
            while time.monotonic() < state.next_start:
                budget.check()
                remaining = state.next_start - time.monotonic()
                if remaining >= budget.remaining(self.limits.total_seconds):
                    raise FetchError("backoff")
                time.sleep(min(.05, max(.001, remaining)))
            yield state
        finally:
            state.touched = time.monotonic()
            state.next_start = max(state.next_start, state.touched + max(delay, self.limits.delay_seconds))
            state.lock.release()


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes
    encoded_bytes: int
    redirects: int

    def metadata(self):
        return {"url": self.url, "status": self.status, "content_type": self.content_type,
                "encoded_bytes": self.encoded_bytes, "decoded_bytes": len(self.body),
                "body_sha256": hashlib.sha256(self.body).hexdigest(), "redirects": self.redirects}


class SafeFetcher:
    def __init__(self, limits=None, resolver=None, transport=None, denied_networks=()):
        self.limits = limits or FetchLimits()
        self.resolver = resolver or ProcessResolver()
        self.transport = transport or SocketTransport()
        self.gate = SiteGate(self.limits)
        self.denied_networks = tuple(ipaddress.ip_network(value, strict=False) for value in denied_networks)

    def new_session(self, owner):
        if not owner:
            raise ValueError("Fetch sessions require a server-owned identity.")
        return FetchSession(owner, self.limits)

    def _one(self, target, budget, decoded_limit, delay):
        budget.request()  # Failed DNS and denied addresses consume the run request budget too.
        with self.gate.enter(target.host, delay, budget) as state:
            addresses = resolve_public(target, self.resolver, budget, self.denied_networks)
            response = self.transport.get(target, addresses, budget, decoded_limit)
            if response.status in {429, 503}:
                value = response.headers.get("retry-after", "")
                seconds = 60
                try:
                    if value.isdigit() and len(value) <= 10:
                        seconds = max(seconds, int(value))
                    elif value:
                        seconds = max(seconds, email.utils.parsedate_to_datetime(value).timestamp() - time.time())
                except (ValueError, TypeError, OverflowError):
                    pass
                state.next_start = max(state.next_start, time.monotonic() + seconds)
            return response

    def _redirect(self, target, response, visited):
        location = response.headers.get("location", "")
        if not location:
            raise FetchError("invalid_response")
        destination = normalize_url(urljoin(target.url, location))
        if destination.host != target.host or (target.scheme == "https" and destination.scheme != "https"):
            raise FetchError("scope")
        if destination.url in visited:
            raise FetchError("invalid_response")
        return destination

    def _robots(self, target, session, budget):
        cached = session.robots.get(target.origin)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        robots = normalize_url(target.origin + "/robots.txt")
        visited = set()
        for index in range(self.limits.robots_redirects + 1):
            visited.add(robots.url)
            response = self._one(robots, budget, self.limits.robots_bytes, 0)
            if response.status in {301, 302, 303, 307, 308}:
                if index >= self.limits.robots_redirects:
                    raise FetchError("robots_unavailable")
                robots = self._redirect(robots, response, visited)
                continue
            if response.status in {404, 410, 204}:
                policy = RobotsPolicy()
            elif response.status == 200:
                policy = parse_robots(response.body, self.limits)
            elif response.status in {401, 403}:
                policy = RobotsPolicy(deny_all=True)
            elif response.status == 429:
                raise FetchError("backoff")
            else:
                raise FetchError("robots_unavailable")
            cache_seconds = self.limits.robots_cache_seconds
            cache_control = response.headers.get("cache-control", "").lower()
            if "no-store" in cache_control or "no-cache" in cache_control:
                cache_seconds = 0
            for item in cache_control.split(","):
                key, _, value = item.strip().partition("=")
                if key == "max-age" and value.isascii() and value.isdigit() and len(value) <= 10:
                    cache_seconds = min(cache_seconds, int(value))
            session.robots[target.origin] = (time.monotonic() + cache_seconds, policy)
            return policy
        raise FetchError("robots_unavailable")

    def fetch(self, session, url, owner, control=None):
        if session.owner != owner:
            raise FetchError("owner")
        if not session.lock.acquire(blocking=False):
            raise FetchError("busy")
        try:
            budget = Budget(session, control)
            target = normalize_url(url)
            # Prevalidate the initial host before even requesting its robots file.
            # DNS is repeated and pinned on EVERY actual wire request, including
            # the content request after robots; no validated result is trusted later.
            if session.host is not None and session.host != target.host:
                raise FetchError("scope")
            session.host = target.host
            visited = set()
            for index in range(self.limits.redirects + 1):
                budget.check()
                visited.add(target.url)
                policy = RobotsPolicy() if target.path == "/robots.txt" and not target.query else self._robots(target, session, budget)
                if not policy.allows(target.request_target, budget.check, self.limits.robots_match_steps):
                    raise FetchError("robots")
                response = self._one(target, budget, self.limits.decoded_bytes, policy.delay)
                if response.status in {301, 302, 303, 307, 308}:
                    if index >= self.limits.redirects:
                        raise FetchError("limit")
                    target = self._redirect(target, response, visited)
                    continue
                if response.status == 429:
                    raise FetchError("backoff")
                if response.status != 200:
                    raise FetchError("inaccessible")
                if not response.body:
                    raise FetchError("content")
                budget.check()
                return FetchResult(target.url, response.status, response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
                                   response.body, response.encoded_bytes, index)
            raise FetchError("limit")
        finally:
            session.lock.release()
