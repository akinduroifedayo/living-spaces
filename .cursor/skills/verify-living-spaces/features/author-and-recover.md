# Build, change, and recover a Space

A user describes an app in ordinary chat, opens its card, requests code changes, and restores older code without rewinding saved records.

## Sub-features

- `author-create` builds a new multi-file app in ordinary chat.
- `author-open-card` opens the returned Open Space card.
- `author-edit` changes existing code, imports supported local assets, and preserves records.
- `author-recover` reads scoped diagnostics and restores code as a new revision.
- `candidate-inspect` observes an exact saved revision through `spaces_inspect`. This is candidate 8008dcc only, not released 0.1.1.

## How to get to it (user POV)

- Open a normal Desktop chat with the `living_spaces` toolset. Ask the bot to build an app.
- Click **Open Space** in the bot's returned `::living-space{id="verification-notebook"}` card.
- Open **Spaces**, then choose the Space card. Ask in the maintaining conversation to change that same Space.
- Choose **History**, or **More Space actions > History** at narrower widths, then **Revisions > Restore…**.
- A crashed Space also offers **Reload Space**, **Restore revision…**, and a copyable repair prompt.
- In candidate 8008dcc, ask the bot to inspect the revision it just wrote. There is no Desktop inspection button.

## Driving it with control-living-spaces

Preconditions:

- Complete Launch and Doctor in SKILL.md. The clean-home proof does not configure a model or a maintaining conversation.
- The scoped candidate follow-up used the disposable app's existing `nous/welcome` model for native inspection and interruption. Do not infer permission to configure another provider, sign in, or copy auth.

- **Chat creation.** Use `"$C" fill --out "$RUN" --selector '[contenteditable=true][aria-label=Message]' --value 'Build a Verification Notebook Space with a Note textbox and Save note button. Save notes to records. Return its Open Space card.'` and `"$C" key --out "$RUN" --value Enter`. Require a completed native turn and the card. This entry remains unverified without a configured model.
- **Card entry.** Run `"$C" click --out "$RUN" --value 'text=Open Space'`. Require the Space heading and a usable canvas. Do not substitute a route assignment or an API request for this click.
- **Code change.** In the same chat, submit `Change Verification Notebook to show a Notes heading. Keep all saved notes.` with the same composer commands. Require a new revision and the unchanged saved note after reopening.
- **History entry.** Open `button[aria-label="More Space actions"]` and click `text=History`, or click `text=Details` then `text=Open history`. There is no standalone History button in the island. Then click `text=Revisions`. Require a current revision and at least one older revision.
- **Restore.** Click the older revision's `Restore…` control, then `text=Restore as new revision`. Require a higher current revision and unchanged record payloads from `"$C" records --out "$RUN"`.
- **Candidate inspection.** From native chat submit a read-only request to inspect Verification Notebook revision 1 with the runtime tool. Require the stored `spaces_inspect` tool result, not a model summary. `candidate-journeys-01` demonstrated native dispatch and `loaded`. The separate `"$C" inspect --out "$RUN"` remains headless handler-only proof.

## Gotchas

- `fixture` prepares an app through the shipped tool handler. It does not prove natural-language authoring, model dispatch, Open Space card rendering, or maintaining-session binding.
- The empty fixture contains one revision. Restore needs a second code revision, created through the authoring path, not direct SQL.
- The clean fixture has no crash. Do not mark the crash recovery entry as covered by a normal History opening.
- Runtime inspection does not capture pixels and does not exist in released 4aea12d. A headless report is not Desktop visual approval.
- `candidate-journeys-01` demonstrated `/stop` while the native tool was visibly running. The stored tool response says explicit-stop cancellation, the SQL digests match, and the owned inspection processes disappeared. This does not qualify every timeout or interruption path.
