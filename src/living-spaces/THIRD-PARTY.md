# Third-party offline shelf

This optional shelf supplies pinned files for the existing `_libraries` copy-on-request architecture. `runtime/vendor/SHELF.json` declares integration data only. It does not install packages, copy files automatically, select a theme, or change network policy. Each selected library must carry every file in its group, including its full upstream license.

All paths below are relative to `runtime/`. SHA-256 hashes and byte counts are in `vendor/SHELF.json`. Source URLs and SHA-512 integrity values identify the exact official npm tarballs. No lifecycle scripts or dependency installation were used.

## htm 3.1.1

License: `Apache-2.0`. Official source: [htm 3.1.1 tarball](https://registry.npmjs.org/htm/-/htm-3.1.1.tgz).

Integrity: `sha512-983Vyg8NwUE7JkZ6NmOqpCZ+sh1bKv2iYTlUkzlWmA5JD2acKoxd4KVxbMmxX/85mtfdnDmTFoNKcg5DGAvxNQ==`.

Selection key: `htm`. Total copied size including notices: 12,548 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/htm.mjs` | 1,207 | `dist/htm.mjs` |
| `vendor/licenses/htm-LICENSE` | 11,341 | `LICENSE` |

## lucide 1.71.0

License: `ISC AND MIT`. Official source: [lucide 1.71.0 tarball](https://registry.npmjs.org/lucide/-/lucide-1.71.0.tgz).

Integrity: `sha512-n6KHs0byHCG6fAQKBb+UhZtrUZM6v0ithDErPte6PkWkSijH0tPQoETnMobubUSj4okhAMeE6xUc/5S8LndrRg==`.

Selection key: `lucide`. Total copied size including notices: 1,125,371 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/lucide.mjs` | 1,122,163 | `dist/esm/lucide.mjs (bundled with esbuild)` |
| `vendor/licenses/lucide-LICENSE` | 3,208 | `LICENSE` |

The npm package declares ISC. Its complete LICENSE also includes the MIT notice and list of icons derived from Feather; both are retained. Lucide was bundled with existing esbuild 0.28.0, without minification, with inline legal notices and no external imports. The SVG namespace and license URLs are identifiers/documentation, not runtime network requests.

## @fontsource/inter 5.3.0

License: `OFL-1.1`. Official source: [@fontsource/inter 5.3.0 tarball](https://registry.npmjs.org/@fontsource/inter/-/inter-5.3.0.tgz).

Integrity: `sha512-RofMylZmjlJEfELXeNHFWBRcSs75rGU/6bV2S2jfnvv/3rPXPGe0LgUJTklcHZ9lM4OZmAVFhcJPnACfb91A3g==`.

Selection key: `font:inter`. Total copied size including notices: 52,828 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/fonts/inter-latin-400-normal.woff2` | 23,664 | `files/inter-latin-400-normal.woff2` |
| `vendor/fonts/inter-latin-700-normal.woff2` | 24,356 | `files/inter-latin-700-normal.woff2` |
| `vendor/fonts/inter.css` | 331 | `latin-400.css + latin-700.css (adapted relative URLs)` |
| `vendor/licenses/inter-LICENSE` | 4,477 | `LICENSE` |

Only Latin, normal style, weights 400 and 700 are included. WOFF2 bytes are unchanged. The readable CSS combines the corresponding upstream Latin CSS declarations, removes WOFF fallback, and points to adjacent WOFF2 files. Loading this CSS defines font faces; it does not apply a font family to any element.

## @fontsource/dm-sans 5.3.0

License: `OFL-1.1`. Official source: [@fontsource/dm-sans 5.3.0 tarball](https://registry.npmjs.org/@fontsource/dm-sans/-/dm-sans-5.3.0.tgz).

Integrity: `sha512-lYJtMXXO28q1z+yz+z8XKd0s4hXaa9QdkETzkyD760sidCv5heI86weYA0sx0Nc4pAMAQTUuyf4gO44cYKKS9g==`.

Selection key: `font:dm-sans`. Total copied size including notices: 33,389 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/fonts/dm-sans-latin-400-normal.woff2` | 14,200 | `files/dm-sans-latin-400-normal.woff2` |
| `vendor/fonts/dm-sans-latin-700-normal.woff2` | 14,348 | `files/dm-sans-latin-700-normal.woff2` |
| `vendor/fonts/dm-sans.css` | 339 | `latin-400.css + latin-700.css (adapted relative URLs)` |
| `vendor/licenses/dm-sans-LICENSE` | 4,502 | `LICENSE` |

Only Latin, normal style, weights 400 and 700 are included. WOFF2 bytes are unchanged. The readable CSS combines the corresponding upstream Latin CSS declarations, removes WOFF fallback, and points to adjacent WOFF2 files. Loading this CSS defines font faces; it does not apply a font family to any element.

## @fontsource/newsreader 5.3.0

License: `OFL-1.1`. Official source: [@fontsource/newsreader 5.3.0 tarball](https://registry.npmjs.org/@fontsource/newsreader/-/newsreader-5.3.0.tgz).

Integrity: `sha512-AFR6ZKY89GNL+9qBI2P2+66NhD5bhOj/v6fsLnFYLM4E0JnMB1yKb+Ro8cA64i1hwAWoBfTq5CHJGWH1toLDkw==`.

Selection key: `font:newsreader`. Total copied size including its license: 51,489 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/fonts/newsreader-latin-400-normal.woff2` | 22,480 | `files/newsreader-latin-400-normal.woff2` |
| `vendor/fonts/newsreader-latin-700-normal.woff2` | 23,796 | `files/newsreader-latin-700-normal.woff2` |
| `vendor/fonts/newsreader.css` | 693 | `latin-400.css + latin-700.css + unicode.json (adapted relative URLs)` |
| `vendor/licenses/newsreader-LICENSE` | 4,520 | `LICENSE` |

Copyright 2020 The Newsreader Project Authors. The full upstream attribution and OFL terms are retained in the license file. The family name is `Newsreader`. Its reading-text specimen uses `'Newsreader', Georgia, serif`.

## @fontsource/bricolage-grotesque 5.3.0

License: `OFL-1.1`. Official source: [@fontsource/bricolage-grotesque 5.3.0 tarball](https://registry.npmjs.org/@fontsource/bricolage-grotesque/-/bricolage-grotesque-5.3.0.tgz).

Integrity: `sha512-MdOVb/5in11IfN/IQJOExMuu6AroCIQbirl0yX7NUvKk+h0HYIKfGaVAXRS/gCPil4aFxWhjZnOw28tUwv7tFw==`.

Selection key: `font:bricolage-grotesque`. Total copied size including its license: 49,878 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/fonts/bricolage-grotesque-latin-400-normal.woff2` | 22,364 | `files/bricolage-grotesque-latin-400-normal.woff2` |
| `vendor/fonts/bricolage-grotesque-latin-700-normal.woff2` | 22,384 | `files/bricolage-grotesque-latin-700-normal.woff2` |
| `vendor/fonts/bricolage-grotesque.css` | 729 | `latin-400.css + latin-700.css + unicode.json (adapted relative URLs)` |
| `vendor/licenses/bricolage-grotesque-LICENSE` | 4,401 | `LICENSE` |

Copyright 2022 The Bricolage Grotesque Project Authors. The full upstream attribution and OFL terms are retained in the license file. The family name is `Bricolage Grotesque`. Its heading specimen uses `'Bricolage Grotesque', system-ui, sans-serif`.

## @fontsource/jetbrains-mono 5.3.0

License: `OFL-1.1`. Official source: [@fontsource/jetbrains-mono 5.3.0 tarball](https://registry.npmjs.org/@fontsource/jetbrains-mono/-/jetbrains-mono-5.3.0.tgz).

Integrity: `sha512-fqDfB5I9f1p1TV486aUgB9t8zP84P0O1FtQR5Ol9vjwPy+S+EIGlVYm1cvj2W5shcZMTg2nZFdVMoH5wFu8a1A==`.

Selection key: `font:jetbrains-mono`. Total copied size including its license: 48,309 bytes.

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/fonts/jetbrains-mono-latin-400-normal.woff2` | 21,168 | `files/jetbrains-mono-latin-400-normal.woff2` |
| `vendor/fonts/jetbrains-mono-latin-700-normal.woff2` | 21,908 | `files/jetbrains-mono-latin-700-normal.woff2` |
| `vendor/fonts/jetbrains-mono.css` | 709 | `latin-400.css + latin-700.css + unicode.json (adapted relative URLs)` |
| `vendor/licenses/jetbrains-mono-LICENSE` | 4,524 | `LICENSE` |

Copyright 2020 The JetBrains Mono Project Authors. The full upstream attribution and OFL terms are retained in the license file. The family name is `JetBrains Mono`. Its technical-text specimen uses `'JetBrains Mono', ui-monospace, monospace`.

### Selected font coverage and fallback

These three groups contain unchanged static Latin WOFF2 files in normal style, at weights 400 and 700. No italic faces, variable axes or non-Latin subsets are bundled. Their CSS combines the upstream Latin declarations, removes the WOFF alternative, uses adjacent relative WOFF2 URLs and `font-display: swap`, and declares the upstream `unicode.json` Latin range:

```text
U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD
```

This range describes the selected subset, not a promise of a glyph at every code point. Unsupported glyphs use the app's fallback stack and the platform's available fonts. CSS defines the faces without applying them. Apps must request a library key, link its CSS and set a fallback stack. Missing font files also use the fallback stack. `kit/font-shelf.html` has reading, heading, code and forced system-fallback samples, including Thai text outside the selected subset. Platform loading, unsupported-script rendering and missing-file layout still require runtime verification.

No new font is selected by default. The existing default kit CSS, modules and font payloads are unchanged. Full upstream license files travel with each requested family. The source version is the Fontsource package version, not the upstream font revision.

## Reproduce and verify

Use the pinned extracted Lucide tarball and an existing esbuild 0.28.0 binary. This command does not run package scripts:

```sh
esbuild .run/sources/lucide/package/dist/esm/lucide.mjs --bundle --format=esm --platform=browser --legal-comments=inline --metafile=.run/lucide-meta.json --outfile=.run/lucide.mjs
```

The submitted `runtime/vendor/lucide.mjs` is the exact output of that command. `htm.mjs`, WOFF2 files, and LICENSE files are exact upstream copies. Run `python3 scripts/check-shelf.py` from the repository root to verify the shelf. This is a development check and is not invoked at plugin startup. Hash verification detects drift against the manifest; it does not independently authenticate a manifest changed together with its payload.

## Existing vendor provenance gaps

The pre-existing modules are outside this shelf and remain unchanged. No complete pinned tarball provenance or full LICENSE copies for them were available in the inspected repository. They are not added to this shelf manifest.

- `vendor/preact.mjs` and `vendor/hooks.mjs`: the historical `docs/evidence/spikes/sandbox-spike-FINDINGS.md` records Preact 10.24.2. Exact artifact source URLs, tarball integrity, and full license notices remain unverified gaps; a historical version label does not authenticate the current bytes.

- `vendor/lightweight-charts.mjs`: its existing header identifies TradingView Lightweight Charts 5.2.1, copyright 2026 TradingView, Inc., and Apache License 2.0. The exact acquisition URL, tarball integrity, full license, and any additional upstream NOTICE remain gaps. No notice text has been invented.
