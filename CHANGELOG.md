# Changelog

## 0.1.4

- Browse Spaces in a gallery. Each card shows a preview of the Space, kept only on this machine, with its icon, name and how fresh it is. An open Space gives the canvas the whole window, with floating controls, a notice dock and a Details sheet.
- Give each Space its own icon. The bot that builds a Space can generate one with your configured Hermes image provider. Living Spaces checks it when the Space is saved and falls back to a glyph, then a sigil. Without an image provider, Spaces keep a glyph icon.
- Read bot replies from Space controls as collapsed, formatted messages you can expand, copy, continue in chat or dismiss.
- Fix a storage warning that a full diagnostic log history could cause. Log history trims itself and never stops a write, so it no longer hides record, source or project warnings.
- Copy details never includes any part of a credential.
- When a Space is refused a permission, its error names the missing capability again. Inspection reads return the same outcome status as live reads.

## 0.1.3

- Inspect saved Spaces with screenshots, interaction checks, and clearer diagnostics when a view fails to load.
- Save and recover editor drafts. Read or edit multiple Space files in one tool call.
- Page through large record sets and see when individual sources last refreshed.
- See what uses storage and preview retention changes before applying them.
- Recover from uncertain upkeep runs without replaying edits. Keep the Spaces list current after pinning, archiving, restoring, or deleting a Space.
- Build with offline charting, Markdown, fonts, motion, and accessible controls. The README now shows three example Spaces.

## 0.1.2

### New and fixed

- Add optional, read-only runtime inspection with `spaces_inspect`. It runs a saved revision in a disposable local Chrome-family browser and returns a text report of runtime errors and visible content. It takes no screenshots.
- Fix per-profile loading so the plugin resolves its own package in the active profile rather than reusing another profile's modules.
- F1 preserves the execution reply if a later status check fails.
- F2 collects blobs referenced only by a deleted Space and preserves shared references held by surviving Spaces.
- F3 coordinates overlapping agent Refresh requests to reduce duplicate model work. Feed Refresh works beside an idle agent schedule while preserving the barriers around active or unknown agent work.
- F4 accepts up to 1,000 parsed feed entries while preserving the generic 500-record batch limit.
- Make scheduled feed updates and retries fetch fresh content instead of reusing terminal run results.
