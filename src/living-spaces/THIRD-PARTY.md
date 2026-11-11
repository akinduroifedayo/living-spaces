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
