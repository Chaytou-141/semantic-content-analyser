"""Bounded, in-memory PDF from server-generated, revision-scoped results only."""
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
from reportlab.platypus import SimpleDocTemplate, Paragraph

MAX_ITEMS = 10  # per method; at most two methods per section
MAX_EVIDENCE = 600
MAX_BYTES = 2_000_000
FONT = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('ReportVera', str(FONT / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('ReportVeraBold', str(FONT / 'VeraBd.ttf')))


def build_report(articles, snapshots, reviews, check=lambda: None):
    output = BytesIO()
    purple = colors.HexColor('#44334f')
    styles = {
        'body': ParagraphStyle('body', fontName='ReportVera', fontSize=9, leading=14, spaceAfter=7, splitLongWords=True),
        'heading': ParagraphStyle('heading', fontName='ReportVeraBold', fontSize=17, leading=23, textColor=purple, spaceBefore=17, spaceAfter=10, keepWithNext=True),
        'title': ParagraphStyle('title', fontName='ReportVeraBold', fontSize=26, leading=32, textColor=purple, spaceAfter=18),
        'label': ParagraphStyle('label', fontName='ReportVeraBold', fontSize=10, leading=15, textColor=purple, spaceBefore=10, spaceAfter=6, keepWithNext=True),
    }
    story = []
    def text(value, kind='body'):
        # ReportLab markup must never interpret imported content.
        value = ''.join(c for c in str(value) if ord(c) >= 32 or c in '\n\t')
        story.append(Paragraph(escape(value).replace('\n', '<br/>'), styles[kind]))
    def url(value):
        if value and urlsplit(value).scheme in ('https', 'http'):
            story.append(Paragraph('<link href="' + escape(value, quote=True) + '">' + escape(value) + '</link>', styles['body']))
    def item(row, label='Article'):
        text(f'{label}: {row["title"]} [{row["id"]}]', 'label')
        url(row.get('url', ''))
        passage = row.get('passage', '')
        text('Evidence: ' + passage[:MAX_EVIDENCE])
        if len(passage) > MAX_EVIDENCE:
            text('[Excerpt shortened to 600 characters; original evidence remains in the application.]')
        if 'passage_start' in row:
            text(f'Saved passage offsets: {row["passage_start"]}-{row["passage_end"]}.')
    by_id = {a.id: a for a in articles}
    domains = sorted({urlsplit(a.url).hostname for a in articles if a.url and urlsplit(a.url).hostname})
    text('Website Content Analysis', 'title')
    text(domains[0] if len(domains) == 1 else 'Current article collection', 'heading')
    if len(domains) > 1:
        text(f'Mixed-source collection: {len(domains)} website hosts.')
    text('Generated: ' + datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC'))
    text(f'Articles in this collection: {len(articles)}')
    text('Snapshot report of the latest completed analysis in each section for this collection. '
         'Results depend on the query, source, method and filters shown below. This is not an exhaustive website audit.')
    text('Summary', 'heading')
    text(f'{len(snapshots)} of 3 analysis sections available for the current collection. '
         'Counts below describe returned results, not independently verified recommendations.')
    for section, title in [('search', 'Related content'), ('links', 'Internal-link opportunities'), ('overlaps', 'Content overlap')]:
        check()
        snap = snapshots.get(section)
        text(title, 'heading')
        if not snap:
            text('Unavailable: analysis not run for the current collection. Run this section in the application and export again.')
            continue
        params, payload = snap['parameters'], snap['payload']
        text('Settings: ' + '; '.join(f'{k}={v}' for k, v in params.items()))
        if section == 'search':
            text('Query-dependent results; similarity is to the search query, not an article-to-article score.')
        if section == 'overlaps':
            groups = {params['method']: payload['pairs']}
            text('Potential overlap only. Similarity does not confirm duplicate content, identical intent or merge eligibility.')
        else:
            groups = {m: (v['results'] if section == 'links' else v) for m, v in payload['results'].items()}
        for method, rows in groups.items():
            check()
            total = payload.get('returned_count', len(rows)) if section == 'overlaps' else len(rows)
            text(f'{method}: showing {min(len(rows), MAX_ITEMS)} of {total} returned results', 'label')
            if not rows:
                text('No results returned for these settings. This does not establish that no relevant relationships exist.')
            if total > MAX_ITEMS:
                text(f'Report truncated: only the first {MAX_ITEMS} returned items per method are included.')
            for rank, row in enumerate(rows[:MAX_ITEMS], 1):
                check()
                text(f'{rank}. Cosine similarity: {row["score"]:.5f}', 'label')
                if section == 'overlaps':
                    item(row['left'], 'First article')
                    item(row['right'], 'Second article')
                elif section == 'links':
                    source = by_id[params['source_id']]
                    text(f'Source: {source.title} [{source.id}]', 'label')
                    url(source.url)
                    text('Source evidence: ' + row['source_passage'][:MAX_EVIDENCE])
                    if len(row['source_passage']) > MAX_EVIDENCE:
                        text('[Source excerpt shortened to 600 characters.]')
                    text(f'Source offsets: {row["source_start"]}-{row["source_end"]}.')
                    item(row, 'Suggested destination')
                    review = next((r for r in reviews if r['source_id'] == source.id and r['target_id'] == row['id']), None)
                    text('Saved editorial status: ' + (review['decision'] if review else 'unreviewed'))
                    if review and review.get('note'):
                        text('Editorial note: ' + review['note'])
                    text('Existing links and ineligible destinations were excluded by the analysis engine. Review before inserting any link.')
                else:
                    item(row)
    text('Methodology and limitations', 'heading')
    text('MiniLM (sentence-transformers/all-MiniLM-L6-v2) represents passages as 384-dimensional vectors. '
         'TF-IDF is the keyword-based comparison method. Cosine similarity measures vector direction; '
         'it is not accuracy, editorial confidence or a percentage of duplicated text. '
         'Passage maxima can overemphasise generic or promotional wording. Review intent, usefulness and original context. '
         'No links are inserted and no content is merged by this report. No independent quality metric is claimed.')
    text('Each section retains only the latest completed run in this server session. Results from older collection revisions '
         'are excluded. Reviews are read at export time. Reports include at most 10 items per method per section and '
         '600 characters per evidence excerpt; URLs and titles are retained. No fresh inference or website fetching is performed.')
    def page(canvas, doc):
        check()
        canvas.setFillColor(colors.HexColor('#f3eff8'))
        canvas.rect(0, A4[1]-22, A4[0], 22, fill=1, stroke=0)
        canvas.setFont('ReportVera', 8)
        canvas.setFillColor(purple)
        canvas.drawString(42, 24, 'SEMANTIC CONTENT ANALYSER | Editorial review required')
        canvas.drawRightString(A4[0]-42, 24, f'Page {doc.page}')
    SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42,
                      bottomMargin=44, title='Website Content Analysis', author='Semantic Content Analyser').build(story, onFirstPage=page, onLaterPages=page)
    data = output.getvalue()
    if len(data) > MAX_BYTES:
        raise ValueError('The PDF exceeds the 2 MB report limit. Reduce result counts and try again.')
    return data
