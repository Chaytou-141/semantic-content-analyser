"""Offline real-content editorial evaluation on a disposable SQLite collection.

Frozen input/labels are checked before loading one local MiniLM. Raw text, scored
passages and the human review packet stay ignored under runtime/phase3d.
"""
import csv
import hashlib
import html
import json
import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime/phase3d'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'2',
                   'MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false',
                   'DATABASE_PATH':str(OUT/'bootstrap.sqlite3'),'WORKSPACE_MODE':'local','PRELOAD_MODEL':'false'})

from phase3d_extraction_audit import audit_article
from phase3d_metrics import summarize_case


def packet(rows, audits, cases, rankings, overlaps=None):
    esc = lambda value: html.escape(str(value))
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>Phase 3D editorial review</title>',
             '<style>body{font:16px/1.65 system-ui;margin:35px auto;max-width:1150px;padding:0 20px;color:#302837}h1,h2{line-height:1.3}details{border:1px solid #ddd;padding:15px;margin:15px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:15px/1.8 Georgia}section{margin:35px 0}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:25px}small{display:block} @media(max-width:700px){.comparison{grid-template-columns:1fr}}</style>',
             '<h1>Freeze Edge editorial review</h1><p>Saved real pages only; no live links, scripts or resources. Review the task criteria and source examples before opening model rankings. Fill independent-review-template.csv with your own yes/no decisions and reasons. Assistant labels are provisional and are not shown here as truth.</p><h2>Tasks</h2>']
    by_id = {a['id']:a for a in rows}
    for case in cases:
        source = by_id.get(case.get('source_id'))
        parts.append('<p><strong>'+esc(case['id'])+'</strong> '+esc(case['query'] or ('Links from '+source['title']))+'<br>'+esc(case['criterion'])+'</p>')
    parts.append('<h2>Blind source and extraction examples</h2><p>The left column is an independent parser’s entry-content text. The right is the saved collection body; review template removals and structural changes before calling them errors.</p>')
    for row,audit in zip(rows,audits):
        parts.append('<details><summary>'+esc(row['id']+' — '+row['title'])+'</summary><small>'+esc(row['url'])+'</small><p>'+esc({k:v for k,v in audit.items() if k not in {'source_plain','id','url'}})+'</p><div class="comparison"><section><h3>Source body text</h3><pre>'+esc(audit['source_plain'])+'</pre></section><section><h3>Saved extracted text</h3><pre>'+esc(row['body'])+'</pre></section></div></details>')
    parts.append('<h2>Model suggestions: open after independent review</h2>')
    for case in cases:
        parts.append('<details><summary>'+esc(case['id'])+' ranked suggestions and exact passage evidence</summary>')
        for method in ['embeddings','tfidf']:
            parts.append('<h3>'+esc(method)+'</h3>')
            for rank,item in enumerate(rankings[case['id']][method],1):
                parts.append('<details><summary>'+esc(f"{rank}. {item['title']} ({item['score']})")+'</summary><small>'+esc(item['id'])+'</small><pre>'+esc(item.get('source_passage',''))+'</pre><pre>'+esc(item['passage'])+'</pre></details>')
        parts.append('</details>')
    parts.append('<h2>Overlap evidence: shared passages do not establish whole-article duplication</h2>')
    for method,pairs in (overlaps or {}).items():
        parts.append('<details><summary>'+esc(method)+' overlap suggestions</summary>')
        for pair in pairs:
            parts.append('<details><summary>'+esc(pair['left']['title']+' / '+pair['right']['title']+' — '+str(pair['score']))+'</summary><div class="comparison"><pre>'+esc(pair['left']['passage'])+'</pre><pre>'+esc(pair['right']['passage'])+'</pre></div></details>')
        parts.append('</details>')
    parts.append('</html>')
    (OUT/'editorial-review.html').write_text(''.join(parts),encoding='utf-8')


