"""Single-process demo admission. No trust in arbitrary forwarded headers."""
from collections import deque
import ipaddress
import threading
import time

from fastapi import HTTPException


class DemoLimits:
    def __init__(self, settings, clock=time.monotonic):
        self.settings, self.clock = settings, clock
        self.networks = tuple(ipaddress.ip_network(n, strict=False) for n in settings.trusted_proxy_cidrs)
        self.lock = threading.Lock()
        self.buckets = {}
        self.active = 0

    def identity(self, request):
        peer = request.client.host if request.client else 'unknown'
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            return peer[:253]
        if any(address.version == n.version and address in n for n in self.networks):
            # Caddy overwrites this single header; X-Forwarded-* is never consulted.
            values = request.headers.getlist('x-demo-client')
            try:
                if len(values) != 1 or '%' in values[0]:
                    raise ValueError()
                identity = str(ipaddress.ip_address(values[0]))
                schemes = request.headers.getlist('x-demo-scheme')
                if schemes:
                    if len(schemes) != 1 or schemes[0] not in {'http','https'}:
                        raise ValueError()
                    request.scope['scheme'] = schemes[0]
                return identity
            except ValueError as error:
                raise HTTPException(400, 'Invalid proxy client identity.') from error
        return str(address)

    def charge(self, kind, identity, individual, total, seconds):
        if not self.settings.demo_limits_enabled:
            return
        with self.lock:
            now = self.clock()
            # Never evict live buckets to make room: doing so would reset budgets.
            for key, (expiry, events) in list(self.buckets.items()):
                if expiry <= now:
                    del self.buckets[key]
            keys = [(kind, identity), (kind, '*global*')]
            if len(self.buckets) + sum(k not in self.buckets for k in keys) > self.settings.demo_rate_keys:
                raise HTTPException(503, 'Demo admission capacity is full.', headers={'Retry-After':'60'})
            for key, limit in zip(keys, [individual, total]):
                events = self.buckets.get(key, (0, deque()))[1]
                while events and events[0] <= now-seconds:
                    events.popleft()
                if len(events) >= limit:
                    raise HTTPException(429, 'Demo request budget reached. Try later.',
                                        headers={'Retry-After':str(max(1, int(events[0]+seconds-now)+1))})
            for key in keys:
                expiry, events = self.buckets.setdefault(key, (0, deque()))
                events.append(now)
                self.buckets[key] = (now+seconds, events)

    def enter(self, identity):
        if not self.settings.demo_limits_enabled:
            return
        self.charge('api', identity, self.settings.demo_requests_per_minute,
                    self.settings.demo_global_requests_per_minute, 60)
        with self.lock:
            if self.active >= self.settings.demo_http_concurrency:
                raise HTTPException(503, 'Demo requests are busy.', headers={'Retry-After':'2'})
            self.active += 1

    def leave(self):
        if self.settings.demo_limits_enabled:
            with self.lock:
                self.active -= 1

    def session(self, identity):
        self.charge('sessions', identity, self.settings.demo_sessions_per_hour,
                    self.settings.demo_global_sessions_per_hour, 3600)

    def outbound(self, owner):
        self.charge('outbound', owner, self.settings.demo_outbound_per_hour,
                    self.settings.demo_global_outbound_per_hour, 3600)
