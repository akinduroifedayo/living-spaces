# Q19 offline evaluation harness

Offline only. Nothing here calls a model or spends anything. Execution of the 72 generation sessions and
144 blinded judgments needs the separate Q19 decision in execution/APPROVAL-PACKET.md.

- briefs.json: the six SPEC briefs, each with an edit request and a deterministic oracle.
- fixtures/: public synthetic inputs, labelled as such.
- scripts/q19_eval.py: frozen plan (seeded, randomized, blind ids), oracles, list-price ledger with the
  packet's stop conditions, visual gate (ACCEPTANCE "Judge visuals") and time gate (failures kept in the
  denominator).
- tests/python/test_q19_harness.py: offline tests for all of the above.

    python3 scripts/q19_eval.py cost
    python3 scripts/q19_eval.py plan --seed <n>
    python3 scripts/q19_eval.py oracles

Not covered yet: the session executor, capture and blinding of artifacts, native persistence checks, the
non-kit and non-Preact compatibility fixtures, and packaged legacy/new/upgraded Spaces (all need N1/N2 or Q19 approval).
