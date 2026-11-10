# Spaces — full product specification v4

**Status:** proposed for Ife's approval; not authorization to build.  
**Owner:** Ife (product choices and final acceptance). Product owns this specification; design owns experience direction; engineering owns architecture, implementation and runtime verification.  
**Date:** November 10, 2026.  
**Canonical review home:** Kanban `t_848f5471`, attachment `SPACES-SPEC-v4.md`. This supersedes v3 and its proposed cut on `t_63ccd42f`; that card is not an input to this specification.

## 1. The full product

### Definition and promise

**A Space is a persistent workspace you build and evolve with the agent in normal Hermes chat, then use in the Desktop Spaces tab. It can house anything you want to build: a dashboard, a full application, an internal tool, a planner, a game, a reading system or a document.**

Spaces brings Muse Spaces / Grok Bot Pages-style capability to Hermes Desktop as a plugin. There is no novelty claim. The product is not restricted to reports, predefined widgets, a single view, a single file or a fixed complexity tier. The sandbox is the security boundary, not a size limit.

A Space can grow from a document into an application with multiple views, navigation, files, assets, bundled libraries, structured records and background behavior without being recreated as a different product. Real resource limits still exist: storage, execution time and model/tool cost must be visible and recoverable. They must not become a concealed product definition that excludes substantial applications.

The user should be able to say **“Build this,” “Change this,” “What is in it?” and “Keep it current”** in the same normal chat they already use. They should not have to become the application's developer or operate a separate builder conversation.

### The problem and evidence

A chat can produce useful answers and code, but repeated work needs a place where structure, interactions and current information survive the conversation. The intended users are Hermes users who want software and workspaces tailored to their workflows, and want their agent to maintain them rather than deliver a disposable artifact.

- **Owner direction:** Ife explicitly wants the full capability, with no ceiling on size or complexity, and has rejected defining the product around a short build window. This is confirmed direction, not market validation. [S1]
- **Reference evidence supplied with the commission:** vendor material describes Grok Bot Pages as persistent chat-built reports/dashboards updated through Routines, with in-page controls that do not save; Muse Spaces as chat-built custom experiences including planners, trackers and games, shown in the sidebar, with persistent edits and background connected-app updates. These are vendor descriptions, not hands-on findings from this task. [S1]
- **Engineering evidence:** the Desktop extension surface and tool/cron-written storage rendering work in an isolated app instance. Safe arbitrary application hosting remains a separate evidence gate. [S2–S3]
- **Untested product bet:** people will return to, interact with and extend their Spaces rather than treat them as one-off generated output. Evidence against the bet would be repeated abandonment after creation, inability to trust persistence, or maintenance effort that pushes users back to external tools. Validate with observed create → use → return → change → upkeep journeys, not creation counts alone.

### How you build and live with a Space

1. **Start in normal chat.** Describe an outcome: “Build a reading system for public AI research, with a library, reading queue and topic dashboard.” The agent resolves only material ambiguities, creates the project and returns an Open Space action. The Space becomes discoverable in the Spaces tab; no code-pasting or separate in-page chat is required.
2. **Use it as software.** Navigate views, create and edit records, search, filter, use forms and controls. Saved input survives navigation, close/reopen and restart. The UI distinguishes saving, saved, failed and conflicted changes; it never labels volatile state as saved.
3. **Evolve it from chat.** “Add a calendar,” “Restyle this,” “Split this into three views,” or “Make the queue sortable.” The agent reads the existing project and data, changes the relevant files, checks the result and reports what changed. Existing records and preferences remain intact unless a destructive change is explicitly approved.
4. **Read and change its data from chat.** “What have I marked to read?” and “Move the selected paper to completed” operate on the same records as the interface. A chat response is not a second copy of the application state. Ambiguous Space references are resolved before mutation.
5. **Keep it current.** The user chooses upkeep rules and sees the owner bot, allowed capabilities, freshness and recent runs. Manual refresh, schedules, opening the Space and selected events can run maintained behavior on the Hermes side.
6. **Repair without starting over.** The agent can see scoped runtime errors and logs, reproduce a failure, propose a repair and apply a new revision. A failed update preserves the last usable version. Users can inspect change history and restore deliberately.

### What a Space contains

