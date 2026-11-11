The goal is a reviewed v6 canvas/file-reference candidate after credential and action-lifecycle repairs. This fresh Comment Sicko audit recommends **two comment-line deletions in one file**. It does not establish product acceptance.

I read `pins.json` first and all **28/28 complete shards**, including the full role definition, poteto-mode skill, Hermes adapter, model policy, historical report, scoped diff and supplemental test. All 28 shard hashes and seven reconstructed source hashes match their pins. HEAD matches `290744327f3f66f12cbc30a9a28d42e904fb14f4`. All ten scoped files match the source-baseline manifest; every diff addition matches its frozen-tree line.

The complete DELETE list follows. Line numbers refer to the unchanged frozen tree.

| Location | Exact comment to delete | Reason |
|---|---|---|
| [canvas-actions.test.mjs:221](/Volumes/Expansion/Development/Projects/living-spaces-wt/repair-comments-r2/tests/js/ui/canvas-actions.test.mjs:221) | `// This models transport and durable claims; it does not run native admissions or models.` | Internal fixture narration. `actionLifecycleFixture` visibly supplies in-memory maps, a synthetic answer and fake host methods. No permitted exception applies. |
| [canvas-actions.test.mjs:308](/Volumes/Expansion/Development/Projects/living-spaces-wt/repair-comments-r2/tests/js/ui/canvas-actions.test.mjs:308) | `// The planned trusted-host seam records a refusal, never a fabricated native receipt.` | Internal branch narration. The adjacent `reject` branch explicitly asserts no admission, records `refusal_reason` and settles the action. “Planned trusted-host seam” supplies no external constraint or public API contract. |

Delete those complete lines, including indentation and terminators. No replacement prose is recommended.

The complete KEEP list is empty.

Inventory was established from **422 added lines across nine diff files**, plus all **174 lines of `tests/python/test_canvas_refusals.py`**.

| Scoped file | Comments | Docstrings | Suppressions |
|---|---:|---:|---:|
| `src/desktop/ui/actions.mjs` | 0 | 0 | 0 |
| `src/living-spaces/dashboard/plugin_api.py` | 0 | 0 | 0 |
| `src/living-spaces/living_spaces_core/__init__.py` | 0 | 0 | 0 |
| `src/living-spaces/living_spaces_core/actions.py` | 0 | 0 | 0 |
| `src/living-spaces/living_spaces_core/db.py` | 0 | 0 | 0 |
| `src/living-spaces/living_spaces_core/file_refs.py` | 0 | 0 | 0 |
| `src/living-spaces/living_spaces_core/migrations.py` | 0 | 0 | 0 |
| `tests/js/ui/canvas-actions.test.mjs` | 2 | 0 | 0 |
| `tests/python/test_file_refs_suffix.py` | 0 | 0 | 0 |
| `tests/python/test_canvas_refusals.py` | 0 | 0 | 0 |

Reconciled totals are **2 inventoried = 2 DELETE + 0 KEEP**. Recommended deletions comprise two lines and two comment blocks. Proven keep-list exceptions total zero.

**MUST KILL flags total zero.** Nearby scoped code makes both comments redundant; their wording alone does not establish a structural defect.

Skipped existing commentary includes `migrations.py:112`, which is context rather than an addition. SQL strings, runtime messages, test names and assertion messages are executable content, not comments. The historical audit grants no acceptance to these new bytes.

Files touched and actual deletions both total zero. No tests, probes, builds or application code ran. Parent retains deletion, testing and separate correctness review.

Required inputs denied or missing total zero. A static inventory command using a heredoc was denied because the shell attempted temporary-file creation; the same read-only analysis succeeded without a heredoc. A parent preflight receipt was not supplied in this seat’s packet, so prelaunch success remains unverified here. This review supplies context independence, not cross-family independence.