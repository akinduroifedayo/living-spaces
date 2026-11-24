# Find, pin, archive, restore, and delete Spaces

A user finds a Space by name or owner, pins it, archives it without losing records, and deletes only an archived disposable Space after confirmation.

## Sub-features

- `index-empty` starts a new chat or copies a prompt when no Spaces exist.
- `index-find` searches names or owners and filters All, Needs attention, and Archived.
- `organize-pin` pins and unpins a Space.
- `lifecycle-archive` preserves records and pauses future upkeep.
- `lifecycle-restore` opens archived content again without resuming upkeep.
- `lifecycle-delete` confirms logical deletion of a disposable archived Space.

## How to get to it (user POV)

- Click the sidebar **Spaces** navigation. The empty state offers **Start a new chat** and example copy prompts.
- Use **Search Spaces or owner** and **All**, **Needs attention**, or **Archived**.
- Open a card. Choose **More Space actions > Pin Space**, **Unpin Space**, or **Archive Space…**.
- An archived view offers **Restore Space** and **Delete…**. Its overflow menu exposes those actions too.

## Driving it with control-living-spaces

Preconditions:

- Use only the manifest-owned disposable app. Start on the empty index before fixture preparation.
- Run `"$C" fixture --out "$RUN"` for card, pin, and archive journeys. Deletion must target only Verification Notebook.

- **Empty state.** Click `text=Spaces`, capture `empty-spaces`, and require **Build your first Space in chat**. **Start a new chat** must open normal chat or explicitly copy a prompt when the host cannot start one. Do not submit to an unconfigured model.
- **Find.** Fill `input[aria-label="Search Spaces or owner"]` with `Verification Notebook` through `"$C" fill --out "$RUN" --selector 'input[aria-label="Search Spaces or owner"]' --value 'Verification Notebook'`. Require only the fixture card. Search `No such W32 Space` and require the explicit no-match state, then clear the field.
- **Filters.** Click `text=Archived` and require **No archived Spaces** initially. Click All to restore the active fixture. The Needs attention entry requires a genuine failed, blocked, or crashed fixture.
- **Pin.** Open the fixture card, click `button[aria-label="More Space actions"]`, then `text=Pin Space`. Return to the index and require Pinned plus a persisted pinned value from `"$C" records --out "$RUN"`. Repeat for Unpin Space.
- **Archive.** Open More Space actions, click `text=Archive Space…`, capture the confirmation, then click `text=Archive Space`. Require the archived banner, absent canvas, unchanged note payload, and archived database state.
- **Restore.** Click `text=Restore Space`, require the canvas and saved note, and verify any upkeep remains paused. The fixture has no upkeep, so the schedule part is unverified.
- **Delete.** Archive the fixture again, click `text=Delete…`, capture the exact target name, then click `text=Delete Space`. Require the empty index and no active fixture rows in the database. This is logical deletion, not secure disk erasure.

## Gotchas

- The single-fixture seed has no attention state and no owner/name collisions. Those search/filter entries need additional user-created fixtures.
- Opening a Space writes last-opened metadata and opens a bridge session. Doctor must not navigate or open it.
- Archive and restore are not deletion. Never accept one as proof of the other.
- Product deletion does not guarantee byte erasure of blobs or backups. Do not assert secure erase.
- Do not delete live data to satisfy a cleanup check. Teardown removes the owned disposable home after evidence capture.
