"""Bounded inert HTML and sitemap parsing. Never executes markup or resolves entities."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from xml.parsers import expat

from .fetch_policy import FetchError, normalize_url

MAX_NODES = 30000
SKIP = {'script', 'style', 'nav', 'footer', 'aside', 'form', 'noscript', 'iframe', 'svg', 'button', 'template', 'dialog'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
NOISE = re.compile(r'(?:^|[\s_-])(nav|menu|sidebar|footer|comments?|related|share|sharing|social|advert\w*|cookie|breadcrumb|subscribe|paywall|login)(?:$|[\s_-])', re.I)


def clean(text):
    return ' '.join(text.split())


def site_url(value, base):
    """Normalize in-scope references without fetching or trusting canonical hosts."""
    target = normalize_url(urljoin(base, value))
    original = normalize_url(base)
    if target.host != original.host or (original.scheme == 'https' and target.scheme != 'https'):
        raise FetchError('scope')
    parts = urlsplit(target.url)
    query = [(k, v) for k, v in parse_qsl(parts.query, max_num_fields=100)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sorted(query)), ''))


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class Document(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        if len(body) > 2 * 1024 * 1024:
            raise ValueError('The HTML exceeds the parsing limit.')
        self.root = Node('document')
        self.stack, self.nodes = [self.root], 0
        try:
            self.feed(body.decode('utf-8-sig'))
            self.close()
        except (UnicodeError, RecursionError, AssertionError) as error:
            raise ValueError('This page needs valid, supported UTF-8 HTML.') from error

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > MAX_NODES or len(self.stack) > 96 or len(attrs) > 100:
            raise ValueError('The HTML structure exceeds the parsing limit.')
        # HTML's common implicit paragraph/list endings; remaining malformed HTML is conservative.
        if tag in {'p', 'li'} and self.stack[-1].tag == tag:
            self.stack.pop()
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag and tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise ValueError('The HTML structure exceeds the parsing limit.')
        self.stack[-1].children.append(text)


def hidden(node):
    attrs = node.attrs
    return (node.tag in SKIP or 'hidden' in attrs or attrs.get('aria-hidden') == 'true' or
            attrs.get('role') in {'navigation', 'banner', 'contentinfo', 'complementary'} or
            bool(NOISE.search((attrs.get('class') or '') + ' ' + (attrs.get('id') or ''))))


def walk(node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from walk(child)


def visible(node):
    if hidden(node):
        return
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from visible(child)


def text(node):
    if hidden(node):
        return ''
    return clean(' '.join(text(c) if isinstance(c, Node) else c for c in node.children))


def homepage_metadata(body, base):
    doc = Document(body)
    api, maps = None, []
    for n in walk(doc.root):
        if n.tag != 'link':
            continue
        rel, href = (n.attrs.get('rel') or '').lower(), n.attrs.get('href') or ''
        try:
            url = site_url(href, base)
        except FetchError:
            continue
        if rel == 'https://api.w.org/':
            api = url
        if 'sitemap' in rel.split() and len(maps) < 10:
            maps.append(url)
    return api, maps


def extract(body, url, fallback=''):
    doc = Document(body)
    nodes = list(walk(doc.root))
    # Explicit protection signals are rejected rather than using API text to bypass them.
    if any(n.tag == 'meta' and (n.attrs.get('itemprop') or '').lower() == 'isaccessibleforfree'
           and (n.attrs.get('content') or '').lower() == 'false' for n in nodes):
        raise ValueError('This page is marked as restricted content.')
    if any((n.tag == 'script' and (n.attrs.get('type') or '').lower() == 'application/ld+json' and
            re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', ''.join(c for c in n.children if isinstance(c, str)), re.I)) or
           re.search(r'(?:^|[\s_-])(paywall|post-password-form)(?:$|[\s_-])', n.attrs.get('class') or '', re.I)
           for n in nodes):
        raise ValueError('This page signals a paywall or password restriction.')
    roots = [n for n in nodes if n.tag == 'article' and not hidden(n)]
    if not roots:
        roots = [n for n in nodes if not hidden(n) and (n.tag == 'main' or n.attrs.get('role') == 'main' or
                 re.search(r'(?:^|\s)(entry-content|post-content|article-content)(?:$|\s)', n.attrs.get('class') or ''))]
    if not roots:
        raise ValueError('No main/article content region was found. JavaScript-only and ambiguous layouts are unsupported.')
    root = max(roots, key=lambda n: len(text(n)))
    title = next((text(n) for n in visible(root) if n.tag == 'h1' and text(n)), '')
    title = title or next((text(n) for n in nodes if n.tag == 'title' and text(n)), '') or fallback
    if not title or len(title) > 200:
        raise ValueError('The extracted title is missing or exceeds 200 characters.')
    canonical = site_url(url, url)
    for n in nodes:
        if n.tag == 'link' and 'canonical' in (n.attrs.get('rel') or '').lower().split():
            try:
                canonical = site_url(n.attrs.get('href') or '', url)
            except FetchError:
                pass  # Never accept a cross-site or unsafe canonical.
            break
    blocks, links = [], []

    def collect(n):
        if hidden(n):
            return
        if n.tag == 'a' and n.attrs.get('href'):
            try:
                links.append(site_url(n.attrs['href'], url))
            except FetchError:
                pass
        # Block extraction supports nested generic divs without duplicating text.
        if n.tag in {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre'}:
            value = text(n)
            if value:
                blocks.append((n.tag, value))
            for a in visible(n):
                if a.tag == 'a' and a.attrs.get('href'):
                    try:
                        links.append(site_url(a.attrs['href'], url))
                    except FetchError:
                        pass
            return
        inline = []
        for child in n.children:
            if isinstance(child, Node):
                if inline and clean(' '.join(inline)):
                    blocks.append(('p', clean(' '.join(inline))))
                inline = []
                collect(child)
            else:
                inline.append(child)
        if clean(' '.join(inline)):
            blocks.append(('p', clean(' '.join(inline))))

    collect(root)
    content = '\n\n'.join(value for _, value in blocks)
    if len(content) < 200 or len(content.split()) < 35:
        raise ValueError('Too little public article text was found; the page may be restricted or require JavaScript.')
    if len(content) > 20000:
        raise ValueError('The article exceeds 20,000 characters. Choose a shorter article.')
    return {'title': title, 'body': content, 'url': canonical, 'blocks': blocks,
            'headings': [v for t, v in blocks if t.startswith('h')][:100], 'links': list(dict.fromkeys(links))[:1000]}


def sitemap(body):
    """Expat rejects DTDs before expansion, including UTF-16 declarations."""
    if len(body) > 2 * 1024 * 1024:
        raise ValueError('The sitemap exceeds the parsing limit.')
    parser = expat.ParserCreate(namespace_separator='}')
    stack, locations, current = [], [], []
    count, root, current_length = 0, None, 0

    def reject(*args):
        raise ValueError('Sitemaps with DTDs or entities are not supported.')

    def start(name, attrs):
        nonlocal count, root, current, current_length
        name = name.rsplit('}', 1)[-1]
        count += 1
        stack.append(name)
        root = root or name
        if count > 20000 or len(stack) > 32 or len(attrs) > 100:
            raise ValueError('The sitemap structure exceeds supported limits.')
        if name == 'loc':
            current = []
            current_length = 0

    def data(value):
        nonlocal current_length
        if stack[-1:] == ['loc']:
            current_length += len(value)
            if current_length > 2048:
                raise ValueError('A sitemap URL exceeds 2,048 characters.')
            current.append(value)

    def end(name):
        if stack == [root, 'sitemap' if root == 'sitemapindex' else 'url', 'loc'] and len(locations) < 200:
            locations.append(''.join(current).strip())
        stack.pop()

    parser.StartElementHandler, parser.EndElementHandler, parser.CharacterDataHandler = start, end, data
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    try:
        parser.Parse(body, True)
    except expat.ExpatError as error:
        raise ValueError('The website returned malformed sitemap XML.') from error
    if root not in {'sitemapindex', 'urlset'}:
        raise ValueError('Expected a sitemap index or URL set.')
    return root, locations
