"""Workspace-local staged website runs. Every network operation uses SafeFetcher."""

import hashlib
import json
import secrets
import time
import logging
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .extraction import Document, extract, homepage_metadata, site_url, sitemap, text
from .fetch_policy import FetchError, normalize_url
from .schemas import Article
from .storage import validate_collection

MAX_CANDIDATES, MAX_SELECTED, MAX_DISCOVERY = 200, 40, 12
WEBSITE_LIFETIME_SECONDS = 15 * 60
LOG = logging.getLogger(__name__)


class CollectionCapacityExceeded(ValueError):
    """Valid article text cannot fit the selected collection; not a parser failure."""


@dataclass
class WebsiteRun:
    identifier: str
    owner: str
    revision: str
    session: object
    base: str
    method: str
    phase: str = 'discovering'
    pending: list = field(default_factory=list)
    visited: set = field(default_factory=set)
    candidates: dict = field(default_factory=dict)
    selected: list = field(default_factory=list)
    extracted: list = field(default_factory=list)
    failures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    articles: list = field(default_factory=list)
    discovery_count: int = 0
    seen_posts: set = field(default_factory=set)

    def expired(self):
        deadline = self.session.deadline()
        return time.monotonic() >= deadline

    def view(self):
        return {'run_id': self.identifier, 'phase': self.phase, 'website': self.base,
                'candidates': list(self.candidates.values()), 'selected': self.selected,
                'processed': len(self.selected) if self.phase == 'ready' else len(self.extracted) + len(self.failures), 'failures': self.failures,
                'warnings': self.warnings[-15:], 'requests_used': self.session.requests,
                'seconds_remaining': max(0, round((self.session.absolute_deadline or self.session.started + self.session.limits.run_seconds) - time.monotonic())),
                'fetch_seconds_remaining': max(0, round(self.session.limits.run_seconds - self.session.active_seconds)),
                'articles': [{**a.model_dump(), 'headings': next((e['headings'] for e in self.extracted if e['url'] == a.url), [])}
                             for a in self.articles],
                'characters': sum(len(a.title) + len(a.body) for a in self.articles),
                'collection_revision': self.revision}


