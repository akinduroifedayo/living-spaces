# Use a canvas and keep its records

A user saves input inside a Space, leaves, and returns to the saved value. Chat and the canvas address the same records.

## Sub-features

- `records-save` persists an in-canvas note through the real sandbox bridge.
- `records-reopen` retains that note across leaving and reopening.
- `records-shared-chat` reads and edits the same data in normal chat.
- `records-conflict` offers Keep my note, Use updated record, and Compare for a stale write.
- `records-batch` applies a multi-record change completely or not at all.
- `canvas-assets` renders local modules, bundled libraries, binary assets, and multiple views.
- `canvas-bot` submits one maintaining-bot request from a configured canvas control.

## How to get to it (user POV)

- Open **Spaces > Verification Notebook**. Type into **Note** and choose **Save note**.
- Choose **Spaces**, then reopen **Verification Notebook**.
- Ask in the maintaining chat to read or change the saved note.
- In a Space that offers a bot control, click that control and read the returned answer in the Space and chat.
- Use an authored multi-view app's own navigation, images, and forms. Those controls belong to that app, not a fixed plugin-wide template.

## Driving it with control-living-spaces

Preconditions:

- Doctor passes. Run `"$C" fixture --out "$RUN"` once in the new home. Fixture preparation creates no records and makes no model calls.
- The native **Spaces** navigation and the fixture card must be visible. An absent card is a failure, not a reason to inject a mount.

- **Open.** Run `"$C" click --out "$RUN" --value 'a[href="#/spaces?space=verification-notebook"]'`. Require the heading and Note input in the actual Space frame.
- **Type.** Run `"$C" guest-fill --out "$RUN" --selector 'input[aria-label="Note"]' --value 'W32 persisted note'`. Capture `"$C" capture --out "$RUN" --value before-save` before submission.
- **Save.** Run `"$C" guest-click --out "$RUN" --value 'button[type="submit"]'`. Require **Note saved**, **W32 persisted note**, and a host saved status. Capture `after-save` and run `"$C" records --out "$RUN"` for a read-only SQLite second view.
- **Reopen.** Run `"$C" click --out "$RUN" --value 'text=Spaces'`, then reopen the same card. Capture `after-reopen`. Require the note in the rendered guest and the same payload in the database.
- **Shared chat.** Ask `Read the saved notes from Verification Notebook, then change W32 persisted note to W32 edited note.` through the composer. Require the persisted changed record and a live canvas update. This is not covered by SQLite readback alone.
- **Conflict.** Two real writers must load the same current record revision. Save from one, then submit the stale second draft. Capture the conflict banner, choose **Compare**, then test **Keep my note** and **Use updated record** in separate runs. The baseline fixture has no existing-record editor, so this entry has an unmet app precondition.
- **Batch and assets.** Use the actual authored app controls and native chat tool calls. Require all changed records in the second view, local asset success, and each view's visible output. No canned response or API-only probe covers these entries.

## Gotchas

- The fixture proves only its own form, sandbox rendering, persistence, and reentry. It is not a complete product qualification.
- A success message alone is not persistence proof. Reopen and inspect a read-only second view.
- Fixture state starts with zero notes. Code revision changes and restore must not erase records.
- Bot controls require a native maintaining-session binding. The fixture deliberately has none, so bot requests remain mapped only.
- Never call `space.put` or a private store setter from the driver to fake a user save. Only the app's submitted form may write the proof note.
