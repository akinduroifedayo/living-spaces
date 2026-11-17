const owners = new WeakMap()
const recipes = {
  disclosure: { duration: 180, closed: { transform: 'translateY(-4px)', opacity: '0' } },
  panel: { duration: 240, closed: { transform: 'translateY(12px)', opacity: '0' } }
}

export function createMotionScope(root) {
  if (root?.nodeType !== 1 || typeof root.contains !== 'function') {
    throw new TypeError('A motion scope requires a root element')
  }
  const view = root.ownerDocument.defaultView
  const entries = new Map()
  const media = view?.matchMedia?.('(prefers-reduced-motion: reduce)')
  let reduced = media?.matches ?? false
  let disposed = false

  const contained = element => !!element?.isConnected && root.contains(element)
  const restore = entry => {
    for (const property of ['transform', 'opacity']) {
      const { value, priority } = entry.styles[property]
      if (value) entry.element.style.setProperty(property, value, priority)
      else entry.element.style.removeProperty(property)
    }
  }
  const stop = entry => {
    entry.epoch++
    const handle = entry.handle
    entry.handle = null
    handle?.cancel()
  }
  const settle = (entry, releasing = false) => {
    stop(entry)
    restore(entry)
    if (entry.kind === 'presence') {
      entry.element.hidden = !entry.target
      entry.element.inert = !entry.target
    } else if (entry.kind === 'press' && entry.target && !reduced && !releasing) {
      entry.element.style.setProperty('transform', 'scale(0.97)')
    }
  }
  const release = entry => {
    entry.generation++
    settle(entry, true)
    entries.delete(entry.element)
    owners.delete(entry.element)
  }
  const sweep = () => {
    for (const entry of entries.values()) {
      if (!contained(entry.element)) release(entry)
    }
  }
  const current = entry => {
    if (disposed || entries.get(entry.element) !== entry) return false
    if (!contained(entry.element)) { release(entry); return false }
    return true
  }
  const acquire = element => {
    if (disposed) return null
    if (!contained(element)) {
      const entry = entries.get(element)
      if (entry) release(entry)
      return null
    }
    if (owners.has(element) && owners.get(element) !== entries) {
      throw new Error('Motion shell already belongs to another scope')
    }
    let entry = entries.get(element)
    if (!entry) {
      const styles = {}
      for (const property of ['transform', 'opacity']) {
        styles[property] = {
          value: element.style.getPropertyValue(property),
          priority: element.style.getPropertyPriority?.(property) ?? ''
        }
      }
      entry = { element, styles, kind: null, recipe: null, target: null, epoch: 0, handle: null, generation: 0 }
      entries.set(element, entry)
      owners.set(element, entries)
    }
    return entry
  }
  const sample = entry => {
    const style = view.getComputedStyle(entry.element)
    return { transform: style.transform, opacity: style.opacity }
  }
  const animate = (entry, frames, duration) => {
    if (reduced || typeof entry.element.animate !== 'function') { settle(entry); return }
    const epoch = entry.epoch
    try {
      const handle = entry.element.animate(frames, { duration, easing: 'ease-out', fill: 'both' })
      entry.handle = handle
      const finish = () => {
        if (current(entry) && entry.epoch === epoch && entry.handle === handle) settle(entry)
      }
      handle.finished.then(finish, finish)
    } catch {
      settle(entry)
    }
  }
  const preferenceChanged = () => {
    if (disposed) return
    reduced = media.matches
    if (reduced) {
      sweep()
      for (const entry of entries.values()) settle(entry)
    }
  }
  if (media?.addEventListener) media.addEventListener('change', preferenceChanged)
  else media?.addListener?.(preferenceChanged)
  const observer = view?.MutationObserver ? new view.MutationObserver(sweep) : null
  observer?.observe(root.ownerDocument.documentElement, { childList: true, subtree: true })

  return {
    press(element, down) {
      const entry = acquire(element)
      if (!entry) return
      down = !!down
      if (entry.kind === 'press' && entry.target === down) return
      const initial = entry.kind !== 'press'
      const from = sample(entry)
      if (initial) settle(entry)
      else stop(entry)
      restore(entry)
      entry.generation++
      entry.kind = 'press'
      entry.target = down
      if (initial && !down) { settle(entry); return }
      const to = down ? { transform: 'scale(0.97)', opacity: from.opacity } : sample(entry)
      animate(entry, [from, to], 120)
    },
    present(element, { recipe, open }) {
      if (!Object.hasOwn(recipes, recipe)) throw new TypeError('Unknown presence recipe')
      const entry = acquire(element)
      if (!entry) return
      open = !!open
      if (entry.kind === 'presence' && entry.recipe === recipe && entry.target === open) return
      const initial = entry.kind !== 'presence'
      // Sample before canceling so a reversal starts at the painted position.
      const from = !initial && !entry.handle && !entry.target ? recipes[recipe].closed : sample(entry)
      if (initial) settle(entry)
      else stop(entry)
      restore(entry)
      entry.generation++
      entry.kind = 'presence'
      entry.recipe = recipe
      entry.target = open
      element.inert = !open
      if (open) element.hidden = false
      if (initial) { settle(entry); return }
      animate(entry, [from, open ? sample(entry) : recipes[recipe].closed], recipes[recipe].duration)
    },
    beginConfirmation(element) {
      const entry = acquire(element)
      if (!entry) return () => {}
      settle(entry)
      entry.kind = 'confirmation'
      entry.target = null
      const generation = ++entry.generation
      let reported = false
      return outcome => {
        if (reported || !current(entry) || entry.generation !== generation) return
        reported = true
        if (outcome !== 'confirmed') return
        const from = sample(entry)
        animate(entry, [from, { transform: 'scale(1.035)', opacity: '1' }, from], 220)
      }
    },
    dispose() {
      if (disposed) return
      disposed = true
      if (media?.removeEventListener) media.removeEventListener('change', preferenceChanged)
      else media?.removeListener?.(preferenceChanged)
      observer?.disconnect()
      for (const entry of entries.values()) release(entry)
    }
  }
}
