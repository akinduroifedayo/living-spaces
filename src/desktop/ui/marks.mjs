// Space marks. One container (the host squircle on the accent ramp), three sources in a fixed order: the Space's
// generated image when it passed the save-time checks, then its kit glyph (legacy Codicon names map through an
// alias table), then a deterministic sigil from the Space id. A mark is never blank. Pure module: no DOM, no React.
// Design: Miro, t_3bb2c4db (kit, sigil, ramp) and t_c6894a3b (image treatment, optical zoom).
import { ACCENTS } from './model.mjs'

const lin = c => (c /= 255, c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
const gam = c => { c = Math.max(0, Math.min(1, c)); return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055 }
function hexToOklch(hex) {
  const [r, g, b] = [1, 3, 5].map(i => lin(parseInt(hex.slice(i, i + 2), 16)))
  const [l, m, s] = [0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b, 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
    0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b].map(Math.cbrt)
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, Math.hypot(A, B), (Math.atan2(B, A) * 180 / Math.PI + 360) % 360]
}
function oklchToRgb([L, C, h]) {
  const a = C * Math.cos(h * Math.PI / 180), b = C * Math.sin(h * Math.PI / 180)
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
  return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s].map(gam)
}
const luminance = rgb => { const [r, g, b] = rgb.map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4); return 0.2126 * r + 0.7152 * g + 0.0722 * b }
export const contrast = (x, y) => { const [a, b] = [luminance(x), luminance(y)].sort((p, q) => q - p); return (a + 0.05) / (b + 0.05) }
const css = ([L, C, h]) => `oklch(${L.toFixed(3)} ${C.toFixed(3)} ${h.toFixed(1)})`
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

// The container ramp: the accent's hue, a richer chroma, and a lightness band that keeps a white glyph at 3:1 or more
// on its lightest stop. A generated image's flat field is painted at the mid stop, so it blends into this light.
export function ramp(accent, { hueShift = 0 } = {}) {
  const [L, C, h0] = hexToOklch(ACCENTS[accent] || ACCENTS.blue)
  const h = h0 + hueShift
  const c = C < 0.03 ? Math.min(C, 0.018) : clamp(C * 1.15, 0.11, 0.19)
  let mid = clamp(L, 0.5, 0.6), top
  for (;;) { top = [mid + 0.075, c * 0.9, h - 8]; if (contrast([1, 1, 1], oklchToRgb(top)) >= 3.05 || mid < 0.4) break; mid -= 0.01 }
  return { top: css(top), mid: css([mid, c, h]), bottom: css([mid - 0.085, c * 1.08, h + 10]),
    glyphContrast: contrast([1, 1, 1], oklchToRgb(top)) }
}

function squirclePath(n = 5, r = 12, steps = 96) {
  const points = []
  for (let i = 0; i < steps; i++) {
    const t = (i / steps) * Math.PI * 2, ct = Math.cos(t), st = Math.sin(t)
    points.push([12 + r * Math.sign(ct) * Math.abs(ct) ** (2 / n), 12 + r * Math.sign(st) * Math.abs(st) ** (2 / n)])
  }
  return 'M' + points.map(p => p.map(v => v.toFixed(3)).join(' ')).join('L') + 'Z'
}
export const SQUIRCLE = squirclePath()
export const SQUIRCLE_INNER = squirclePath(5, 11.6)

