# Live OSM tile check

The default Python suite is hermetic. This separate, opt-in integration check makes one public HTTPS request through `bridge.dispatch` → production `net.fetch` → the real pinned TLS transport. It does not replace DNS, HTTP, or the bridge with a test implementation.

Use the same Python environment as the stock suite, including its PyYAML test dependency. From the repository root:

```sh
mkdir -p .run/osm-home .run/tmp
HERMES_HOME="$PWD/.run/osm-home" TMPDIR="$PWD/.run/tmp" \
  LIVING_SPACES_LIVE_OSM=1 LIVING_SPACES_OSM_EVIDENCE="$PWD/.run/osm-tile" \
  python -m unittest tests.integration.test_osm_tile -v
```

The check requests one Lisbon street tile at `https://tile.openstreetmap.org/13/3886/3138.png`. It saves `osm-tile.png` and `osm-tile.json` before checking the response, so a failed assertion retains evidence. The receipt includes the URL, HTTP status, response headers, MIME type, byte count, and SHA-256.

A pass requires HTTP 200, PNG MIME/signature, a 256×256 IHDR, no `X-Blocked` header, a digest different from the known W21 policy-block PNG, and more than 10,000 bytes. The size threshold is a heuristic for this detailed street tile, not a general test for all map tiles. W21's HTTP-200 policy-block PNG was 6,725 bytes with SHA-256 `109722facb0459991ce2c9983b3ae40232e84be7273aaa454071b50049e3d88b`. Inspect the saved image when qualifying a release. An OSM outage, rate limit, or changed tile can fail this live check without failing the hermetic suite.

The transport identifies itself as `LivingSpaces/0.1.0 (+https://github.com/akinduroifedayo/living-spaces)` on every request and redirect. A stock unit test checks its version against `plugin.yaml`. Guest User-Agent headers are reserved and stripped case-insensitively. Existing explicitly Space-supplied Authorization/Cookie behavior is unchanged; no Hermes ambient credentials are attached.

This check verifies application identification and the received tile content. It does not certify every requirement of [OSM's tile usage policy](https://operations.osmfoundation.org/policies/tiles/). Map authors must also provide attribution and meet caching and usage requirements. Do not bulk-fetch or prefetch tiles to run this test.
