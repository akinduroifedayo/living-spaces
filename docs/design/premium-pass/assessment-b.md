# Assessment B — historical provenance, coverage and source availability

**Verdict:** usable historical screenshot baseline, not present-day runtime qualification or design acceptance. All **10 authorized PNGs are exactly 1690 × 858 pixels** (PNG IHDR read directly); these are whole Desktop-window captures, not proven guest CSS viewport dimensions. Source availability is mixed: Sky Window revision 4 is missing; Pair Play has an older revision 1 snapshot, not the captured revision 4 source; Research Desk revision 8's generation payload can be reconstructed from the authorized evidence. No current reference HTML was substituted.

## Scope and capture correspondence

Roots used below:
- `P` = `/Volumes/Expansion/Development/Projects/living-spaces`
- `E` = `/Volumes/Expansion/Development/Build/living-spaces-r1/evidence`

Only named evidence and project Git history were inspected, plus Impeccable tooling instructions/help. No app, profile, database, browser, service or installation was used; no repository files were changed. Images were inspected as historical files.

| Space / evidence | Exact PNG dimensions, each | Revision and state correspondence |
|---|---|---|
| Sky Window: `P/docs/evidence/runs/sky-same-session-repair/{opened,week,cities}.png` | 1690 × 858 | Request/receipt advance **3 → 4**, finishing **2026-11-11 02:02:15.736508 −06:00**. Images show Today, Week/Chicago and Cities; text records show three live cities, retrieved **02:05 AM**. This later captured state is distinct from the maintainer's explicit “not run” repair reply. |
| Research Desk: `E/regenerate-research-desk-20261111-025333/opened.png` | 1690 × 858 | Request, write-tool response and receipt establish **7 → 8**, finishing **02:56:59.875871 −06:00**. Overview screenshot/text agree on **26 papers / 22 queued / 0 reading / 4 completed**. |
| Research Desk: `E/research-kit-interaction-20261111-032116/{overview,queue,review,saved,reopened}.png` | 1690 × 858 | Follow-up described as the existing regenerated Space; no separate code-revision assertion or per-PNG digest binding. Overview shows **27 / 22 / 1 / 4** after the fixture was added; Queue shows 23 waiting; Review shows the fixture and saved note. `saved.png` shows Reading, High and Saved in the editor. `reopened.png` shows the selected fixture's Reading/High badges, **not its note editor**; note persistence is supplied by the receipt, not those pixels alone. |
| Pair Play: `E/postpackage-pair-play-open.png` | 1690 × 858 | Play view visibly shows **2 turns, 1/6 pairs, matched watermelon pair and star backs**. The repair receipt establishes **good 2 → harness fault 3 → agent repair 4**; later Sky/Research snapshots also identify head 4. The postpackage receipt itself has no revision field or PNG hash, so correspondence to head 4 is contextual, not a cryptographic capture-to-revision binding. |

**Capture limits:** none of the supplied PNG-associated JSON records provides a complete capture manifest binding exact timestamp, PNG digest, generated-file digests, host build and CSS viewport/DPR. Request/turn clocks and forecast retrieval times are not exact screenshot timestamps. Dark appearance is evidenced; a light/mobile matrix is not. Scroll clipping means screenshots are not full-document coverage.

## Historical checks available — not re-executed

Counts below were parsed from JSON and compared with enumerated results; do not aggregate duplicate or overlapping runs as independent coverage.

- **Sky repair:** four true receipt checks; before/after hashes independently compared within the artifacts. Only Sky's `spaces` and `revisions` hashes change; records, grants and schedules remain equal, and the other four Spaces' snapshot hashes remain equal. `opened.json` records `errors: []`; Week includes canvas dimensions plus a seven-day text table; Cities includes input/button details. These are limited observations, not a network-contract or accessibility proof. `aria: null` alone does not establish an unlabeled control.
- **Research regeneration:** seven true receipt checks; target records/grants/schedules and all other Space hashes agree before/after. Trace records the revision-8 write success. Follow-up interaction receipt has **14/14** true enumerated checks: fixture creation, note/status/priority saving, prior-record preservation, Queue/Review/Overview access and close/reopen persistence. This is historical behavioral evidence, not a new pass by this assessment.
- **Pair Play:** postpackage **9/9**, reopen **8/8**, controlled repair **15/15** true enumerated checks. Coverage includes isolation assertions, persisted round/settings, Progress navigation, scoped error reporting and record-preserving repair. **Both** `pair-play-01-interaction.json` and `.attempt-2.json` are identical **7/8** records: “index exposes the second independent app” failed. Reopen documents harness targeting/readiness/selector faults and later successful checks. Preserve the failed attempts; do not relabel them as all-pass. The game record's **rev 9** and settings **rev 2** are record revisions, not application code revisions.