// The fallback kit: shapes on a 24-unit grid, live area 3..21. t: 1 primary (white 97%), 2 secondary (white 50%).
// s: a 2-unit round stroke. Scoped as fallback-only (t_dbb8fbe9): the generated image is the primary route.
export const KIT = {
  graph: [{ t: 2, s: 1, d: 'M7.5 7.5L16.5 9M7.5 7.5L9.5 16.5M16.5 9L9.5 16.5M16.5 9L18 17.5M9.5 16.5L18 17.5' },
    { t: 1, d: 'M7.5 4.5a3 3 0 1 1 0 6a3 3 0 1 1 0-6z' }, { t: 1, d: 'M16.5 6.5a2.5 2.5 0 1 1 0 5a2.5 2.5 0 1 1 0-5z' },
    { t: 1, d: 'M9.5 12.8a3.7 3.7 0 1 1 0 7.4a3.7 3.7 0 1 1 0-7.4z' }, { t: 1, d: 'M18 15.5a2 2 0 1 1 0 4a2 2 0 1 1 0-4z' }],
  seismo: [{ t: 2, d: 'M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18z' }, { t: 1, s: 1, d: 'M3 12.5h4l2-5.5l3.2 10l2.3-7l1.7 2.5H21' }],
  plane: [{ t: 2, d: 'M17.5 3.5a3.5 3.5 0 1 1 0 7a3.5 3.5 0 1 1 0-7z' },
    { t: 1, d: 'M20.2 14.6v-1.7l-6.7-4.2V4.1a1.25 1.25 0 0 0-2.5 0v4.6l-6.7 4.2v1.7l6.7-2.1v4.6l-1.7 1.2v1.3l2.9-.8l2.9.8v-1.3l-1.7-1.2v-4.6z' }],
  book: [{ t: 1, d: 'M3 5.6c2.7-1.2 5.6-1.1 8.2.5v13.4c-2.6-1.5-5.5-1.6-8.2-.6z' }, { t: 2, d: 'M21 5.6c-2.7-1.2-5.6-1.1-8.2.5v13.4c2.6-1.5 5.5-1.6 8.2-.6z' }],
  weather: [{ t: 2, d: 'M15 4a4.6 4.6 0 1 1 0 9.2a4.6 4.6 0 1 1 0-9.2z' }, { t: 1, d: 'M7.2 20h9.6a3.9 3.9 0 0 0 .5-7.8A5.4 5.4 0 0 0 7 13.2a3.4 3.4 0 0 0 .2 6.8z' }],
  dice: [{ t: 2, d: 'M13 3h5a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3h-5a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3z' },
    { t: 1, d: 'M6 8.5h7a3 3 0 0 1 3 3v6.5a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-6.5a3 3 0 0 1 3-3zM6.8 11a1.3 1.3 0 1 0 0 2.6a1.3 1.3 0 1 0 0-2.6zM9.5 13.5a1.3 1.3 0 1 0 0 2.6a1.3 1.3 0 1 0 0-2.6zM12.2 16a1.3 1.3 0 1 0 0 2.6a1.3 1.3 0 1 0 0-2.6z' }],
  coins: [{ t: 2, d: 'M15 3.5a6 6 0 1 1 0 12a6 6 0 1 1 0-12z' },
    { t: 1, d: 'M9 8.5a6.5 6.5 0 1 1 0 13a6.5 6.5 0 1 1 0-13zM9 10.6a4.4 4.4 0 1 0 0 8.8a4.4 4.4 0 1 0 0-8.8zM9 12.4a2.6 2.6 0 1 1 0 5.2a2.6 2.6 0 1 1 0-5.2z' }],
  pulse: [{ t: 2, d: 'M12 20.6s-8.4-4.7-8.4-10.6A4.6 4.6 0 0 1 12 7.4A4.6 4.6 0 0 1 20.4 10c0 5.9-8.4 10.6-8.4 10.6z' }, { t: 1, s: 1, d: 'M3 12.6h4.6l1.9-3.4l3 6.8l2-3.4H21' }],
  sprout: [{ t: 1, s: 1, d: 'M12 21v-8.5' }, { t: 2, d: 'M12 13.5C7.2 13.5 4.4 10.6 4.4 5.6c5 0 7.6 2.9 7.6 7.9z' }, { t: 1, d: 'M12 11.6c0-4.8 2.8-7.6 7.6-7.6c0 4.8-2.8 7.6-7.6 7.6z' }],
  vinyl: [{ t: 2, d: 'M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18z' }, { t: 1, d: 'M12 12V3a9 9 0 0 1 9 9z' }, { t: 1, d: 'M12 8.6a3.4 3.4 0 1 1 0 6.8a3.4 3.4 0 1 1 0-6.8zM12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2z' }],
  briefcase: [{ t: 2, s: 1, d: 'M9 7.5V6a1.6 1.6 0 0 1 1.6-1.6h2.8A1.6 1.6 0 0 1 15 6v1.5' },
    { t: 1, d: 'M6 7.5h12a3 3 0 0 1 3 3v6.5a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-6.5a3 3 0 0 1 3-3zM10.6 11.6a.9.9 0 0 0-.9.9v1.6a.9.9 0 0 0 .9.9h2.8a.9.9 0 0 0 .9-.9v-1.6a.9.9 0 0 0-.9-.9z' }],
  chart: [{ t: 2, d: 'M3.5 19h17v2h-17z' }, { t: 1, d: 'M5 12.5a1.5 1.5 0 0 1 3 0V17H5zM10.5 6.5a1.5 1.5 0 0 1 3 0V17h-3zM16 10a1.5 1.5 0 0 1 3 0v7h-3z' }],
  calendar: [{ t: 2, s: 1, d: 'M8 3.5v3M16 3.5v3' },
    { t: 1, d: 'M6 5.5h12a3 3 0 0 1 3 3V18a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V8.5a3 3 0 0 1 3-3zM6 10.5v1.8h2.4v-1.8zM10.8 10.5v1.8h2.4v-1.8zM15.6 10.5v1.8H18v-1.8zM6 15v1.8h2.4V15zM10.8 15v1.8h2.4V15z' }],
  pin: [{ t: 2, d: 'M12 18.5c3.9 0 6.5 1 6.5 1.8S15.9 22 12 22s-6.5-.9-6.5-1.7s2.6-1.8 6.5-1.8z' },
    { t: 1, d: 'M12 2.5a7 7 0 0 1 7 7c0 4.6-5 8.8-7 10.4C10 18.3 5 14.1 5 9.5a7 7 0 0 1 7-7zM12 7a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5z' }],
  peaks: [{ t: 2, d: 'M13.5 20.5L17 9.5l5 11z' }, { t: 1, d: 'M2 20.5L9.2 6.2a1 1 0 0 1 1.8 0L18.2 20.5z' }],
  target: [{ t: 2, d: 'M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18zM12 5.6a6.4 6.4 0 1 0 0 12.8a6.4 6.4 0 1 0 0-12.8z' }, { t: 1, d: 'M12 8a4 4 0 1 1 0 8a4 4 0 1 1 0-8z' }],
  flask: [{ t: 2, s: 1, d: 'M8.5 3.5h7' }, { t: 1, d: 'M10 4.5h4v5l5.4 8.4A2 2 0 0 1 17.7 21H6.3a2 2 0 0 1-1.7-3.1L10 9.5z' }],
  home: [{ t: 2, d: 'M10 21v-5.5a2 2 0 0 1 4 0V21z' },
    { t: 1, d: 'M12 3.2l8.6 7.3a1 1 0 0 1-.6 1.8H19V19a2 2 0 0 1-2 2h-2.6v-5.5a2.4 2.4 0 0 0-4.8 0V21H7a2 2 0 0 1-2-2v-6.7H4a1 1 0 0 1-.6-1.8z' }],
  camera: [{ t: 2, d: 'M8.6 4h6.8l1.4 2.5H7.2z' },
    { t: 1, d: 'M5.5 6.5h13a2.5 2.5 0 0 1 2.5 2.5v9a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18V9a2.5 2.5 0 0 1 2.5-2.5zM12 9.3a4.2 4.2 0 1 0 0 8.4a4.2 4.2 0 1 0 0-8.4z' }],
  compass: [{ t: 2, d: 'M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18z' }, { t: 1, d: 'M16.5 7.5l-2.6 6.4l-6.4 2.6l2.6-6.4z' }],
  chat: [{ t: 2, d: 'M11 3.5h7.5A2.5 2.5 0 0 1 21 6v4.5a2.5 2.5 0 0 1-2.5 2.5H18v2.2L15.5 13H11z' },
    { t: 1, d: 'M5.5 7.5h8A2.5 2.5 0 0 1 16 10v5a2.5 2.5 0 0 1-2.5 2.5H9.5L6 20.5v-3h-.5A2.5 2.5 0 0 1 3 15v-5a2.5 2.5 0 0 1 2.5-2.5z' }],
  shield: [{ t: 1, d: 'M12 2.8l7.5 3v5.6c0 4.6-3.2 8.3-7.5 9.8z' }, { t: 2, d: 'M12 2.8l-7.5 3v5.6c0 4.6 3.2 8.3 7.5 9.8z' }],
  bolt: [{ t: 2, d: 'M12 3a9 9 0 1 1 0 18a9 9 0 1 1 0-18z' }, { t: 1, d: 'M13.2 4.5L7.5 13h4l-1 6.5L16.5 11h-4z' }],
  key: [{ t: 2, s: 1, d: 'M12.8 12.2L20 19.4M17 16.4l2-2M19 18.4l1.6-1.6' },
    { t: 1, d: 'M8.5 4a5.5 5.5 0 1 1 0 11a5.5 5.5 0 1 1 0-11zM7.7 7.2a1.7 1.7 0 1 0 0 3.4a1.7 1.7 0 1 0 0-3.4z' }]
}
// Today's Codicon names map onto the kit, so existing manifests upgrade without edits.
export const LEGACY = { brain: 'graph', globe: 'seismo', 'globe-alt': 'compass', checklist: 'calendar', 'graph-line': 'chart', heart: 'pulse',
  'device-camera': 'camera', beaker: 'flask', zap: 'bolt', 'comment-discussion': 'chat', location: 'pin', music: 'vinyl', game: 'dice' }
