# Q19 offline evaluation harness

Offline only. Nothing here calls a model or spends anything. Execution of the 72 generation sessions and
144 blinded judgments needs the separate Q19 decision in execution/APPROVAL-PACKET.md.

- briefs.json: the six SPEC briefs, each with an edit request and a deterministic oracle.
- fixtures/: public synthetic inputs, labelled as such.
- scripts/q19_eval.py: frozen plan (seeded, randomized, blind ids; refuses without pinned SHAs, routes, effort,
  skills and environment), build and edit oracles computed from fixtures, a list-price ledger that bills
  long or unknown requests at the long-context tier and enforces inclusive token, tool-call and time limits plus
  the packet's stop conditions, a visual gate that is incomplete without every planned artifact and two reviewers,
  and a time gate that counts omitted builds as failures and never passes when everything failed.
- tests/python/test_q19_harness.py: offline tests for all of the above.

    python3 scripts/q19_eval.py cost
    python3 scripts/q19_eval.py plan --seed <n> --controls controls.json   # refuses unless every control is pinned
    python3 scripts/q19_eval.py oracles

Not covered yet: the session executor, capture and blinding of artifacts, native persistence checks, the
non-kit and non-Preact compatibility fixtures, and packaged legacy/new/upgraded Spaces (all need N1/N2 or Q19 approval).