## Generated source and Impeccable

**Research Desk — exact generation material exists inside JSON.** `pair-play-before-evolution.json.research_project.files` contains revision-3 source. The regeneration trace's `spaces_revisions` response supplies revision-7 file hashes; its `spaces_write_files` call contains ten complete revision-8 file bodies and returns revision 8. Four unchanged files from the snapshot match the revision-7 SHA-256 values: `index.html`, both vendor modules and `kit/spaces-kit.mjs`. Combining those verified unchanged files with the ten literal write bodies yields a 14-file generation reconstruction, without inventing HTML or using today's reference. This is **not** a fresh read-back of all persisted revision-8 file hashes. The entry HTML SHA-256 is `78b4d527fd7fde414c9930298dcb79e447cb3079db0e3ada6cc0fc401347fbb2`.

**Pair Play — exact older source only.** `pair-play-before-evolution.json.project` contains 11 source files at application revision 1, before Progress/evolution/repair. This cannot stand in for the screenshot's later source. **Sky Window — exact generated revision-4 markup absent** in the authorized evidence; repair narrative and hashes do not reconstruct its source.

Extracted source copies were staged only in Miro scratch under `assessment-b-exact-sources/`. Ran the installed launcher, with download fallback disabled (`IMPECCABLE_LAUNCHER_PROBE=1`):

```text
impeccable detect --json --no-config --no-design-system <exact-source-copy>/index.html
Research Desk generation reconstruction: exit 0, stdout []
Pair Play revision 1 (NOT screenshot revision 4): exit 0, stdout []
```

**Neither empty scan is a clean bill.** Both entry documents contain an empty `#app` shell plus a module script. Static HTML analysis does not instantiate the Preact views, saved data, host theme/sandbox or dynamic states. Linked CSS is available, but there is no demonstrated populated-DOM coverage. The Pair scan additionally targets an older revision and cannot qualify the baseline. Sky's source scan and Pair's revision-4 scan were skipped for missing exact baseline source. Impeccable is **not applicable to PNGs**; no PNG was fed to it.

## Reference separation and skipped-test reasons

Git history identifies later showcase references: Sky `8b48cd3` at **04:43:17 −06:00**, Pair `848814e` at **04:57:13 −06:00**, plus earlier research-kit/reference work. These paths and commit subjects do not prove generated-source identity. None was read or scanned as a replacement. Sky evidence entered Git in `43b7d6b` at **02:37:07 −06:00**; all three inspected Sky PNG Git blob hashes match HEAD. The inspected Pair repair JSON also matches its HEAD blob. This supports artifact retention, not full reproducibility.

- **Live/browser/CDP, network retrieval, save/reopen reruns:** expressly prohibited; existing receipts only.
- **Keyboard, screen reader, focus order, touch gestures, actual responsive behavior:** no interaction performed; PNG/text dumps cannot establish them.
- **WCAG contrast/computed typography, theme switching, reduced motion, zoom:** no populated DOM/computed styles or alternate captures; no conformance score assigned.
- **Performance, bundles, frame timing, loading/error/conflict/empty-state matrix:** no relevant measurements or complete state captures; source-shell detector output cannot substitute.
- **Project-wide Impeccable context/config scan:** deliberately omitted to honor evidence-only reads; detector used `--no-config --no-design-system`. No repairs, installs or reference-source scans were attempted.

**Next evidence needed:** revision-bound generated-source exports for Sky and Pair; persisted-file digest confirmation for Research; a manifest linking every capture to its source revision/digests, host build, timestamp and guest viewport/DPR. Live qualification requires separately authorized work.
