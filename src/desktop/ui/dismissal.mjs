// Host notice dismissals persist in localStorage. Memory holds a dismissal that storage refused,
// so it is newer than any stored value and wins on read.
const memory = new Map()
export function readDismissed(key) {
  if (memory.has(key)) return memory.get(key)
  try { return globalThis.localStorage?.getItem(key) ?? null } catch { return null }
}
export function writeDismissed(key, value) {
  try {
    if (!globalThis.localStorage) throw new Error('No storage')
    globalThis.localStorage.setItem(key, value)
    memory.delete(key)
  } catch { memory.set(key, value) }
}