| Component | Product contract |
|---|---|
| Identity and manifest | Stable identity, name, description, owner bot, entry view, project metadata and compatibility requirements. Renaming never breaks references or changes ownership. |
| Application project | Many source files and assets, internal routes/navigation, bundled dependencies and library assets. Dependencies do not require arbitrary network access from application code. |
| Persistent state | Structured records, user input, preferences, relevant interaction history and source metadata. Application code and user data have separate lifecycles. |
| Permissions | Explicit per-Space capabilities, scope, purpose, approval status and revocation controls, enforced outside generated code. |
| Upkeep | Triggers, handlers, status, run history, last successful update, next eligible run and failure information. |
| Revisions and diagnostics | Recoverable project changes, data recovery points, migration history and scoped runtime errors/logs accessible to the maintaining agent. |

**Data correctness is part of the promise.** UI edits, chat writes and upkeep share authoritative state. Stale writes must conflict rather than silently overwrite newer work. Source refreshes update source-owned fields without erasing user-owned notes, checkoffs or classifications. Multi-record operations that must succeed together cannot leave a misleading half-completed result. Schema evolution requires a migration and recovery path; a code restore does not silently rewind current data.

### Example Spaces

**Research Desk — a full reading application.** Overview shows topic counts and source freshness; Library supports searchable records and detail views; Queue supports status, priority and notes. The user reads and edits in the app, asks chat to add a new view, and configures public-source refresh. New source records arrive without clearing reading status. This is also the proposed demonstration Space.

**Relationship workspace — a CRM shaped around the user's process.** Organizations, contacts, opportunities, activity and dashboard views share structured records. Forms, filters and linked detail views persist. Its owner bot can summarize activity or draft a next step. Connected-system reads or outgoing actions require their own grants; owning a CRM never implies permission to contact anyone. This is a product example, not permission to use real contact data in a demonstration.

**Project studio — an evolving internal tool.** Projects, milestones, board/list/calendar views, documents and decision history live together. The user asks the agent to add a workflow or change reporting. Approved events can update status; a second Space owned by a different bot can serve another workflow. Cross-Space data exchange requires a distinct grant rather than shared unrestricted storage.

Documents and games are equally valid Spaces. These examples demonstrate breadth; they are not templates that bound what can be built.

### Ownership, organization and surfaces

- **Owner bot:** each Space names one accountable maintainer. Different Spaces can belong to different bots. The owner is not the user's identity and does not own the user's data. Other bots gain access only through explicit delegation; ownership transfer shows the consequences for capabilities, credentials and pending upkeep. Transfer cannot silently inherit broader privileges. If an owner is unavailable, the Space remains usable; owner-dependent runs show blocked rather than disappearing.
- **Find and organize:** index with search, descriptive names, owner and status; pin favorites; group/tag Spaces; reopen the last-used view where appropriate. Empty, building, ready, updating, failed and archived states are understandable.
- **Duplicate:** create an independent identity and project, with a clear choice about copying data. Credentials, grants and active schedules do not silently clone. The copy starts with upkeep paused until reviewed.
- **Share/export:** export the project and optionally selected data in a portable package, with dependency and compatibility information. Preview included data and exclude secrets, credentials and permission tokens. A recipient imports into a new identity and grants capabilities afresh. Sharing a snapshot is distinguishable from sharing an independently runnable application; neither is a promise of live multi-user collaboration.
- **Version and restore:** inspect named revisions and what changed; restore code as a new revision without losing later history. Data restoration is separate, shows what will be replaced and preserves a recovery point. Undoing an external action is not implied by restoring a Space.
- **Archive/delete:** archive pauses upkeep and removes the Space from the active list without destroying it. Deletion is explicit, explains data loss and cancels future work; published/exported copies are not retroactively removed.
- **Desktop first; web dashboard later:** the same Space identity, project and data model should support a later web surface. Web access requires an explicit authenticated exposure model and equivalent permission enforcement; a Desktop Space is not publicly reachable merely because it exists. Concurrent clients must not lose writes. Cross-device sync and live collaboration need their own semantics before being promised.

## 2. Capability and permission model

### Trust boundary

Generated application code, bundled libraries and imported projects are untrusted. They cannot directly reach the parent Desktop page, Hermes backend, host filesystem, other Spaces, credentials, browser storage belonging to Hermes or unrestricted network destinations. The trusted host mediates authorized operations; hiding buttons or trusting a requested Space identifier is not authorization.

