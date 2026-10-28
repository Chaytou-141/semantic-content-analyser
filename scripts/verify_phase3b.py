"""One final suite + focused local HTTP/browser/offline MiniLM verification.

No public website access; no historical performance benchmark is executed.
All state/logs/screenshots are disposable under runtime/phase3b.
"""
import csv
import hashlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime/phase3b'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.environ.update({'DATABASE_PATH': str(OUT / 'bootstrap.sqlite3'), 'WORKSPACE_MODE': 'local',
                  'APP_ENV': 'development', 'APP_PASSWORD': '', 'PRELOAD_MODEL': 'false',
                  'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                  'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
                  'TOKENIZERS_PARALLELISM': 'false', 'ENABLE_WEBSITE_FETCH': 'false'})


def preservation():
    protected = json.loads((OUT / 'preservation-before.json').read_text())
    changed = [name for name, digest in protected.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    return len(protected)


def capture_preservation():
    guard = OUT / 'preservation-before.json'
    if guard.exists():
        return
    paths = [p for folder in ['data', 'labels', 'benchmarks', 'infra', 'deploy']
             for p in (ROOT / folder).rglob('*') if p.is_file() and '.terraform' not in p.parts]
    paths += [p for p in (ROOT / 'runtime').rglob('*.sqlite3*') if p.is_file() and 'phase3b' not in p.parts]
    paths += list((ROOT / 'docs').glob('*verification.json'))
    guard.write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in paths}, indent=2), encoding='utf-8')