def main():
    review_path=ROOT/'evaluations/phase3d/editorial-review-set.json'
    review=json.loads(review_path.read_text(encoding='utf-8'))
    source=ROOT/review['source_path']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==review['source_sha256'],'Frozen input changed'
    rows=json.loads(source.read_text(encoding='utf-8'))
    assert 1<=len(rows)<=30
    assert {a['id'] for a in rows}=={a['id'] for a in review['articles']}
    for row,meta in zip(rows,review['articles']):
        assert row['id']==meta['id'] and hashlib.sha256(row['body'].encode()).hexdigest()==meta['body_sha256']
    for case in review['cases']:
        assert {j['article_id'] for j in case['judgements']}=={a['id'] for a in rows}
    prior=json.loads((ROOT/'runtime/phase3c/corrected30/result.json').read_text())
    pages={r['url']:ROOT/f'runtime/phase3c/corrected30/response-{i:03d}.bin' for i,r in enumerate(prior['requests'],1)}
    heads={a['candidate_id']:a['headings'] for a in prior['articles']}
    selected={a['url']:a['id'] for a in rows}
    audits=[audit_article(a,pages[a['url']].read_bytes(),heads[a['id']],selected) for a in rows]
    (OUT/'extraction-audit.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')

    network_attempts=[]
    def blocked(*args,**kwargs):
        network_attempts.append('blocked')
        raise RuntimeError('Phase 3D is offline; no network calls permitted.')
    old_connect,old_dns=socket.socket.connect,socket.getaddrinfo
    socket.socket.connect,socket.getaddrinfo=blocked,blocked
    try:
        import torch
        from sentence_transformers import SentenceTransformer
        from semantic_analyser.config import MODEL_REVISION
        from semantic_analyser.engine import AnalysisEngine
        from semantic_analyser.collections import CollectionService
        from semantic_analyser.storage import Store
        torch.set_num_threads(2)
        constructions=[]
        def factory():
            constructions.append(1)
            model=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',revision=MODEL_REVISION,device='cpu',local_files_only=True)
            model.eval()
            return model
        engine=AnalysisEngine(model_factory=factory)
        database=OUT/('disposable-'+str(time.time_ns())+'.sqlite3')
        store=Store(database)
        started=time.perf_counter();cpu=time.process_time()
        count=CollectionService(store,engine).replace(rows)
        admitted=time.perf_counter()-started
        articles=store.articles();by_id={a.id:a for a in articles}
        rankings,metrics={},{}
        for case in review['cases']:
            rankings[case['id']],metrics[case['id']]={},{}
            for method in ['embeddings','tfidf']:
                results=(engine.search(articles,case['query'],method,5,0) if case['kind']=='related' else
                         engine.links(articles,case['source_id'],method,5,0)['results'])
                rankings[case['id']][method]=results
                metrics[case['id']][method]=summarize_case([a['id'] for a in results],case['judgements'])
        overlaps={m:engine.overlaps(articles,m,0,10) for m in ['embeddings','tfidf']}
        evidence_checks=0
        def evidence(item):
            nonlocal evidence_checks
            assert item['passage']==by_id[item['id']].body[item['passage_start']:item['passage_end']]
            evidence_checks+=1
        for case in review['cases']:
            for method,results in rankings[case['id']].items():
                for item in results:
                    evidence(item)
                    if case['kind']=='internal_link':
                        src=by_id[case['source_id']]
                        assert item['source_passage']==src.body[item['source_start']:item['source_end']]
                        assert item['id'] not in {src.id,*src.existing_links}
                        evidence_checks+=1
        for items in overlaps.values():
            for pair in items:
                evidence(pair['left']);evidence(pair['right'])
        result={'baseline_commit':'34b613d','input_sha256':review['source_sha256'],
                'review_set_sha256':hashlib.sha256(review_path.read_bytes()).hexdigest(),
                'articles':count,'characters':sum(len(a.title)+len(a.body) for a in articles),'passages':len(engine.chunks),
                'embedding_shape':list(engine.embeddings.shape),'model_constructions':len(constructions),
                'model_revision':MODEL_REVISION,'admission_wall_seconds':round(admitted,3),
                'analysis_wall_seconds':round(time.perf_counter()-started,3),'process_cpu_seconds':round(time.process_time()-cpu,3),
                'network_attempts':len(network_attempts),'exact_evidence_checks':evidence_checks,
                'case_metrics':metrics,'rankings':rankings,'overlaps':overlaps,
                'database':str(database.relative_to(ROOT)),'independently_reviewed_judgements':0,
                'metric_scope':'Assistant provisional development judgements; single-site sample; not held out or independent.'}
        assert len(constructions)==1 and not network_attempts
        (OUT/'analysis-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        packet(rows,audits,review['cases'],rankings,overlaps)
        print(json.dumps({k:v for k,v in result.items() if k not in {'rankings','overlaps','case_metrics','database'}},indent=2))
    finally:
        socket.socket.connect,socket.getaddrinfo=old_connect,old_dns


if __name__=='__main__':
    main()
