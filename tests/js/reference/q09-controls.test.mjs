import assert from 'node:assert/strict'
import test, { afterEach } from 'node:test'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { setImmediate as tick } from 'node:timers/promises'
import { h, render } from '../../../src/living-spaces/runtime/vendor/preact.mjs'
import { useLayoutEffect, useRef } from '../../../src/living-spaces/runtime/vendor/hooks.mjs'
import * as kit from '../../../src/living-spaces/runtime/kit/spaces-kit.mjs'

const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const { JSDOM } = require('jsdom')
let dom, root
const controllers = []
function setup() {
  dom = new JSDOM('<style>button { border-radius: 0; color: navy } dialog { padding: 3px }</style><main id="root"></main><aside id="untouched" inert>Existing inert</aside>', { pretendToBeVisual: true })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  root = document.getElementById('root')
}
function binding(name, options) {
  assert.equal(typeof kit[name], 'function', `${name} is an optional kit behavior export`)
  const controller = kit[name](options)
  controllers.push(controller)
  return controller
}
function layer(name = 'bindDialog', id = 'outer', parent = root) {
  const shell = document.createElement('section')
  shell.innerHTML = `<button id="${id}-trigger">Open ${id}</button><dialog id="${id}"><h2 id="${id}-title">${id} settings</h2><button disabled>Disabled</button><input aria-label="Name"><button data-close>Close</button></dialog>`
  parent.append(shell)
  const trigger = shell.querySelector('button')
  const content = shell.querySelector('dialog')
  const controller = binding(name, { trigger, content, labelledBy: `${id}-title` })
  return { shell, trigger, content, controller }
}
function key(target, value, options = {}) {
  const event = new dom.window.KeyboardEvent('keydown', { key: value, bubbles: true, cancelable: true, ...options })
  target.dispatchEvent(event)
  return event
}
function activate(button) { button.focus(); key(button, 'Enter'); button.click() }
function menu(parent = root, id = 'actions') {
  const shell = document.createElement('div')
  shell.innerHTML = `<button id="${id}-trigger">Actions</button><div id="${id}"><button role="menuitem">Archive</button><button role="menuitem" disabled>Unavailable</button><button role="menuitem">Delete</button></div>`
  parent.append(shell)
  const trigger = shell.querySelector('button')
  const content = shell.querySelector('div')
  const controller = binding('bindMenu', { trigger, content, label: 'Record actions' })
  return { shell, trigger, content, controller, items: [...content.querySelectorAll('button')] }
}
afterEach(() => {
  for (const controller of controllers.splice(0).reverse()) controller.destroy()
  if (root) render(null, root)
  dom?.window.close()
})

test('q09 dialog enters focus, traps Tab, names itself and returns to its trigger', () => {
  setup()
  const f = layer()
  assert.equal(f.content.hidden, true)
  f.trigger.focus(); activate(f.trigger)
  assert.equal(f.content.open, true)
  assert.equal(f.trigger.getAttribute('aria-expanded'), 'true')
  assert.equal(f.content.getAttribute('aria-labelledby'), 'outer-title')
  assert.equal(f.content.getAttribute('aria-modal'), 'true')
  assert.equal(document.activeElement, f.content.querySelector('input'))
  key(document.activeElement, 'Tab', { shiftKey: true })
  assert.equal(document.activeElement, f.content.querySelector('[data-close]'))
  key(document.activeElement, 'Tab')
  assert.equal(document.activeElement, f.content.querySelector('input'))
  assert.equal(key(document.activeElement, 'Escape').defaultPrevented, true)
  assert.equal(f.content.open, false)
  assert.equal(document.activeElement, f.trigger)
  assert.equal(f.trigger.getAttribute('aria-expanded'), 'false')
})

