# Intent source qualification

The goal is one ordinary Hermes chat turn from a genuine click inside a generated Space, without a second Send control. This report does not qualify the native Desktop path.

## Contract and implementation

[BOT-INTENT-BOUNDARY.md](BOT-INTENT-BOUNDARY.md) records the owner-approved weaker guarantee and next-release proposal. The trusted loader captures the current genuine click before guest handlers run. It consumes that opportunity once before sending `bot.request`. Captured native getters prevent guest property overrides from turning a synthetic or stale event into a current trusted event.

The loader also captures MessagePort, MessageEvent, Promise, and pending-map operations before guest execution. Guest startup occurs after the port-bearing boot dispatch ends. This protects the private transport against the tested interception paths. It is not arbitrary same-realm memory isolation or exact callback attribution. A nested callback or immediate promise during a genuine click can consume its opportunity.

Existing host one-in-flight handling and backend claim, deduplication, and rate controls remain unchanged. Dispatch remains an ordinary native chat admission under Hermes approvals. Direct frame internet remains disabled.

## Executed evidence

The parent ran the unchanged nine new Node tests against the pre-fix loader at `8134be424b5a5756a89278e729ab537475f45155`. One passed and eight failed. These are modeled event and port fixtures, not browser evidence. The same nine identities pass against the repaired loader.

The first full receiving-tree replay failed two pre-existing console tests. Their reduced MessagePort double exposed `postMessage` but lacked `close`. The parent added only a no-op `close` to that double. No assertion, production branch, or test count changed to accommodate the fixture. The next full replay passed395 Python,125 grouped Node,251 standalone Node, and19 reference cases, both builds, renderer graph checks, and generated-artifact parity. Node commands overlap and are not additive.

The parent ran the authored standalone Chrome probe. Its original frame discovery found no guest execution context and executed zero cases. A diagnostic confirmed an out-of-process iframe target. The parent changed only the probe to attach to that target and select its actual default guest realm. The repaired source probe passes eight cases against both the writer and receiving trees.

The browser cases cover unattended mount/timers, unrelated host clicks, duplicate consumption and later genuine clicks, stale and synthetic replay, an immediate promise, a nested synthetic shadow callback consuming a genuine click, prototype poisoning, and session closure. Bootstrap observation is checked with the mount case. The probe uses actual nested sandbox and action-adapter code, but intercepts persistence and native submissions. It makes no model calls.

## Attribution and limits

The writer is a private Codex `gpt-6-astra` xhigh Priority seat. Parent audit binds thread `01a1cb9c-f358-7473-9990-a52cf8ab765a`, exact cwd, successful completion, and58 complete frozen bodies. Configured effort and Priority are client-session receipts, not proof of hidden provider execution. The owner pinned Astra for these seats. Fresh-context source and comment reviews are same-model evidence, not cross-family review.

The parent removed exactly two added loader comment lines without changing executable bytes. The new test file remains byte-identical to the writer's file. Native event behavior is exercised in standalone Chrome, not yet in the installed Desktop package. Exact-package native dispatch, model response, and final release acceptance remain open.

## Retained receipts

Paths below are relative to `/Volumes/Expansion/Development/Build/living-spaces-r1/`.

- `run/recovery-r3-evidence/intent-red-r5/` retains the pre-fix test log.
- `run/recovery-r3-evidence/intent-browser-impl-r5/` retains the zero-case failed probe.
- `run/recovery-r3-evidence/intent-browser-diagnostic-r5b/` records the OOP target diagnosis and a timeout during teardown. That attempt is not a cleanup pass.
- `run/recovery-r3-evidence/intent-browser-receiving-r6/observation.json` contains the eight passing source-browser cases.
- `evidence/gate-intent-receiving-r5/receipt.json` retains the failed full replay.
- `evidence/gate-intent-receiving-r6/receipt.json` contains the clean full replay.
- `run/seats/intent-implement-r5/attempt-1/parent-audit.json` records writer attribution, reads, and source drift.
