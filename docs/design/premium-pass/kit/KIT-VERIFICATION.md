# Premium canvas kit — verified handoff

## Revision and scope

Pushed branch: `miro/premium-pass`
Revision: `6000b735cd7b73d08ae1ba0b9c75f23145370c95`
Recovered canvas layer: `9a5d52daebffcd804e4d2800ef016c9a81bc1466`

`git push` succeeded; `git ls-remote origin refs/heads/miro/premium-pass` returned
the exact revision above. Worktree was clean after the push.

The new commit changes only five permitted paths: the design section of
`src/living-spaces/skills/build-space/SKILL.md` and four files under
`src/living-spaces/runtime/kit/` (CSS, gallery, guide and verifier). A scope check
compared the skill's prefix and suffix with HEAD before commit and found them
unchanged. No host, runtime bridge, manifest schema, reference app or production
store was edited by this task.

## Meaningful changes

- Ambition without a house style: start from task/mode, concept, material/light
  and signature. User design skills win; kit JS and visual CSS remain optional.
- Six material starting points now have **three different compositions**, not a
  weather dashboard recoloured six ways: sky/range plot, unboxed reading desk,
  and tactile tile workbench. SVG art is authored and public/generic.
- Concrete typography, imagery/generation, licensed web-image byte fetching,
  visualization, motion, state and mobile recipes. The guide separates current
  mediated network/binary capabilities from planned direct web/file-reference
  support and never enables a provider or spends quota.
- Fixed inherited token aliases freezing the base palette; fallbacks now resolve
  where used and preserve explicit inherited custom values when a material does
  not override them. Named display fonts are preferences, not shipped assets.
- Shimmer is opt-in. OS reduced motion and explicit `data-motion="none"` show end
  states and stop kit motion; reduced transparency gives solid panels.
- State previews put failure/loading feedback before the affected work, retain
  content at full contrast and expose working preview-recovery controls.

## Executed verification

```sh
node src/living-spaces/runtime/kit/verify-canvas.mjs --out /Volumes/Expansion/Development/Projects/living-spaces-wt/.tmp/premium-kit
node --import ./tests/js/reference/env.mjs --experimental-vm-modules --test tests/js/reference/compatibility.test.mjs tests/js/sandbox/theme.test.mjs
git diff --check
```

The final verifier process exited 0. Its JSON reports **57 passed checks**:

- 36 material/width/scheme combinations: six materials × 1440/390/320px × light
  and dark host preference. No horizontal overflow or runtime exceptions; all
  measured visible controls at least 44px. Checked body/muted/action/surface
  token contrast pairs all exceed 4.5:1. These fixed-scheme materials remain
  their chosen light or dark world under either host preference.
- Nine simulated empty/loading/error states, three keyboard-focus checks,
  native Space activation of a tile plus reset, Enter expansion of an abstract,
  and Enter disclosure of the exact-data table.
- A calculated seven-day range domain of −2 to 21°C, including the negative low;
  explicit motion opt-out; three CSS-200%-zoom geometry checks; inherited-token
  override regression; and reduced-transparency fallback.

**22 existing compatibility/theme tests passed**, covering confirmed saves,
failed drafts, conflicts, requery/subscriptions, refresh states and keyboard
creation alongside the base theme. The first invocation lacked the repository's
provided import resolver and failed to find `preact`; rerunning with
`--import ./tests/js/reference/env.mjs` passed without installing anything.

The local Chrome verifier initially needed an Enter character in its CDP key
payload and forceful shutdown of its own browser process. Both harness issues
were corrected; the final command returned exit 0, not merely a success print.

### Visual inspection and detector

Inspected all six desktop materials, three 390px ready compositions and all nine
state screenshots. Inspected native-pixel crops of the range chart, reading list,
tile workbench and enamel board text. The chart retains units, a shared scale,
direct low/high labels and a keyboard-accessible table. No observed clipping in
those captures. Fixed the default figure indentation, low-contrast board caption,
dimmed retained loading content and misplaced state feedback during the pass.

Ran Impeccable context and its requested manual detector once, using the bolder
and polish guidance for the scoped extension. Detector exit 2 reported two
blueprint-grid advisories and a zero-offset glow warning. The drafting grid is
intentional inside the optional blueprint material; the unused generic glow
helper was removed. No detector-clean claim is made; it was not rerun.
Independent read-only review found inherited alias and ambiguous future
file-reference wording issues; both were corrected and the alias regression is
in the verifier.

## Evidence files

`summary.json` enumerates **20 PNGs**: two recovered-gallery before frames, nine
current ready frames (six desktop and three 390px), and nine state captures.
`verification.json` contains the final 57 check records. Before frames show the
kit's recovered common weather layout, not the incumbent chat-built Spaces.
Ready captures are full-height at 2×; state captures are 390×1100 viewports at 2×
and intentionally show the state plus the start of retained content.

## Limits and downstream acceptance

This is an exercised **local synthetic kit specimen**, not evidence that normal
chat now generates premium output. No live weather, feed, generation provider,
remote image request, persistence, host permission change, cron or Desktop
integration was exercised here. No supplied private/personal data was used.
The existing save tests are automated compatibility tests, not real-host saves.

Browser-native 200% zoom, screen-reader reading, real touch, non-Chromium engines,
long/localized production content, arbitrary image/gradient contrast and the
host's actual sandbox remain unqualified by this task. CSS zoom checked reflow,
not browser-native zoom. Showcase completion and review of chat regeneration
remain with the pre-created downstream cards.

## Exact integration boundary for Engineering

Do not merge the whole premium-pass branch or replace the entire build skill:
that branch contains earlier reference/docs work and its runtime prose may lag
Engineering's newer capability changes. From `6000b735...`, take the four kit
files and transplant only the section from `## Design the canvas` up to (not
including) `## JavaScript-controlled forms` into the current skill, replacing the
old optional design section. Keep all runtime, tools, data and upkeep sections
from the current integration branch. The recovered CSS canvas layer is included
in the full CSS source at this final revision.

The source guide and gallery are **not copied automatically into a created
Space**: the existing spaces-kit library maps only its JS, CSS and Preact
files. They are package/source references linked from the design section.

Ready for Engineering integration and the ordinary-chat regeneration after the
integrated candidate actually loads this skill/kit revision. The critique card
supplies the three prompts; this task does not substitute hand-authored specimens
for that proof.
