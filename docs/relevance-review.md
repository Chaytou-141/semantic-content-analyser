# Relevance review worksheet

## Purpose

Judge whether an article helps answer a specific reader question, rather than whether it merely shares words or a topic. These are human relevance labels, not model scores or training data.

For this first exercise, use a strict rule: mark an article relevant only if its supplied title and body directly help with the stated task. Record a reason for each decision. These labels are provisional and can be revised if the task definition changes.

## Q01: Cleaning a refrigerated display cabinet

Reader question: How do I clean the shelves and glass of a refrigerated display cabinet used for cakes?

| Candidate | Supplied article text | Relevant? (yes/no) | Reason |
| --- | --- | --- | --- |
| A21: Cleaning a refrigerated bakery display cabinet | Routine cleaning of a bakery's refrigerated display includes the glass, shelves and removable trays used for chilled cakes. Follow the cabinet manufacturer's cleaning instructions and keep food protected during the task. | yes | Covers cleaning the shelves and glass of the requested equipment. |
| A04: Measuring space for a cafe display refrigerator | Measure the service counter and delivery doorway before buying a refrigerated display cabinet. Allow room for ventilation and staff movement when comparing equipment sizes. | no | Covers measuring space, not cleaning. |
| A11: Cleaning cafe coffee equipment | Regular cleaning removes coffee residue from espresso equipment. Follow the manufacturer's instructions for the machine and grinder rather than treating all equipment the same way. | no | Covers cleaning different equipment. |
| A07: Choosing a chest freezer for bulk storage | A restaurant buying a chest freezer should compare storage capacity, basket layout and floor space. Bulk frozen ingredients need a different storage arrangement from products displayed to customers. | no | Covers buying a freezer, not cleaning a display cabinet. |

## Q02: Buying an espresso machine

Reader question: What should I consider when buying an espresso machine for a small cafe?

The learner selected A08 before inspecting model rankings for this question. The other candidates are labelled no under the strict direct-answer rule.

| Candidate | Summary | Relevant? (yes/no) | Reason |
| --- | --- | --- | --- |
| A08: Choosing an espresso machine for a small cafe | Compares drink volume, counter space, ease of use, workflow and capacity. | yes | Directly explains considerations for buying the requested equipment. |
| A09: Selecting a coffee grinder for espresso | Compares grind adjustment, consistency, capacity and workspace. | no | Concerns buying a grinder, not an espresso machine. |
| A11: Cleaning cafe coffee equipment | Describes removing residue and following equipment cleaning instructions. | no | Concerns cleaning rather than buying. |
| A12: Planning a cafe coffee station | Describes equipment arrangement, counter dimensions and staff access. | no | Related planning context, but does not directly explain machine selection. |

## Q03: Why a loaf mixture expands

Reader question: Why does my loaf mixture expand while resting before it goes into the oven?

The learner selected A14 before inspecting either method's ranking, explaining that expanding and rising express a similar idea here.

| Candidate | Summary | Relevant? (yes/no) | Reason |
| --- | --- | --- | --- |
| A13: Choosing an oven for a small bakery | Compares oven capacity, tray sizes and kitchen space. | no | Concerns buying equipment, not why dough expands. |
| A14: Why bread dough needs time to rise | Explains that yeast produces gas during fermentation, expanding bread dough. | yes | Directly explains the expansion described in the question. |
| A15: Keeping pastry layers light and crisp | Describes dough and fat layers, resting and careful handling. | no | Concerns preserving pastry layers rather than explaining loaf expansion. |
| A16: Planning a bakery production schedule | Coordinates mixing, resting and baking around demand. | no | Concerns scheduling rather than the cause of expansion. |

## Evaluation limits

- Each question uses four reviewed candidates, not a complete labelled evaluation set. Other relevant articles may exist in the collection.
- A21 was written after inspecting earlier results. This example is useful for learning but is not an independent test of generalisation.
- Before reporting retrieval metrics across the full collection, review every eligible candidate for each evaluation question and define self-exclusion consistently.
- Later, add new questions and label them before inspecting rankings. Use the same questions, collection and relevance labels for embeddings and TF-IDF.