def browser_and_model(real_model=True):
    import torch
    import uvicorn
    from playwright.sync_api import sync_playwright, expect
    from semantic_analyser.api import create_app
    from semantic_analyser.config import Settings
    from semantic_analyser.engine import AnalysisEngine
    from semantic_analyser.fetch_policy import FetchLimits, public_address
    from semantic_analyser.fetch_transport import PinnedConnector, SocketTransport
    from semantic_analyser.safe_fetch import SafeFetcher
    from website_fixtures import routes

    class DNS:
        def resolve(self, *args):
            return ['8.8.8.8']  # Logical public address; connector below maps ONLY to loopback.

    count = 36 if real_model else 3
    all_routes = {host: routes(method, count, realistic=real_model) for host, method in
                  [('wp.example', 'wordpress'), ('map.example', 'sitemap')]}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            host = self.headers['Host']
            assert host in all_routes
            assert not self.headers.get('Cookie') and not self.headers.get('Authorization')
            status, body, headers = all_routes[host].get(self.path, (404, b'', {}))
            # Fixtures advertise the actual test protocol. Do not ask the pinned
            # TLS connector to talk HTTPS to this plaintext loopback HTTP server.
            body = body.replace(b'https://public.example', b'http://' + host.encode())
            self.send_response(status)
            self.send_header('Content-Type', headers.get('content-type', 'text/plain'))
            self.send_header('Content-Length', str(len(body)))
            if 'x-wp-totalpages' in headers:
                self.send_header('X-WP-TotalPages', headers['x-wp-totalpages'])
            self.end_headers()
            self.wfile.write(body)

    fixture = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    fixture.daemon_threads = True
    fixture_thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    fixture_thread.start()

    class LocalConnector(PinnedConnector):
        """Test-only mapping; production retains its public destination/peer policy."""
        def _dial(self, address, port, timeout):
            assert public_address(address) == '8.8.8.8'
            value = socket.socket()
            value.settimeout(timeout)
            value.connect(fixture.server_address)
            return value

        def _verify_peer(self, sock, address):
            assert sock.getpeername()[0] == '127.0.0.1'

    class CountingEngine(AnalysisEngine):
        constructions = 0

        def load(self):
            with self.lock:
                missing = self.model is None
                model = super().load()
                if missing:
                    self.constructions += 1
                return model

    torch.set_num_threads(2)
    if real_model:
        shared = CountingEngine()
    else:
        from conftest import FakeModel
        shared = CountingEngine(model_factory=FakeModel)
    # Only polite delay is removed for controlled fixture speed; all safety/byte/time/run caps stay.
    fetcher = SafeFetcher(FetchLimits(delay_seconds=0), DNS(), SocketTransport(LocalConnector()))
    settings = Settings(database_path=OUT / 'never-open-local.sqlite3', workspace_mode='visitor',
                        visitor_root=OUT / ('visitors-' + str(time.time_ns())), password='', production=False,
                        secret=os.urandom(32).hex(), preload_model=False, website_fetch_enabled=True)
    app = create_app(settings, shared, fetcher)
    app_socket = socket.socket()
    app_socket.bind(('127.0.0.1', 0))
    base = 'http://127.0.0.1:' + str(app_socket.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[app_socket]), daemon=True)
    thread.start()
    result = {'real_model': real_model, 'offline': True, 'public_websites_fetched': False,
              'transport': 'Actual loopback HTTP with mocked DNS/test-only numeric connector',
              'test_delay_seconds': 0, 'browser_errors': []}
    try:
        for _ in range(200):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='chromium', args=['--disable-gpu'])
            a, b = browser.new_context(viewport={'width': 1440, 'height': 1000}), browser.new_context(viewport={'width': 1440, 'height': 1000})
            pa, pb = a.new_page(), b.new_page()
            for page in [pa, pb]:
                page.on('pageerror', lambda error: result['browser_errors'].append(str(error)))
                page.on('dialog', lambda dialog: dialog.accept())
                page.goto(base + '/#collection')
                expect(page.locator('#collection-count')).to_have_text('21 articles in your collection')

            def collection(context):
                return context.request.get(base + '/api/articles').json()

            def post(context, path, data, revision):
                return context.request.post(base + '/api/' + path, data=data,
                    headers={'X-Workspace-Request': 'true', 'If-Match': revision})

            def workflow(page, context, host):
                original = collection(context)
                page.locator('#website-open').click()
                page.locator('#website-url').fill('http://' + host + '/')
                page.locator('#website-form button[type=submit]').click()
                expect(page.locator('.website-candidates input')).to_have_count(count, timeout=30000)
                for checkbox in page.locator('.website-candidates input').all():
                    checkbox.check()
                expect(page.locator('#website-selection-count')).to_have_text(f'{count} selected (maximum 40)')
                page.locator('#website-extract').click()
                try:
                    expect(page.locator('.website-preview')).to_have_count(count, timeout=30000)
                except AssertionError:
                    diagnostic = {'progress': page.locator('#website-progress').inner_text(),
                                  'error': page.locator('#app-error').inner_text(),
                                  'browser_errors': result['browser_errors'],
                                  'run': page.evaluate('websiteRun')}
                    (OUT / 'workflow-failure.json').write_text(json.dumps(diagnostic, indent=2), encoding='utf-8')
                    page.screenshot(path=str(OUT / 'workflow-failure.png'), full_page=True)
                    print(json.dumps({k: diagnostic[k] for k in ['progress', 'error', 'browser_errors']}), flush=True)
                    raise
                expect(page.locator('#app-error')).to_be_hidden()
                assert collection(context) == original  # Preview did not write the collection.
                page.locator('.website-preview').first.locator('summary').click()
                assert not page.evaluate('Boolean(window.evil)')
                page.screenshot(path=str(OUT / (host + '-preview.png')), full_page=True)
                return page.evaluate('websiteRun.run_id'), original['collection_revision']

            aid, ar = workflow(pa, a, 'wp.example')
            br = collection(b)['collection_revision']
            assert post(b, 'website/import', {'run_id': aid}, br).status == 404
            assert post(b, 'website/step', {'run_id': aid}, br).status == 404
            assert post(b, 'website/select', {'run_id': aid, 'ids': ['foreign']}, br).status == 404
            pa.locator('#website-commit').click()
            expect(pa.locator('#collection-count')).to_have_text(f'{count} articles in your collection', timeout=60000)
            expect(pa.locator('#website-dialog')).not_to_be_visible()
            imported = collection(a)
            assert all('POISON' not in x['body'] and 'window.evil' not in x['body'] for x in imported['articles'])
            assert len(collection(b)['articles']) == 21
            begin = time.monotonic()
            response = post(a, 'search', {'query': 'choosing refrigeration equipment for a cafe', 'method': 'compare'}, imported['collection_revision'])
            assert response.status == 200, response.text()
            payload = response.json()
            article_by_id = {x['id']: x for x in imported['articles']}
            for rows in payload['results'].values():
                assert rows
                for row in rows:
                    assert row['passage'] in article_by_id[row['id']]['body']
            result['real_compare_seconds'] = round(time.monotonic() - begin, 3)
            entry = next(e for e in app.state.workspaces.entries.values() if e.engine.cache_key)
            result['real_collection'] = {'articles': count, 'characters': sum(len(x['title']) + len(x['body']) for x in imported['articles']),
                                         'passages': len(entry.engine.chunks), 'embedding_shape': list(entry.engine.embeddings.shape)}
            source = imported['articles'][0]
            links = post(a, 'links', {'source_id': source['id'], 'method': 'compare'}, imported['collection_revision'])
            assert links.status == 200
            for group in links.json()['results'].values():
                assert group['results']
                assert not {r['id'] for r in group['results']} & {source['id'], *source['existing_links']}
                for row in group['results']:
                    assert row['source_passage'] in source['body']
                    assert row['passage'] in article_by_id[row['id']]['body']
            overlap = post(a, 'overlaps', {'method': 'tfidf', 'threshold': 0, 'limit': 3}, imported['collection_revision'])
            assert overlap.status == 200 and overlap.json()['pairs']
            result['wordpress_workflow'] = f'{count} articles: discovery -> selection -> preview -> atomic import -> both-method search/link evidence and overlap'

            workflow(pb, b, 'map.example')
            pb.locator('#website-commit').click()
            expect(pb.locator('#collection-count')).to_have_text(f'{count} articles in your collection', timeout=60000)
            assert all('map.example' in x['url'] for x in collection(b)['articles'])
            assert all('wp.example' in x['url'] for x in collection(a)['articles'])
            result['sitemap_workflow'] = f'{count} articles: REST 404 fallback -> sitemap index -> URL set -> selection -> preview -> import'
            assert shared.constructions == 1

            # Existing CSV interface: invalid replacement leaves all website articles intact.
            pa.locator('#import-collection').click()
            pa.locator('#csv-text').fill('id,title,body\nx,One,first\nx,Two,second')
            pa.locator('#import-form button[type=submit]').click()
            expect(pa.locator('#import-dialog .dialog-error')).to_be_visible()
            assert len(collection(a)['articles']) == count
            pa.locator('#csv-text').fill('id,title,body\nx,Coffee equipment,Plan counter equipment for a small cafe.\ny,Refrigerator layout,Measure display refrigerator ventilation clearance.')
            pa.locator('#import-form button[type=submit]').click()
            expect(pa.locator('#collection-count')).to_have_text('2 articles in your collection', timeout=60000)
            with pa.expect_download() as download:
                pa.get_by_role('link', name='Export CSV', exact=True).click()
            rows = list(csv.DictReader(io.StringIO(Path(download.value.path()).read_text(encoding='utf-8-sig'))))
            assert len(rows) == 2 and {r['id'] for r in rows} == {'x', 'y'}
            result['csv_browser'] = 'Invalid import rollback; valid import and actual CSV download passed'
            pa.set_viewport_size({'width': 390, 'height': 844})
            pa.locator('#website-open').click()
            expect(pa.locator('#website-commit')).to_be_hidden()
            assert pa.evaluate('document.documentElement.scrollWidth <= innerWidth')
            pa.screenshot(path=str(OUT / 'website-mobile.png'), full_page=True)
            result['model_constructions'] = shared.constructions
            result['visitor_contexts'] = 2
            assert not result['browser_errors']
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=20)
        fixture.shutdown()
        fixture.server_close()
        fixture_thread.join(timeout=3)
        app_socket.close()
        assert not thread.is_alive()
    result['servers_stopped'] = True
    return result


