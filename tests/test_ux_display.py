"""Protect limits and display-only source cleanup without inference or public fetching."""
import json
from pathlib import Path
import re
import subprocess

from semantic_analyser.engine import MAX_PASSAGES
from semantic_analyser.schemas import Article
from semantic_analyser.storage import MAX_ARTICLES, MAX_TOTAL_CHARACTERS
from semantic_analyser.websites import MAX_SELECTED
from semantic_analyser.extraction import extract
from website_fixtures import article

ROOT=Path(__file__).resolve().parents[1]


def test_ui_resource_values_match_authoritative_admission_limits():
    source=(ROOT/'web/app.js').read_text(encoding='utf-8')
    block=re.search(r'const LIMITS = Object.freeze\(\{(.*?)\}\)',source)[1]
    values={k:int(v) for k,v in re.findall(r'(\w+): (\d+)',block)}
    assert values==dict(characters=MAX_TOTAL_CHARACTERS,articles=MAX_ARTICLES,
                       body=Article.model_json_schema()['properties']['body']['maxLength'],
                       passages=MAX_PASSAGES,selected=MAX_SELECTED)


def test_display_cleanup_is_exact_and_never_changes_original_argument():
    source=(ROOT/'web/app.js').read_text(encoding='utf-8')
    function=next(line for line in source.splitlines() if line.startswith('function displayText('))
    cases=[['before :contentReference[oaicite:2]{index=2} after','before  after'],
           ['contentReference[oaicite:12]{index=1}',''],
           ['contentReference[other:2]{index=2}','contentReference[other:2]{index=2}'],
           ['keepcontentReference[oaicite:2]{index=2}','keepcontentReference[oaicite:2]{index=2}']]
    code=function+'\nconst cases='+json.dumps(cases)+'; for (const [input,expected] of cases) { const saved=input; if(displayText(input)!==expected || input!==saved) throw Error("display cleanup changed meaning or input"); }'
    result=subprocess.run(['node','-e',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_extractor_retains_source_marker_for_evidence_offsets():
    marker=':contentReference[oaicite:2]{index=2}'
    html=article(1).replace(b'</p>',(' '+marker+'</p>').encode(),1)
    extracted=extract(html,'https://public.example/posts/1')
    assert marker in extracted['body']
