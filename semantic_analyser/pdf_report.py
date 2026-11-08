"""Feature-specific, bounded PDFs from revision-scoped server snapshots."""
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, KeepTogether, Spacer

MAX_ITEMS = 10
MAX_EVIDENCE = 180
MAX_BYTES = 2_000_000
TITLES = {'search': 'Related Content', 'links': 'Internal-Link Opportunities', 'overlaps': 'Content Overlap'}
METHODS = {'embeddings': 'Semantic similarity (MiniLM)', 'tfidf': 'Keyword similarity (TF-IDF)'}
FONT = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('ReportVera', str(FONT / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('ReportVeraBold', str(FONT / 'VeraBd.ttf')))


def build_report(articles, section, snapshot, reviews, check=lambda: None):
    if section not in TITLES or not snapshot:
        raise ValueError('Run the selected analysis before exporting.')
    check()
    output = BytesIO()
    purple = colors.HexColor('#44334f')
    lavender = colors.HexColor('#f3eff8')
    styles = {
        'body': ParagraphStyle('body', fontName='ReportVera', fontSize=9, leading=12, spaceAfter=6, splitLongWords=True),
        'small': ParagraphStyle('small', fontName='ReportVera', fontSize=8, leading=11, textColor=colors.HexColor('#65586f'), spaceAfter=5, splitLongWords=True),
        'heading': ParagraphStyle('heading', fontName='ReportVeraBold', fontSize=13, leading=18, textColor=purple, spaceBefore=13, spaceAfter=8, keepWithNext=True),
        'title': ParagraphStyle('title', fontName='ReportVeraBold', fontSize=24, leading=30, textColor=purple, spaceAfter=12),
        'label': ParagraphStyle('label', fontName='ReportVeraBold', fontSize=10, leading=13, textColor=purple, spaceAfter=4, splitLongWords=True),
    }
    def clean(value):
        return ''.join(c for c in str(value) if ord(c) >= 32 or c in '\n\t')
    def para(value, kind='body'):
        return Paragraph(escape(clean(value)), styles[kind])
    def shortened(value, limit):
        value=clean(value)
        return value if len(value)<=limit else value[:limit]+'... [shortened]'
    def article_cell(title, url, passage, label):
        cell=[para(label, 'small'), para(title, 'label')]
        if url and urlsplit(url).scheme in ('http','https'):
            cell.append(Paragraph('<link color="#604577" href="'+escape(url,quote=True)+'">'+escape(shortened(url,130))+'</link>', styles['small']))
        else:
            cell.append(para('No article URL recorded', 'small'))
        cell.append(para(shortened(passage,MAX_EVIDENCE)))
        return cell
    params, payload = snapshot['parameters'], snapshot['payload']
    by_id={a.id:a for a in articles}
    domains=sorted({urlsplit(a.url).hostname for a in articles if a.url and urlsplit(a.url).hostname})
    identity=domains[0] if len(domains)==1 else 'Current article collection'
    story=[para(TITLES[section], 'title'),para(identity,'label'),
           para('Generated '+datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')+f' | {len(articles)} articles in collection','small')]
    if len(domains)>1:
        story.append(para(f'Mixed collection from {len(domains)} website hosts.','small'))
    if section=='overlaps':
        groups={params['method']:payload['pairs']}
        story.append(para('Potential semantic overlap for editorial review. A high score does not prove duplication or justify merging content.'))
        settings=f"Minimum cosine similarity: {params.get('threshold',0):g} | Requested pair limit: {params.get('limit',len(payload['pairs']))}"
    else:
        groups={m:v['results'] if section=='links' else v for m,v in payload['results'].items()}
        settings=f"Requested results per method: {params.get('top_k',5)} | Minimum cosine similarity: {params.get('min_score',0):g}"
        if section=='search':
            story.append(para('Search question: '+shortened(params['query'],500),'label'))
            story.append(para('Query-dependent results: these scores compare passages with your question, not with each other.'))
        else:
            story.append(para('Source article: '+by_id[params['source_id']].title,'label'))
            story.append(para('Candidate destinations, not approved recommendations. Existing links and ineligible destinations were excluded.'))
    story.append(para(settings,'small'))
    for method,rows in groups.items():
        check()
        total=payload.get('returned_count',len(rows)) if section=='overlaps' else len(rows)
        story.extend([para(METHODS[method],'heading'),para(f'Showing {min(len(rows),MAX_ITEMS)} of {total} returned candidates.','small')])
        if total>MAX_ITEMS:
            story.append(para(f'Report truncated: first {MAX_ITEMS} candidates per method only.','small'))
        if not rows:
            story.append(para('No results returned for these settings. This is not proof that no relevant relationships exist.'))
        for rank,row in enumerate(rows[:MAX_ITEMS],1):
            check()
            score=para(f'{rank}. Cosine similarity: {row["score"]:.5f}','label')
            if section=='search':
                cells=[article_cell(row['title'],row.get('url',''),row.get('passage',''),'Matching article')]
                data=[[score],[cells[0]]]; widths=[505]
            else:
                if section=='links':
                    src=by_id[params['source_id']]
                    left=article_cell(src.title,src.url,row['source_passage'],'Source · link from')
                    right=article_cell(row['title'],row.get('url',''),row.get('passage',''),'Destination · link to')
                    relation='Suggested link: source -> destination'
                else:
                    a,b=row['left'],row['right']
                    left=article_cell(a['title'],a.get('url',''),a.get('passage',''),'Article A')
                    right=article_cell(b['title'],b.get('url',''),b.get('passage',''),'Article B')
                    relation='Article A <-> Article B | Potential semantic overlap'
                data=[[score,''],[para(relation,'small'),''],[left,right]]; widths=[252.5,252.5]
            if section=='links':
                review=next((r for r in reviews if r['source_id']==src.id and r['target_id']==row['id']),None)
                decision={'useful':'Useful','not_useful':'Not useful','pending':'Pending review'}
                status=decision.get(review['decision'],'Unreviewed') if review else 'Unreviewed'
                note='Editorial status: '+status
                if review and review.get('note'): note+=' | Note: '+shortened(review['note'],240)
                data.append([para(note,'small'),''])
            table=Table(data,colWidths=widths,hAlign='LEFT')
            commands=[('BACKGROUND',(0,0),(-1,0),lavender),('BOX',(0,0),(-1,-1),0.6,colors.HexColor('#ded6e6')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4)]
            if section!='search':
                commands.extend([('SPAN',(0,0),(-1,0)),('SPAN',(0,1),(-1,1))])
                if section=='links': commands.append(('SPAN',(0,3),(-1,3)))
            table.setStyle(TableStyle(commands))
            story.append(KeepTogether([table,Spacer(1,12)]))
    story.extend([para('How to read this report','heading'),para(
        'MiniLM compares meaning using passage embeddings; TF-IDF compares weighted words. Cosine similarity is a ranking signal, '
        'not accuracy, editorial confidence or a percentage of duplicate text. Generic wording can produce strong matches. '
        'Check reader intent and original context before acting. No links are inserted or pages merged.','small'),para(
        f'This report covers only the latest completed {TITLES[section].lower()} analysis, not a full website audit. '
        'Saved link reviews are read at export time. Up to 10 candidates per method; original evidence excerpts are capped at 180 characters. '
        'Shortened text and displayed URLs are labelled; URL links retain their complete destinations.','small')])
    def page(canvas,doc):
        check()
        canvas.setFillColor(lavender);canvas.rect(0,A4[1]-26,A4[0],26,fill=1,stroke=0)
        canvas.setFont('ReportVera',8);canvas.setFillColor(purple)
        canvas.drawString(45,A4[1]-17,'SEMANTIC CONTENT ANALYSER')
        canvas.drawString(45,24,'Editorial review required')
        canvas.drawRightString(A4[0]-45,24,f'Page {doc.page}')
    SimpleDocTemplate(output,pagesize=A4,leftMargin=45,rightMargin=45,topMargin=44,bottomMargin=44,
                      title=TITLES[section],author='Semantic Content Analyser').build(story,onFirstPage=page,onLaterPages=page)
    result=output.getvalue()
    if len(result)>MAX_BYTES:
        raise ValueError('The PDF exceeds the 2 MB report limit. Reduce result counts and try again.')
    return result
