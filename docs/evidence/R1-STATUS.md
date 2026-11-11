# Release 1 evidence status

The goal is a real application built and evolved from normal Hermes chat, used in Desktop, with durable shared data and controlled upkeep. This report does not assert release acceptance.

## Current checkpoint

All five primary lanes and the packaging repair are committed on `forge/r1-contracts`, not main. The current parent qualification uses source at `9a3019201541ff672f3ed90913bd47b02ce6bb90`. A detached copy under the external build directory matches every tracked file byte for byte. The actual Hermes runtime ran all 151 Python cases with no failures or skips. The rebuilt renderer passed its dependency-graph gate. The combined sandbox and UI Node run passed 108 cases, and the reference suite passed 19 cases, with no failures or skips.

The current real-Chrome sandbox smoke passed 17 checks on Chrome `157.0.8103.51`. Static rendering passed 40 assertions. These are fixture results, not Desktop acceptance. The stock form replay passed 13 Research Desk checks, then stopped on native input targeting in habit-planner. That failure remains open. The first qualification attempt omitted the renderer-metafile build prerequisite and changed `HOME`, preventing Chrome startup and hiding the installed React runtime. Its failed logs and the corrected environment are retained separately under `evidence/postpackage-stock/` and `evidence/postpackage-stock-attempt-2/`. No source or assertion changed between those attempts. The historical 146-case runtime and bare-venv receipts remain in their original directories.

The packaging candidate passes unchanged full validation, including Desktop admission, under the actual Hermes runtime in a separate test home. The native `cron.jobs` private-import warning remains. The parent ran all 151 Python cases successfully on the repaired candidate. Its 108-case sandbox and UI run and 19-case reference run pass. The parent verified the red run's 17 behavioral failures and preserved case identities, the byte-identical loader relocation, and all 133 frozen Python methods. Validation is not sandbox or release acceptance. The repository remains private and no verified-unit merge to main has occurred.

The initial model-access smoke returned `ISOLATED-TURN-OK`. Subsequent normal Desktop turns created Research Desk revision 1 and repaired its native-submit bug as revision 2 through `claude-sonnet-5-5` and `claude-subscription-directsdk-experimental`. The existing machine-wide login is used without copying credentials. The first real interaction exposed a generation-reference defect that fake hook tests had not caught. Frame permissions remain unchanged.

The current isolated Desktop and gateway remain in use for qualification. Their home and evidence are under the external `living-spaces-r1` build directory, outside Git. Actual mouse activation added a fifth public paper and saved notes, status and priority. Canonical storage and reopened controls agree. The first replay hit a harness frame-readiness race during reopen; its failed log is retained beside the successful reopen-only retry. A further model turn read those values and changed that same record while the Space stayed mounted. The real app reflected the new note and completed status without a manual reload. This is not full restart evidence.

The real-model trace is `evidence/normal-chat-03.trace.json` in that build directory. `journey-interaction.log.attempt-1`, `journey-interaction-attempt-2.log`, `journey-chat-live-update.json` and its screenshot retain the interaction evidence and the harness failure. The exact packaged renderer SHA-256 is `4ec39eca0987f25709dd8de52de39208bb4c688ea0407fee975b637e5d6fdd00`. These observations precede the packaging repair and must be requalified afterward.

## Scheduled upkeep checkpoint (19:10 CT)

`harness/qualify_schedule.py` drives the real isolated Desktop, the isolated gateway's cron ticker and native `cron/jobs.json`. Runs were made due with `cron.jobs.trigger_job`, which only moves `next_run_at`; the gateway ticker still claimed and executed the no-agent script. To show an update, the harness overwrites one record's `source` title directly in SQLite, then requires the scheduled run to correct it. This is a test fixture, not a product path. Two harness limits are disclosed. The isolated window is occluded, so the renderer reports `document.visibilityState=hidden` and TanStack Query pauses polling. The open-view pickup check therefore holds CDP focus emulation. The in-frame Library tab press did not route under that state, so the harness set the frame's hash directly. Twelve failed or vacuous attempts are retained beside the passing runs.