export const glyphKey = name => typeof name !== 'string' ? null : Object.hasOwn(KIT, name) ? name : Object.hasOwn(LEGACY, name) ? LEGACY[name] : null

// The deterministic sigil: four cells of simple primitives, seeded from the Space id, re-rolled until it has a
// primary shape and spans enough of the grid to read as more than a speck.
export function fnv(text) { let h = 0x811c9dc5; for (const ch of text) { h ^= ch.codePointAt(0); h = Math.imul(h, 0x01000193) >>> 0 } return h >>> 0 }
function rng(seed) { let s = seed || 1; return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296 } }
const PRIM = {
  circle: () => 'M4 0a4 4 0 1 1 0 8a4 4 0 1 1 0-8z',
  quarter: r => ['M0 0H8A8 8 0 0 1 0 8z', 'M8 0V8A8 8 0 0 1 0 0z', 'M8 8H0A8 8 0 0 1 8 0z', 'M0 8V0A8 8 0 0 1 8 8z'][r],
  half: r => ['M0 0H8A4 4 0 0 1 0 0z', 'M8 0V8A4 4 0 0 1 8 0z', 'M8 8H0A4 4 0 0 1 8 8z', 'M0 8V0A4 4 0 0 1 0 8z'][r],
  square: () => 'M2 0h4a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2z',
  leaf: r => r % 2 ? 'M8 0v4a4 4 0 0 1-4 4H0V4a4 4 0 0 1 4-4z' : 'M0 0h4a4 4 0 0 1 4 4v4H4a4 4 0 0 1-4-4z',
  tri: r => ['M0 0H8L0 8z', 'M8 0V8L0 0z', 'M8 8H0L8 0z', 'M0 8V0L8 8z'][r]
}
const PRIM_KEYS = ['circle', 'quarter', 'quarter', 'half', 'half', 'square', 'leaf', 'tri']
const CELLS = [[3.5, 3.5], [12.5, 3.5], [3.5, 12.5], [12.5, 12.5]]
// Cell paths use only absolute M/H/V/L/A with relative h/v/a, so translating the absolute coordinates moves them.
function shiftPath(d, dx, dy) {
  return d.replace(/([MLHVA])([^MLHVAZmlhvacz]*)/g, (all, cmd, args) => {
    const n = args.trim().split(/[\s,]+/).filter(Boolean).map(Number)
    if (cmd === 'H') return 'H' + (n[0] + dx)
    if (cmd === 'V') return 'V' + (n[0] + dy)
    if (cmd === 'A') return 'A' + [n[0], n[1], n[2], n[3], n[4], n[5] + dx, n[6] + dy].join(' ')
    const out = []; for (let i = 0; i < n.length; i += 2) out.push(n[i] + dx, n[i + 1] + dy)
    return cmd + out.join(' ')
  })
}
function sigilOnce(seedText) {
  const rand = rng(fnv(seedText))
  const empty = Math.floor(rand() * 5)
  let primaries = 0
  const shapes = CELLS.map(([x, y], i) => {
    if (i === empty) return null
    const key = PRIM_KEYS[Math.floor(rand() * PRIM_KEYS.length)], r = Math.floor(rand() * 4)
    const t = rand() < 0.62 ? 1 : 2
    if (t === 1) primaries++
    return { t, d: shiftPath(PRIM[key](r), x, y), cell: i }
  }).filter(Boolean)
  if (primaries < 2) shapes.slice(0, 2).forEach(s => (s.t = 1))
  if (!shapes.some(s => /A/.test(s.d))) shapes[0].d = shiftPath(PRIM.circle(), ...CELLS.find((_, i) => i !== empty))
  return { shapes, hueShift: Math.round((rand() - 0.5) * 24) }
}
// Cells sit at 3.5 and 12.5 with 8-unit primitives, so two cells on one axis span 17 units, one cell 8.
const spansGrid = shapes => { const cells = new Set(shapes.map(s => s.cell)); return [[0, 1], [2, 3], [0, 2], [1, 3]].some(([a, b]) => cells.has(a) && cells.has(b)) }
export function sigil(seedText) {
  const seed = String(seedText ?? '')
  for (let n = 0; n < 8; n++) {
    const out = sigilOnce(n ? `${seed}#${n}` : seed)
    if (out.shapes.some(s => s.t === 1) && spansGrid(out.shapes)) return out
  }
  return sigilOnce(seed)
}

export const ICON_DATA = /^data:image\/(?:webp|png);base64,[A-Za-z0-9+/]+={0,2}$/
export const ICON_DATA_MAX = 1_000_000

// Which source a mark draws. `image` is the Space's checked icon as a data URL already read from local storage,
// or null while it loads, after it failed to decode, or when the Space has none that passed.
export function resolveMark(space, image = null) {
  if (typeof image === 'string' && image.length <= ICON_DATA_MAX && ICON_DATA.test(image)) return { source: 'image', image }
  const key = glyphKey(space?.icon)
  if (key) return { source: 'glyph', key, shapes: KIT[key], hueShift: 0 }
  return { source: 'sigil', ...sigil(space?.id ?? space?.name ?? '') }
}

export const tierFor = px => px <= 18 ? 'micro' : px <= 28 ? 'small' : px <= 56 ? 'medium' : 'hero'
// How much of the tile the glyph covers, and how far a generated image is cropped in. The image's outer ring is a
// verified flat field, so the host can zoom it at small sizes and the symbol grows.
export const GLYPH_SCALE = { micro: 0.74, small: 0.7, medium: 0.64, hero: 0.58 }
export const IMAGE_ZOOM = { micro: 1.32, small: 1.22, medium: 1.08, hero: 1 }
