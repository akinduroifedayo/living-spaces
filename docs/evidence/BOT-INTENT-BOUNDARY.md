# Bot requests require a click inside the Space

## Release 1 decision

On 2026-11-11 at 11:18 CT, Bjorn approved the bounded intent guarantee for R1 on task `t_d40eb81d`. The generated Space keeps its own button and `space.ask` call. There is no second Send control and no action-registration API.

A genuine click inside a Space can authorize at most one bot turn. The click is attributed to that Space, not a particular callback. Space code can use another click inside the same Space to start that one turn. Strict callback attribution is not claimed.

Mounting, timers, synthetic clicks without a genuine Space click, stale event replay, and unrelated clicks elsewhere in Hermes must not authorize a request. Private-port hardening and existing one-in-flight, rate, and deduplication checks are part of the implementation requirement. The source change is under qualification; this decision is not a pass.

The resulting request starts an ordinary native Hermes chat turn. Hermes's approvals and tool policy still apply to what the bot does. The plugin must not dispatch model calls or tools through a separate privileged path.

## Why strict callback attribution was rejected

The parent ran a standalone Chrome prototype using captured native event getters. A genuine Space click could enter a nested synthetic callback while the captured native `Window.event` still referred to the trusted outer click. A promise continuation also retained the tested checks in one observation. These counterexamples disprove the prototype's strict-callback claim, not the weaker Space-click guarantee.

Retained evidence is `run/recovery-r3-evidence/intent-probe-r5-settled/observation.json` in the release build directory. Other cases in those runs had missed-input problems, so neither complete prototype run is reported as passing.

## Proposed next-release control

A stronger optional design would let generated code register a bot action with its label, request text, and selected record references. A trusted shell-owned control inside the Space would render that action and submit on its single real user click. It would replace the generated ask button rather than adding a confirmation click.

The trusted shell would own event attribution, immutable request capture, single consumption, and private transport. Guest code would supply action data but would not hold the authority used to submit. Native Hermes chat and approvals would remain the execution path.

This design changes both the public API and control rendering. It needs product and design approval, accessibility and layout qualification, and adversarial tests of registration, stale actions, session closure, and forged messages. Bjorn explicitly excluded it from R1 because it could constrain what an agent builds. It is a next-release proposal, not an approved implementation.