test('q09 modal blocks background focus and clicks and preserves existing inertness', () => {
  setup()
  const f = layer()
  const outside = document.createElement('button')
  outside.textContent = 'Outside'
  root.append(outside)
  let clicks = 0
  outside.addEventListener('click', () => clicks++)
  activate(f.trigger)
  assert.equal(outside.hasAttribute('inert'), true)
  outside.focus()
  assert.equal(document.activeElement, f.content.querySelector('input'))
  outside.click()
  assert.equal(clicks, 0)
  f.content.querySelector('[data-close]').click()
  assert.equal(outside.hasAttribute('inert'), false)
  assert.equal(document.getElementById('untouched').hasAttribute('inert'), true)
  outside.click()
  assert.equal(clicks, 1)
})

test('q09 nested dialog and menu close only the innermost layer on each Escape', () => {
  setup()
  const outer = layer()
  const inner = layer('bindDrawer', 'inner', outer.content)
  const actions = menu(inner.content)
  activate(outer.trigger); activate(inner.trigger)
  key(actions.trigger, 'ArrowDown')
  assert.equal(document.activeElement, actions.items[0])
  key(document.activeElement, 'ArrowDown')
  assert.equal(document.activeElement, actions.items[2])
  key(document.activeElement, 'Home')
  assert.equal(document.activeElement, actions.items[0])
  key(document.activeElement, 'End')
  assert.equal(document.activeElement, actions.items[2])
  key(document.activeElement, 'ArrowDown')
  assert.equal(document.activeElement, actions.items[0])
  key(document.activeElement, 'Escape')
  assert.equal(actions.content.hidden, true)
  assert.equal(inner.content.open, true)
  assert.equal(outer.content.open, true)
  assert.equal(document.activeElement, actions.trigger)
  key(document.activeElement, 'Escape')
  assert.equal(inner.content.open, false)
  assert.equal(outer.content.open, true)
  assert.equal(document.activeElement, inner.trigger)
  key(document.activeElement, 'Escape')
  assert.equal(document.activeElement, outer.trigger)
  assert.equal(root.hasAttribute('inert'), false)
})

test('q09 drawer teardown during Preact unmount releases the background and restores focus', async () => {
  setup()
  assert.equal(typeof kit.bindDrawer, 'function', 'bindDrawer is an optional kit behavior export')
  function Drawer({ show }) {
    const trigger = useRef(null), content = useRef(null)
    useLayoutEffect(() => {
      if (!show) return
      return kit.bindDrawer({ trigger: trigger.current, content: content.current, label: 'Edit record' }).destroy
    }, [show])
    return h('section', null, h('button', { ref: trigger }, 'Edit'), show && h('dialog', { ref: content }, h('input', { 'aria-label': 'Draft' })))
  }
  render(h(Drawer, { show: true }), root)
  const trigger = root.querySelector('button')
  trigger.focus(); activate(trigger)
  assert.equal(root.querySelector('dialog').getAttribute('aria-label'), 'Edit record')
  render(h(Drawer, { show: false }), root)
  await tick()
  assert.equal(document.activeElement, trigger)
  assert.equal(document.querySelector('[inert]:not(#untouched)'), null)
  key(trigger, 'Escape')
  assert.equal(document.activeElement, trigger)
})

test('q09 detached ancestor closes descendants and leaves no stale modal blocker', async () => {
  setup()
  const outer = layer()
  const inner = layer('bindDrawer', 'inner', outer.content)
  activate(outer.trigger); activate(inner.trigger)
  outer.content.remove()
  await tick()
  assert.equal(document.activeElement, outer.trigger)
  assert.equal(document.querySelector('[inert]:not(#untouched)'), null)
  outer.controller.destroy(); inner.controller.destroy()
  activate(outer.trigger)
  assert.equal(document.querySelector('[inert]:not(#untouched)'), null)
})

