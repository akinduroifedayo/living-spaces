# Spaces — full product specification v5

**Status:** proposed for Ife's approval; not authorization to build.  
**Owner:** Ife (product choices and final acceptance). Product owns this specification; design owns experience direction; engineering owns architecture, implementation and runtime verification.  
**Date:** November 10, 2026.  
**Canonical review home:** Kanban `t_0b4db0d1`, attachment `SPACES-SPEC-v5.md`. This proposed revision supersedes v4 on `t_848f5471`. The current commission [S4] removes deadline-led scope and ordering; approval remains with Ife.

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

**Reported by engineering [S2–S3], not independently rerun by Product:** the isolated installed Desktop build (`7f3ac61295`, Electron 44.9.3) supports the extension/storage path. The completed sandbox spike demonstrated a multi-file project, ESM/import maps, bundled Preact and lightweight-charts, local CSS/images, hash routing, saved notes/checkoffs across renderer reload and navigation, live agent-tool writes, manual refresh, no-agent cron refresh and agent-readable runtime logs. These prove specific paths, not complete product acceptance. Plugin storage was per profile; cross-profile ownership still requires an engineering solution.

**Landed mechanism [S3]:** nested opaque-origin sandboxed frames, strict CSP and a versioned per-mount MessagePort bound by the trusted host to one Space, with own-data, refresh and logs grants. Reported hostile probes blocked parent/top/host bridge access, cookies/browser storage/Node globals, HTTP/WS and tested navigation paths, cross-Space access, ungranted operations and forged host messages. The HTTP listener received no requests during those probes.

**Known failure — the no-network safety gate has NOT passed.** Forge demonstrated WebRTC STUN/TURN egress carrying a Space's own saved note to a listener. Chromium ignored the proposed WebRTC CSP restriction; frame-level removal was bypassable through a nested frame. This does not show access to host credentials or another Space, but it does allow disclosure of data that the malicious Space can read. Zero HTTP requests is not zero network egress.

**Product recommendation in v5: require verified closure before release; disclosure alone does not meet the permission promise.** Do not ship the current sandbox as satisfying no-direct-network enforcement. Forge's proposed host/Electron mitigations are unverified, require separate authorization and are engineering choices—not approved implementations in this spec. Retest WebRTC and the other boundaries after any fix; do not weaken the permission model or substitute a public-only demo for the safety gate.

**Still pending:** safe-hosting verdict covering the known egress gap; a real model-driven normal-chat turn (the spike lacked model credentials); persistence after a full Desktop/backend restart; stress/resource behavior; malformed/oversized messages; stale-session replay, cancellation and revocation lifecycle; and investigation of non-fatal Chromium origin-check errors during navigation probes. Hermes-side generated background handlers also need isolation and resource/permission enforcement. Moving generated code out of the frame must not create unrestricted execution authority. These requirements remain open unless subsequent engineering evidence explicitly proves them.

Project manifests, content-addressed storage/revisions and versioned structured records are architectural proposals, not a completed foundation. Engineering may choose different internals that satisfy the contracts. Forge stopped after the spike; no foundation was built. Feature build waits for Ife's v5 approval and a separately commissioned engineering scope. [S3–S4]

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

**The target is the full product in sections 1–3.** Releases follow dependency and user value, not a calendar, competition entry or demonstration length. Each release must be useful in its own right and retain earlier acceptance. Unfinished capabilities remain visible full-product commitments, not silently discarded scope.

### Dependency order

1. **Safe hosting:** close the known egress gap and establish the trusted/untrusted boundary in the actual Desktop environment. This is a gate, not a shippable release.
2. **Project model:** stable identity, owner, manifest, multi-file/assets, revisions and recoverable updates. Do not build a disposable single-file format to replace later.
3. **Authoritative data:** persistent structured state separate from code, conflict handling, coherent writes and recovery. Establish the shared contract before UI, chat and upkeep mutate it.
4. **Permissioned bridge:** bind requests to identity/session, enforce own-data/refresh/log scope and expose host-owned grants and errors. Connect the app to the established data model, not a parallel state copy.
5. **Useful application loop:** normal-chat creation/evolution, durable app use, manual and scheduled maintenance, diagnostics and repair. Qualify this complete loop as release 1.
6. **Broader capability and ownership, then portability and additional surfaces:** expand what applications can do without weakening their data or permission guarantees.

Engineering owns architecture and can overlap independent work; design can qualify interactions throughout. These dependencies express required outcomes, not a prescribed technical implementation.

### Release 1 — a dependable application you can live in

The first release lets a user build a real multi-view application in normal chat, use it repeatedly, trust saved data, evolve it without starting over and keep it current under explicit control. Research Desk is one acceptance example, not the product definition. Release 1 is not a prototype or demo cut.

