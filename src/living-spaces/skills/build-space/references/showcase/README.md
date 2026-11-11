# Premium showcase references (in progress)

Art-directed Space references. Read them for ambition and technique, not to copy their look.

| Space | Concept | Signature | Imagery |
|---|---|---|---|
| sky-window (data dashboard) | A window per city: sky colour follows live conditions and local time | Skyline silhouettes (luminance CSS mask) under a sky gradient computed from weather code + local hour; temperature ribbon for the week | Generated skyline silhouettes (`art/*-skyline.webp`, white on black, use as `mask-image` with `mask-mode: luminance`) |
| pair-play (game) | Letterpress card table on green felt | 3D card flip, oxblood-on-cream card backs, celebration on win | Generated card back (`art/card-back.webp`); faces drawn as SVG fruit |
| live board (neither) | To come | | |

Provenance: all rasters were generated with the Hermes image generation tool (Nov 11) as decoration. They are not photographs.
Offline fallback: each Space must still render with a gradient or SVG if an asset is missing.
