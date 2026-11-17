# Optional motion reference

`motion.mjs` exports `createMotionScope(root)`. The module has no import-time DOM access, framework dependency, vendor dependency, or network request. It uses native Web Animations API handles. It does not add layout animation, springs, gestures, persistence, or a focus policy.

```js
import { createMotionScope } from './motion.mjs'

const motion = createMotionScope(document.querySelector('main'))
```

The relative import above applies to another module in this kit directory. An app that copies the module to `kit/motion.mjs` imports `./kit/motion.mjs` from its root module. The kit index does not re-export this optional module.

## Scope and shell ownership

`root` is an element. A recipe accepts a connected element contained by `root`, including `root` itself. Detached and out-of-root elements acquire no work. An invalid root throws `TypeError`. A shell owned by another active scope throws an ownership error. Ownership lasts until removal cleanup or disposal, including after an animation finishes.

Each shell reserves its `transform` and `opacity`. A dedicated wrapper separates motion from caller-authored transforms, opacity effects, or other recipes. These recipes replace transforms rather than compose arbitrary transforms. Other styles and unrelated animation handles remain untouched. The scope restores the original inline transform, opacity, and their priorities when appropriate. Caller changes to these reserved properties during ownership are unsupported.

The scope has one entry per shell. A shell has one current recipe and one owned animation handle. Changing recipes settles the preceding recipe and invalidates its callbacks. Independent simultaneous effects require different shells.

## `press(element, down)`

`down` selects pressed or released decoration. Changed targets use a 120 ms scale transition. Equivalent targets do not restart motion. Pressed decoration remains until release. The caller supplies pointer and keyboard events, including cancellation, blur, and release outside the control.

The operation never disables the control, changes its text, sets `hidden` or `inert`, prevents default events, or waits before accepting an action. A native button remains responsible for activation. Decorative motion is not an activation lock.

## `present(element, { recipe, open })`

`recipe` is `disclosure` or `panel`. Unknown recipes throw `TypeError`. `open` selects the semantic endpoint.

| Recipe | Duration | Closed decoration |
| --- | --- | --- |
| `disclosure` | 180 ms | 4 px upward translation and zero opacity |
| `panel` | 240 ms | 12 px downward translation and zero opacity |

The first call settles without an entrance or exit. Repeating the same recipe and target is a no-op during motion and at rest. A mounted list can receive equivalent targets after refresh without replaying entrances.

Opening synchronously clears `hidden` and `inert`. Closing synchronously sets `inert`, then sets `hidden` only when the latest exit finishes. A reversal samples the painted transform and opacity before canceling the owned handle. Obsolete completions cannot hide or restyle a newer state.

The caller updates ARIA and restores focus before closing content that contains focus. The module neither moves focus nor supplies dialog, modal, menu, or disclosure keyboard behavior. Animating a shell does not make it an accessible control.

## `beginConfirmation(element)`

The return value is a one-shot reporter. Starting an attempt cancels an existing confirmation pulse and invalidates earlier reporters for that shell. Beginning an attempt does not animate anything.

The reporter accepts `confirmed`, `failed`, `conflict`, or `uncertain`. Only `confirmed` starts a 220 ms scale and opacity pulse. Every other value, including an unknown value, consumes the reporter without success decoration. Repeated reports have no effect. Different shells have independent attempts.

The caller supplies the authoritative outcome and all essential status text. The module does not inspect promises, interpret records, write data, retry operations, or turn an unknown result into success. In particular, resolution of `useSaveState.run` is not authoritative confirmation. That existing helper catches failures and returns `undefined`.

```js
const report = motion.beginConfirmation(resultShell)

// In the caller's current-session authoritative result handler:
resultText.textContent = 'Record changed. Review before retrying.'
report('conflict')
```

A stale reporter cannot animate after a newer attempt, removal, or disposal. This protects decoration only. The caller must also reject stale data and status updates in its own asynchronous handlers.

## Reduced motion and unavailable animation

The scope observes `prefers-reduced-motion: reduce` at creation and while mounted. Reduced motion skips movement. A live change to reduced motion cancels owned work and settles the latest semantic target synchronously. Turning reduced motion off does not replay anything. Later deliberate changes can animate again.

Absent or throwing WAAPI settles the latest endpoint without blocking input. Essential text remains caller-owned. These recipes animate only transform and opacity, with no per-frame component state, ambient loop, or polling timer.

## `dispose()` and removal

`dispose()` is idempotent. It cancels only owned handles, settles the latest presence targets, restores reserved inline decoration, releases ownership, removes the preference listener, disconnects the removal observer, and invalidates reporters. Later operations on the disposed scope do no work, apart from invalid recipe validation.

A document subtree observer releases detached or out-of-root shells and their owned descendants after DOM removal. Removal delivery follows normal MutationObserver timing. Scope operations also reject detached shells synchronously. A host must explicitly dispose its scope at unmount or session replacement. Removal observation does not replace that session boundary.

Cleanup never restores old `hidden` or `inert` snapshots over the latest requested presence state. A closing panel remains closed after disposal. An opening panel remains open. Teardown does not restore focus or change application records.

## Local fixture

[`motion-example.html`](./motion-example.html) uses this module through `./motion.mjs`, native controls, a non-modal panel, and a disclosure. It keeps 200 synthetic list rows mounted across manual refreshes. It includes panel reversal, a retained last-good list after refresh failure, and explicit save-result simulation controls.

The fixture has no persistence API. Its confirmed result is labelled as a simulation and updates only an in-memory snapshot. Failure, conflict, and uncertainty retain that snapshot and the visible draft. A stale-result control and a motion-session reset demonstrate caller guards alongside reporter invalidation. Page hide disposes the scope and aborts input listeners. Page show remounts after a cached-page return.

The example is source-relative, not a shelf registration or an installed-runtime qualification. Native behavior, actual persistence, performance, visual review, and assistive-technology acceptance require separate evidence.