The independent packaging review found that the renderer graph gate resolved paths against the process cwd and compared case-sensitively. Commit `783cff8` resolves against the repo root and lowercases. Three regression tests fail on the old gate and pass on the new one, and the real esbuild metafile still passes.

## Failure, restore and lifecycle checkpoint (20:00 CT)

`harness/qualify_failure_restore.py` passed 18/18 in the isolated Desktop. A disclosed harness-authored revision points the feed at a failing path on the already-granted host. Refresh now records a failed run. Every record keeps its data, source and rev. The host banner names the last-good data and says notes and statuses are unchanged. Restore through the host Revisions dialog creates a new `restore` revision whose file map equals the good revision; user records are not rewound. The next refresh succeeds and clears the banner. One earlier run had a vacuous file-equality check (it compared missing keys); it is retained and not counted.

`harness/qualify_lifecycle.py` passed 23/23. Guest calls run in the Space frame's own realm through the real bridge. Results: oversized and malformed writes fail with typed errors and store nothing; a guest batch op carrying `space: 'pair-play'` lands only in the bound Space and Pair Play is byte-identical; closing the Space closes its session and a replay of that session through `core.dispatch` returns `session_invalid` and writes nothing; reopening issues a fresh session; three rapid Refresh now presses create one run. A disposable `Lifecycle Probe` fixture Space with an active native schedule was archived through host controls (cron job paused, refresh blocked, retention copy shown) and deleted (Space, cron job and shim removed). Model-built Spaces were untouched.

That run found a real host defect. The renderer silently dropped any bridge request over 1 MB, so the guest promise never settled. The host now replies `limit` (or `invalid`) when a rejected envelope carries a usable id. A host test failed before the fix and passes after. The bundle was rebuilt with `--jsx=automatic`, which matches the committed artifact; the contract build line omitted that flag and is corrected.

## Acceptance ledger

| Check | Status | Missing evidence |
|---|---|---|
| R1-01 safe hosting | Pending | Requalify integrated sandbox in isolated Desktop, adversarial ordinary-network probes and origin-check diagnosis. Prior spike is historical evidence only. |
| R1-02 real creation | Observed before packaging repair | Real normal Desktop chat created Research Desk; working Open Space, owner index and three shared-data views observed. Native-submit defect repaired through the same chat without permissions changes. Requalify after packaging changes. |
| R1-03 durable interaction | Partial | Actual add/save/reopen and model read/change reflected in the mounted app. Ambiguous-target non-mutation remains unproven. |
| R1-04 evolution and breadth | Partial | Normal chat added Research Desk's Review view and created the distinct Pair Play game. Pair Play's revision-2 Progress view works in the restarted packaged Desktop with the original round and settings intact. Broader evolution and acceptance review remain. |
| R1-05 authority | Pending | Actual grant panel, denial and revocation checks, WebRTC disclosure and secret checks. |
| R1-06 refresh | Partial | Real arXiv retrieval through Refresh now kept user notes. A failing source on the granted host records a failed run, keeps every record unchanged and shows the last-good banner; recovery clears it (`evidence/failure-restore/`). Open: a stale concurrent edit during refresh has not been exercised in the Desktop. |
| R1-07 schedule | Partial | Model-requested daily schedule approved through the host-owned Approve control (native input). One native no-agent cron job, cadence `0 7 * * *` America/Chicago, next eligible 07:00 shown. The isolated gateway ticker executed scheduled runs with the Space closed (index only, zero frames) and open; each corrected one diverged source record, kept all user data, and the open frame showed the new value without remount. History shows the schedule run. Host Pause paused the native job; no run across two ticker intervals. Job left paused. Open: offline/missed-run catch-up not observed, revoke-stops-schedule not exercised, final job deletion pending at release end. Evidence `evidence/schedule/`. |
| R1-08 restart and failure | Partial | Full isolated Desktop and gateway restart preserved all projects, records, revisions and grants. Pair Play reopened with retained game and settings. Resource-limit, interrupted-work and recovery cases remain. |
| R1-09 repair | Pending | Bounded scoped error and real chat repair without data loss. |
| R1-10 restore | Partial | Host Revisions dialog restored revision 5 as new `restore` revision 7 with an identical file map; user records were not rewound (`evidence/failure-restore/`). Open: restoring across an incompatible `data_version` has not been exercised in the Desktop. |
| R1-11 lifecycle | Partial | 23/23 in `evidence/lifecycle/`: closed-session replay refused, fresh session on reopen, oversized and malformed guest writes fail typed (host defect found and fixed), forged cross-Space batch confined, triple Refresh now deduped to one run, archive pauses cron and blocks refresh, delete removes Space, cron job and shim. Open: in-place frame reload replay has not been exercised separately. |
| R1-12 usability | Pending | Miro's qualification of running candidate and observed return-use journey. Static design frames do not pass. |