**Effective authority is the intersection of the user's grant to this Space, the executing bot's actual permissions, and the target tool's own policy.** A Space cannot use a bot as a proxy to gain authority it lacks. Data, web content and runtime errors are not instructions that can enlarge a grant.

### Capability families

| Capability | User-visible scope and behavior |
|---|---|
| Own data | Read/write the Space's own structured state; separate destructive data operations. Cannot enumerate another Space's records. |
| Refresh | Request an identified upkeep handler, not supply an unrestricted shell command or arbitrary privileged code. Shows queued/running/succeeded/failed outcome. |
| Diagnostics | Submit and inspect bounded runtime logs and errors for this Space. Redact secrets; logs must not become an exfiltration channel or grant request disguised as an error. |
| Ask the agent | Request a named task from the maintaining bot; show action, expected inputs and outcome. Return a result/status to the Space. This is not blanket permission to execute whatever a prompt requests. |
| Hermes tools | Allow named tools and operations with scoped arguments/destinations. Examples: permitted web retrieval, specified GBrain sources/read or write operations, selected MCP server tools. Having a connected tool does not grant all Spaces access to it. |
| User-granted files | Select files/directories with read versus write scope. Host-mediated access; prevent traversal and symlink escape. Do not expose arbitrary paths or host credentials to application code. |
| Cross-Space access | Explicit source, destination and allowed operations. Off by default; not a side effect of sharing an owner bot. |

The first bridge need not implement every family, but its contract must accommodate them without treating broad backend access as a shortcut.

### Grant lifecycle and user control

A permission request identifies the requesting Space, owner bot, capability, resource scope, purpose, whether data leaves the device and whether access is once-only or continuing/background. The trustworthy approval surface belongs to the host, outside the generated app. The user can deny, grant a narrower scope and revoke from a per-Space permissions panel. Denial produces an actionable unavailable state, not an endless prompt loop.

- Creation grants no outside access. Own-data authority is visible; external capabilities require consent.
- Changing application code does not confer new grants. New requested capabilities return to approval. Material changes to what an existing grant will be used for must be surfaced rather than hidden in a code update.
- Revocation stops queued/future operations and prevents unauthorized results from being newly delivered. Running operations are canceled where possible; already-completed external effects cannot be undone by revoking permission, and the user is told that limitation.
- Sensitive/destructive external actions retain the tool's normal confirmation rules. Approval to fetch public information does not authorize sending messages, purchases or account changes.
- Credentials remain on the Hermes side and are never bundled into project files, browser messages, logs or exports. A result may contain user data only within the approved task and destination scope.
- Requests have identity, revision/context, cancellation and bounded execution. Retries must not duplicate side effects. Unsupported bridge versions/capabilities fail explicitly; a reloaded frame cannot reuse an obsolete session's access.
- Audit history records which Space/bot requested which capability, approval and result, with useful redaction. Users can see why an operation was denied or failed.

**Direct network access is denied by default.** Public and connected data should travel through authorized Hermes-side retrieval. External links may be offered as explicit user navigation, not an application escape route. A future direct-network grant would require its own destination/egress policy and evidence; it is not implicitly approved here.

### Engineering evidence and pending points

**Verified by engineering report [S2]:** an isolated installed Desktop build (`7f3ac61295`) displayed a plugin Spaces sidebar row and full page, read plugin storage, and displayed registered-tool and no-agent-cron writes through three-second polling. This proves the extension/storage/update path, not application sandbox safety or real chat invocation. Plugin storage was per profile; cross-profile ownership is therefore a product requirement still needing an engineering solution.

**Proposed by Forge, not yet a landed verdict at drafting [S3]:** a project manifest with many files/assets, content-addressed blobs and revisions; versioned structured records; an opaque-origin frame; frame-local blob assets, import maps and hash routing; vendored libraries; and a versioned per-mount MessagePort bound by the host to a Space. Proposed initial grants are own data, refresh and runtime logs.

These are promising mechanisms, not a safety certification. The following remain **pending Forge evidence**: working multi-file/module and asset resolution under the actual Desktop CSP; real bundled-library execution; navigation; persistent bridge writes; external writes appearing in the running app; host/credential/other-Space isolation; no-network enforcement; bridge spoofing/replay rejection; and safe handling of oversized/malformed messages. Hermes-side generated background handlers also need isolation and resource/permission enforcement; moving code out of the frame must not create an unrestricted execution path.

