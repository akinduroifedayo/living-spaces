# Visual inspection evidence

Load this when you need geometry or pixels from `spaces_inspect`. The default
report captures no pixels.

For visual evidence, supply explicit `width` and `height` and `visual`, for example
`{"screenshot":true,"routes":[{"hash":"","landmarks":{"primary":"#primary"}}]}`.
Geometry includes the actual canvas, outer browser dimensions, landmark bounds and
overflow. Up to four fresh hash routes share a 1 MiB PNG cap and the total timeout;
each route has at most 10 seconds. Nonempty hashes need landmark selectors. A missing
landmark or other failure makes coverage failed or incomplete and discards all PNGs.
Images return inline only and are never retained in project files or records.
Pixels contain this Space's rendered data without secret redaction. Share only with
authority. `loaded` and measured geometry do not establish correctness or good design.