test('q09 menu has a name, roves, supports typeahead, selection and Tab dismissal', () => {
  setup()
  const f = menu()
  f.trigger.focus(); key(f.trigger, 'ArrowUp')
  assert.equal(f.trigger.getAttribute('aria-haspopup'), 'menu')
  assert.equal(f.content.getAttribute('role'), 'menu')
  assert.equal(f.content.getAttribute('aria-label'), 'Record actions')
  assert.equal(document.activeElement, f.items[2])
  assert.deepEqual(f.items.map(item => item.tabIndex), [-1, -1, 0])
  key(document.activeElement, 'a')
  assert.equal(document.activeElement, f.items[0])
  key(document.activeElement, 'Enter')
  assert.equal(f.content.hidden, true)
  assert.equal(document.activeElement, f.trigger)
  activate(f.trigger)
  key(document.activeElement, 'Tab')
  assert.equal(f.content.hidden, true)
  assert.equal(document.activeElement, f.trigger)
})

test('q09 tabs expose linked names and roving selection without kit CSS', () => {
  setup()
  root.innerHTML = '<div id="tabs"><button>Summary</button><button disabled>Unavailable</button><button>History</button></div><section>Summary data</section><section>Unavailable data</section><section>History data</section>'
  const list = root.querySelector('div')
  const tabs = [...list.children], panels = [...root.querySelectorAll('section')]
  binding('bindTabs', { list, tabs, panels, label: 'Record views' })
  assert.equal(list.getAttribute('aria-label'), 'Record views')
  assert.equal(list.getAttribute('role'), 'tablist')
  assert.deepEqual(tabs.map(tab => tab.tabIndex), [0, -1, -1])
  tabs[0].focus(); key(tabs[0], 'ArrowRight')
  assert.equal(document.activeElement, tabs[2])
  assert.equal(tabs[2].getAttribute('aria-selected'), 'true')
  assert.equal(panels[0].hidden, true)
  assert.equal(panels[2].hidden, false)
  assert.equal(panels[2].getAttribute('role'), 'tabpanel')
  assert.equal(panels[2].getAttribute('aria-labelledby'), tabs[2].id)
  assert.equal(tabs[2].getAttribute('aria-controls'), panels[2].id)
  key(tabs[2], 'Home'); assert.equal(document.activeElement, tabs[0])
  key(tabs[0], 'End'); assert.equal(document.activeElement, tabs[2])
  key(tabs[2], 'ArrowRight'); assert.equal(document.activeElement, tabs[0])
  assert.equal(document.styleSheets.length, 1, 'only unrelated author CSS is loaded')
})

test('q09 vertical tabs ignore horizontal arrows and skip disabled tabs', () => {
  setup()
  root.innerHTML = '<div><button>One</button><button>Two</button></div><section>One</section><section>Two</section>'
  const list = root.querySelector('div'), tabs = [...list.children], panels = [...root.querySelectorAll('section')]
  const controller = binding('bindTabs', { list, tabs, panels, label: 'Sections', orientation: 'vertical' })
  tabs[0].focus(); key(tabs[0], 'ArrowRight')
  assert.equal(document.activeElement, tabs[0])
  key(tabs[0], 'ArrowDown'); assert.equal(document.activeElement, tabs[1])
  tabs[0].disabled = true
  key(tabs[1], 'ArrowDown'); assert.equal(document.activeElement, tabs[1])
  controller.destroy()
  tabs[0].disabled = false
  key(tabs[1], 'Home'); assert.equal(document.activeElement, tabs[1])
})

test('q09 native disclosure names, nested Escape and close return preserve details semantics', async () => {
  setup()
  root.innerHTML = '<details><summary>More filters</summary><input aria-label="Filter"><details><summary>Advanced</summary><button>Apply</button></details></details>'
  const [outer, inner] = root.querySelectorAll('details')
  binding('bindDisclosure', { content: outer })
  binding('bindDisclosure', { content: inner })
  const trigger = outer.querySelector('summary')
  activate(trigger); await tick()
  assert.equal(outer.open, true)
  assert.equal(document.activeElement, trigger)
  activate(inner.querySelector('summary')); await tick()
  inner.querySelector('button').focus()
  key(document.activeElement, 'Escape')
  assert.equal(inner.open, false)
  assert.equal(outer.open, true)
  assert.equal(document.activeElement, inner.querySelector('summary'))
  key(document.activeElement, 'Escape')
  assert.equal(outer.open, false)
  assert.equal(document.activeElement, trigger)
})