Engineering may choose different internals that satisfy these contracts. No sandbox bypass is acceptable if the proposed mechanism fails. The latest instruction on the spike card is to finish the spike and stop; feature foundation work waits for Ife's approval of this specification. [S3]

## 3. Upkeep model

**Upkeep maintains the Space's useful state and behavior, not merely its visible page.** A run can retrieve data, reconcile records, compute derived values and execute approved application-specific background logic on the Hermes side while the Space is closed. Code maintenance is distinguishable from data refresh.

| Trigger | Contract |
|---|---|
| On demand | User requests a refresh from the Space or chat. Both invoke the same declared handler and permissions; repeated clicks do not create uncontrolled duplicate work. |
| Scheduled/cron | User approves cadence, timezone, owner, purpose and capability scope. The UI shows the next eligible run and provides pause/edit/disable controls. |
| On open | A declared freshness policy checks whether an update is due. Opening never secretly approves new capabilities, creates a schedule or repeatedly launches the same run. |
| Event-driven | Explicit subscriptions to supported sources/events, with filtering and deduplication. A data change must not produce an infinite self-triggering loop. |

Each handler declares inputs, expected outputs and allowed effects. Each run records trigger, owner, start/end, status, source timestamps, changed records and a useful error. Show **last attempt** separately from **last successful update** and from **source freshness**. Failed fetches leave last-known-good data visible with a stale/error indicator rather than presenting it as fresh.

Runs move through queued, running, succeeded, failed, canceled or blocked. Missing permissions/owner/connection creates a blocked state with a recovery action. Bound retries and backoff; do not retry destructive external effects without idempotency. Overlapping runs serialize or safely reconcile writes. Partial source failure is reported precisely and does not reset unrelated records. User edits win over refreshes to user-owned fields; conflicting writes require resolution.

If the host is asleep/offline, do not imply continuous service. Show missed/delayed work and apply the approved catch-up policy on return; default to one current refresh rather than replaying every missed interval. Background execution depends on the Hermes runtime being available. No always-on cloud service is assumed.

The user can inspect and pause upkeep without deleting the Space. Resource and model/tool costs should be visible before enabling recurring agent work, with limits and stop controls. Automatic data maintenance follows approved rules; generated code repairs or schema-changing migrations require a preview/revision and explicit approval by default. A future user-authorized automatic repair policy must be bounded and reversible.

## 4. Build sequence

**The sequence delivers the full product in releases; it does not redefine it.** The hackathon entry is release 1, targeting **Wednesday, November 11, 2026, 4 PM CT**. Dates in this section are sequencing targets, not evidence of capacity or permission to skip acceptance. If approval or safety evidence arrives too late, report an incomplete release honestly; do not narrow the product or mislabel a recording as proof.

### Release 1 — the working application loop

Recommend a complete vertical slice: build and change a multi-view application through real normal chat; use persistent structured records in the Spaces tab; maintain its data manually and by a deliberately approved cron path; inspect a runtime error; recover a revision. Ship the foundation as a project, not a single-file artifact with a later rewrite required.

Included: multi-file projects/assets with at least one bundled library; index and application navigation; own-data and refresh bridge; visible grants and runtime diagnostics; basic owner identity; chat create/read/edit/list and data operations; safe project revisions/restore; manual and scheduled upkeep with truthful freshness/failure states. First-release external refresh can use a host-controlled, explicitly scoped public-source handler rather than exposing general tool invocation to generated code. Initial own-data/refresh/log grants are not represented as a completed general permission system.

Not yet release-1 acceptance: general in-app agent/tool/file requests; cross-profile ownership transfer; event/on-open triggers; full organizing/portability workflows; web access. These remain full-product commitments in following releases, not rejected scope. A single capable demonstration application does not mean the product is limited to its domain or structure.

**Prerequisites:** Ife approves this spec and release sequence; Forge supplies a safe-hosting verdict; engineering confirms feasibility and test setup. Model credentials for a real chat test must be legitimately available in the isolated environment. If unavailable, record that exact blocker: direct registry calls do not pass chat acceptance. Separate permission is required for live-profile installation, shared-service restarts, publication or submission.

### Release 1 acceptance — tonight (Tuesday, November 10)

These are observable checks to execute after approval, not claims of completed work.

