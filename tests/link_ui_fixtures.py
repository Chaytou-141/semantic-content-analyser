"""Original synthetic editorial examples. Scores are display fixtures, not evaluations."""
from copy import deepcopy

REVISION = 'offline-links-v1'
TITLES = [
    'Measuring your café for a display fridge',
    'Understanding display fridge running costs',
    'A practical maintenance schedule for display fridges',
    'Choosing a refrigerated display for a bakery',
    'Open or closed displays: matching the cabinet to your menu',
]
TOPICS = [
    'Measure the counter, service aisle and ventilation clearance before choosing a cabinet. '
    'A display that fits the floor plan should also leave staff room to restock safely.',
    'Compare energy use alongside purchase price. Door openings, room temperature and the '
    'position of the cabinet can change how hard the refrigeration system needs to work.',
    'Plan regular cleaning around your service schedule. Accessible shelves and removable '
    'parts make it easier to maintain the cabinet without disrupting the café team.',
    'Think about the food being displayed. Cakes, sandwiches and pastries may need different '
    'shelf arrangements, and staff must be able to reach products during busy service.',
    'Consider whether customers serve themselves or order at the counter. Open and closed '
    'cabinets offer different ways to display food and manage frequent access.',
]


def fixture():
    blocks = [(topic + ' Discuss these requirements with the team before making a purchase. ') * 3 for topic in TOPICS]
    source = {'id':'S01','title':'Choosing a display fridge for a small café',
              'body':'\n\n'.join(blocks),'topic':'cafe_equipment','url':'https://example.test/guides/display-fridge',
              'eligible':True,'existing_links':['X01']}
    articles=[source];results=[];cursor=0
    for i,(title,block) in enumerate(zip(TITLES,blocks),1):
        target_text = (TOPICS[i-1] + ' Check the specification and compare it with your own installation. ') * 3
        if i==5:target_text += ' Literal markup: <img src=x onerror="window.linkFixtureExecuted=true"> :contentReference[oaicite:2]{index=2}'
        intro='A guide for café owners.\n\n'
        article={'id':f'D0{i}','title':title,'body':intro+target_text+'\n\nEnd of the guide.',
                 'topic':'cafe_equipment','url':f'https://example.test/guides/destination-{i}',
                 'eligible':True,'existing_links':[]}
        articles.append(article)
        results.append({'id':article['id'],'title':title,'url':article['url'],'topic':article['topic'],
                        'score':[.7691,.7023,.6197,.5997,.5528][i-1],
                        'source_passage':block,'source_start':cursor,'source_end':cursor+len(block),
                        'passage':target_text,'passage_start':len(intro),'passage_end':len(intro)+len(target_text),
                        'review_required':True})
        cursor+=len(block)+2
    for aid,eligible in [('X01',True),('X02',False)]:
        articles.append({'id':aid,'title':'Excluded fixture page '+aid,'body':'Excluded content for fixture integrity.',
                         'topic':'','url':f'https://example.test/{aid}','eligible':eligible,'existing_links':[]})
    baseline_reviews=[{'source_id':'S01','target_id':'D02','decision':'not_useful','note':'The intent does not fit this source.'},
                      {'source_id':'S01','target_id':'D03','decision':'useful','note':'Useful maintenance context.'}]
    tfidf=[deepcopy(results[i]) for i in [1,0,3,2,4]]
    for result,score in zip(tfidf,[.51,.48,.36,.29,.21]):result['score']=score
    groups={method:{'results':rows,'excluded':{'self':'S01','existing':['X01'],'disallowed':['X02']}}
            for method,rows in [('embeddings',results),('tfidf',tfidf)]}
    return articles,groups,baseline_reviews