test('q09 empty dialog fallback and repeated open close never accumulate blockers', () => {
  setup()
  const f = layer()
  f.content.replaceChildren(document.createTextNode('No interactive content'))
  for (let i = 0; i < 3; i++) {
    activate(f.trigger)
    assert.equal(document.activeElement, f.content)
    key(f.content, 'Tab')
    assert.equal(document.activeElement, f.content)
    key(f.content, 'Escape')
    assert.equal(document.activeElement, f.trigger)
    assert.equal(document.querySelector('[inert]:not(#untouched)'), null)
  }
})


test('q09 closing an inner dialog by button keeps the outer dialog open', () => {
  setup()
  const outer = layer()
  const inner = layer('bindDialog', 'inner', outer.content)
  activate(outer.trigger); activate(inner.trigger)
  inner.content.querySelector('[data-close]').click()
  assert.equal(outer.content.open, true)
  assert.equal(inner.content.open, false)
  assert.equal(document.activeElement, inner.trigger)
})

test('q09 nested menu navigation and selection stay within the active menu', () => {
  setup()
  const outer = menu()
  const inner = menu(outer.content, 'submenu')
  activate(outer.trigger); key(inner.trigger, 'ArrowDown')
  assert.equal(document.activeElement, inner.items[0])
  key(document.activeElement, 'ArrowDown')
  assert.equal(document.activeElement, inner.items[2])
  key(document.activeElement, 'Enter')
  assert.equal(inner.content.hidden, true)
  assert.equal(outer.content.hidden, false)
  assert.equal(document.activeElement, inner.trigger)
})

test('q09 dynamic background and removed trigger recover without blocked elements', async () => {
  setup()
  const f = layer('bindDrawer')
  activate(f.trigger)
  const extra = document.createElement('button')
  extra.textContent = 'Added while open'
  document.body.append(extra)
  await tick()
  assert.equal(extra.hasAttribute('inert'), true)
  f.shell.remove()
  await tick()
  assert.equal(document.querySelector('[inert]:not(#untouched)'), null)
  extra.focus()
  assert.equal(document.activeElement, extra)
})

test('q09 bindings require names and support explicit initial focus', () => {
  setup()
  assert.equal(typeof kit.bindDialog, 'function', 'bindDialog is an optional kit behavior export')
  root.innerHTML = '<button>Open</button><dialog><button>First</button><button>Last</button></dialog>'
  const trigger = root.querySelector('button'), content = root.querySelector('dialog')
  assert.throws(() => kit.bindDialog({ trigger, content }), TypeError)
  binding('bindDialog', { trigger, content, label: 'Choose action', initialFocus: content.lastChild })
  activate(trigger)
  assert.equal(document.activeElement, content.lastChild)
  assert.equal(content.getAttribute('aria-label'), 'Choose action')
})

test('q09 closing one nonmodal branch leaves a newer sibling disclosure open', async () => {
  setup()
  root.innerHTML = '<details><summary>First</summary><button>First action</button></details><details><summary>Second</summary><button>Second action</button></details>'
  const [first, second] = root.querySelectorAll('details')
  const firstControl = binding('bindDisclosure', { content: first })
  binding('bindDisclosure', { content: second })
  activate(first.querySelector('summary')); await tick()
  activate(second.querySelector('summary')); await tick()
  firstControl.close()
  assert.equal(first.open, false)
  assert.equal(second.open, true)
  key(second.querySelector('summary'), 'Escape')
  assert.equal(second.open, false)
})
