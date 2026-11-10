# Sandbox document admission

Users build a multi-view app in normal chat and open it in Spaces. Its loader must run outside the privileged Desktop renderer. The shipped package must also pass unchanged Hermes admission.

## Caller and ownership

```js
const session = createSpaceSession({rest, sid, container, mount: mountSpace, onEvent})
await session.ready
session.postEvent('data.changed', page)
await session.destroy()
```

`SpaceView` keeps this call. `createSpaceSession` still opens the backend session, fetches the bundle, checks the revision, and mounts synchronously inside its existing try boundary. The bound `call` closure owns the Space id and session. Guest messages cannot select either.

```ts
type SandboxWire = Readonly<{format: 1; shell_srcdoc: string}>
type BundleWire = ProjectBundle & {sandbox: SandboxWire}
function parseBundle(value: unknown): {
  project: ProjectBundle; document: string
} { throw Error('not implemented') }
function mountSpace(container: HTMLElement, input: {
  bundle: BundleWire; grants: Grant[]; call: BoundBridge; onEvent: MountEventHandler
}): {postEvent(event: SpaceEvent, payload: unknown): void; destroy(): void} {
  throw Error('not implemented')
}
```

`parseBundle` is private. It rejects missing, extra, or incorrectly typed sandbox fields, unsupported format, and an empty document. It projects only the existing `space`, `rev`, `manifest`, and `files` fields into guest boot. The new sandbox field and backend session never reach the guest boot envelope. Preserve existing project validation at its current boundary rather than duplicating core business rules in the renderer.

```python
def trusted_document() -> dict:
    # Read only the fixed installed guest/space-host.html asset.
    raise NotImplementedError

async def space_bundle(space_id: str) -> dict:
    # Existing _run and core.bundle; append trusted_document().
    raise NotImplementedError
```

The backend adds `sandbox` to the existing REST bundle response. Core bundles, revisions, stored project files, manifests, agent tools, grants, and record schemas do not change.

## Synthesis decision

Candidate A is the refinement base, not implementation or release approval. It keeps document composition behind the existing bundle boundary. Candidate B contributes deterministic build-time assembly of one reviewable static guest document and importable source modules for direct test migration. The graft removes A's runtime document generation without adding B's route, public document loader, mount option, or asynchronous acquisition/cache lifecycle.

The installed backend is already trusted to bind the session and enforce grants. A shape check cannot prove document trust. Trust comes from the fixed SDK REST operation, the installed package's pinned reviewed bytes, and exclusive ownership of the producer. Project storage and request arguments cannot supply document bytes, a policy, or a filesystem path. The renderer does not evaluate, decode into executable renderer code, or import guest sources. It assigns the authenticated backend's fixed document only to the existing opaque frame.

B's compiled document hash would reject all skew, but it adds an asynchronous prerequisite to the mount boundary. That is not adopted. Compatibility uses the explicit wire format. Unsupported formats fail inside `ready`, close the opened session, and show a useful reinstall message. Keep format 1 only while the bridge/boot schema and immutable policy floor remain compatible. Bump it when either changes. Same-format implementation changes must preserve that contract. This is not a claim that every same-format byte sequence is interchangeable or safe without review.

## Exact file map

- `src/guest/loader.mjs` owns the relocated `projectResolver` and `spaceLoader`. Keep behavior unchanged, including local assets, computed imports, hash navigation, logs, and bridge events.
- `src/guest/document.mjs` owns the single CSP source, both document producers, and the shell relay. Move the actual existing functions here. It can import the loader because this module is build/test code, never renderer code.
- `scripts/build-sandbox.mjs` imports those producers and deterministically writes `src/living-spaces/guest/space-host.html`. The emitted document is plaintext and committed. Do not encode, split, or rename executable syntax to avoid a scan.
- `src/living-spaces/dashboard/_sandbox.py` reads that one literal installed package-relative asset and returns `SandboxWire`. A fixed sibling load in the loose-module adapter is allowed. No request/project lookup or runtime JS composition is allowed.
- `src/living-spaces/dashboard/plugin_api.py` augments only the existing bundle response. A missing or unreadable package asset produces a visible unavailable error, not a fallback document.
- `src/desktop/sandbox/index.js` retains host mounting, the port and grants, request validation, log limits, and `WEBRTC_NOTE`. It gains private wire parsing and loses all guest producer imports and definitions.
- Remove `src/desktop/sandbox/loader.js` in the same relocation. Do not leave a compatibility shim that can pull it into renderer dependencies.
- `src/desktop/ui/session.mjs` stops passing session bytes to mounting. `SpaceView` stays unchanged unless an observed error-display issue requires an explicit deviation.
- Rebuild `src/living-spaces/desktop/plugin.js` with the existing esbuild command and retain a metafile. A gate rejects every `src/guest/` or generated guest HTML input in the renderer dependency graph.