**Included:** multi-file projects/assets and bundled libraries; discoverable index and application navigation; basic owner identity; normal-chat create/list/read/edit and data operations; persistent structured records; host-owned own-data/refresh/log permissions; recoverable project revisions; runtime diagnostics and repair; manual and approved scheduled upkeep; truthful freshness, failures, costs/limits and pause controls. Basic archive/delete must stop future upkeep from the first release. A scoped host-controlled public-source handler can serve initial refresh; it is not claimed to be general tool invocation or arbitrary generated background execution.

**Later, not rejected:** general in-app agent/tool/file requests, generated background handlers, cross-Space grants, cross-profile delegation/transfer, on-open/event triggers, full collection/portability workflows and web access. They depend on the foundation and have explicit later acceptance below.

**Prerequisites:** Ife approves v5; safe-hosting evidence closes the known gap; engineering confirms feasibility/test setup and legitimately available credentials for real-chat checks. Missing credentials are a named blocker—direct registry calls do not pass chat acceptance. Host changes, live-profile installation, shared-service restarts and publication need separate authorization. This spec task runs no code or schedules.

All checks below are requirements for future execution, not claims of completed work.

| ID | Required observation |
|---|---|
| R1-01 — safe hosting | In isolated real Desktop, a multi-file app navigates and uses local assets/libraries without CDN calls. Hostile code cannot read parent/host credentials/files, another Space or backend, or exfiltrate by HTTP, WebSocket, WebRTC STUN/TURN or navigation. External listeners and adversarial boundary tests verify enforcement, including fresh/nested frames. Unauthorized/spoofed bridge calls have no side effect. Investigate the spike's origin-check errors and record the final mechanism and remaining limitations. |
| R1-02 — real creation | A model-driven normal-chat request creates Research Desk and returns working Open Space. Index shows its owner; Overview, Library and Queue use shared structured records. No code-pasting or separate builder chat is required. |
| R1-03 — durable interaction | Add a record, save a note and change status in the app. Navigate away/reopen; values survive. Chat reads those same values and changes a selected record; the running app reflects the change without manual reload. Ambiguous target references do not mutate the wrong Space. |
| R1-04 — evolution and breadth | Normal chat adds a meaningful view/behavior to the existing project without losing saved records/preferences. A previous revision remains recoverable. Also create and evolve a materially different application, such as a planner or game, through the same path without Research Desk-specific host changes or fixed widget restrictions. |
| R1-05 — authority | Host-owned controls show scope and purpose of own-data, refresh and log grants. Denied refresh performs no fetch/write; cross-Space requests cannot bypass grants. Credentials are absent from app files, results and logs. A code revision gains no new authority silently. |
| R1-06 — correct refresh | Manual refresh updates public-source records with provenance/timestamps while retaining user notes/status. Fetch failure keeps last-good data with stale/error indicators. A stale concurrent edit conflicts or reconciles without silent loss; an interrupted multi-record operation leaves coherent state. |
| R1-07 — scheduled upkeep | With explicit authorization in isolated testing, scheduled upkeep updates durable data while the Space is closed; reopening shows change/run history, and an open view picks up subsequent writes. Show cadence/timezone, limits, next eligible run and pause controls. Pause/revoke stops future work. Offline/missed runs show truthful status and obey catch-up policy. Clean up test jobs. |
| R1-08 — restart and failure | Records, project, revisions and owner survive full isolated Desktop/backend restart. Failed writes never appear saved; interrupted updates retain the last usable project and coherent data. Resource-limit failures are visible/recoverable, not silent truncation. |
| R1-09 — repair | A controlled runtime error produces a bounded Space-scoped diagnostic. The maintainer repairs through normal chat without data loss. No other Space's logs or secrets leak. |
| R1-10 — restore | Restore prior code as a new revision without silently rewinding user records. An incompatible schema is blocked or migrated safely with a recovery point. Failed migration retains usable prior state. |
| R1-11 — lifecycle isolation | Reload/close invalidates old bridge sessions; revoked operations/results are not newly authorized. Malformed/oversized requests fail safely. Repeated refresh and retry do not multiply effects. A second independent Space proves namespace separation. Archive/delete cancel future upkeep and explain retention/loss. |
| R1-12 — everyday usability | Design qualifies keyboard use, readable forms, focus/navigation, and coherent empty/building/saving/saved/failed/conflicted states. In an observed return-use journey, the user finds the Space, completes useful work, distinguishes failure from success and requests a change without developer intervention. Engineering supplies real chat traces, tests and real-app evidence; Product reviews the promise and Ife retains final acceptance. |

Primary acceptance seam: **normal chat → real Desktop → trusted host → persistence/upkeep**. Add adversarial, restart, conflict and failure tests at the boundaries; screenshots cannot prove safety, persistence or real chat invocation. Release 1 requires every R1 check, not just a successful happy-path demonstration.