class WebsiteService:
    def __init__(self, fetcher):
        self.fetcher = fetcher

    def start(self, owner, revision, url, method):
        target = normalize_url(url)
        session = self.fetcher.new_session(owner)
        session.active_time_budget = True
        session.absolute_deadline = session.started + WEBSITE_LIFETIME_SECONDS
        # Explicit sitemap endpoints may be extensionless or query-based. A bare
        # website root instead discovers its advertised maps without probing REST.
        kind = 'map' if (target.path.lower().endswith('.xml') or
                         (method == 'sitemap' and (target.path != '/' or target.query))) else 'home'
        url = target.url
        return WebsiteRun(secrets.token_hex(16), owner, revision, session, target.url, method,
                          pending=[(kind, url, 0, 1)])

    def reference(self, run, value):
        return site_url(value, run.base)

    def candidate(self, run, url, title=''):
        try:
            url = self.reference(run, url)
        except FetchError:
            if 'Some unsafe or off-site URLs were excluded.' not in run.warnings:
                run.warnings.append('Some unsafe or off-site URLs were excluded.')
            return
        if len(run.candidates) >= MAX_CANDIDATES:
            return
        identifier = 'W' + hashlib.sha256(url.encode()).hexdigest()[:16]
        run.candidates.setdefault(identifier, {'id': identifier, 'url': url, 'title': title[:200] or urlsplit(url).path})

    def queue_maps(self, run, urls, depth=0):
        queued = {p[1] for p in run.pending}
        for value in urls:
            try:
                url = self.reference(run, value)
            except FetchError:
                continue
            if url in run.visited or url in queued:
                continue
            if depth > 3 or len(run.pending) >= MAX_DISCOVERY:
                warning = 'Sitemap discovery reached its bounded depth or queue limit; this is not the complete website.'
                if warning not in run.warnings:
                    run.warnings.append(warning)
            else:
                run.pending.append(('map', url, depth, 1))
                queued.add(url)

    def fallback_maps(self, run):
        origin = normalize_url(run.base).origin
        self.queue_maps(run, [origin + p for p in ['/sitemap.xml', '/sitemap_index.xml', '/wp-sitemap.xml']])

    def step(self, run, control):
        control.check()
        if run.phase not in {'discovering', 'extracting'}:
            raise ValueError('This website run has no pending fetch. Start again if it expired.')
        if not run.pending:
            raise ValueError('This website run has no pending work.')
        kind, url, depth, page = run.pending[0]
        try:
            response = self.fetcher.fetch(run.session, url, run.owner, control)
            control.check()
            # Only retire the item after network success; cancellation never silently skips it.
            run.pending.pop(0)
            if kind == 'article':
                if response.content_type not in {'text/html', 'application/xhtml+xml'}:
                    raise ValueError('The selected article did not return HTML.')
                item = extract(response.body, response.url, run.candidates[depth]['title'])
                item['candidate_id'], item['source_url'] = depth, url
                if sum(len(e['body']) + len(e['title']) for e in run.extracted) + len(item['body']) + len(item['title']) > 250000:
                    raise CollectionCapacityExceeded('Not included: this article would exceed the 250,000-character collection limit.')
                run.extracted.append(item)
            else:
                run.discovery_count += 1
                run.visited.add(url)
                if kind == 'home':
                    if response.content_type in {'application/xml', 'text/xml'}:
                        self.read_map(run, response.body, depth)
                    else:
                        api, maps = homepage_metadata(response.body, response.url)
                        if run.method in {'auto', 'sitemap'}:
                            self.queue_maps(run, maps)
                            for _, policy in run.session.robots.values():
                                self.queue_maps(run, policy.sitemaps)
                        if run.method == 'sitemap':
                            if not run.pending:
                                self.fallback_maps(run)
                        else:
                            origin = normalize_url(response.url).origin
                            api = api or origin + '/wp-json/'
                            api = api.rstrip('/') + '/wp/v2/posts'
                            run.pending.insert(0, ('wp', api + '?per_page=20&page=1&_fields=id,link,title,content.protected', 0, 1))
                elif kind == 'wp':
                    self.read_wp(run, response, url, page)
                else:
                    self.read_map(run, response.body, depth)
        except FetchError as error:
            # Only a genuine absent endpoint allows fallback. Never bypass auth/robots/anti-bot.
            if kind != 'article' and getattr(error, 'upstream_status', None) in {404, 410}:
                run.pending.pop(0)
                run.discovery_count += 1
                run.visited.add(url)
                if kind == 'wp' and not run.candidates and run.method == 'auto':
                    self.fallback_maps(run)
                elif kind == 'map':
                    message = f'An XML sitemap was unavailable (HTTP {error.upstream_status}). Use a published sitemap URL if discovery finds no articles.'
                    if message not in run.warnings:
                        run.warnings.append(message)
            else:
                run.phase = 'failed'
                labels = {'home':'Homepage discovery', 'wp':'WordPress discovery', 'map':'XML sitemap discovery', 'article':'Article extraction'}
                error.discovery_stage = labels[kind]
                error.diagnostic_reference = secrets.token_hex(6)
                error.message = labels[kind] + ': ' + error.message
                error.args = (error.message,)
                LOG.warning('Website fetch stopped reference=%s stage=%s resource=%s code=%s source_http_status=%s requests=%s',
                            error.diagnostic_reference, kind, getattr(error, 'fetch_resource', 'request'),
                            error.code, getattr(error, 'upstream_status', None), run.session.requests)
                run.warnings.append(error.message)
                raise
        except (ValueError, RecursionError) as error:
            message = str(error) if isinstance(error, ValueError) else 'The page structure is too complex.'
            if kind == 'article':
                run.failures.append({'id': depth, 'message': message,
                                     'kind': 'capacity' if isinstance(error, CollectionCapacityExceeded) else 'extraction'})
            else:
                run.phase = 'failed'
                raise ValueError('Discovery failed: ' + message) from error
        control.check()
        if run.phase == 'discovering':
            if run.discovery_count >= MAX_DISCOVERY or len(run.candidates) >= MAX_CANDIDATES:
                if run.pending:
                    run.warnings.append('Discovery reached its bounded limit; this is not the complete website.')
                run.pending.clear()
            if not run.pending:
                run.phase = 'selecting'
                if not run.candidates:
                    run.warnings.append('No posts found. Try an explicit XML sitemap URL; general link crawling is not supported.')
        elif run.phase == 'extracting' and not run.pending:
            try:
                self.assemble(run)
                run.phase = 'ready'
            except ValueError:
                run.phase = 'failed'
                raise
        return run.view()

    def read_wp(self, run, response, url, page):
        if response.content_type != 'application/json':
            raise ValueError('The WordPress endpoint did not return JSON. Try explicit sitemap discovery.')
        try:
            rows = json.loads(response.body)
        except (ValueError, RecursionError, UnicodeError) as error:
            raise ValueError('The WordPress endpoint returned invalid JSON.') from error
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('Unexpected WordPress posts response.')
        added = 0
        for row in rows:
            if not isinstance(row, dict) or type(row.get('id')) is not int or not isinstance(row.get('link'), str):
                raise ValueError('Unexpected WordPress post fields.')
            if isinstance(row.get('content'), dict) and row['content'].get('protected'):
                continue
            if row['id'] in run.seen_posts:
                continue
            run.seen_posts.add(row['id'])
            title = row.get('title', {})
            rendered = title.get('rendered', '') if isinstance(title, dict) else ''
            rendered = rendered if isinstance(rendered, str) else ''
            self.candidate(run, row['link'], text(Document(rendered.encode()).root))
            added += 1
        total = response.headers.get('x-wp-totalpages', '')
        if total and (not total.isascii() or not total.isdigit() or len(total) > 6):
            raise ValueError('Invalid WordPress pagination metadata.')
        more = page < int(total) if total else len(rows) == 20
        if added and more and page < 10:
            run.pending.insert(0, ('wp', url.replace(f'page={page}&', f'page={page + 1}&'), 0, page + 1))
        elif more:
            run.warnings.append('WordPress pagination stopped at its cap or repeated posts.')
        # Prefer REST when available; sitemap fallback is for absent REST only.
        if run.candidates:
            run.pending[:] = [p for p in run.pending if p[0] == 'wp']
        elif not run.pending and run.method == 'auto':
            self.fallback_maps(run)

    def read_map(self, run, body, depth):
        root, urls = sitemap(body)
        if len(urls) >= MAX_CANDIDATES:
            warning = 'A sitemap reached its bounded 200-location limit; this may not be the complete website.'
            if warning not in run.warnings:
                run.warnings.append(warning)
        if root == 'sitemapindex':
            self.queue_maps(run, urls, depth + 1)
        else:
            for url in urls:
                self.candidate(run, url)

    def select(self, run, ids):
        if run.phase != 'selecting':
            raise ValueError('Finish discovery before selecting articles.')
        if not 1 <= len(ids) <= MAX_SELECTED or len(set(ids)) != len(ids) or any(i not in run.candidates for i in ids):
            raise ValueError('Choose between 1 and 40 distinct discovered articles from this run.')
        run.selected = ids
        run.pending = [('article', run.candidates[i]['url'], i, 1) for i in ids]
        run.phase = 'extracting'
        return run.view()

    def assemble(self, run):
        # Only short exact paragraph boilerplate repeated across >=80% of >=3 pages.
        counts = Counter(v for e in run.extracted for v in {v for t, v in e['blocks'] if t == 'p' and 20 <= len(v) <= 240})
        repeated = {v for v, n in counts.items() if len(run.extracted) >= 3 and n >= max(3, .8 * len(run.extracted))}
        aliases, hashes, kept = {}, {}, []
        for e in run.extracted:
            body = '\n\n'.join(v for t, v in e['blocks'] if t != 'p' or v not in repeated)
            if len(body.split()) < 35 or len(body) < 200:
                run.failures.append({'id': e['candidate_id'], 'message': 'Too little unique text remains after template removal.'})
                continue
            fingerprint = hashlib.sha256(body.encode()).hexdigest()
            previous = hashes.get(fingerprint) or aliases.get(e['url'])
            identifier = previous or e['candidate_id']
            for url in [e['source_url'], e['url'], self.reference(run, e['source_url'])]:
                aliases[url] = identifier
            if previous:
                run.warnings.append('Duplicate canonical URL or article text was collapsed.')
                continue
            hashes[fingerprint] = identifier
            kept.append((e, identifier, body))
        run.articles = [Article(id=i, title=e['title'], body=body, url=e['url'],
                                existing_links=list(dict.fromkeys(aliases[u] for u in e['links'] if u in aliases and aliases[u] != i))[:100])
                        for e, i, body in kept]
        if run.articles:
            validate_collection(run.articles)  # Model admission remains at the final atomic commit.
        if repeated:
            run.warnings.append(f'Removed {len(repeated)} short repeated template paragraphs; review the preview.')
