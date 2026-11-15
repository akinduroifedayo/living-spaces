// Host page for spaces_inspect. Python loads the built IIFE (src/living-spaces/inspection/runner.js) into a
// throwaway headless page and drives it over the DevTools pipe. The Space runs through the real mountSpace,
// unchanged, so the sandbox, CSP and 1 MiB request cap are the ones Desktop uses. Guest frames are opaque
// sandboxed origins and cannot reach this page; every bridge request is queued here and answered by Python
// from a frozen snapshot.
import { mountSpace } from '../desktop/sandbox/index.js'

const MAX_QUEUE = 1000

function createInspector() {
  const queue = []
  const pending = new Map()
  const events = []
  let seq = 0
  let mounted = null
  let wake = null
  let refused = 0
  const notify = () => { if (wake) { const w = wake; wake = null; w() } }
  const call = (op, args) => new Promise(resolve => {
    if (queue.length >= MAX_QUEUE) {
      refused++
      resolve({ ok: false, error: { code: 'limit', message: 'Inspection bridge queue is full' } })
      return
    }
    const id = ++seq
    pending.set(id, resolve)
    queue.push({ id, op, args })
    notify()
  })
  return {
    mount(bundle, grants) {
      const container = document.createElement('div')
      container.id = 'space'
      container.style.cssText = 'position:fixed;inset:0'
      document.body.style.margin = '0'
      document.body.append(container)
      mounted = mountSpace(container, { bundle, grants, call, onEvent: event => { events.push(event); notify() } })
      return true
    },
    // Resolves with everything queued, or after `ms` with nothing.
    next(ms) {
      const drain = () => ({ requests: queue.splice(0), events: events.splice(0), refused, viewport: [innerWidth, innerHeight, devicePixelRatio] })
      if (queue.length || events.length) return Promise.resolve(drain())
      return new Promise(resolve => {
        const timer = setTimeout(() => { wake = null; resolve(drain()) }, ms)
        wake = () => { clearTimeout(timer); resolve(drain()) }
      })
    },
    reply(id, body) {
      const resolve = pending.get(id)
      if (!resolve) return false
      pending.delete(id)
      resolve(body)
      return true
    },
    destroy() {
      for (const resolve of pending.values()) resolve({ ok: false, error: { code: 'session_invalid', message: 'Inspection ended' } })
      pending.clear()
      mounted?.destroy()
      mounted = null
      return true
    }
  }
}

Object.defineProperty(globalThis, '__lsInspect', { value: createInspector() })
