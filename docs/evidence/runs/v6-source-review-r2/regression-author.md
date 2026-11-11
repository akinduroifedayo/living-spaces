Added regression-only coverage for safe asset imports and canvas requests that neither duplicate work nor strand refused intents. Only the two authorized files gained appended code. **Tests have NOT RUN.**

Added **10 tests**.

In [test_file_refs_suffix.py](/Volumes/Expansion/Development/Projects/living-spaces-wt/v6-regressions-author-r2/tests/python/test_file_refs_suffix.py), under `ConventionalCredentialStoreTests`:

- `test_create_refuses_claude_credentials_atomically`
- `test_create_refuses_claude_credentials_alias_atomically`
- `test_write_refuses_claude_credentials_atomically`
- `test_write_refuses_claude_credentials_alias_atomically`
- `test_tokens_css_imports_through_create_and_write`

In [canvas-actions.test.mjs](/Volumes/Expansion/Development/Projects/living-spaces-wt/v6-regressions-author-r2/tests/js/ui/canvas-actions.test.mjs):

- `one activation burst cannot dispatch new inputs after coalesced work settles`
- `a fresh activation after completed work admits a different input and payload`
- `definitive permission_denied settles refusal across reload and permits a fresh intent`
- `definitive queue_full settles refusal across reload and permits a fresh intent`
- `ambiguous transport loss remains unresolved across reload until exact-ID explicit retry`

Expected behavioral red, inferred from source, covers seven tests. Four credential cases should expose accepted imports and changed project state. The burst should submit two distinct inputs instead of one. `permission_denied` should leave its intent unsettled; `queue_full` should incorrectly report `unknown`. These predictions are not execution results.

The independent canvas fixture uses real `createBotActions`, native method shapes, separate activation-key and intent maps, and settlement that permits later fresh work. Its planned `reject` operation records refusal without fabricating admission or completion. “Test Behavior, Not Implementation” shaped the observable assertions. “Model the Domain” shaped the separate intent and admission stores.

Confirmed cwd and HEAD `a96bd3b1c797f03f47c50cd1f7385807389dffba`. Native preflight exited zero with parsed `status: verified` for all 621 baseline files. Final inspection verified all 41 packet hashes, 619 untouched baseline files, 12 untouched required source files, unchanged file inventory, and both original prefixes. `git diff --check` was clean.

Scope SHA-256 hashes:

| File | Original prefix | Final file |
|---|---|---|
| Python | `ce470d59fcc0990dc16e21dfc4723b332fe849897f29f19a7dc70b76494bb681` | `6279a6d641b61250da2c391a3f1fbdd3dda89dfa5113e2f388bf031dc9906ed2` |
| JavaScript | `c855bb882659e12634610323a71c462674fc4a3c5e8a578dde3364c5d9058c08` | `487758dc6b198347bb83d92db6016d5accccb7373a93923c078ee936c413b46b` |

The preserved prefixes contain 1,491 and 12,190 bytes respectively. The pre-existing delimiter correction remains untouched.

These are synthetic transport fixtures, not real native admission or model-spending evidence. Reload preserves the fixture store across adapters; it does not exercise backend restart persistence. The accepted window-wide transient activation limitation remains. No cumulative spending cap was introduced. Parent-owned execution and acceptance remain outstanding.