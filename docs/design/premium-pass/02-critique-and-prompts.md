# Chat-built Spaces: critique and regeneration prompts

Evidence inspected at full resolution (1690×858):
- Sky Window: `docs/evidence/runs/sky-same-session-repair/{opened,week,cities}.png`, a real chat build in Desktop.
- Pair Play: `docs/evidence/runs/r1-09-repair/02-progress-repaired.png` and `00-chat-before.png`, a real chat build in Desktop.
- Research Desk: **no chat-built screenshot with content exists.** `panel-opacity/{before,after}.png` show the frame with a blank canvas behind the Permissions sheet. I critique the bundled reference render (`docs/design/space-kit/screens/research-desk-dark.png`) because chat builds copy that reference.

Shared root cause (also flagged by Bjorn): until now the design guidance read as an avoid list, every example linked `kit/spaces-kit.css`, and nothing asked the agent to pick a concept, use imagery or draw a custom visual. The agent did what we asked. It built a competent Hermes-looking form. Rewritten in `SKILL.md` § "Design the canvas" (commit 8184fc8).

## Sky Window: competent, generic (5/10)

What works: big temperature numerals; live Open-Meteo data with honest provenance; a real Week chart with high/low lines and rain bars and direct labels; tabbed views; a clear Cities form.

What holds it back:
1. **No concept.** It's a navy card grid that could hold any data. Nothing says sky: no sky colour that follows conditions, no time of day, no sun or moon.
2. **Identical cards side by side.** Chicago and Lisbon get the same box and the same eight-cell metrics grid. The eye has no lead city, and Tokyo falls below the fold.
3. **Metric grid is a spreadsheet.** Feels like / humidity / wind / rain / high / low sit as equal-weight mono cells. Today's range (4° → 12°) belongs on a range bar, and rain belongs on a gauge.
4. **Icon is a stock weather glyph** at small size next to a 96px numeral. The condition is the story and deserves the art.
5. **Week chart is the default line chart.** Plain axes, generic orange and blue, rain bars clipped at the bottom, a lot of empty plot. A temperature ribbon (low → high band per day) with condition icons above each day would read faster and look like a weather product.
6. **Lat/long coordinates in mono** take the top-right of each card. They're metadata, not information.
7. **Cities view** is a form plus a list with heavy outline buttons. Fine, but nothing to look at.
8. The eyebrow label ("TODAY" above "Current conditions…") is a kicker. Delete it.

## Pair Play: functional skeleton (3/10)

What works: a clear current-round progress bar with "1 of 6 pairs found · 2 turns"; honest empty "Completed rounds" copy; a found card (watermelon) gets a green outline plus a text label.

What holds it back:
1. **No game feel at all.** It's a white-on-charcoal form. The board is a 3×2 grid of dashed boxes reading "? Not yet". There's no table surface, no card backs and no deck.
2. **Emoji as the only art.** A single 🍉 at about 20px.
3. **Narrow centred column** (~440px) in a 1400px canvas. Most of the screen is empty grey.
4. **Stats are kit stat cards** ("0 Rounds", "0 Total turns", "— Personal best"): the hero-metric template, and the most boring part of the screen.
5. No motion. A memory game without a card flip is missing its core moment.
6. No celebration state, no streak, no personality.

## Research Desk (reference render): quiet editorial, under-designed (4/10)

What works: serif display heading; "Next in your reading queue" leads; an honest empty and fixture label.

What holds it back:
1. **A row of four identical stat cards** (In library / Queued / Reading / Completed) with tinted icon squares: the exact sameness pattern.
2. Big empty canvas below. The overview has nothing to look at, no cover art, no topic map.
3. "Public source freshness" is collapsed in a full-width card, so the most live thing is hidden.
4. The editorial preset gives a serif and a green button, and that's all of its personality.

## Regeneration prompts for Forge

Use one prompt per Space, in a fresh chat after the new `SKILL.md` lands, with Internet access left on (the default). The prompts say what the Space is for and the vibe. They don't spell out design, because the test is that the skill does the design.

**Sky Window**
> Build me a Space called Sky Window that shows live public weather for Chicago, Lisbon and Tokyo: what it's like right now in each city, today's range, and the next seven days, plus a way to add or remove cities. Use Open-Meteo. I want it to feel like looking out of a window at the sky in each place, something I'd leave open on a second screen. Generate any art it needs.

**Pair Play**
> Build me a Space called Pair Play: a memory matching game with 6 pairs (12 cards). Track turns, keep a history of completed rounds and my personal best, and let me resume a round in progress. Make it feel like a real tabletop card game with proper card art and a satisfying flip, not a form. Generate the card art.

**Research Desk**
> Build me a Space called Research Desk for keeping up with public AI research. Pull new papers from the arXiv cs.AI RSS feed, let me search the library, queue papers with a status and priority, and write notes on each one. Refreshing must never wipe my notes. Make it a beautiful place to read, more like a well-designed literary magazine or a library reading room than an admin panel.

Acceptance for the regenerated screenshots (I review these):
- A named concept is visible in the first viewport without a caption.
- At least one generated or drawn image is in the Space (Sky Window and Pair Play must have one).
- The main visual is custom to the subject, not a default chart or stat-card row.
- The empty or loading state is in character.
- At 390px wide, the hero and main action stay in the first screen.
- Contrast, focus and status words still meet the floor.

Send me: opened desktop at 1690×858, one secondary view, and one narrow (≈390px) capture per Space.
