# Changelog

## 0.1.2

### New and fixed

- Add optional, read-only runtime inspection with `spaces_inspect`. It runs a saved revision in a disposable local Chrome-family browser and returns a text report of runtime errors and visible content. It takes no screenshots.
- Fix per-profile loading so the plugin resolves its own package in the active profile rather than reusing another profile's modules.
- F1 preserves the execution reply if a later status check fails.
- F2 collects blobs referenced only by a deleted Space and preserves shared references held by surviving Spaces.
- F3 coordinates overlapping agent Refresh requests to reduce duplicate model work. Feed Refresh works beside an idle agent schedule while preserving the barriers around active or unknown agent work.
- F4 accepts up to 1,000 parsed feed entries while preserving the generic 500-record batch limit.
- Make scheduled feed updates and retries fetch fresh content instead of reusing terminal run results.
