# Network verification

The stock Python suite is hermetic. `tests/python/test_net.py` checks the package User-Agent, redirect behavior, and case-insensitive removal of guest-supplied reserved headers with synthetic transport responses.

From the repository root, using the project's test environment:

```sh
python3 -m unittest tests.python.test_net -v
```

The transport identifies itself as `LivingSpaces/0.1.0 (+https://github.com/akinduroifedayo/living-spaces)` on requests and redirects. The tests compare headers with `net.USER_AGENT`; they do not compare its version with `plugin.yaml`. Update the constant in `src/living-spaces/living_spaces_core/net.py` when changing the package's advertised identity. Existing explicitly Space-supplied Authorization/Cookie behavior is unchanged. Hermes ambient credentials are not attached.

No live OSM integration-test module is shipped in this directory. The hermetic tests do not prove that an OSM server received the header or returned a usable tile. A release using OSM tiles needs separate live-content and [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) qualification. Do not bulk-fetch or prefetch tiles for verification.