### Release 2 — more capable maintained applications

Build on the proven project/data/bridge loop: scoped in-app agent requests, named Hermes tools (including GBrain, web and MCP), user-granted files, explicit cross-Space access, bounded generated Hermes-side handlers, on-open/event triggers and richer run/data recovery controls. Complete multi-bot delegation and ownership transfer across applicable profile boundaries. These expand utility only once authority and data correctness can be preserved.

| ID | Required observation |
|---|---|
| R2-01 — scoped capabilities | Permitted agent/tool/file/cross-Space operations return results; denied, narrower-scope and revoked requests cannot escape resource/destination limits. Traversal/symlink and prompt-injection attempts gain no authority. Tool confirmations remain enforced; audit history explains outcomes. |
| R2-02 — maintained behavior | Generated handlers run under equivalent isolation, grants and cost/resource limits. On-open freshness does not launch duplicate work; filtered events deduplicate and cannot self-trigger forever. Missing connections/permissions produce recoverable blocked states, and cancel/retry does not duplicate effects. |
| R2-03 — ownership | Two bots maintain independent Spaces. Explicit delegation/transfer shows changed authority and pending-work consequences, inherits no broader permissions and works across supported profile boundaries. An unavailable owner leaves the app usable and owner-dependent work visibly blocked. |
| R2-04 — data recovery | Inspect data/migration history and restore deliberately with preview/recovery points. Concurrent UI/chat/upkeep writes preserve user work; restoration cannot silently undo external effects. Earlier release checks remain passing with the new capabilities. |

### Release 3 — a lasting collection of user-owned software

Complete search/grouping/pinning, independent duplication, portable import/export, explicit sharing semantics, revision comparison and polished recovery/organization workflows. These depend on stable identity, grants and versioned project/data contracts; they make accumulated work reusable rather than trapping it in one installation.

| ID | Required observation |
|---|---|
| R3-01 — organization | Find, rename, pin and group multiple Spaces without breaking references or ownership. Archived items are distinguishable and recoverable; archive/delete preserve the established upkeep-stop guarantees. |
| R3-02 — duplication and portability | Duplicate/export/import a substantial multi-file app with selected data/assets and compatibility metadata. New identity cannot mutate the original; credentials/grants/active schedules do not clone. Upkeep starts paused for review. Missing dependencies/compatibility fail intelligibly rather than losing data. |
| R3-03 — honest sharing and recovery | Sharing preview matches exactly the exported data and distinguishes snapshot from runnable application. Revision comparison explains a change; code and data recovery remain separate and preserve later history. No live collaboration is implied. Earlier acceptance remains passing. |

### Release 4 — authenticated web dashboard access

Expose the same identity/project/data model through an authenticated web surface after the Desktop contracts are established. Preserve capability mediation, freshness, compatibility and concurrent-write protection; do not quietly introduce public hosting, cloud execution or live team collaboration.

| ID | Required observation |
|---|---|
| R4-01 — access boundary | Authorized users reach only their permitted Spaces; unauthorized users cannot read or mutate them. Web entry never bypasses per-Space grants or leaks credentials. |
| R4-02 — consistent use | Desktop/web edits stay consistent; concurrent stale writes cannot silently overwrite work. Freshness/run status agrees across clients, including offline/reconnect cases. |
| R4-03 — compatibility | Desktop-only capabilities fail intelligibly or run through an explicitly connected authorized host. Absent runtime is shown as unavailable, not always-on service. Applicable prior-release acceptance passes on the new surface. |

Build progress must distinguish proposed, implemented and runtime-verified. User observations can inform refinement; changes to the promised full product remain explicit owner decisions rather than a deadline-driven cut.

## 5. Quality bar

The hackathon judging criteria are retained solely as product standards. They do not determine release dates, scope or demonstration length.

| Standard | What it means for Spaces | Acceptance evidence |
|---|---|---|
| Usefulness | Users build software for their own workflow, return to use it, evolve it and maintain the same data rather than collect disposable output. | R1-02–04 and R1-06–07 demonstrate the loop; R1-12 observes return use. R2-01–03 extend practical capability; R3-02 and R4-02 make work reusable across contexts. |
| Reliability | Saved means durable; refresh preserves user work; failure is honest and recoverable; granted authority is the actual boundary. | R1-01, R1-03, R1-05–11; R2-01–04; R3-02–03; R4-01–03. Known WebRTC egress must be closed, not waived by a polished presentation. |
| Polish | The application and host controls feel coherent, readable and navigable; users know where they are, what saved, what failed and what to do next. | R1-12 design qualification and observed use, R1-05 permission clarity, R1-08–10 recovery states; R3-01/03 and R4-03 extend this bar to collection and web use. |
| Creativity | Users can shape genuinely different experiences and evolve them through conversation; Spaces is not a fixed dashboard/template builder. This is creative utility, not a novelty claim against Muse Spaces or Grok Bot Pages. | R1-04 proves two materially different apps plus meaningful conversational evolution; R2-01–02 prove extensible behavior within grants; R3-02 proves substantial applications remain portable. |