## Promotion and publication

The repository remains private. Periodic `forge/*` pushes and verified-unit PR merges are authorized. Public visibility, catalog submission, upstream PRs and hackathon submission need separate owner approval. No catalog PR has been opened.

## Procedural gaps

The initial contracts were authored before completing the prescribed HOW exploration and Architect arena. The lane launches also preceded a full frozen-input and native-preflight audit. Those stages cannot be claimed retroactively. The artifacts require fresh independent qualification against the integrated state before unit acceptance or merge. File-separated worktrees do not prove an OS sandbox or worker qualification.

## Next work

The form-reference correction is integrated. Its parent Chrome replay passed 13 Research Desk checks and 11 habit-planner checks without widening frame permissions. Package design synthesis is committed at `d65126d`. Candidate A is the refinement base with B's deterministic static document and source-module graft. The Opus cross-judge read all 98 bound bodies; overlap with B is disclosed and its recommendation is non-binding. `docs/architecture/SANDBOX-ADMISSION.md` records the choice and remaining runtime gates.

Package implementation is committed and privately backed up on `forge/r1-package` at `157043223b6f98f2d375808f2f851c0283bd0c06`. The parent audited the actual Codex `gpt-6.1-sol` high session and all 86 required bodies. A no-match lookup in an unbound Codex memory file is a procedural deviation. The parent also removed one extra EOF blank line that the worker's unstaged-only whitespace check missed. Rebuilding proved identical shipped guest bytes. Raw route, scope, red/green and full-validator receipts are retained in `run/seats/package/attempt-1/` and `evidence/package-parent/` under the external build directory.

A fresh Sonnet medium Comment Sicko seat completed its bounded audit. The parent verified all 48 required bodies, successful Claude attribution, no denied tools, and exactly two redundant module docstring removals. Those removals are committed as `27fb2a3` and merged on the build branch. No other tracked bytes changed in that audit. The integrated source has passed the current suites above.

The parent stopped and restarted only the isolated Desktop and gateway after checking that the model session was idle. Fresh canonical reads found every Space's project, records, revisions and grants unchanged. The actual restarted Desktop mounts the byte-exact installed guest HTML. Nine actual-app checks passed for opaque origin, blocked parent-document access, retained Pair Play round and settings, visible matched cards, and native navigation to the new Progress view. Evidence is in `restart-before.json`, `restart-after.json`, `pair-play-02-preservation.json` and `postpackage-pair-play.json`, with screenshots in the external evidence directory. These checks do not complete network, failure-recovery or full lifecycle acceptance.

Independent executable source review and the remaining R1 checks are next. Pair Play's earlier session-lookup race and DOM-targeting failures remain retained. Miro's running-candidate review and Ife's final acceptance remain separate gates.
