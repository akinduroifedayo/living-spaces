# Parent-owned Chrome form replay

Run this only in the parent's isolated Chrome fixture. The implementation seat
did not launch a browser or server. This uses the actual reference source, kit,
and sandbox with a synthetic in-memory backend. It proves no Desktop, durable
backend, model-chat, restart, or R1 acceptance result.

Start the existing `node tests/js/reference/smoke-server.mjs` fixture in the
parent environment. Open its printed URL with `?example=research-desk`, then
repeat on a fresh page with `?example=habit-planner`. Attach the parent's CDP
driver and locate the default host and innermost app execution contexts.

Import `replayForms` from `tests/js/reference/forms-replay.mjs` in the parent
Node driver. Supply these existing driver functions:

- `host(expression)` evaluates in the fixture page, awaits promises, returns
  values, and throws on CDP exception details.
- `app(expression)` does the same in the innermost sandbox frame.
- `cdp(method, params, sessionId)` sends CDP requests. Pass the top-level page's
  `sessionId` for input dispatch. Use a page viewport large enough to show the
  frame and controls.

```js
import { replayForms } from './tests/js/reference/forms-replay.mjs';
const receipt = await replayForms({host, app, cdp, sessionId, example: 'research-desk'});
// Persist receipt under .run/forms in the parent-owned checkout.
```

On failure, persist `error.receipt` too and keep the failed run separate from a
retry. The replay uses CDP mouse presses/releases, key events, and text insertion.
It does not invoke Preact handlers, `element.click()`, `requestSubmit()`, or
`space.put()` as an activation shortcut. It records trusted DOM events and
bridge write requests, checks the unchanged sandbox/CSP, and holds backend
confirmation to check pending state and duplicate suppression without a timer
race. It checks empty input, modifier Enter, click creation, plain Enter creation,
and Research Desk textarea newlines followed by an explicit save click.

IME composition, invalid control reporting, immediate duplicate callbacks,
failure, conflict, retained drafts, and retries also have offline component
coverage. That coverage is narrower than native browser evidence. The existing
fixture's chat edit, failed save, and refresh controls remain available for the
parent's broader replay. No actual replay result is recorded by this document.
