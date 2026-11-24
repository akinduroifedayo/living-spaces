# Living Spaces verification map

This is the maintained map of user-facing journeys, complementary to W31's formal models. Read [SKILL.md](../SKILL.md) before driving. The scoped Desktop driver is exercised on both pins. Product coverage remains partial and the native Desktop plus chat Refresh race fails on both pins.

## Baseline preconditions

- Product `4aea12db5375b30e90b5e0fa8f7d12ad7e0fdf98` (released 0.1.1), or the separately labeled exact candidate `8008dcc`.
- A manifest-owned disposable real Hermes Desktop; fresh home, user-data directory, OS home and cwd; existing installed host and venv; free loopback CDP 19432 rechecked immediately before launch.
- Only Living Spaces enabled in the disposable config. No model plugin, copied auth, or live profile changes.
- Prove runtime storage isolation, set the one Desktop decision with `flag_enable.py`, finish native onboarding, and require Doctor at a usable Spaces index. Spaces navigation can exist without a native inventory switch.
- `fixture` creates Verification Notebook through the shipped tool handler: one code revision, zero notes, default data/logs/net grants. It is setup, never chat/UI proof.
- The optional agent fixture declares a read-only agent-upkeep task for Refresh. No feed, recurring upkeep, maintaining-session binding, second revision or profile, pending grant, crash state, binary asset, or multiple views is supplied. Each affected journey must name the missing precondition.

## Driving conventions

Run the literal Launch block in SKILL.md first. It sets:

```sh
export C=/Volumes/Expansion/Development/Build/living-spaces-app-verification/.cursor/skills/verify-living-spaces/scripts/control.py
export RUN=/Volumes/Expansion/Development/Build/living-spaces-app-verification-evidence/manual-rerun
```

- The feature map calls that executable **control-living-spaces**. Commands use those exact environment assignments, not placeholder values.
- Prefer stable ARIA labels, `data-tour`, and exact native controls. CSS selectors must match one visible target; ambiguity fails.
- Every state-changing recipe starts on a new disposable run unless it says otherwise. Native chat/model, network source, cron and cross-profile setup require their actual safe preconditions and authority; do not silently supply live contexts.
- `guest-*` operates native input at observed sandbox-frame bounds. Save and reopen were exercised on both pins. Never use internal data setters or bridge method calls to fake the user action.
- Keep baseline/candidate evidence separate and use identity-owned teardown after every attempt, including failures.

## Proof and failure reporting

Record feature ID, entry point, command, exit status, action timestamp, before/result PNG and AX snapshots, visible result, read-only persisted side effect and teardown. Fixture creation and SQLite reads alone do not prove user interaction. Direct handler invocation is not native chat dispatch. A headless renderer is not Desktop pixel proof. An unreachable journey is **blocked/unmet**, not passed through a convenient alternative.

## Features

| Feature | Native and chat entry points | Current coverage |
|---|---|---|
| [Build, change, recover](author-and-recover.md) | Normal chat, Open Space card, Spaces card, History/menu, crash panel; candidate-only inspect tool | Native card and History exercised; candidate native inspection and explicit-stop cancellation demonstrated. Authoring and older-code restore remain unverified |
| [Canvas and records](records-and-canvas.md) | Input and explicit save button in canvas, leave/reopen card, maintaining chat, conflict/bot controls | Native save and reopen with matching SQLite passed on both pins. Shared chat, conflicts, batches, assets, and bot controls remain unverified |
| [Refresh and upkeep](refresh-and-upkeep.md) | Refresh now, Try again, guest refresh, Upkeep/menu, History, normal chat, Scheduled jobs | Empty Upkeep and unavailable Refresh exercised. Desktop twice creates one job. Desktop plus native chat reproduces two jobs and two model runs on both pins |
| [Access and ownership](access-and-ownership.md) | Permissions, Internet on, blocked banner, grant controls, profile selector, owning chat | Native Internet Off, reopen, and persisted revoke/audit passed on both pins. Other grant and ownership paths remain unverified |
| [Find and lifecycle](organize-and-lifecycle.md) | Sidebar, empty-state chat/prompts, search, filters, card, overflow, archived banner | Empty index, search, Archived filter, pin/unpin, archive/restore with records, and logical delete exercised on both pins. Other empty-state actions and attention fixtures remain unverified |

Each feature file has exactly four H2 sections: Sub-features; How to get to it (user POV); Driving it with control-living-spaces; Gotchas. The map covers discovered paths rather than declaring them complete because one path is convenient.

## Discovery anchors

The repository interview used `README.md`, `harness/app.py`, `harness/cdp.py`, `CONTRACTS.md`, the build-space skill/reference apps, `src/desktop/ui/{index,space,history,permissions,upkeep}.jsx`, sandbox and guest bridge, package tool schemas and core upkeep/lifecycle modules. Candidate inspection was read and exercised only from this workstream's separate candidate copy. Forge's active worktree/evidence and W31's formal tree were not used as writable fixtures.

## Maintenance

Use `/maintain-verification-skill` after changes to menus, native APIs, host plugin discovery, sandbox framing, tool schemas or ownership. Add the real entry-point proof before promoting a mapped-only row. No recurring maintenance job is created by this document.
