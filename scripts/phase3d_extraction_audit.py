"""Independent HTMLParser source view for offline, human-reviewable extraction checks.

This deliberately does not call the application's extract/hidden/text functions.
It is a structural reference, not a browser rendering or independently labelled truth.
"""
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
SKIP = {'script','style','nav','footer','aside','form','noscript','iframe','svg','button','template'}


def clean(value):
    return ' '.join(value.split())


class SourceView(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.stack, self.body, self.headings, self.links, self.canonicals = [], [], [], [], []
        self.body_depth, self.heading = None, None
        self.feed(raw.decode('utf-8-sig'))
        self.close()

    def handle_starttag(self, tag, values):
        attrs = dict(values)
        skipped = tag in SKIP or 'hidden' in attrs or attrs.get('aria-hidden') == 'true'
        if tag not in VOID:
            self.stack.append((tag, skipped))
        if self.body_depth is None and 'entry-content' in (attrs.get('class') or '').split():
            self.body_depth = len(self.stack)
        active = self.body_depth is not None and len(self.stack) >= self.body_depth
        if re.fullmatch('h[1-6]', tag):
            self.heading = [tag, [], active]
        if active and tag == 'a' and attrs.get('href') and not any(skip for _,skip in self.stack):
            self.links.append(attrs['href'])
        if tag == 'link' and 'canonical' in (attrs.get('rel') or '').lower().split():
            self.canonicals.append(attrs.get('href') or '')

    def handle_endtag(self, tag):
        if self.heading and tag == self.heading[0]:
            self.headings.append({'tag':tag,'text':clean(' '.join(self.heading[1])),'in_body':self.heading[2]})
            self.heading = None
        for index in range(len(self.stack)-1,-1,-1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if self.body_depth is not None and len(self.stack) < self.body_depth:
            self.body_depth = None

    def handle_data(self, value):
        if any(skip for _,skip in self.stack):
            return
        if self.body_depth is not None and len(self.stack) >= self.body_depth:
            self.body.append(value)
        if self.heading:
            self.heading[1].append(value)


def audit_article(article, raw, recorded_headings, selected):
    source = SourceView(raw)
    plain = clean(' '.join(source.body))
    expected = Counter(re.findall(r'\w+', plain.casefold()))
    actual = Counter(re.findall(r'\w+', article['body'].casefold()))
    missing, extra = expected - actual, actual - expected
    h1 = [h['text'] for h in source.headings if h['tag']=='h1']
    body_headings = [h['text'] for h in source.headings if h['in_body']]
    # References here preserve meaningful query strings/fragments separately from
    # production normalization, making a mapping difference visible for review.
    expected_links = set()
    for link in source.links:
        parts = urlsplit(urljoin(article['url'],link))
        url = urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
        if url in selected and selected[url] != article['id']:
            expected_links.add(selected[url])
    mapped = set(article['existing_links'])
    return {'id':article['id'],'url':article['url'],'title_matches_source_h1':article['title'] in h1,
            'source_h1_count':len(h1),'source_body_words':sum(expected.values()),'saved_body_words':sum(actual.values()),
            'missing_word_occurrences':sum(missing.values()),'extra_word_occurrences':sum(extra.values()),
            'missing_word_types':dict(missing.most_common(15)),
            'missing_body_headings':[h for h in body_headings if h not in recorded_headings],
            'additional_recorded_headings':[h for h in recorded_headings if h not in body_headings],
            'canonical_matches_source':article['url'] in [urljoin(article['url'],x) for x in source.canonicals],
            'missing_selected_link_ids':sorted(expected_links-mapped),'extra_selected_link_ids':sorted(mapped-expected_links),
            'residual_contact_signal':bool(re.search(r'contact freeze edge|call 1300',article['body'],re.I)),
            'source_plain':plain}