Each release meets the bar for what it ships and clearly marks later capabilities unavailable; later checks do not excuse an incomplete first-release loop.

## 6. Demonstration — Research Desk

This is a way to show the finished product, not a scope definition or acceptance substitute. There is no target duration or date.

**Public content only:** publicly accessible research titles, abstracts and URLs, with clearly labeled demonstration notes/statuses. No private GBrain material, personal files, connected accounts or credentials. Use actual product behavior; do not stage fake tool success or present fixtures as live retrieval.

| Step | Action and narration |
|---|---|
| Create in chat | “Build Research Desk with an overview, searchable library and reading queue. Keep my notes and reading status.” Show the real creation response and Open Space. “I build it where I already talk to my agent.” |
| Use the application | Navigate Overview, Library, item detail and Queue. Show a bundled chart over the same records. “These are working views of shared data, not screenshots of an answer.” |
| Save and return | Save a labeled demo note and move an item to Reading. Close/reopen; show the retained state. “What I do here persists.” |
| Evolve with chat | Request a priority filter in normal chat, then use it. Ask chat for Reading items and show the edited item. “The agent develops the application and works with the same data.” |
| Show upkeep | Run permitted public-source refresh; show genuine outcome, provenance, freshness and retained note/status. Show a real approved scheduled-run record and pause controls only when verified. “It maintains source data without erasing my work.” |
| Show control and recovery | Open host-owned grants, owner and revision history; show a verified safe restore without rewinding current notes. Return to the index. “I choose what each Space can reach and how it is maintained.” |

If no new source records exist, show a truthful no-change run. If a live action is unavailable, explain the limitation or use a clearly labeled recording of an actual verified run, not an invented completion. A recording is not live evidence; any edits or omissions must be disclosed. The demo cannot establish safety or pass unfinished acceptance. Public-only content does not make the known egress gap acceptable for release.

## 7. Decisions for Ife only

1. **Approve v5.** Recommendation: approve the full-product definition, dependency/value-led releases and quality bar, including verified no-direct-network enforcement as a release condition. The existing permission promise should not be weakened to ship the current WebRTC gap. Approval is not an instruction to execute anything within this spec-writing task; feature build needs subsequent engineering commission, and host changes need their own authorization.
2. **Choose the public name.** Recommendation: provisional **Living Spaces** plugin / **Spaces** Desktop tab. “Cua Spaces” and “Spaces by Peakflo” already exist in the plugin catalog per the commission. Check availability before publication; “Living Spaces” is not asserted available or legally cleared. No rename or catalog write occurs here.

No additional discovery interview is required. Transport, module loading, datastore and sandbox mechanisms are engineering decisions to resolve and prove, not requests for Ife to design a safety workaround. If acceptance cannot be met, report the gap rather than shrink the product definition.

### Sources, status and execution boundary

- **[S1] v4 product baseline:** `SPACES-SPEC-v4.md`, attachment on `t_848f5471`, read November 10, 2026. Sections 1–3 retained except for the landed safety evidence. Its reference-vendor descriptions and catalog collision notice are inherited commission evidence, not fresh hands-on research or availability checks.
- **[S2] Render-spike evidence inherited through v4:** `t_ee67c0af` as summarized in v4. Supports extension/storage/update feasibility, not real chat invocation or blanket sandbox safety. Not independently rerun here.
- **[S3] Completed sandbox spike:** `t_4833de47`, final verdict/comment and completion metadata read November 10, 2026. Multi-file/bridge/update paths demonstrated; WebRTC egress demonstrated; full restart, real chat and stress remain unproven. Engineering stopped before foundation. Historical dates and build authorization in that card's original body do not govern v5.
- **[S4] Governing v5 commission:** `t_0b4db0d1`, read November 10, 2026. Ife removes hackathon time constraints, retains usefulness/reliability/polish/creativity as standards, and keeps feature build held for v5 approval.
- **Continuity:** GBrain retrieval found the prior v4 proposal and older entry framing under `projects/living-spaces`. Current [S4] supersedes their release framing. The card attachment remains the canonical spec; this revision is proposed, not owner-approved, implemented or verified.

**This task produces a specification only.** No feature implementation, prototype, schedule, install, external publishing or engineering acceptance is performed or claimed. Feature build remains held for Ife's approval of v5.
