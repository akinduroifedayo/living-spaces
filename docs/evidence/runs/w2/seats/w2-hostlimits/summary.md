Implemented the focused sandbox repair across four allowed files.

- UTF-8 envelope limits now include numeric `limit` and `actual`.
- Local write failures emit `write-rejected` with the full error.
- Log limits return numeric errors; console truncation preserves the original count.
- `data.changed` requires a live data grant.

Verification: initial stock red was **84/93**; final regression run is **13/13**. Final full suite is **94/95**. The sole failure is the unchanged legacy assertion that conflicts with replying `invalid` to malformed-version requests.

Static guest build, syntax, whitespace, and `git diff --check` pass. UI integration, renderer rebuild, and real Desktop qualification remain parent-owned and unexecuted here.

Git staging failed because creating `index.lock` was denied. All changes remain **unstaged**, with no commit or push.

[Full report with exact commands, counts, tests, and scope](.run/hostlimits-report.md)