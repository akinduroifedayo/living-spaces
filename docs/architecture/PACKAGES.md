# Host-managed packages for Spaces

## Proposal, not release 1 behavior

Ife asked for a release 2 design note on November 10, 2026. Nothing in this document authorizes implementation or dependency installation. Ife decides whether this enters release 2.

The agent needs libraries beyond the curated offline shelf. Requiring the agent to paste every transitive dependency into a Space wastes context and makes provenance difficult to audit. Opening the frame's network policy would not solve package integrity and would weaken the current isolation boundary.

## Proposed request and receipt

A future host tool accepts a Space reference and an exact `name@version`. Scoped names remain valid. Tags, ranges, Git references, filesystem paths, arbitrary registry URLs, and credential-bearing URLs are outside the first proposal.

The durable receipt contains the requested package, exact resolved dependency graph, registry origins, tarball integrity, bundled-file hashes, licenses, import aliases, and resulting Space revision. The package list belongs to the Space and remains visible in host-owned UI. It is not inferred from source comments.

A proposed operation has these states.

1. Requested. The agent names the package and intended use. No package code executes.
2. Awaiting approval. The host shows the source, version, expected additions, resource limits, and permission consequences.
3. Resolving. The host resolves an exact dependency graph under the approved source policy.
4. Verifying. The host validates every downloaded archive before extraction.
5. Bundling. A separate bounded build process produces browser ESM without executing package lifecycle scripts.
6. Committing. The host writes the bundle, licenses, import aliases, and receipt in one new Space revision.
7. Succeeded or failed. Failure leaves the prior Space revision usable and exposes an actionable error.

The same request identifier must not create duplicate revisions after a retry. Approval binds the displayed package graph or its digest. A changed graph returns to approval.

## Isolation and integrity requirements

The sandbox does not run `npm install`. The host does not install packages into Hermes, a user's project, or a shared `node_modules` directory.

All downloads use a vetted public destination policy with checked redirects. Registry trust and tarball integrity are separate checks. A checksum from an untrusted source proves consistency with that source, not publisher identity.

Extraction rejects path traversal, symlinks that escape the workspace, device files, excessive expansion, and oversized archives. Builds reject Node-only entry points, native addons, and unresolved runtime imports. The initial tool never executes `preinstall`, `install`, `postinstall`, or package-provided build scripts.

Bundled output must work inside an opaque-origin Space without external module imports. A package does not gain Hermes tools, backend headers, filesystem access, or permission to another Space's data.

Time, memory, file count, archive size, expanded size, dependency count, and final bundle size need explicit limits. A timeout ends the owned build processes and records failure. These limits protect host resources rather than constrain app appearance.

License coverage includes transitive code in the bundle. Missing or incompatible notices block admission. No silent public-registry substitution or paid service fallback is proposed.

## Options for a future commission

A host-side deterministic browser bundler offers the smallest useful first implementation. It can reuse existing Space revision storage and the shelf's import-map conventions.

A remote build service adds credentials, cost, source disclosure, and another availability dependency. It needs a separate decision. Running arbitrary package scripts locally also needs separate security authority and is not part of this proposal.

This recommendation is not an accepted architecture. A future commission must prototype package resolution and opaque-frame execution before choosing the implementation.

## Acceptance evidence required later

The future tool needs tests for exact-version parsing, scoped names, dependency pinning, license completeness, malicious archives, native addons, resource exhaustion, cancellation, and retry idempotence.

Qualification must also exercise a real generated Space. The test installs an approved browser library, opens it offline, records its package receipt, restores the previous revision, and confirms that saved user records remain unchanged.

A package update must not change network or tool grants. An Internet access switch does not authorize package installation. Existing owner approval rules for dependencies and security changes still apply.
