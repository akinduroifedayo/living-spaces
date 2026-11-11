# Submission checklist

Lead with the definition: "I see spaces as an open canvas for your bots that live in Hermes." Open internet in the frame, file-by-reference, canvas-to-bot and premium design are in progress, not qualified; none is claimed below.

This is a private submission candidate, not a submitted or accepted entry. Forge
sets `PIN_40_CHAR_SHA_AT_FINAL_COMMIT` only after the final candidate's validator
run. Do not substitute a branch, tag, short SHA or the historical validation SHA.

Authority is the Hermes **Catalog submission** guide and its linked
`plugin-catalog/README.md` entry schema, read from the local Hermes checkout.
The tables below cover the guide's preflight, PR steps and all 18 admission rules.
The demo and Typeform are separate delivery gates requested for this lane, not
requirements invented for the catalog. Evidence status comes from
[the R1 ledger](../evidence/R1-STATUS.md).

## Entry and preflight

| Requirement | Status and evidence or next owner |
|---|---|
| Public HTTPS repository anyone can clone | **Pending Ife approval: public repo.** Keep `https://github.com/akinduroifedayo/living-spaces` as the current private URL. Forge verifies public clone access only after approval. |
| Owner or major contributor submits | **Pending Ife approval: catalog PR.** `maintainer: akinduroifedayo`; Forge verifies submission identity and repository ownership before opening. |
| Catalog name, repo, description, maintainer and community tier | **Done (draft).** [catalog-entry.draft.yaml](catalog-entry.draft.yaml); `name` and description match [plugin.yaml](../../src/living-spaces/plugin.yaml). No verified/official tier claim. Final name/lineage availability check is **pending Forge**. |
| Full 40-hex `sha` | **Pending Forge.** Required literal placeholder remains. [Checker](../../scripts/check-catalog-draft.py) accepts only that placeholder or 40 hex characters; acceptance of the placeholder does not mean ready for catalog CI. |
| Loadable manifest and entrypoint at the pin; correct monorepo subdir | **Done at historical candidate; pending Forge at final pin.** `subdir: src/living-spaces`; Python, Desktop and dashboard entrypoints are in the package. [Validation](../evidence/runs/validate-8724804/raw.log) passed at `872480426c70fb7cfac1eda3d0837809a66e6955`. |
| Matching tools, hooks, middleware and environment declarations | **Done (draft).** Checker compares the catalog mapping with the manifest's 14 tools, empty hooks/middleware and absent env declarations normalized to `[]`. Manifest host `capabilities: []` is a different schema; checker fails if that declaration changes and requires disclosure review. |
| Desktop surface, SDK use and truthful category | **Done at historical candidate; pending Forge at final pin.** `category: desktop`; `/spaces`, sidebar and `living-space` transcript card documented in [PR description](PR-DESCRIPTION.draft.md). Prior validator passed Desktop surface. Manual review is still required. |
| Matching SemVer floor and quoted version | **Done (draft).** `requires_hermes: ">=0.23.1"`, `version: "0.1.0"`; checker compares both. Prior validator parsed the floor. Forge reconfirms support on the submission runtime. |
| Truthful platform metadata | **Done (draft).** `platforms: [macos]`; existing qualification is macOS only. Linux and Windows remain unqualified. |
| Optional display metadata | **Done (draft).** Title and known issues provided. `docs_url`, image and onboarding omitted; README renders by default. No optional field implies a finished release. |
| UI screenshots in PR; optional catalog gallery limited to six GitHub-hosted images pinned to SHA | **Pending Forge.** Capture after Miro's design kit merges and final qualification. Populate `screenshots: []` with at most six approved final images. Shot/capture list in [DEMO-SCRIPT.md](DEMO-SCRIPT.md). |
| Local `hermes plugins validate <checkout>/src/living-spaces --install-deps` at exact candidate commit | **Done at `8724804`; pending Forge at final pin.** Exit 0, 16 passed checks, one private-import warning in [raw.log](../evidence/runs/validate-8724804/raw.log) and [exit](../evidence/runs/validate-8724804/exit). No new validator run claimed by this lane. |
| Fix failures and review every warning | **Pending Forge.** Historical run has no failures; private `cron.jobs` warning remains. A passing validator does not grant a public-surfaces exception. See rule 9 below. |

## Admission rules

