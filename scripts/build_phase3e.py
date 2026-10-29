"""Build an offline independent-review packet from saved Phase 3D evidence only."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def script_json(value):
    return json.dumps(value,ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')


def build(root=ROOT):
    manifest_path=root/'evaluations/phase3d/editorial-review-set.json'
    raw_path=root/'runtime/phase3d/analysis-results.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    raw=json.loads(raw_path.read_text(encoding='utf-8'))
    corpus=root/manifest['source_path']
    if digest(corpus)!=manifest['source_sha256'] or digest(manifest_path)!=raw['review_set_sha256'] or raw['input_sha256']!=manifest['source_sha256']:
        raise ValueError('Frozen Phase 3D corpus/label/evidence fingerprints differ; no refetch fallback.')
    articles={a['id']:a for a in json.loads(corpus.read_text(encoding='utf-8'))}
    for a in manifest['articles']:
        if hashlib.sha256(articles[a['id']]['body'].encode()).hexdigest()!=a['body_sha256']:
            raise ValueError('Saved article body differs from frozen review set.')
    packet_id=hashlib.sha256((digest(raw_path)+digest(manifest_path)+digest(corpus)).encode()).hexdigest()
    registry={'schema_version':1,'packet_id':packet_id,'source_commit':'771c4cb',
              'input_sha256':digest(corpus),'ranking_evidence_sha256':digest(raw_path),
              'provisional_manifest_sha256':digest(manifest_path),'items':[],'cases':[]}
    items=[]
    def checked(row):
        if row['passage']!=articles[row['id']]['body'][row['passage_start']:row['passage_end']]:
            raise ValueError('A cached supporting passage does not match its saved article.')
        return row['passage']
    for case in manifest['cases']:
        judgements={j['article_id']:j for j in case['judgements']}
        rankings=raw['rankings'][case['id']]
        registry['cases'].append({'id':case['id'],'kind':case['kind'],
                                  'rankings':{m:[r['id'] for r in rows] for m,rows in rankings.items()}})
        ids=sorted({r['id'] for rows in rankings.values() for r in rows})
        for aid in ids:
            meta={'item_id':f'C-{case["id"]}-{aid}','item_type':'candidate','case_id':case['id'],
                  'source_id':case['source_id'] or '', 'target_id':aid}
            evidence=[]
            for method,rows in rankings.items():
                for rank,row in enumerate(rows,1):
                    if row['id']!=aid:
                        continue
                    source_text=None
                    if case['source_id']:
                        source=articles[case['source_id']]
                        source_text=row['source_passage']
                        if source_text!=source['body'][row['source_start']:row['source_end']]:
                            raise ValueError('Cached source passage differs.')
                    evidence.append({'method':method,'rank':rank,'score':row['score'],
                                     'source_passage':source_text,'target_passage':checked(row)})
            label=judgements[aid]
            items.append({**meta,'kind':case['kind'],'question':case['query'],'criterion':case['criterion'],
                          'existing_link':aid in articles[case['source_id']]['existing_links'] if case['source_id'] else None,
                          'evidence':evidence,'ai_notes':[{'label':'Relevant' if label['relevant'] else 'Not relevant',
                            'rationale':label['rationale'],'provenance':'Frozen assistant-provisional label; not a human decision'}]})
            registry['items'].append(meta)
    notes=json.loads((root/'evaluations/phase3d/review-notes.json').read_text(encoding='utf-8'))
    pairs=sorted({tuple(sorted([p['left']['id'],p['right']['id']])) for rows in raw['overlaps'].values() for p in rows})
    for index,(left,right) in enumerate(pairs,1):
        meta={'item_id':f'O{index:02}','item_type':'overlap','case_id':'OVERLAP','source_id':left,'target_id':right}
        evidence=[]
        for method,rows in raw['overlaps'].items():
            for rank,pair in enumerate(rows,1):
                if {pair['left']['id'],pair['right']['id']}!={left,right}:
                    continue
                a,b=(pair['left'],pair['right']) if pair['left']['id']==left else (pair['right'],pair['left'])
                evidence.append({'method':method,'rank':rank,'score':pair['score'],
                                 'source_passage':checked(a),'target_passage':checked(b)})
        ai=[]
        for pair in manifest['overlap_judgements']:
            if {pair['left'],pair['right']}=={left,right}:
                ai.append({'label':pair['judgement'].replace('_',' '),'rationale':pair['rationale'],
                           'provenance':'Assistant-provisional relationship fixed before ranking inspection'})
        for pair in notes['overlap_examples']:
            if {pair['left_id'],pair['right_id']}=={left,right}:
                ai.append({'label':'Exploratory AI interpretation','rationale':pair['interpretation'],
                           'provenance':'Assistant note written after inspecting scores; not an independent label'})
        items.append({**meta,'kind':'overlap','question':'Is this a useful pair to investigate for substantive content overlap?',
                      'criterion':'Shared topic or promotional wording alone is insufficient. Useful means worth investigating, not permission to merge or delete.',
                      'existing_link':right in articles[left]['existing_links'],
                      'reverse_existing_link':left in articles[right]['existing_links'],'evidence':evidence,'ai_notes':ai})
        registry['items'].append(meta)
    pair_ids={tuple(sorted([i['source_id'],i['target_id']])):i['item_id'] for i in registry['items'] if i['item_type']=='overlap'}
    registry['overlap_rankings']={m:[pair_ids[tuple(sorted([p['left']['id'],p['right']['id']]))] for p in rows]
                                 for m,rows in raw['overlaps'].items()}
    if len(items)!=59 or sum(i['item_type']=='candidate' for i in items)!=44:
        raise ValueError('Expected the original 44 candidates and 15 overlap pairs.')
    return registry,{'registry':registry,'articles':articles,'items':items}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/phase3e/independent-review.html')
    parser.add_argument('--overwrite',action='store_true')
    args=parser.parse_args()
    try:
        registry,payload=build()
        assets=ROOT/'evaluations/phase3e'
        js=(assets/'reviewer.js').read_text(encoding='utf-8')
        css=(assets/'reviewer.css').read_text(encoding='utf-8')
        template=(assets/'reviewer.html').read_text(encoding='utf-8')
        signature=base64.b64encode(hashlib.sha256(js.encode()).digest()).decode()
        content=template.replace('@@STYLE@@',css).replace('@@SCRIPT_HASH@@',signature).replace('@@DATA@@',script_json(payload)).replace('@@SCRIPT@@',js)
        registry_path=assets/'packet-registry.json'
        if registry_path.exists() and json.loads(registry_path.read_text(encoding='utf-8'))!=registry:
            raise ValueError('Existing registry differs. Preserve/version the review round rather than overwriting it.')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('w' if args.overwrite else 'x',encoding='utf-8') as file:
            file.write(content)
        if not registry_path.exists():
            registry_path.write_text(json.dumps(registry,indent=2)+'\n',encoding='utf-8')
        print(f'Built {len(payload["items"])} unreviewed items: {args.output}')
    except (OSError,ValueError,KeyError) as error:
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':
    main()
