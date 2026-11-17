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

## @observablehq/plot 0.6.19 (with D3 7.9.2)

License: `ISC`. Official source: [@observablehq/plot 0.6.19 tarball](https://registry.npmjs.org/@observablehq/plot/-/plot-0.6.19.tgz).

Integrity: `sha512-8Tg8+doIBDKTG6gL9Px7Tws+Tuni+bwjhaJufAKR3V8HFi2dtGQf57fH0UKwOrMYgjmEdX2PP1E4LIi7gyhgYw==`.

Selection key: `plot`. Total copied size including notices: 446,606 bytes (budget: 1 MiB).

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/plot.mjs` | 387,154 | `dist/plot.js + d3 7.9.2 ESM modules (bundled and minified with esbuild)` |
| `vendor/licenses/plot-LICENSE` | 59,452 | `LICENSE` of every bundled package, plus embedded jStat (MIT), quickselect (ISC) and ColorBrewer (Apache-2.0) notices |

Built with the repository's existing esbuild 0.28.0 as one minified browser ESM file with no external imports. Every tarball was fetched directly from registry.npmjs.org and its SHA-512 checked against registry metadata before use. No package manager, install script, package.json, lockfile or node_modules was added to the repository. `vendor/licenses/plot-LICENSE` holds the full license text of each of the 38 packages compiled into the file (ISC 34, MIT 2, BSD-3-Clause 1, Unlicense 1). d3-dsv's command-line dependencies (rw, commander, iconv-lite, safer-buffer) are in the npm closure but are not bundled.

| Bundled package | Version | License | Integrity |
| --- | --- | --- | --- |
| @observablehq/plot | 0.6.19 | ISC | `sha512-8Tg8+doIBDKTG6gL9Px7Tws+Tuni+bwjhaJufAKR3V8HFi2dtGQf57fH0UKwOrMYgjmEdX2PP1E4LIi7gyhgYw==` |
| d3 | 7.9.2 | ISC | `sha512-ZKb/mONPVKzaO5UlcWcwN8bS4ezvQaYu+bsou+XgNABdGC800kwH651ADTbbTxMPHW13UlvbQafdmJQDk1w7Mg==` |
| binary-search-bounds | 2.0.5 | MIT | `sha512-H0ea4Fd3lS1+sTEB2TgcLoK21lLhwEJzlQv3IN47pJS976Gx4zoWe0ak3q+uYh60ppQxg9F16Ri4tS1sfD4+jA==` |
| d3-array | 3.2.5 | ISC | `sha512-Th8qGXoBalmWsstpkuhmBuTsBQIFqYOJtjlBvNVvBfJ8E3uYusBUwUR8HU20U0qKKQkgCvKyR1YjiozWadk5QA==` |
| d3-axis | 3.0.1 | ISC | `sha512-E5QCXfaf/uJZEHHiqoWRq+bQEm2PzoVFv2rDC7CZ3wwI0MjfMW3w83J3ubobG4IJj3lShAI5eiPJhOu/8wHofA==` |
| d3-brush | 3.0.1 | ISC | `sha512-L5Glqa/Gb7LU3ndIOMtA5mDzlJ0aXKp5ELP2X09ctWF23jO7+faIUVDbmaIi+D6k3EemXFWn1F3lkfguExoVhA==` |
| d3-chord | 3.0.2 | ISC | `sha512-cGmADo5M2PTi3ewJZ2lcE32eURd4JmHtQ5JwRIUcas5L1SXqufG9yPyjWp8fW0gRi7aZi9bgbZPFZO1eyZ+1CQ==` |
| d3-color | 3.1.1 | ISC | `sha512-lfab8x0Bj0UO7SNsY8dZSbNIA6ipbkE3X0NG9nqjCu6CfCHZseuDnOSJY7hidKrjpP++i1M2qT+FlAdPKYRilA==` |
| d3-contour | 4.0.3 | ISC | `sha512-5DYURc8KwXPOhSUBblU0P9rVcArsSPxPOxsfO0Eud0s28oU0sB2e80aRHRL9AZW3usT8ikFKyIHpHHLNWLdRVA==` |
| d3-delaunay | 6.0.6 | ISC | `sha512-DMQIEvSJhZCB6pwedcXaAlQ+MeKU5LlM2XakKtc73b/VM+RBiI1SRXycOEOKg2jsKj4zZ9F0KGYG6nCGwwWu/g==` |
| d3-dispatch | 3.0.2 | ISC | `sha512-sAzH4Y4nsLo8eSqw5jKiZt+LU2wZmL/qS+OkxQGjhwazB/D7TY34R/QK1eshfGr7cZEKymKZ/Haem7m+lu98Sg==` |
| d3-drag | 3.0.1 | ISC | `sha512-OWeoayCq8J69hUIjvL+Mb6Q6Oaj/fyHV5XaXByEUAG+JUjIfTGDnk3qGpcXrD3VmQ3BSV96fcbM6fqq7C0tbPA==` |
| d3-dsv | 3.0.2 | ISC | `sha512-FUnXhX7I4/AXyRCZzwfZTDGSq8PGZ4oR0tiCBqNGOZMsDrQ+6sIWNQnBzcCGhzJKZ6uCvCezTwflUqI209RRiQ==` |
| d3-ease | 3.0.2 | BSD-3-Clause | `sha512-B5znKqRmKROAN4oHWQ50W/qisVjA9GXh2WMsVKdFVp4DxWmcrOsweqgUOUVsv5th96kwaZlokU6SlV4J3gak1w==` |
| d3-fetch | 3.0.2 | ISC | `sha512-1wGF62bgjMRbF6mqbD+6rRWBL2hwWVYQjFO2UP3Wm1nIAvJZKaQxXM5caVY7athoCa8wIq9lCf7g44lPWFk50g==` |
| d3-force | 3.0.1 | ISC | `sha512-kAaaHLFebBYwgi5cYBXAI8vKrQFMCD2MEswj2QuPKKbdU1wYLc8WXtS7O8F/b6POCIe3gJjY6hkDstHi1yMETQ==` |
| d3-format | 3.1.3 | ISC | `sha512-+F+/49swqmGuQJmSKnVMIDH/QkEFV5li9QRj0xm/KhyAUBv099O5PrvpQFxBp24PYph17Mnvt9mjKQV0ii0nMA==` |
| d3-geo | 3.1.2 | ISC | `sha512-5R8ZgDQorIxmauv7R6gpE/ndz+Z0qAZssigq0aXFdvPHdY41RqtW02jrRUQAL724NdPABYXo1+gQEGBBr7uKNg==` |
| d3-hierarchy | 3.1.3 | ISC | `sha512-GRajN5ZcnEwYFWqqdzhG1qJ3+fDg6WWzk47TJg7ePY7yvYAgRfD2r1mUx+wviBOWuCwamCUzjwMSdato43jbGA==` |
| d3-interpolate | 3.0.2 | ISC | `sha512-IRzGU62DtxhvsnSTWMQIdnoZ6gA+BCWwBon1EJI6SjoN595799b6z/QRBzXfFhE8iupUPp3042yBNo0STPqnzQ==` |
| d3-path | 3.1.1 | ISC | `sha512-jsbgV8zIT38ReB9O7X7gcLndTQRONSqNNd+oGIaTBdUug4r5jFmp0N6RY9R5GWbdUDucn0qoTGyfjapT4tDhcg==` |
| d3-polygon | 3.0.2 | ISC | `sha512-WAUvPudGU1Dn4mDPfb6+JnnbeVEV53hG/BoT+bxts6AkZsOpTEiV1jHYX+2vtwCICNFG9Wxv8QS+eW1zE/Dwfg==` |
| d3-quadtree | 3.0.2 | ISC | `sha512-9Lu9mqJKRbIk0d6mKDjpvPURaPdwHVK5CYbcdd0/4vBgz4ldz/7TIOse3kNERsByGNfld58KEco507AztJWyTQ==` |
| d3-random | 3.0.2 | ISC | `sha512-PxJi9LNV+7mulaYO77nd+oGurXGL1fhedXjHnB3pWLUcqDnQtF4VASoqnQGHgoXLByVdv5QJ/2kfwkGn5HTS8g==` |
| d3-scale | 4.0.3 | ISC | `sha512-66cWobCNzcMvlfoaDHCxuIv9TBUWG1BLOWdv9kHHFuCr1JdqAWPvTmsaEYDD5NRMyWZ5+7u0GqiCDfMXMqh3hg==` |
| d3-scale-chromatic | 3.1.1 | ISC | `sha512-lA5gfN2yMvmChubmptnDiBfeGpHD7Yb1EbvCz0TZE0WHXhyR6W2allPuhKtzV5ILQRqeOdefF0qYtERReLUBDg==` |
| d3-selection | 3.0.1 | ISC | `sha512-ODSf35vqCrlCfp7hrm0eZjvOosSXSYLjqvIlhMBV9q9VOx7EBJG6pc+uXBswEZNJgCGJ+qnKYcWutbZDIxe/Xg==` |
| d3-shape | 3.2.1 | ISC | `sha512-dm2o+lbKdzg9tY7GEag/dB9hcbodLfwkE/DkvqbELJXaMz0yKzWWhZqhbI7CKubukA7HnRyz0avdtvi7EPxPvw==` |
| d3-time | 3.1.1 | ISC | `sha512-Ze7rjrhMzdeulh0/hjcfFj7XLAHOfowtEMfsoG6DU866HPynQNW7Wfen6hzXcqKTv8XzxvF6Hzr5XD6bMHr2ug==` |
| d3-time-format | 4.1.1 | ISC | `sha512-22XaqjyCjpqgda20erhsOjGmC3vvYwTNYniKAd45W5UWLDF43moeOuV9qYpRqobIlsnK0UhnKZjUUJm3VgORUA==` |
| d3-timer | 3.0.2 | ISC | `sha512-1Il1aliroVSErrv5aulRBxAY+7+DnaoLIWGd1C6SsBTWDeobWiP/V69vwb8vT6abR1kKwaNe1196pmaQ1fK90A==` |
| d3-transition | 3.0.2 | ISC | `sha512-RcjCsdFgyFoDB+QXLC5m60ZkTN0k9zH+ovoLlTdJnDS1AbfbcuowiM4pCKSTOclNibS4f4J4cbv2m7O7y8NTOQ==` |
| d3-zoom | 3.0.1 | ISC | `sha512-kfjD3BDQu/FOatpZ6JdMSyIoDwTxIpI29ySTI2J5ZlDaH1WbuJGQJ2Q9oJkWTEZEW98j6idezoomSD3Cn2zwiw==` |
| delaunator | 5.1.0 | ISC | `sha512-AGrQ4QSgssa1NGmWmLPqN5NY2KajF5MqxetNEO+o0n3ZwZZeTmt7bBnvzHWrmkZFxGgr4HdyFgelzgi06otLuQ==` |
| internmap | 2.0.3 | ISC | `sha512-5Hh7Y1wQbvY5ooGgPbDaL5iYLAPzMTUrjMulskHLH6wnv/A+1q5rgEaiuqEjB+oxGXIVZs1FF+R/KPN3ZSQYYg==` |
| interval-tree-1d | 1.0.4 | MIT | `sha512-wY8QJH+6wNI0uh4pDQzMvl+478Qh7Rl4qLmqiluxALlNvl+I+o5x38Pw3/z7mDPTPS1dQalZJXsmbvxx5gclhQ==` |
| isoformat | 0.2.1 | ISC | `sha512-tFLRAygk9NqrRPhJSnNGh7g7oaVWDwR0wKh/GM2LgmPa50Eg4UfyaCO4I8k6EqJHl1/uh2RAD6g06n5ygEnrjQ==` |
| robust-predicates | 3.0.3 | Unlicense | `sha512-NS3levdsRIUOmiJ8FZWCP7LG3QpJyrs/TE0Zpf1yvZu8cAJJ6QMW92H1c7kWpdIHo8RvmLxN/o2JXTKHp74lUA==` |

## marked 18.2.1 and DOMPurify 3.4.18 (safe rich text)

License: `MIT AND Apache-2.0`. marked is MIT. DOMPurify is offered as `MPL-2.0 OR Apache-2.0`; this distribution elects **Apache-2.0**.

Official sources: [marked 18.2.1 tarball](https://registry.npmjs.org/marked/-/marked-18.2.1.tgz) and [dompurify 3.4.18 tarball](https://registry.npmjs.org/dompurify/-/dompurify-3.4.18.tgz).

Integrity: marked `sha512-ii4bxCTCqqwpT86XZWgJNs+ZnAIZksmLGYMViWA7PDIXYIeNo1x6cDdX3JOip9NM/cI6p8z57FxliACboTruMA==`; dompurify `sha512-ofe3wI/uNm68HInABYFJYqQxRw1EaKAjNdrFVKqjUY+UZurvNd2L/HuQe097s/4RivWiZyP6tT7aoT8atjfhwg==`.

Selection key: `markdown`. Total copied size including notices: 99,168 bytes (budget: 512 KiB).

| Bundled file | Bytes | Upstream input |
| --- | ---: | --- |
| `vendor/markdown.mjs` | 83,917 | `lib/marked.esm.js` + `dist/purify.es.mjs` + `scripts/vendor/markdown-entry.mjs` |
| `vendor/licenses/markdown-LICENSE` | 15,251 | `LICENSE` of marked and the Apache-2.0 `LICENSE` of DOMPurify |

Built with the existing esbuild 0.28.0 as one minified browser ESM file with no external imports, from the repository's own entry `scripts/vendor/markdown-entry.mjs`, which exports only `renderMarkdown` (parse, then sanitize) and `versions`. Both tarballs were fetched directly from registry.npmjs.org and their SHA-512 checked against registry metadata before use. DOMPurify's `prepare: husky` script is a development hook and was never run; no install script ran. @types/trusted-types is types-only and is not bundled.
