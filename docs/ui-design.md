# Interface redesign

The interface is organised as a content review desk. Article text, passage evidence and editorial decisions take priority over promotional copy or decorative graphics.

## Guidance used

- Installed `frontend-design` skill: subject-specific layout, deliberate typography, restrained visual elements and screenshot critique.
- Installed `find-skills` workflow: searched the skills.sh directory and verified the source of relevant interface guidance.
- Vercel `web-design-guidelines`: https://skills.sh/vercel-labs/agent-skills/web-design-guidelines
- Applied guideline source: https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md

No framework rewrite or database change was needed. The remote guidance was read and applied to this task; no user-level skill installation was performed.

## Design choices

- A top navigation gives the five workflows equal, visible positions. Navigation uses real links and retains modifier-click behaviour.
- Instrument Sans is hosted locally under its included SIL Open Font License. Georgia is reserved for reading source excerpts.
- Plum ink, white surfaces and a pale lavender background form the base palette. Colour distinguishes controls and review states without gradients or decorative metric cards.
- The opening page previews actual collection articles. The collection rail calculates real topic and word counts and links topic selections to the article filter.
- Search results use real rank positions and grouped passage lists. Evidence retains its original source text; model scores are not presented as confidence percentages.
- Link review places source and destination text together and labels review notes. Errors appear inside an open dialog, and closing unsaved edits requires confirmation.
- Forms retain visible labels, keyboard focus and native semantics. A skip link, reduced-motion behaviour, table headers and polite status updates support accessible interaction.

## Verification

- 15 API tests passed; the backend implementation was unchanged.
- Browser flows passed for comparison search, link exclusions and review saving, overlap, collection filters, editing, evaluation and import dialogs.
- Added browser checks for live topic filtering, the search keyboard shortcut and accepting/rejecting the unsaved-edit confirmation.
- 25 layout checks passed: all five views at widths of 320, 390, 768, 1024 and 1440 pixels. The article table scrolls inside its own container on narrow screens.
- Automated axe-core WCAG A/AA scans reported zero violations in nine inspected states: search opening, search results, link results, overlap results, collection, evaluation, article dialog, import dialog and mobile search. This is not a complete accessibility certification.
- JavaScript syntax and Git whitespace checks passed. Desktop and mobile screenshots were visually inspected.

Checks ran against an ignored disposable SQLite workspace, not the existing user workspace. Browser screenshots and audit output are retained under ignored `runtime/` paths. No AWS resources, publishing integrations or application database migrations were involved.
