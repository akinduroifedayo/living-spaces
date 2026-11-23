// Card previews. A snapshot is a downscaled raster of a Space's own canvas, rendered inside its sandbox by the
// host-owned loader when the host asks, and kept only in this Desktop's localStorage. It is never sent to a
// backend or over the network. A Space that was never captured, whose code changed since, or whose stored image
// is invalid has no snapshot, and its card shows the accent and icon fallback instead.
const PREFIX = 'living-spaces:snapshot:'
const INDEX = 'living-spaces:snapshot-index'
// The Desktop origin's localStorage is shared with the rest of Hermes, so previews get a small, fixed budget.
export const SNAPSHOT_LIMITS = Object.freeze({ maxChars: 200_000, budgetChars: 1_200_000, maxEntries: 24, width: 480, minSide: 16, maxSide: 1024 })
const IMAGE = /^data:image\/(?:webp|png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/
const side = value => Number.isInteger(value) && value >= SNAPSHOT_LIMITS.minSide && value <= SNAPSHOT_LIMITS.maxSide

export const snapshotKey = (scopeKey, sid) => PREFIX + JSON.stringify([scopeKey ?? null, sid])

// The only accepted shape: a raster data URL within the size cap, its pixel size, capture time and revision.
export function parseSnapshot(value) {
  let snapshot = value
  if (typeof value === 'string') {
    try { snapshot = JSON.parse(value) } catch { return null }
  }
  if (!snapshot || typeof snapshot !== 'object') return null
  const { image, width, height, at, rev } = snapshot
  if (typeof image !== 'string' || image.length > SNAPSHOT_LIMITS.maxChars || !IMAGE.test(image)) return null
  if (!side(width) || !side(height) || !Number.isFinite(at) || !(rev == null || Number.isSafeInteger(rev))) return null
  return { image, width, height, at, rev: rev ?? null }
}

const storage = () => { try { return globalThis.localStorage ?? null } catch { return null } }
const readIndex = store => {
  try {
    const keys = JSON.parse(store.getItem(INDEX) || '[]')
    return Array.isArray(keys) ? keys.filter(key => typeof key === 'string' && key.startsWith(PREFIX)) : []
  } catch { return [] }
}

// The stored preview for this Space, or null. A snapshot of an earlier code revision is not shown.
export function readSnapshot(scopeKey, sid, rev) {
  const store = storage()
  if (!store) return null
  let snapshot
  try { snapshot = parseSnapshot(store.getItem(snapshotKey(scopeKey, sid))) } catch { return null }
  if (!snapshot || (rev != null && snapshot.rev != null && snapshot.rev !== rev)) return null
  return snapshot
}

// Replaces this Space's snapshot. Evicts the oldest previews beyond the entry count or character budget.
// Returns whether it stored.
export function writeSnapshot(scopeKey, sid, value) {
  const snapshot = parseSnapshot(value)
  const store = storage()
  if (!snapshot || !store) return false
  const key = snapshotKey(scopeKey, sid)
  const serialised = JSON.stringify(snapshot)
  const keys = readIndex(store).filter(entry => entry !== key)
  try {
    const sizes = new Map(keys.map(entry => [entry, store.getItem(entry)?.length ?? 0]))
    let total = serialised.length + [...sizes.values()].reduce((sum, size) => sum + size, 0)
    while (keys.length && (keys.length + 1 > SNAPSHOT_LIMITS.maxEntries || total > SNAPSHOT_LIMITS.budgetChars)) {
      const oldest = keys.shift()
      total -= sizes.get(oldest)
      store.removeItem(oldest)
    }
    store.setItem(key, serialised)
    store.setItem(INDEX, JSON.stringify([...keys, key]))
    return true
  } catch {
    // Quota or a disabled store: never leave a half-written entry that could render as a broken image.
    try { store.removeItem(key) } catch {}
    return false
  }
}

export function forgetSnapshot(scopeKey, sid) {
  const store = storage()
  if (!store) return
  const key = snapshotKey(scopeKey, sid)
  try {
    store.removeItem(key)
    store.setItem(INDEX, JSON.stringify(readIndex(store).filter(entry => entry !== key)))
  } catch {}
}
