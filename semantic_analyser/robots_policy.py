"""Bounded REP matching: grouped agents, longest rule, wildcard/end anchor."""

import math
import re
from dataclasses import dataclass

from .fetch_policy import FetchError

PRODUCT = "semanticcontentanalyser"
UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def units(value):
    """Normalize percent-encoded unreserved and UTF-8 octets without decoding / etc."""
    result, i = [], 0
    while i < len(value):
        if value[i] == "%" and i + 2 < len(value) and re.fullmatch("[0-9a-fA-F]{2}", value[i + 1:i + 3]):
            code = int(value[i + 1:i + 3], 16)
            char = chr(code)
            result.append(char if char in UNRESERVED else f"%{code:02X}")
            i += 3
        else:
            char = value[i]
            result.extend([f"%{byte:02X}" for byte in char.encode("utf-8")] if ord(char) > 127 else [char])
            i += 1
    return result


def matches(pattern, path, counter=None, limit=200000):
    # Operation-bounded wildcard scan, not attacker-controlled regex backtracking.
    counter = counter if counter is not None else [0]
    anchored = bool(pattern and pattern[-1] == "$")
    pattern = pattern[:-1] if anchored else pattern + ["*"]
    p = s = 0
    star, resume = -1, 0
    while s < len(path):
        counter[0] += 1
        if counter[0] > limit:
            raise FetchError("robots_unavailable")
        if p < len(pattern) and pattern[p] != "*" and pattern[p] == path[s]:
            p, s = p + 1, s + 1
        elif p < len(pattern) and pattern[p] == "*":
            star, resume = p, s
            p += 1
        elif star >= 0:
            resume += 1
            s, p = resume, star + 1
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


@dataclass(frozen=True)
class RobotsPolicy:
    rules: tuple = ()
    delay: float = 0
    deny_all: bool = False
    sitemaps: tuple = ()

    def allows(self, request_target, check=lambda: None, match_steps=200000):
        if self.deny_all:
            return False
        path = units(request_target)
        matched, counter = [], [0]
        for pattern, allow in self.rules:
            check()
            if matches(list(pattern), path, counter, match_steps):
                weighted = pattern[:-1] if pattern and pattern[-1] == "$" else pattern
                matched.append((sum(x != "*" for x in weighted), allow))
        if not matched:
            return True
        longest = max(weight for weight, _ in matched)
        return any(allow for weight, allow in matched if weight == longest)


def parse_robots(body, limits):
    try:
        text = body.decode("utf-8-sig")
    except UnicodeError as error:
        raise FetchError("robots_unavailable") from error
    if len(body) > limits.robots_bytes:
        raise FetchError("limit")
    groups, agents, rules, delays = [], [], [], []
    count, had_rule, sitemaps = 0, False, []

    def finish():
        nonlocal had_rule
        if agents:
            groups.append((tuple(agents), tuple(rules), tuple(delays)))
        agents.clear()
        rules.clear()
        delays.clear()
        had_rule = False

    for raw in text.splitlines():
        if len(raw) > 8192:
            raise FetchError("robots_unavailable")
        line = raw.split("#", 1)[0].strip()
        if not line:
            # Empty/comment lines do not terminate a REP group. A subsequent
            # User-agent after rules is what starts the next group.
            continue
        key, colon, value = line.partition(":")
        if not colon:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == 'sitemap' and len(sitemaps) < 10 and len(value) <= 2048:
            sitemaps.append(value)
        if key == "user-agent":
            if had_rule or delays:
                finish()
            if value == "*" or re.fullmatch(r"[A-Za-z_-]+", value):
                agents.append(value.lower())
        elif key in {"allow", "disallow"} and agents:
            had_rule = True
            if value.startswith("/"):
                count += 1
                if count > limits.robots_rules:
                    raise FetchError("robots_unavailable")
                rules.append((tuple(units(value)), key == "allow"))
        elif key == "crawl-delay" and agents:
            try:
                delay = float(value)
                if math.isfinite(delay) and delay >= 0:
                    delays.append(delay)
            except ValueError:
                pass
    finish()
    selected = [g for g in groups if PRODUCT in g[0]]
    if not selected:
        selected = [g for g in groups if "*" in g[0]]
    delay = max((d for _, _, ds in selected for d in ds), default=0)
    if delay > limits.max_crawl_delay:
        raise FetchError("robots")
    return RobotsPolicy(tuple(rule for _, rs, _ in selected for rule in rs), delay, sitemaps=tuple(sitemaps))
