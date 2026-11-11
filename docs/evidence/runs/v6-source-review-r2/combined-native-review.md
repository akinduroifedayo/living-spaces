**ISSUES — source readiness only**, for frozen commit `651892d8fdf260aa364e3e1411cd07198dcd3ee9`.

Paths below use:
- **S**: `/Volumes/Expansion/Development/Projects/living-spaces-wt/combined-native-review-v6`
- **H**: `/Users/ifedayoakinduro/.hermes/hermes-agent`

Findings are source-derived hypotheses for parent reproduction; I executed no tests or live acceptance.

1. **P1 — An obvious credential path remains importable.**  
   **S/src/living-spaces/living_spaces_core/file_refs.py:15–31,50–59,71–82** omits `.claude/.credentials.json`: neither its directory nor basename matches the deny tables, while the user’s home is an allowed root. Required behavior is refusal of known credential files; actual predicates allow this conventional credential-store path, including an alias whose resolved target is that path. Parent should reproduce with synthetic bytes at that relative location under a fixture home, through both create and write adapters, and require atomic rejection. This finding requires a finite path rule, not content scanning or detection of disguised secrets.

2. **P1 — One activation window can authorize later, sequential model work.**  
   **S/src/desktop/ui/actions.mjs:6,21–24,155–171** checks window-wide transient activation when enqueuing, then drains an unbounded promise chain without consuming or revalidating that authorization. **S/src/living-spaces/living_spaces_core/actions.py:94–121** coalesces only while an intent remains unresolved; after settlement, a fresh activation key receives a fresh native input ID.  
   Parent reproduction: enqueue several distinct keys during one activation window; expire activation; let the first admission finish before a coalesced request’s receipt check; drain subsequent queued requests. A later request can obtain another admission without another user activation. Required behavior is preventing unnoticed duplicate work from repeated activation or refresh. Actual spending is bounded to one unresolved intent, but can proceed sequentially from the same queued burst. This is not a request for an arbitrary cumulative-cost limit.

3. **P2 — Definitive refusal can strand the Space’s unresolved slot.**  
   **S/src/desktop/ui/actions.mjs:44–50,115–118,147–150,174–180** reports refusals without settling the previously persisted claim. **S/src/living-spaces/living_spaces_core/actions.py:100–121,138–140** therefore continues coalescing new requests into it; only a terminal receipt releases the slot. Retry preserves the rejected payload. Additionally, native `queue_full`, raised before admission at **H/hermes_state_runtime.py:163–168**, falls through to `unknown`.  
   Parent should reject a first submission with a definitive pre-admission error, then request different text. Required behavior is truthful refusal and recoverable new intent; actual behavior retains the old unresolved intent. Preserve conservative handling for genuinely ambiguous transport failures.

4. **P3 — Separate stale skill claim.**  
   **S/src/living-spaces/skills/build-space/SKILL.md:192–193** calls file references “future,” despite the implemented schemas and the skill’s current runtime guidance. Update this capability statement independently of product repairs.

The native source supports the intended identity distinctions. **H/hermes_constants.py:194–201** selects context-local home; **H/agent/tool_executor.py:1719–1720** supplies physical session and conversation separately; **H/agent/prompt_cache_scope.py:40–66** derives conversation lineage, including inherited child context. **H/gateway/run.py:3952–3957** separately binds session key, physical session and profile. **S/src/living-spaces/__init__.py:611–623** captures those identities. Native `session.resume` resolves the admission target; **H/gateway/session_authority.py:261–271** distinguishes logical admission owner from physical transcript tip.

The plugin retains and revalidates the exact registered route, checks native profile identity, attaches before submission, and correlates receipt target/admission fields (**S/src/desktop/ui/actions.mjs:26–89,120–150**). Its RPC names and shapes match the inspected native handlers. It does not use ambient `host.request`; submission enters native authority rather than parallel plugin execution. Stable IDs support replay; close guards suppress late dispatch/publication.

R1-14 source also supports descriptor-relative no-follow reads, identity/race checks, bounded reads, adapter budget preflight, transactional project publication, origin-only original/redirect provenance, and legitimate token-named assets. Packet logs report the repaired 49-case run and combined gates passing; these remain fixture evidence.

**Live gaps remain parent-owned:** a real chat-built canvas producing an answer or Space change through its maintaining bot with another chat/profile active; visible busy/offline/refusal behavior; native tool denial enforcement; repeated activation, refresh, replay and close behavior with observed spending. No Desktop/chat/production acceptance is claimed.

**Required shards consumed completely: 129/129. Denied or missing required inputs: none.**