"""Original synthetic, authorised fixture pages; no network or model loading."""
import csv
import html
import io
import json
from pathlib import Path

BASE = 'https://public.example'


def article(index, body=None):
    prose = body or ('Choose equipment that fits the available counter space and daily workflow. '
                     'Measure ventilation clearance before planning the installation. Review maintenance '
                     'needs and energy costs with staff before buying a refrigerator. ' * 5)
    paragraphs = ''.join('<p>' + html.escape(p) + '</p>' for p in prose.split('\n\n'))
    return (f'<html><head><title>Equipment guide {index}</title><link rel="canonical" href="/posts/{index}"></head>'
            f'<body><nav>NAVIGATION POISON<a href="/posts/3">Menu</a></nav><article><h1>Equipment guide {index}</h1>'
            f'<h2>Planning equipment {index}</h2>{paragraphs}<p><a href="/posts/{index % 40 + 1}">Next equipment guide</a></p>'
            '<div class="related">RELATED POISON</div><script>window.evil=true</script></article>'
            '<footer>FOOTER POISON</footer></body></html>').encode()


def routes(method='wordpress', count=40, realistic=False):
    values = {
        '/robots.txt': (200, b'User-agent: *\nAllow: /\n', {'content-type': 'text/plain'}),
        '/': (200, b'<html><head></head><body>Public blog</body></html>', {'content-type': 'text/html'}),
    }
    corpus = list(csv.DictReader(io.StringIO((Path(__file__).resolve().parents[1] / 'benchmarks/phase1b/articles.csv').read_text(encoding='utf-8')))) if realistic else []
    for index in range(1, count + 1):
        values[f'/posts/{index}'] = (200, article(index, corpus[index - 1]['body'] if corpus else None), {'content-type': 'text/html'})
    if method == 'wordpress':
        for page in range(1, (count + 19) // 20 + 1):
            rows = [{'id': index, 'link': f'{BASE}/posts/{index}', 'title': {'rendered': f'Equipment guide {index}'}, 'content': {'protected': False}}
                    for index in range(1 + 20 * (page - 1), min(count, 20 * page) + 1)]
            values[f'/wp-json/wp/v2/posts?per_page=20&page={page}&_fields=id,link,title,content.protected'] = (
                200, json.dumps(rows).encode(), {'content-type': 'application/json', 'x-wp-totalpages': str((count + 19) // 20)})
    else:
        values['/sitemap.xml'] = (200, f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{BASE}/blog-map.xml</loc></sitemap></sitemapindex>'.encode(), {'content-type': 'application/xml'})
        values['/blog-map.xml'] = (200, ('<urlset>' + ''.join(f'<url><loc>{BASE}/posts/{i}</loc></url>' for i in range(1, count + 1)) + '</urlset>').encode(), {'content-type': 'application/xml'})
    return values