| ID | Required observation |
|---|---|
| T1 — safe hosting | In the isolated real Desktop, a multi-file application uses internal navigation, local assets and a bundled library without CDN calls. Hostile code cannot read the parent, host cookies/files/credentials, another Space or the backend, or make direct network calls. Unauthorized/spoofed bridge calls fail with no side effect. Engineering records mechanism and test evidence. |
| T2 — real creation | A real model-driven normal chat request creates Research Desk and returns a working Open Space action. The index lists it with its owner. Overview, Library and Queue share actual structured records, not separate decorative screens. |
| T3 — durable interaction | Add a record, change its queue status and save a note in the app. Navigate away and reopen. Values survive. Chat reads the same updated values, then changes a selected record; the running app reflects that change without manual reload. |
| T4 — evolution | Ask in normal chat for a meaningful view/behavior change. Agent reads and edits the existing multi-file project; the update works and previously saved records remain. The previous project revision remains recoverable. |
| T5 — authority visibility | Host-owned permissions UI shows current own-data, refresh and log authority. Denial of refresh causes no fetch/write; cross-Space requests cannot bypass the grant. No credentials appear in app files, bridge results or logs. |
| T6 — refresh correctness | Manual public-source refresh changes source-derived records with provenance and timestamps while preserving user notes/status. Failure retains last-good data and shows failure/staleness. A concurrent stale edit is rejected or reconciled without silent data loss. |

### Release 1 acceptance — Wednesday morning (November 11)

| ID | Required observation |
|---|---|
| W1 — scheduled upkeep | With separate explicit authorization in the isolated test environment, a cron-triggered handler updates public data while the Space is closed. Reopening shows the durable change and run record; an already-open view picks up a subsequent write. The user can pause it; paused work does not run. Clean up disposable jobs afterward. |
| W2 — restart and failure | Saved records, project files, revisions and owner survive a full isolated app/backend restart. A failed write is not displayed as saved. Interrupted refresh leaves coherent data and a truthful run status. |
| W3 — repair | Introduce a controlled non-security runtime error in test. The maintainer can retrieve its Space-scoped diagnostic, repair through normal chat and demonstrate recovery without losing user data. Logs do not expose another Space. |
| W4 — restore | Restore a previous project revision as a new revision. Current user records remain intact; an incompatible data schema is blocked or migrated safely, not silently corrupted. |
| W5 — isolation lifecycle | Reload/close invalidates stale bridge sessions. Revocation prevents subsequent operations, malformed requests fail safely, and repeated refresh does not multiply side effects. A second Space with independent records proves namespace separation. |
| W6 — usable evidence | Design qualifies navigation, forms, saved/error states and visual coherence as an application. Engineering supplies actual chat trace, test output and real-app evidence for T/W checks. Product reviews against the promise; Ife makes final acceptance. Public-only demonstration is rehearsed under 90 seconds. |

Test the user-visible path through normal chat → real Desktop → trusted host → persistence/upkeep as the primary acceptance seam. Supplement it with adversarial boundary tests and restart/conflict tests; screenshots alone cannot prove isolation, persistence or chat invocation. The known render spike is prior art for the extension path, not a substitute for any new application check.

### Following releases

**Release 2 — capable, dependable maintained applications.** Implement scoped in-app agent requests, named Hermes tool access (GBrain, web and MCP), user-granted files, bounded Hermes-side handlers, on-open/event triggers, richer run controls, data history/migrations and restore. Complete multi-bot ownership/delegation/transfer across applicable profile boundaries. Acceptance: permitted operations work; denied/revoked operations do not; background work has equivalent authority checks; unavailable owners produce recoverable blocked states; conflicting writes preserve work.

**Release 3 — a lasting collection of user-owned software.** Complete search/grouping/pinning, independent duplication, portable import/export and explicit sharing semantics, revision comparison and recovery ergonomics. Acceptance: a copied/imported substantial application runs with its selected data and bundled assets, carries no credentials or inherited grants, and cannot modify the original. Sharing previews exactly what leaves the user's environment. Archive/delete properly stop upkeep.

**Release 4 — web dashboard access.** Expose the same Spaces through an authenticated web surface with feature compatibility, capability mediation, concurrent-write protection and freshness controls. Acceptance: authorized Desktop/web edits remain consistent; unauthorized users cannot access a Space; Desktop-only capabilities fail intelligibly or run through an explicitly connected host. This does not quietly introduce public hosting, team collaboration or cloud execution promises.

