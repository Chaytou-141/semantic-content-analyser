"""Explicitly authorised real-site observation; not an unrestricted crawler.

Uses production SafeFetcher, real DNS/TLS, normal robots and pacing. Raw responses
stay ignored locally; portable evidence contains counts/hashes and observations only.
No model load, database writes, import, external parser or browser request.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from semantic_analyser.execution import Deadline
from semantic_analyser.fetch_policy import FetchError, normalize_url
from semantic_analyser.safe_fetch import SafeFetcher
from semantic_analyser.websites import WebsiteService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--website', required=True)
    parser.add_argument('--method', choices=['auto', 'wordpress', 'sitemap'], default='auto')
    parser.add_argument('--select', type=int, default=0, choices=range(0, 41))
    parser.add_argument('--label', default='initial')
    parser.add_argument('--check-tokenizer', action='store_true')
    args = parser.parse_args()
    target = normalize_url(args.website)
    # User authorisation supplied in this session. Other sites need explicit review.
    if target.host not in {'freezeedge.com.au', 'www.freezeedge.com.au'}:
        parser.error('This evidence run is authorised only for freezeedge.com.au and its www alias.')
    if not args.label.replace('-', '').isalnum():
        parser.error('Use an alphanumeric evidence label.')
    output = ROOT / 'runtime/phase3c' / args.label
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite a prior observation.
    fetcher = SafeFetcher()
    original = fetcher.transport
    trace, observations = [], []
    result = {'website': target.url, 'requested_method': args.method,
              'source_sha256': {name: hashlib.sha256((ROOT / 'semantic_analyser' / name).read_bytes()).hexdigest()
                                for name in ['websites.py', 'extraction.py', 'safe_fetch.py', 'fetch_policy.py']},
              'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'authorisation': 'User supplied this site for Phase 3C evaluation',
              'network': 'Production SafeFetcher, real DNS/pinned sockets/TLS, default robots/pacing/limits',
              'synthetic': False, 'model_loaded': False, 'requests': trace, 'articles': observations}

    def save():
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

    class ObservedTransport:
        def get(self, target, addresses, budget, decoded_limit):
            started = time.monotonic()
            record = {'url': target.url}
            trace.append(record)
            try:
                response = original.get(target, addresses, budget, decoded_limit)
                record.update({'status': response.status, 'headers': response.headers,
                               'decoded_bytes': len(response.body), 'sha256': hashlib.sha256(response.body).hexdigest()})
                (output / f'response-{len(trace):03d}.bin').write_bytes(response.body)
                return response
            except FetchError as error:
                record['error'] = error.code
                raise
            finally:
                record['transport_seconds'] = round(time.monotonic() - started, 3)
                save()

    fetcher.transport = ObservedTransport()
    service = WebsiteService(fetcher)
    run = service.start('phase3c-authorised-observer', 'no-database', target.url, args.method)
    started = time.monotonic()
    try:
        while run.phase == 'discovering':
            service.step(run, Deadline(25))
        result['discovery_seconds'] = round(time.monotonic() - started, 3)
        result['candidates'] = list(run.candidates.values())
        result['discovered_count'] = len(run.candidates)
        if args.select and run.candidates:
            chosen = list(run.candidates)[:args.select]
            result['selected_count'] = len(chosen)
            service.select(run, chosen)
            extraction_start = time.monotonic()
            while run.phase == 'extracting':
                before = len(run.extracted)
                service.step(run, Deadline(25))
                for item in run.extracted[before:]:
                    record = {'candidate_id': item['candidate_id'], 'source_url': item['source_url'],
                              'canonical_url': item['url'], 'title': item['title'], 'headings': item['headings'],
                              'body_characters': len(item['body']), 'words': len(item['body'].split()),
                              'internal_link_count': len(item['links']), 'body_sha256': hashlib.sha256(item['body'].encode()).hexdigest()}
                    observations.append(record)
                    (output / (item['candidate_id'] + '.txt')).write_text(item['body'], encoding='utf-8')
                save()
            result['extraction_seconds'] = round(time.monotonic() - extraction_start, 3)
            result['prepared_count'] = len(run.articles)
            result['prepared_characters'] = sum(len(a.title) + len(a.body) for a in run.articles)
            (output / 'prepared.json').write_text(json.dumps([a.model_dump() for a in run.articles]), encoding='utf-8')
            if args.check_tokenizer and run.articles:
                # Admission needs the exact tokenizer, not model inference/weights.
                os.environ['HF_HUB_OFFLINE'] = '1'
                os.environ['TRANSFORMERS_OFFLINE'] = '1'
                from transformers import AutoTokenizer
                from semantic_analyser.config import MODEL_REVISION
                from semantic_analyser.engine import AnalysisEngine
                begin = time.monotonic()
                tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2',
                                                         revision=MODEL_REVISION, local_files_only=True)
                wrapper = type('TokenizerOnly', (), {'tokenizer': tokenizer})()
                engine = AnalysisEngine(model_factory=lambda: wrapper)
                result['tokenizer_capacity'] = engine.preflight(run.articles)
                result['tokenizer_capacity_seconds'] = round(time.monotonic() - begin, 3)
                result['tokenizer_only_no_model_weights'] = True
    except (FetchError, ValueError) as error:
        result['failure'] = {'code': error.code if isinstance(error, FetchError) else 'validation', 'message': str(error)}
    finally:
        result.update({'phase': run.phase, 'wall_seconds': round(time.monotonic() - started, 3),
                       'requests_used': run.session.requests, 'wire_bytes': run.session.wire_bytes,
                       'decoded_bytes': run.session.decoded_bytes, 'warnings': run.warnings,
                       'active_fetch_seconds': round(run.session.active_seconds, 3),
                       'extraction_failures': run.failures})
        save()
        print(json.dumps({k: v for k, v in result.items() if k not in {'requests', 'articles', 'candidates'}}, indent=2))


if __name__ == '__main__':
    main()
