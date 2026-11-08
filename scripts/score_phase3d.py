"""Recompute editorial metrics/portable evidence from cached rankings; no model load."""
import csv
import hashlib
import json
from pathlib import Path

from phase3d_metrics import summarize_case

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/phase3d'


def main():
    manifest_path=ROOT/'evaluations/phase3d/editorial-review-set.json'
    labels=json.loads(manifest_path.read_text(encoding='utf-8'))
    raw=json.loads((OUT/'analysis-results.json').read_text(encoding='utf-8'))
    assert raw['review_set_sha256']==hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert raw['input_sha256']==labels['source_sha256']
    portable={k:v for k,v in raw.items() if k not in {'rankings','overlaps','case_metrics','database'}}
    portable['cases']=[]
    blank=[]
    for case in labels['cases']:
        results={}
        union=set()
        for method,rows in raw['rankings'][case['id']].items():
            union.update(row['id'] for row in rows)
            results[method]={'metrics':summarize_case([r['id'] for r in rows],case['judgements']),
                             'ranking':[{'id':r['id'],'score':r['score'],'passage_start':r['passage_start'],
                                         'passage_end':r['passage_end'],'passage_sha256':hashlib.sha256(r['passage'].encode()).hexdigest()}
                                        for r in rows]}
        portable['cases'].append({'id':case['id'],'kind':case['kind'],'results':results,
                                 'relevant_label_count':sum(j['relevant'] for j in case['judgements'])})
        blank.extend([case['id'],aid,'','',''] for aid in sorted(union))
    with (ROOT/'evaluations/phase3d/top5-independent-review-template.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['case_id','article_id','relevant_yes_no','reviewer','rationale']);writer.writerows(blank)
    portable['top5_union_judgements_to_review']=len(blank)
    portable['macro_provisional']={}
    for kind in ['related','internal_link']:
        portable['macro_provisional'][kind]={}
        for method in ['embeddings','tfidf']:
            portable['macro_provisional'][kind][method]={}
            for k in [3,5]:
                values=[c['results'][method]['metrics']['provisional'][f'precision@{k}']['value']
                        for c in portable['cases'] if c['kind']==kind]
                assert all(v is not None for v in values)
                portable['macro_provisional'][kind][method][f'precision@{k}']=sum(values)/len(values)
    portable['overlap_rankings']={method:[{'left':pair['left']['id'],'right':pair['right']['id'],'score':pair['score'],
                                         'left_passage_sha256':hashlib.sha256(pair['left']['passage'].encode()).hexdigest(),
                                         'right_passage_sha256':hashlib.sha256(pair['right']['passage'].encode()).hexdigest()}
                                        for pair in rows] for method,rows in raw['overlaps'].items()}
    audit=json.loads((OUT/'extraction-audit.json').read_text(encoding='utf-8'))
    portable['extraction_audit']=[{k:v for k,v in a.items() if k!='source_plain'} for a in audit]
    (ROOT/'evaluations/phase3d/results.json').write_text(json.dumps(portable,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'macro_provisional':portable['macro_provisional'],'top5_review_rows':len(blank)},indent=2))


if __name__=='__main__':
    main()
