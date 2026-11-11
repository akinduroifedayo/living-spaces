# Mediated image helper qualification

The candidate adds `space.net.blob(url, options)` over the existing mediated `net.fetch` operation. The caller owns each object URL and its revocation. No direct frame network access, credential lookup, URL registry, or new bridge operation is added.

## Source and checks

The helper forces byte retrieval, preserves MIME and decoded bytes, rejects non-success HTTP status, and preserves typed bridge failures. Existing `space.net.fetch` behavior stays unchanged.

The parent ran nine new loader tests. The receiving-tree gate passed 395 Python tests, 125 grouped Node tests, 242 standalone Node tests, and 19 reference tests. The Node groups overlap and are not a combined unique test count. Both builds, the renderer graph check, and rebuilt-artifact parity passed. The source hashes below bind the tested bytes before commit.

- `src/guest/loader.mjs` SHA-256 `ab50a2b7e5609b74f0862e61d9f3863b7ca9f9ed07a001b1d8d4df70fbd1b257`.
- `tests/js/sandbox/net-blob.test.mjs` SHA-256 `003fc14ba2cb034c2889b0b41005191f804937a378546b045734699edb2f4cdf`.
- `src/living-spaces/guest/space-host.html` SHA-256 `43f860491aa3f5cb29687be730952b837cb8f7a27474424672087ddd837ecf33`.

A standalone Chrome run rendered a public Python logo through the packaged nested sandbox and real core bridge/network code, using a disposable store and custom HTTP transport. All seven checks passed. This proves that path, not native Desktop installation or final release acceptance. Failed probe attempts are retained separately, including frame-context and log-observer errors. The successful run reads the guest DOM directly for the revoked-grant result.

## Independent review

Fresh Astra/high reviewers completed the scoped comment audit and source review. The comment audit found zero comments or suppressions in the added helper and new tests. The source reviewer found no fixed-contract defect. Parent audits verified all 43 and 49 required input bodies respectively, unchanged reviewed source, successful completion, and client-recorded Astra/high/priority attribution. This is independent context under the owner's Astra-only pin, not cross-family review or proof of provider internals.

Retained build evidence is `evidence/gate-image-helper-r5-20261111/`. Browser evidence is `run/recovery-r3-evidence/image-a-browser-r5-dom/`. Reviewer receipts are `run/seats/image-comments-r5/attempt-1/` and `run/seats/image-review-r5/attempt-1/` within the release build directory.

Native qualification, final exact-head validation, promotion, and owner acceptance remain separate.