| Rule | Status and evidence or next owner |
|---|---|
| 1. Human-merged gate | **Pending Ife approval: catalog PR**, then catalog maintainer review/merge. No automated listing or PR opened. |
| 2. Exact SHA pin | **Pending Forge.** Validate final candidate, then replace the placeholder with that exact 40-hex commit. |
| 3. No self-updating code | **Pending Forge final source review.** Draft does not advertise an updater. Project revisions change user-created Spaces, not the installed plugin. Catalog updates must use reviewed SHA-bump PRs and `hermes plugins update living-spaces`. |
| 4. SHA bumps are new PRs | **Done (documented process).** Any later version/pin update gets a new reviewed PR; re-pin screenshots/image URLs too. No later update claimed. |
| 5. Owner/contributor submission or maintainer sweep | **Pending Ife approval: catalog PR.** Submit as owner/contributor, not an unauthorized third-party listing. |
| 6. Capabilities match registrations | **Done at historical validation and draft check; pending Forge at final pin.** [Manifest](../../src/living-spaces/plugin.yaml), [checker](../../scripts/check-catalog-draft.py), historical declared-tools/hooks/middleware passes. |
| 7. Install security scan | **Done at historical validation; pending Forge at final pin.** Scan was `safe`; `dangerous` must fail, and any `caution` finding requires review. |
| 8. Desktop stays inside SDK | **Done at historical validator; pending Forge manual review.** Check final renderer for prototype patching, eval/new Function, unsupported dynamic imports, script injection, internal stores/markup mutation and raw bridge access. The validator alone does not cover every manual-review rule. |
| 9. No runtime overrides; public surfaces only | **Pending Forge and catalog maintainers.** Historical `no core override` passed. `living_spaces_core/upkeep.py` imports private `cron.jobs` and `cron.executions`. Reason and calls are disclosed in README/PR. The public automation blueprint cannot create/control a no-agent script job. Resolve the seam with maintainers; any upstream issue/PR needs Ife approval. Do not call this public-API compliant merely because validation warns instead of failing. |
| 10. Dependency security | **Done at historical validation; pending Forge final dependency review.** No Python dependencies declared; validation used Hermes constraints. Audit vendored JavaScript source/licenses and any changed dependencies at the final pin. If dependencies are added, use oldest compatible floors with upper bounds; release quarantine is recommended by the guide. |
| 11. Credentials through Hermes only | **Done for observed scope; pending Forge final review.** No plugin credentials required or stored. R1-05's [authority receipt](../evidence/runs/r1-05-authority/authority.json) checks secret redaction and absence in Space content. No claim that this proves every future integration; no direct credential-store access is allowed. |
| 12. Respect approvals and unattended runs | **Partial, pending Forge.** Upkeep follows the native-cron flow (A-03): chat creates an ordinary Hermes cron job and the Upkeep panel reads it live, with no plugin-side approval step and no Refresh grant. R1-05 (shortened), R1-06, R1-07 and R1-11 are being rerun; earlier receipts for the removed flow do not count. Catch-up remains open. The linked job runs with what an ordinary chat-created cron job gets, so no unattended prompt/approval bypass is proposed. |
| 13. Disclose risky behavior in README and PR | **Done (draft).** Both cover HTTPS feed hosts, profile/cron reads, schedule script writes, shell/subprocess distinction, worker threads/native cron, no stored credentials, no telemetry, local SQLite and verbatim WebRTC note. Revocation and deletion instructions included. |
| 14. Truthful compatibility/version | **Done at historical validator and draft check; pending Forge final runtime validation.** Matching SemVer floor/version and macOS-only qualification scope. |
| 15. No skins/forks of bundled plugins | **Pending Forge provenance review.** Candidate is Living Spaces, not advertised as a Nous-branded skin. Verify against bundled plugins before submission. |
| 16. One listing per lineage | **Pending Forge catalog/provenance check.** Verify no existing lineage/name collision. If derived from another listing, disclose origin and satisfy the material-difference rule; do not silently rebrand. |
| 17. Readable/scannable source only | **Done at historical safe scan; pending Forge final payload review.** Final tree must contain no compiled executables/libraries, WASM, Python bytecode, opaque archives or encoded code that evades scanning. The guide permits a necessary native component built from this repository's source in its own public GitHub Actions only with a verified build attestation tied to the pinned commit. A setup-time binary download must come from the upstream official source, be checksum-pinned and disclosed. Neither exception is claimed here. |
| 18. Password-manager vendor restriction | **Done / not applicable to this manifest.** No `browser_vault` login backend registered. Community tier does not authorize one. Forge confirms no registration change at final pin. |

## Opening, recording and submitting

| Requirement | Status and evidence or next owner |
|---|---|
| Add exactly `plugin-catalog/living-spaces.yaml` to `NousResearch/hermes-agent` | **Pending Ife approval: catalog PR.** Forge uses the final validated draft as the one-file change after approval. |
| PR states what it does, Hermes surfaces, rule 13 disclosures and UI screenshots | **Done text; pending Forge images.** [PR-DESCRIPTION.draft.md](PR-DESCRIPTION.draft.md). Final factual review required after integration. |
| Catalog CI clones the public repo at the pin and passes validation | **Pending Forge after Ife-approved catalog PR.** No CI receipt yet. |
| Maintainer reviews pinned tree and merges/requests changes/declines | **Pending catalog maintainers after approved PR.** Rules 3 and 9 design violations can be declined; no acceptance claim. |
| Pinned README and gallery render correctly on generated plugin page | **Pending Forge.** Verify relative links resolve to the plugin repository, and replace draft-relative links in the PR body with final pinned repository URLs. There is no separate published listing yet. |
| All R1 acceptance gates and final cleanup | **Pending Forge, Miro and Ife.** [R1-STATUS](../evidence/R1-STATUS.md) remains partial/pending. Do not promote fixture counts or the package validator to release acceptance. Rehearse uninstall in isolation; final scheduled test-job deletion remains open. |
| Public-content demo under 90 seconds | **Done plan; pending Forge recording and Ife approval: demo video.** [Shot list](DEMO-SCRIPT.md) totals 83 seconds. Final screenshots/footage follow Miro's design kit merge. Use arXiv/Research Desk and Pair Play only; label time compression and demo notes. |
| Hackathon Typeform | **Pending Ife approval: Typeform.** Forge prepares final approved repo/catalog/video links and checks the form's current required fields before submission. No form URL, completed submission or independently verified deadline is claimed. |
| Candidate handoff target | **Pending Forge.** User-requested target is Wednesday November 11, 10 AM CT. Publication actions above remain separately approval-gated. |