Engineering and design may parallelize these outcomes after approval. The ordering expresses dependency and value, not a mandate to finish every item in one release before learning from users. Build progress must retain the difference between proposed, implemented and runtime-verified.

## 5. Demonstration — Research Desk, under 90 seconds

**Public content only:** use publicly accessible research titles, abstracts and source URLs, plus clearly labeled demonstration notes/statuses. No private GBrain material, personal files, connected accounts or credentials. Use a recorded real creation/evolution trace if generation takes longer than the demonstration; label time compression. Do not stage fake tool success or present fixtures as a live fetch.

| Elapsed | Action and narration |
|---|---|
| 0–12 seconds | In normal Hermes chat: “Build Research Desk with an overview, searchable library and reading queue. Keep my notes and reading status.” Show the real completed creation response and Open Space. “I build it where I already talk to my agent.” |
| 12–28 seconds | Open Spaces → Research Desk. Move through Overview, Library, an item detail and Queue. A bundled chart summarizes the same records. “This is an application with views and shared data, not a screenshot of an answer.” |
| 28–42 seconds | Save a public demo note and move an item to Reading. Close/reopen the Space; the same state remains. “What I do here persists.” |
| 42–57 seconds | Show a real normal-chat request that adds a priority filter, then use that filter in the app. Ask chat for the current Reading items and show the just-edited item. “The agent develops it and works with the same data.” |
| 57–72 seconds | Trigger the permitted public-source refresh; show a genuine result, freshness/run history and retained note/status. Show an actual scheduled-run record only if it passed acceptance. “It can maintain the data while preserving my work.” |
| 72–85 seconds | Open host-owned permissions/owner controls and the Spaces index. “I choose what each Space can reach and which bot maintains it. This one is a research app; the next can be whatever I need.” |

If the source has no new records, show a truthful successful no-change run and timestamp, not invented novelty. If live refresh is slow, use a labeled recording of the verified run rather than waiting unpredictably or claiming an unobserved completion. The application navigation, persistent input and conversational evolution remain the center of the demo.

## 6. Decisions for Ife only

These are owner choices, not requests for Ife to settle implementation details. No additional discovery interview is required.

1. **Approve the full product and proposed release-1 acceptance package.** Recommendation: approve the definition and application loop above, with the safety gate intact. This authorizes subsequent build planning only within the separately commissioned engineering scope; it does not authorize installs, schedules or publication in this spec-writing task. If acceptance cannot be met, report the release gap rather than shrink the definition.
2. **Choose the public name.** “Cua Spaces” and “Spaces by Peakflo” already exist in the plugin catalog, per the commission. Recommendation: use **Living Spaces** as the provisional public plugin name and **Spaces** as the in-Desktop tab label, subject to a catalog/name availability check before publication. “Living Spaces” is not asserted to be available or legally cleared. Ife chooses the public identity; no rename or catalog write is made here.

No decision is needed from Ife about message transport, module loading, datastore implementation or sandbox mechanics: engineering must resolve and prove those. Pending technical evidence is not an excuse to ask the owner to approve a safety bypass.

### Sources, status and execution boundary

- **[S1] Current commission:** `t_848f5471`, body and verbatim Ife scope corrections, read November 10, 2026. Authoritative for the product direction, requested structure, reference-vendor summary and name collision notice. No fresh vendor hands-on research or catalog verification is claimed.
- **[S2] Completed render spike:** `t_ee67c0af`, completion summary/metadata read November 10, 2026. Reports isolated real Desktop route/storage/polling evidence and explicitly excludes a model-invoked chat turn and live-profile installation.
- **[S3] Sandbox spike:** `t_4833de47`, architecture comments and latest stop-after-spike instruction, read November 10, 2026. At drafting the card was running and no verdict was present. Architecture proposals remain pending evidence as labeled above.
- **Continuity check:** GBrain retrieval surfaced the earlier v3 direction; the newer [S1] scope supersedes it. This document does not inherit its restricted product framing or its approval status. The card attachment is the spec's canonical home, not a parallel memory copy.

**This task produces a specification only.** No feature implementation, prototype, schedule, install, external publishing or engineering acceptance is performed or claimed. Feature build remains held for Ife's approval.
