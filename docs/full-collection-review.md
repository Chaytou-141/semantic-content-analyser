# Full-collection relevance review

## Q05: Organising an espresso preparation area

Reader question: How can I arrange the espresso preparation area so cafe staff can work efficiently?

Rule: mark yes only when the supplied article directly helps answer the layout and staff-workflow question. Shared cafe or equipment vocabulary alone is insufficient. Use unsure for borderline cases and explain the uncertainty before resolving it.

Status: all 21 articles reviewed by the assistant at the learner's request, before inspecting Q05 rankings. These are assistant-proposed labels, not independent human ground truth. Under the strict direct-answer rule, A12 is relevant and the other 20 articles are not. Human review can revise these provisional judgements.

Review every article before running retrieval. TODO means unreviewed, not irrelevant. Do not calculate full-collection recall until all 21 decisions are resolved.

| ID | Title | Body | Relevant? (yes/no/unsure) | Reason |
| --- | --- | --- | --- | --- |
| A01 | Choosing a display fridge for a cafe | Compare cabinet capacity, shelf layout and available counter space when selecting a refrigerated display for a cafe. Consider how customers will see and access cakes and drinks. | no | Concerns choosing and displaying a fridge, not arranging espresso preparation. |
| A02 | Selecting a refrigerated cabinet for a bakery | A bakery display cabinet should present pastries and chilled cakes clearly. Compare shelf height, lighting and cabinet size before choosing equipment for a small shop. | no | Concerns buying a bakery display cabinet, not espresso station layout. |
| A03 | Open versus closed refrigerated displays | Retail shops can choose open refrigerated shelves or cabinets with glass doors. Compare customer access, product visibility and energy use when selecting a display for drinks and snacks. | no | Compares refrigerated display types, not staff workflow at a coffee station. |
| A04 | Measuring space for a cafe display refrigerator | Measure the service counter and delivery doorway before buying a refrigerated display cabinet. Allow room for ventilation and staff movement when comparing equipment sizes. | no | Mentions staff movement but specifically concerns fitting a refrigerator; no espresso-area arrangement guidance. |
| A05 | Comparing running costs of display fridges | When choosing a commercial display refrigerator, compare energy consumption alongside purchase price and capacity. Opening hours and cabinet placement can affect operating costs. | no | Concerns refrigerator running costs rather than espresso workflow. |
| A06 | Cleaning a commercial display fridge | Plan routine cleaning of shelves and glass in a commercial refrigerated cabinet. Follow the equipment manual and keep food handling separate from cleaning activities. | no | Concerns cleaning a refrigerator rather than arranging coffee equipment. |
| A07 | Choosing a chest freezer for bulk storage | A restaurant buying a chest freezer should compare storage capacity, basket layout and floor space. Bulk frozen ingredients need a different storage arrangement from products displayed to customers. | no | Concerns choosing bulk freezer storage rather than a coffee preparation area. |
| A08 | Choosing an espresso machine for a small cafe | Compare espresso machines by expected drink volume, counter space and ease of use. A small cafe should consider staff workflow and equipment capacity before purchasing. | no | Borderline: mentions workflow and counter space, but gives buying considerations rather than layout guidance; no under the strict rule. |
| A09 | Selecting a coffee grinder for espresso | Compare grind adjustment, consistency and daily capacity when buying an espresso grinder. Match the grinder to the cafe's drink volume and available workspace. | no | Borderline: mentions workspace, but concerns grinder selection rather than arranging equipment; no under the strict rule. |
| A10 | Adjusting espresso grind for a balanced shot | Changing grind size affects how quickly water passes through coffee. Adjust one variable at a time and record the resulting extraction time and taste. | no | Concerns grind adjustment and extraction rather than physical workflow. |
| A11 | Cleaning cafe coffee equipment | Regular cleaning removes coffee residue from espresso equipment. Follow the manufacturer's instructions for the machine and grinder rather than treating all equipment the same way. | no | Concerns cleaning equipment, not arranging the preparation area. |
| A12 | Planning a cafe coffee station | Arrange the espresso machine, grinder and milk workspace to reduce unnecessary movement. Counter dimensions and staff access help determine an efficient coffee preparation layout. | yes | Directly describes positioning the espresso machine, grinder and milk workspace to reduce movement and improve access. |
| A13 | Choosing an oven for a small bakery | Compare oven capacity, tray sizes and available kitchen space when buying bakery equipment. Select an oven suited to the products and production volume of the business. | no | Concerns buying a bakery oven rather than an espresso preparation area. |
| A14 | Why bread dough needs time to rise | During fermentation, yeast produces gas that expands bread dough. Dough temperature and fermentation time influence the final loaf's texture and flavour. | no | Explains dough fermentation rather than cafe layout. |
| A15 | Keeping pastry layers light and crisp | Layered pastry relies on alternating dough and fat. Resting and careful handling help preserve the layers before baking. | no | Explains pastry handling rather than cafe layout. |
| A16 | Planning a bakery production schedule | Schedule mixing, resting and baking around expected customer demand. Coordinate oven use and preparation tasks so different products are ready at useful times. | no | Concerns bakery production timing, not espresso equipment arrangement. |
| A17 | Writing a cafe equipment buying guide | A useful buying guide explains equipment choices for its intended reader. Organise comparisons around capacity, workspace and practical trade-offs rather than repeating product keywords. | no | Concerns writing a buying guide rather than giving espresso layout advice. |
| A18 | Linking related buying guides on a website | An internal link can help a reader move from a general buying guide to a useful equipment comparison. Review the source paragraph and destination page before recommending a link. | no | Concerns website internal links rather than physical cafe workflow. |
| A19 | Reviewing two articles about the same topic | Two articles may discuss the same equipment while answering different reader questions. Compare their purpose and unique information before deciding whether they should remain separate. | no | Concerns reviewing article overlap rather than cafe workflow. |
| A20 | Improving a cafe website contact page | A contact page should help visitors find the cafe's location, opening hours and contact details. Clear practical information serves a different purpose from an equipment buying guide. | no | Concerns website contact information rather than staff preparation space. |
| A21 | Cleaning a refrigerated bakery display cabinet | Routine cleaning of a bakery's refrigerated display includes the glass, shelves and removable trays used for chilled cakes. Follow the cabinet manufacturer's cleaning instructions and keep food protected during the task. | no | Concerns cleaning a refrigerated cabinet rather than espresso station layout. |

## Evaluation procedure

1. Complete and review every label before seeing rankings.
2. Use all 21 articles as the candidate collection for both methods.
3. Fit TF-IDF on the article texts only; transform the question with that vocabulary.
4. Compare identical result limits, initially K = 1, 3 and 5.
5. Record rankings, precision, recall and false matches without changing the question or labels to favour a method.

This is a new development example on a familiar synthetic collection, not an independent held-out benchmark.