def main():
    capture_preservation()
    if '--ui-only' in sys.argv:
        result = browser_and_model(real_model=False)
        result['protected_files_checked'] = preservation()
        (OUT / 'ui-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print('PASS: two browser workflows, reopened dialog, CSV rollback/import/download and mobile layout; deterministic encoder, no MiniLM load')
        return
    # --focused-only is for affected end-to-end checks after a verification failure;
    # it never invents a new full-suite result.
    if '--focused-only' not in sys.argv:
        suite = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                                '--basetemp', str(OUT / 'final-tests')], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        (OUT / 'tests.log').write_text(suite.stdout + suite.stderr, encoding='utf-8')
        print(suite.stdout, flush=True)
        assert suite.returncode == 0, 'See runtime/phase3b/tests.log'
        matched = re.search(r'(\d+) passed(?:, (\d+) skipped)? in ([0-9.]+)s', suite.stdout)
        assert matched
        (OUT / 'suite.json').write_text(json.dumps({'passed': int(matched[1]), 'skipped': int(matched[2] or 0), 'seconds': float(matched[3])}))
    result = {'baseline_commit': 'f93c03b', 'phase': '3B', 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'full_suite': json.loads((OUT / 'suite.json').read_text()), 'focused': browser_and_model(),
              'protected_files_checked': preservation(), 'changed_protected_files': [], 'production_readiness_claimed': False}
    subprocess.run(['node', '--check', 'web/app.js'], cwd=ROOT, check=True)
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
