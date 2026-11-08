"""Display excerpts must remain exact source prefixes, never generated summaries."""
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def run_excerpt_checks(checks):
    source=(ROOT/'web/app.js').read_text(encoding='utf-8')
    helper=re.search(r'function linkExcerpt\(text\) \{.*?^\}',source,re.S|re.M).group()
    result=subprocess.run(['node','-e',helper+'\n'+checks],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_short_excerpts_keep_whitespace_markup_and_citation_markers_exact():
    examples=['', '  Original text.\nSecond line. ', '<img src=x onerror=alert(1)>',
              ':contentReference[oaicite:2]{index=2}', 'Café display — original punctuation.']
    run_excerpt_checks('for(const s of '+json.dumps(examples)+') if(linkExcerpt(s)!==s) throw Error("Original short text changed");')


def test_long_excerpts_are_bounded_source_prefixes_with_full_input_unchanged():
    examples=['An article about café ventilation and counter space. '*30,
              'An article without sentence breaks '*30, 'x'*500,
              'x'*219+'🙂'+' More original context.'*30,
              'Original citation :contentReference[oaicite:2]{index=2} '+'original words '*50]
    run_excerpt_checks('for(const s of '+json.dumps(examples)+'){const original=s;const p=linkExcerpt(s);if(Array.from(p).length>220||!p.isWellFormed()||!s.startsWith(p)||s!==original||!p.length)throw Error("Excerpt is not an exact bounded prefix");}')


def test_excerpts_prefer_complete_sentences_without_filling_missing_context():
    sentence='Measure the counter, service aisle and ventilation clearance before choosing a display cabinet.'
    lead=sentence+' Compare the daily workflow with the available space and check staff access before buying.'
    text=lead+(' Additional context continues without a sentence boundary until much later. '*30)
    run_excerpt_checks('const s='+json.dumps(text)+';const p=linkExcerpt(s);if(p!=='+json.dumps(lead)+')throw Error("Sentence boundary or original context changed");')