No new dependency, host patch, SDK hook, navigation URL, endpoint, permission, credential, service, or install is needed.

## Fixed invariants

Both frames retain `sandbox="allow-scripts"` and `referrerpolicy="no-referrer"`. Both receive the exact existing CSP before scripts execute. The shell remains free of project markup and supplies the immutable inner-frame navigation floor. Keep `frame-src 'none'`, ordinary-network denial, and `form-action 'none'`. The WebRTC limitation and exact disclosure remain unchanged. Do not add `allow-forms` to repair an app form.

Lifecycle remains created, booted, then terminal closed. Preserve duplicate-load handling, one-shot port transfer, Space-bound calls, revocation checks before result delivery, and suppression of late replies. Setup failure and destruction release acquired frames, ports, and listeners. Closing a session remains idempotent. Guest boot is `{type:'space-boot',v:1,bundle:project,grants}` plus the port.

## Required implementation repairs

1. Tests import relocated producers and loaders from their real modules. Mounting and browser fixtures use the exact emitted installed HTML. A test compares it byte-for-byte with fresh producer output. No second loader copy or test-only runtime is allowed.
2. Adapt the sandbox, UI, and reference fixtures to provide `bundle.sandbox`. Remove only their old expectation that guest boot carries a session. Retain host-bound session, wrong-Space, closed-session, revocation, late-result, and policy assertions.
3. Test every malformed/unsupported wire case, the useful error and backend-session closure, and the absence of `sandbox` and `session` from guest boot.
4. Create project files named like package guest assets and add marker text to request/project fields. They must never change the emitted shell document. Repeated document reads and repeated builds must be byte-stable. The installed artifact hash is retained for review, not treated as a network-safety proof.
5. Prove the renderer graph excludes guest code and run unchanged `desktop_surface_hits` and the full validator. No lint suppression or host validation change is allowed.
6. Preserve all current test identities and behavior assertions. Document mechanical import/fixture migrations separately from the changed guest-session expectation. App content, kit, grants, core, upkeep, build skill, and record tests stay frozen.

## Verification and remaining gates

Run the existing Python suite and the actual sandbox/UI/reference Node commands, with explicit TAP output for parsed Node results. The current parent baseline is 146 Python cases, 76 sandbox/UI Node cases, and 19 reference cases. Those are observations before this repair, not acceptance predictions. Keep direct process exits and ordered case identities.

Parent-owned Chrome and Desktop checks requalify both opaque frames, multi-view local assets/imports/hash routes, real chat-created apps, ordinary HTTP/WebSocket/navigation denial with external listeners, fresh/nested hostile frames, spoofed/cross-Space bridge requests, grants, reload, late replies, and near-limit bundles. Run the repaired reference form replay too. The old renderer's real admission failure remains the negative control. Do not mislabel fixture Chrome as Desktop or a green validator as isolation proof.

The package stays private. Promotion, design qualification, all R1 checks, catalog review, public visibility, and owner acceptance remain separate.

## Review record

Candidate hashes are A `f745d690cb4f823ebae2eda88b86eab4e199a3fe2c19c8b969d67e09b3afd16a` and B `c7dbae393dd002e1d6a649bf1b926b27bbfbb6138e9102a3f4383427cdecf378`. Parent provisional scoring preceded the judge. Fresh Opus read all 98 bound bodies with no denied inputs and recommended A. Its family overlaps B and its recommendation is non-binding. Parent selection rests on the smaller existing caller boundary, not model preference. Both designs converge on moving guest ownership and rejecting direct URL frames or renderer syntax hiding.

The parent accepted the judge's test-migration, skew-contract, deterministic-output, and build-graph findings. It did not treat B's thinner browser recipe as a weaker CSP mechanism; that is a verification-plan gap. The parent resolved the mixed-tree concern by byte-comparing the four load-bearing caller/adapter/bridge files against the frozen candidate base. The actual SDK `pluginRest` definition confirms plugin-relative namespace construction and profile-scoped host transport. Unchanged admission still needs execution on the implementation.

This is design synthesis and internal consistency verification only. No implementation or runtime pass is claimed here. Prove It Works keeps runtime gates separate. Laziness Protocol keeps the existing synchronous caller boundary. Model the Domain keeps the document producer and session authority separate.
