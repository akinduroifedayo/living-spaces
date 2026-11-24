# Control access and keep ownership scoped

A user reviews a Space's grants, turns mediated Internet access off, and keeps work within its owning profile and conversation.

## Sub-features

- `access-internet` turns Internet access on and off with readback.
- `access-data-logs` grants, denies, and revokes own data and diagnostics.
- `access-audit` records permission decisions with actor and outcome.
- `ownership-profile` switches the active profile without retargeting an open Space session or stale card.
- `ownership-maintainer` binds and addresses the maintaining conversation through native context.

## How to get to it (user POV)

- Open a Space and choose **Permissions**, **Internet on**, or the blocked banner's **Review permissions**.
- Use the **Internet access** switch, request **Approve** or **Deny**, and **Revoke** controls.
- Read **Owner** and **Audit** in the Permissions drawer.
- Use Hermes's profile selector to change between separately prepared disposable profiles, then reopen Spaces or a saved chat card.
- Ask in the owning conversation to bind an existing unbound Space. A canvas bot button addresses that native maintaining context.

## Driving it with control-living-spaces

Preconditions:

- Doctor confirms the disposable home and profile. The Notebook fixture starts with the product's default grants.
- Cross-profile and native maintaining-session journeys need separately prepared disposable contexts. Do not use a live profile to fill that gap.

- **Permissions.** Run `"$C" click --out "$RUN" --value 'text=Permissions'`. Require the drawer titled **Permissions · Verification Notebook** and the correct owner.
- **Internet off.** Capture `before-internet-off`, then run `"$C" click --out "$RUN" --value 'button[role="switch"][aria-labelledby="ls-net-title"]'`. Require aria-checked=false, the WebRTC limitation, the success feedback, and the persisted revoked net grant plus audit row from `"$C" records --out "$RUN"`.
- **Reopen.** Close the drawer with `"$C" key --out "$RUN" --value Escape`, reopen Permissions, and capture `after-internet-off`. Require the same off setting.
- **Pending grant.** Use a Space that actually requests a capability. Click **Approve** or **Deny** and verify the matching stored grant and audit. No pending request is seeded here.
- **Revoke.** Choose the specific grant card's **Revoke**, then confirm. Require that capability unavailable in the canvas. Revoking Own data also removes the fixture's persistence precondition.
- **Scope.** Open only a separately prepared disposable second profile through the host profile selector. Require distinct lists and the old session's cleanup against its original owner. Capture both profile identities and read both disposable stores. This entry remains mapped only until two safe profiles exist.

## Gotchas

- Internet Off limits mediated fetch, not every outbound browser mechanism. WebRTC remains a disclosed limitation.
- A visible owner label is not proof of native maintaining-session binding.
- Turning Internet access off does not disable the bot's normal native tools.
- Do not call permission endpoints to stand in for a Desktop switch click.
- The fixture has no pending grant or second profile. Record those as precondition gaps, not passes.
