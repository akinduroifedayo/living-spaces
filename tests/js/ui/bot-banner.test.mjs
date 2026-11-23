import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import * as model from '../../../src/desktop/ui/model.mjs'
import * as markdown from '../../../src/desktop/ui/markdown.mjs'
import * as dismissal from '../../../src/desktop/ui/dismissal.mjs'
import { createSpaceSession as realSession } from '../../../src/desktop/ui/session.mjs'

const root = resolve(import.meta.dirname, '../../..')
const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')
const { JSDOM } = require('jsdom')

// The session stub records each opened controller so a test can publish bot statuses through the
// same onAction callback the real session uses, including the republish that restore() performs on open.
const sessions = []
const session = { createSpaceSession(options) {
  const controller = { options, links: [], checks: 0, retries: 0, continued: 0, continuable: false, ready: Promise.resolve(), postEvent() {}, destroy: async () => {},
    checkAction() { controller.checks++ }, retryAction() { controller.retries++ }, openLink(url) { controller.links.push(url) },
    canContinue() { return controller.continuable }, continueInChat() { controller.continued++; return true } }
  sessions.push(controller)
  return controller
} }
let dom, view, data
const cache = new Map()
function load(path) {
  if (cache.has(path)) return cache.get(path)
  const output = execFileSync('esbuild', ['--loader=jsx', '--format=cjs', '--jsx=automatic'], { input: readFileSync(path), encoding: 'utf8' })
  const module = { exports: {} }
  const imports = name => {
    if (name === '@hermes/plugin-sdk') return sdk
    if (name === './session.mjs') return session
    if (name === './model.mjs') return model
    if (name === './markdown.mjs') return markdown
    if (name === './dismissal.mjs') return dismissal
    if (name === '../sandbox/index.js') return { WEBRTC_NOTE: 'Public demo disclosure', mountSpace: () => ({ destroy() {} }) }
    if (name.startsWith('.')) return load(resolve(dirname(path), name))
    return require(name)
  }
  new Function('require', 'module', 'exports', output)(imports, module, module.exports)
  cache.set(path, module.exports)
  return module.exports
}
const baseSdk = load(resolve(root, 'tests/js/ui/sdk-stub.js'))
const sdk = { ...baseSdk, useQuery(options) { return { data: data[options.queryKey[3]], dataUpdatedAt: 1, refetch: async () => {} } } }
const { SpaceView } = load(resolve(root, 'src/desktop/ui/space.jsx'))

before(() => {
  dom = new JSDOM('<div id="root"></div>', { url: 'https://demo.invalid' })
  globalThis.window = dom.window
  globalThis.document = dom.window.document
  Object.defineProperty(globalThis, 'localStorage', { value: dom.window.localStorage, configurable: true, writable: true })
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
})
after(() => dom.window.close())

const LONG = ['Here is the summary of **three** findings.', '', '- First item with **bold** text', '- Second item', '  continued here', '- Third [docs](https://example.com/docs)', '', ...Array.from({ length: 40 }, (_, n) => `Line ${n} of a long answer.`)].join('\n')
const completed = (activationId = 'click-1', answer = LONG) => ({ activationId, status: 'completed', message: 'The maintaining bot completed this request.', answer })
const props = () => {
  data.detail = { id: 'demo-space', name: 'Demo', owner: 'Hermes', status: 'active', head_rev: 2, grants: [], freshness: {} }
  return { sid: 'demo-space', ctx: { rest: async () => ({}) } }
}
const text = () => document.body.textContent
// Any bot notice, whichever label its kind uses.
const NOTICE = /Hermes replied|Bot request/
const notice = () => document.querySelector('.ls-banner')
const region = () => document.querySelector('.ls-collapse')
// A collapsed reply stays in the DOM so it can animate, but is inert and hidden from assistive tech.
function assertCollapsed() {
  const inner = region().firstElementChild
  assert.equal(region().getAttribute('data-open'), 'false')
  assert.equal(inner.hasAttribute('inert'), true)
  assert.equal(inner.getAttribute('aria-hidden'), 'true')
  assert.equal(button('Read reply').getAttribute('aria-expanded'), 'false')
}
function assertExpanded() {
  const inner = region().firstElementChild
  assert.equal(region().getAttribute('data-open'), 'true')
  assert.equal(inner.hasAttribute('inert'), false)
  assert.equal(inner.getAttribute('aria-hidden'), 'false')
  assert.equal(button('Collapse').getAttribute('aria-expanded'), 'true')
}
const button = label => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label)
async function click(label) { const b = button(label); assert.ok(b, label); await act(async () => b.click()) }
async function mount() {
  view = createRoot(document.getElementById('root'))
  await act(async () => view.render(React.createElement(SpaceView, props())))
  return sessions.at(-1)
}
const publish = async (controller, status) => act(async () => controller.options.onAction(status))
const unmount = () => act(async () => view.unmount())
function fresh() { data = {}; sessions.length = 0; localStorage.clear() }

test('parseMarkdown yields paragraph, heading, list and code blocks with inline spans', () => {
  const blocks = markdown.parseMarkdown('# Title **x**\n\nfirst line\nsecond `code` line\n\n1. one\n2) two\n   more\n\n* a\n+ b\n\n```\n<b>raw</b>\n  kept\n```\ntail _em_ and *em2* and __strong__')
  assert.deepEqual(blocks, [
    { type: 'heading', spans: [{ type: 'text', text: 'Title ' }, { type: 'strong', text: 'x' }] },
    { type: 'paragraph', spans: [{ type: 'text', text: 'first line' }, { type: 'break' }, { type: 'text', text: 'second ' }, { type: 'code', text: 'code' }, { type: 'text', text: ' line' }] },
    { type: 'list', ordered: true, items: [[{ type: 'text', text: 'one' }], [{ type: 'text', text: 'two more' }]] },
    { type: 'list', ordered: false, items: [[{ type: 'text', text: 'a' }], [{ type: 'text', text: 'b' }]] },
    { type: 'code', text: '<b>raw</b>\n  kept' },
    { type: 'paragraph', spans: [{ type: 'text', text: 'tail ' }, { type: 'em', text: 'em' }, { type: 'text', text: ' and ' }, { type: 'em', text: 'em2' }, { type: 'text', text: ' and ' }, { type: 'strong', text: 'strong' }] }
  ])
})
test('parseMarkdown keeps raw HTML as text and links only https targets', () => {
  assert.deepEqual(markdown.parseMarkdown('<script>alert(1)</script>'), [{ type: 'paragraph', spans: [{ type: 'text', text: '<script>alert(1)</script>' }] }])
  assert.deepEqual(markdown.parseMarkdown('[a](javascript:alert(1)) [b](http://x.test) [c](https://ok.test/p) see https://bare.test/x.'), [{ type: 'paragraph', spans: [
    { type: 'text', text: 'a) b ' }, { type: 'link', text: 'c', href: 'https://ok.test/p' }, { type: 'text', text: ' see ' }, { type: 'link', text: 'https://bare.test/x', href: 'https://bare.test/x' }, { type: 'text', text: '.' }
  ] }])
  const spans = markdown.parseMarkdown('[a](javascript:alert) [b](http://x.test)')[0].spans
  assert.ok(spans.every(span => span.type !== 'link'))
  assert.deepEqual(markdown.parseInline('snake_case_name and 2 * 3 * 4'), [{ type: 'text', text: 'snake_case_name and 2 * 3 * 4' }])
})
test('parseMarkdown turns a line that is only bold text into a heading', () => {
  const heading = text => ({ type: 'heading', spans: [{ type: 'text', text }] })
  assert.deepEqual(markdown.parseMarkdown('**Summary:**\nBody text.\n\n__Next steps__'), [heading('Summary:'), { type: 'paragraph', spans: [{ type: 'text', text: 'Body text.' }] }, heading('Next steps')])
  assert.deepEqual(markdown.parseMarkdown('Lead **bold** tail:'), [{ type: 'paragraph', spans: [{ type: 'text', text: 'Lead ' }, { type: 'strong', text: 'bold' }, { type: 'text', text: ' tail:' }] }])
})
test('answerSummary is the first sentence of the first prose block, capped at 160 characters', () => {
  assert.equal(markdown.answerSummary('**Summary:**\n\nYes, there is an update. You are on 0.60 and stable is 0.61.'), 'Yes, there is an update.')
  assert.equal(markdown.answerSummary('## **Key** findings\n\nThe *first* one is `x`! Then more.'), 'The first one is x!')
  assert.equal(markdown.answerSummary('Version 0.60.722 is current? Maybe.'), 'Version 0.60.722 is current?')
  assert.equal(markdown.answerSummary('Line one\nline two. Rest'), 'Line one line two.')
  assert.equal(markdown.answerSummary('- see [docs](https://x.test) and `code`'), 'see docs and code')
  assert.equal(markdown.answerSummary('# Only a heading'), 'Only a heading')
  const long = `${'word '.repeat(60)}end.`
  const summary = markdown.answerSummary(long)
  assert.equal(summary.length, 160)
  assert.ok(summary.endsWith('…'))
  assert.ok(long.startsWith(summary.slice(0, -1)))
  assert.equal(markdown.answerSummary(''), '')
})
test('botBanner labels each kind and carries the reply, reason and time', () => {
  assert.equal(model.botBanner(null), null)
  assert.equal(model.botBanner(completed(), { dismissed: true }), null)
  assert.deepEqual(model.botBanner({ ...completed('click-1', '**Done:**\n\nAll set. More.'), at: 1700000000 }), { status: 'completed', kind: 'reply', label: 'Hermes replied', reason: null, summary: 'All set.', answer: '**Done:**\n\nAll set. More.', at: 1700000000, expanded: false, collapsible: true, canRetry: false, canDismiss: true })
  assert.equal(model.botBanner(completed(), { expanded: true }).expanded, true)
  assert.equal(model.botBanner(completed()).at, null)
  for (const status of ['failed', 'offline', 'unknown']) {
    const banner = model.botBanner({ activationId: 'a', status, message: 'Route unavailable. No automatic resend.', answer: 'stale' }, { expanded: true })
    assert.deepEqual(banner, { status, kind: 'failed', label: 'Bot request failed', reason: 'Route unavailable. No automatic resend.', summary: '', answer: null, at: null, expanded: false, collapsible: false, canRetry: true, canDismiss: true })
    assert.equal(model.botBanner({ status, message: 'm' }).canRetry, false)
  }
  for (const status of ['submitted', 'queued', 'busy']) {
    const banner = model.botBanner({ activationId: 'a', status, message: 'Working' })
    assert.equal(banner.kind, 'progress')
    assert.equal(banner.label, `Bot request: ${status}`)
    assert.equal(banner.canDismiss, false)
  }
  assert.equal(model.botDismissKey({ activationId: 'a', status: 'failed' }), 'a:failed')
  assert.equal(model.botDismissKey({ status: 'failed' }), null)
  assert.equal(model.botDismissKey(null), null)
})

test('a reply starts collapsed to its summary and time, and expands into rendered markdown', async () => {
  fresh()
  const controller = await mount()
  try {
    const before = Date.now() / 1000
    await publish(controller, completed())
    assert.equal(notice().getAttribute('role'), 'status')
    assert.match(notice().querySelector('strong').textContent, /^Hermes replied/)
    const time = notice().querySelector('strong time')
    assert.ok(time, 'the reply shows when it arrived')
    const at = Date.parse(time.getAttribute('datetime')) / 1000
    assert.ok(at >= Math.floor(before) && at <= Date.now() / 1000 + 1)
    const summary = document.querySelector('.ls-answer-summary')
    assert.equal(summary.textContent, 'Here is the summary of three findings.')
    assert.equal(summary.title, summary.textContent)
    const toggle = button('Read reply')
    assert.equal(toggle.getAttribute('aria-controls'), region().id)
    assertCollapsed()
    assert.equal(button('Check status'), undefined)
    assert.ok(document.querySelector('button[aria-label="Dismiss reply"]'))
    await click('Read reply')
    assertExpanded()
    const answer = document.querySelector('.ls-answer')
    assert.equal(answer.getAttribute('tabindex'), '0')
    assert.equal(answer.getAttribute('role'), 'region')
    assert.equal(answer.getAttribute('aria-label'), 'Hermes reply')
    assert.deepEqual([...answer.querySelectorAll('li')].map(li => li.textContent), ['First item with bold text', 'Second item continued here', 'Third docs'])
    assert.deepEqual([...answer.querySelectorAll('strong')].map(node => node.textContent), ['three', 'bold'])
    assert.match(answer.textContent, /Line 39 of a long answer/)
    assert.equal(region().querySelector('button[data-copy]').getAttribute('data-copy'), LONG)
    assert.equal(button('Continue in chat'), undefined)
    const link = answer.querySelector('a')
    assert.equal(link.getAttribute('href'), 'https://example.com/docs')
    const event = new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })
    await act(async () => link.dispatchEvent(event))
    assert.equal(event.defaultPrevented, true)
    assert.deepEqual(controller.links, ['https://example.com/docs'])
    await click('Collapse')
    assertCollapsed()
  } finally { await unmount() }
})
test('bold-only lines in a reply render as headings', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed('click-1', '**Summary:**\n\nYes, there is an update.\n\n## Details\n\n**Next steps**\n- Upgrade'))
    await click('Read reply')
    assert.deepEqual([...document.querySelectorAll('.ls-answer h5')].map(node => node.textContent), ['Summary:', 'Details', 'Next steps'])
    assert.equal(document.querySelector('.ls-answer-summary').textContent, 'Yes, there is an update.')
  } finally { await unmount() }
})
test('Continue in chat shows only when the session can open the chat, and opens it', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed())
    assert.equal(button('Continue in chat'), undefined)
    controller.continuable = true
    await publish(controller, completed('click-2', 'A second reply.'))
    await click('Read reply')
    await click('Continue in chat')
    assert.equal(controller.continued, 1)
  } finally { await unmount() }
})
test('raw HTML in an answer renders as text, not elements', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed('click-1', 'Intro\n\n<script>window.pwned = 1</script><img src=x onerror=alert(1)>\n[bad](javascript:alert(1))'))
    await click('Read reply')
    const answer = document.querySelector('.ls-answer')
    assert.equal(answer.querySelector('script, img'), null)
    assert.equal(answer.querySelector('a'), null)
    assert.match(answer.textContent, /<script>window\.pwned = 1<\/script><img src=x onerror=alert\(1\)>/)
  } finally { await unmount() }
})
test('Dismiss hides the answer across re-render and reopen of the same activation', async () => {
  fresh()
  let controller = await mount()
  try {
    await publish(controller, completed())
    await click('Dismiss')
    assert.doesNotMatch(text(), NOTICE)
    assert.deepEqual(JSON.parse(localStorage.getItem('living-spaces:bot-dismissed:demo-backend:demo-profile:demo-space')), { id: 'click-1', statuses: ['completed'] })
    await publish(controller, completed())
    await act(async () => view.render(React.createElement(SpaceView, props())))
    assert.doesNotMatch(text(), NOTICE)
    await unmount()
    controller = await mount()
    await publish(controller, completed())
    assert.doesNotMatch(text(), NOTICE)
    await publish(controller, { activationId: 'click-1', status: 'failed', message: 'Native request failed.' })
    assert.match(text(), /Bot request failed/)
    await publish(controller, completed('click-2', 'Another answer'))
    assert.match(text(), /Hermes replied/)
    assert.match(document.querySelector('.ls-answer-summary').textContent, /Another answer/)
  } finally { await unmount() }
})
test('a dismissed activation stays hidden when reopen can only report it offline or unknown', async () => {
  fresh()
  let controller = await mount()
  try {
    await publish(controller, completed())
    await click('Dismiss')
    await unmount()
    controller = await mount()
    for (const status of ['offline', 'unknown']) {
      await publish(controller, { activationId: 'click-1', status, message: 'The exact maintaining profile route is unavailable or ambiguous. No automatic resend.' })
      assert.doesNotMatch(text(), NOTICE, status)
    }
    await publish(controller, completed())
    assert.doesNotMatch(text(), NOTICE)
    await publish(controller, { activationId: 'click-2', status: 'offline', message: 'Route unavailable.' })
    assert.match(text(), /Bot request failed/)
    assert.ok(button('Retry same request'))
  } finally { await unmount() }
})
test('botDismissed treats unobservable statuses as the dismissed activation, other outcomes as new', () => {
  const record = (id, ...statuses) => ({ id, statuses })
  assert.equal(model.botDismissed({ activationId: 'a', status: 'completed' }, record('a', 'completed')), true)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'offline' }, record('a', 'completed')), true)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'unknown' }, record('a', 'failed')), true)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'failed' }, record('a', 'completed')), false)
  assert.equal(model.botDismissed({ activationId: 'ab', status: 'offline' }, record('a', 'completed')), false)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'offline' }, record('ab', 'completed')), false)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'offline' }, null), false)
  assert.equal(model.botDismissed({ status: 'offline' }, record('a', 'completed')), false)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'offline', userInitiated: true }, record('a', 'completed', 'offline')), false)
  assert.equal(model.botDismissed({ activationId: 'a', status: 'completed', userInitiated: true }, record('a', 'completed')), false)
})
test('parseBotDismissal accepts only an activation record and dismissBot accumulates statuses', () => {
  assert.deepEqual(model.parseBotDismissal('{"id":"a","statuses":["completed"]}'), { id: 'a', statuses: ['completed'] })
  for (const value of [null, '', 'a:completed', '{', '{"id":1,"statuses":[]}', '{"id":"a"}', '{"id":"a","statuses":[1]}', '"a"', 'null']) {
    assert.equal(model.parseBotDismissal(value), null, String(value))
  }
  const first = model.dismissBot(null, { activationId: 'a', status: 'completed' })
  assert.deepEqual(first, { id: 'a', statuses: ['completed'] })
  assert.deepEqual(model.dismissBot(first, { activationId: 'a', status: 'offline' }), { id: 'a', statuses: ['completed', 'offline'] })
  assert.deepEqual(model.dismissBot(first, { activationId: 'a', status: 'completed' }), first)
  assert.deepEqual(model.dismissBot(first, { activationId: 'b', status: 'failed' }), { id: 'b', statuses: ['failed'] })
})
test('a status the user just caused shows even for a dismissed activation, and its dismissal keeps the earlier one', async () => {
  fresh()
  let controller = await mount()
  try {
    await publish(controller, completed())
    await click('Dismiss')
    const offline = { activationId: 'click-1', status: 'offline', message: 'The exact maintaining profile route is unavailable or ambiguous. No automatic resend.' }
    await publish(controller, { ...offline, userInitiated: true })
    assert.match(text(), /Bot request failed/)
    assert.ok(button('Retry same request'))
    assert.ok(button('Check status'))
    await click('Dismiss')
    assert.doesNotMatch(text(), NOTICE)
    assert.deepEqual(JSON.parse(localStorage.getItem('living-spaces:bot-dismissed:demo-backend:demo-profile:demo-space')), { id: 'click-1', statuses: ['completed', 'offline'] })
    await unmount()
    controller = await mount()
    await publish(controller, completed())
    assert.doesNotMatch(text(), NOTICE)
    await publish(controller, offline)
    assert.doesNotMatch(text(), NOTICE)
  } finally { await unmount() }
})
test('a dismissal that storage refused wins over an older stored one after reopen', async () => {
  fresh()
  const key = 'living-spaces:bot-dismissed:demo-backend:demo-profile:demo-space'
  localStorage.setItem(key, 'click-0:completed')
  const setItem = Object.getPrototypeOf(localStorage).setItem
  Object.getPrototypeOf(localStorage).setItem = () => { throw new Error('quota') }
  let controller
  try {
    controller = await mount()
    await publish(controller, completed('click-7'))
    await click('Dismiss')
    await unmount()
    controller = await mount()
    await publish(controller, completed('click-7'))
    assert.doesNotMatch(text(), NOTICE)
  } finally {
    Object.getPrototypeOf(localStorage).setItem = setItem
    await unmount()
  }
})
test('expanded state resets when the activation changes', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed())
    await click('Read reply')
    assertExpanded()
    await publish(controller, completed('click-2', 'Second answer'))
    assertCollapsed()
  } finally { await unmount() }
})
test('a banner without an activation dismisses in memory only', async () => {
  fresh()
  let controller = await mount()
  try {
    const refused = { status: 'failed', message: 'Bot requests need a current user activation. No request was sent.' }
    await publish(controller, refused)
    assert.equal(button('Retry same request'), undefined)
    await click('Dismiss')
    assert.doesNotMatch(text(), NOTICE)
    assert.equal(localStorage.length, 0)
    await unmount()
    controller = await mount()
    await publish(controller, { ...refused })
    assert.match(text(), /Bot request failed/)
  } finally { await unmount() }
})
for (const status of ['failed', 'offline', 'unknown']) {
  test(`${status} bot status is a failure alert with Retry same request and Check status`, async () => {
    fresh()
    const controller = await mount()
    try {
      const message = `Status ${status}. No automatic resend.`
      await publish(controller, { activationId: 'click-1', status, message })
      assert.equal(notice().getAttribute('role'), 'alert')
      assert.match(notice().querySelector('strong').textContent, /^Bot request failed/)
      const reason = notice().querySelector('.ls-oneline')
      assert.equal(reason.textContent, message)
      assert.equal(reason.title, message)
      await click('Retry same request')
      await click('Check status')
      assert.equal(controller.retries, 1)
      assert.equal(controller.checks, 1)
      assert.ok(button('Dismiss'))
      assert.equal(button('Read reply'), undefined)
      assert.equal(region(), null)
    } finally { await unmount() }
  })
}
test('in-flight bot statuses cannot be dismissed', async () => {
  fresh()
  const controller = await mount()
  try {
    for (const status of ['submitted', 'queued', 'busy']) {
      await publish(controller, { activationId: 'click-1', status, message: 'Working' })
      assert.match(text(), new RegExp(`Bot request: ${status}`))
      assert.equal(notice().getAttribute('role'), 'status')
      assert.equal(button('Dismiss'), undefined)
      assert.ok(button('Check status'))
    }
  } finally { await unmount() }
})
test('dismiss storage failures fall back to memory for the open view', async () => {
  fresh()
  const storage = globalThis.localStorage
  Object.defineProperty(globalThis, 'localStorage', { get() { throw new Error('denied') }, configurable: true })
  try {
    const controller = await mount()
    await publish(controller, completed('click-9'))
    await click('Dismiss')
    await publish(controller, completed('click-9'))
    assert.doesNotMatch(text(), NOTICE)
  } finally {
    await unmount()
    Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true, writable: true })
  }
})
test('session openLink routes answer links through the guarded link path', async () => {
  const notices = []
  const controller = realSession({ sid: 'demo-space', container: {}, onEvent() {}, mount: () => ({ destroy() {} }), userActivation: () => true,
    host: { notify: notice => notices.push(notice) }, os: { openExternal: async () => true },
    rest: async path => path.endsWith('/sessions') ? { session: 's', head_rev: 1, grants: [] } : path.endsWith('/bundle') ? { rev: 1 } : path.endsWith('/actions/context') ? { maintainer: null, action: null } : { closed: true } })
  await controller.ready
  assert.equal(controller.openLink('https://example.com/docs').result.status, 'confirming')
  assert.match(notices.at(-1).title, /example\.com/)
  assert.equal(controller.openLink('javascript:alert(1)').ok, false)
  await controller.destroy()
})

test('session marks statuses from the guest bot request as user-initiated, never the guest event or restore', async () => {
  const route = { connectionId: 'conn', profile: 'owner', targetProfile: 'owner', mode: 'local' }
  const previous = { activation_id: 'A', input_id: 'input-A', admission_id: 'admission-A', settled: true,
    target: { route, profile_id: 'native-owner', session_id: 'canonical' }, text: 'previous request' }
  const actions = [], events = [], posts = []
  let mounted
  const host = { state: { connectionId: { get: () => 'conn' }, profile: { get: () => 'owner' } },
    profileRoutes: async () => [], retainProfile: async () => () => {}, requestProfile: async method => { throw new Error(`Unexpected RPC ${method}`) } }
  const rest = async (path, options) => {
    if (path.endsWith('/sessions')) return { session: 's', head_rev: 1, grants: [] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (path.endsWith('/actions/context')) return { maintainer: { profile_id: 'native-owner', stored_session_id: 'canonical' }, action: structuredClone(previous) }
    if (options?.method === 'DELETE') return { closed: true }
    posts.push(path)
    throw new Error(`Unexpected request ${path}`)
  }
  const navigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', { value: { userActivation: { isActive: true } }, configurable: true, writable: true })
  const controller = realSession({ sid: 'demo-space', backend: route, host, rest, container: {}, onEvent() {}, onAction: value => actions.push(value),
    mount: (_container, options) => { mounted = options; return { destroy() {}, postEvent: (event, payload) => events.push([event, payload]) } } })
  try {
    await controller.ready
    for (let n = 0; n < 50 && !actions.length; n++) await new Promise(resolve => setTimeout(resolve, 0))
    const restored = actions.splice(0)
    assert.equal(restored.length, 1)
    assert.equal(restored[0].status, 'offline')
    assert.equal(restored[0].activationId, 'A')
    assert.equal('userInitiated' in restored[0], false)
    events.length = 0
    const reply = await mounted.call('bot.request', { activation_id: 'B', text: 'A new question', records: [] })
    assert.equal(reply.result.activationId, 'A')
    assert.equal(reply.result.status, 'offline')
    assert.ok(actions.length > 0)
    assert.ok(actions.every(value => value.userInitiated === true))
    assert.deepEqual(events.map(([event]) => event), actions.map(() => 'bot.status'))
    assert.ok(events.every(([, payload]) => !('userInitiated' in payload)))
    assert.deepEqual(posts, [])
  } finally {
    await controller.destroy()
    if (navigator) Object.defineProperty(globalThis, 'navigator', navigator)
    else delete globalThis.navigator
  }
})

test('session Continue in chat opens the maintainer stored session through the host', async () => {
  const route = { connectionId: 'conn', profile: 'owner', targetProfile: 'owner', mode: 'local' }
  const opened = []
  const base = { state: { connectionId: { get: () => 'conn' }, profile: { get: () => 'owner' } },
    profileRoutes: async () => [], retainProfile: async () => () => {}, requestProfile: async method => { throw new Error(`Unexpected RPC ${method}`) } }
  const rest = maintainer => async (path, options) => {
    if (path.endsWith('/sessions')) return { session: 's', head_rev: 1, grants: [] }
    if (path.endsWith('/bundle')) return { rev: 1 }
    if (path.endsWith('/actions/context')) return { maintainer, action: null }
    if (options?.method === 'DELETE') return { closed: true }
    throw new Error(`Unexpected request ${path}`)
  }
  const open = async (host, maintainer) => {
    const actions = []
    const controller = realSession({ sid: 'demo-space', backend: route, host, rest: rest(maintainer), container: {}, onEvent() {}, onAction: value => actions.push(value),
      mount: () => ({ destroy() {}, postEvent() {} }) })
    await controller.ready
    for (let n = 0; n < 50 && controller.canContinue() === false && maintainer && typeof host.openSession === 'function'; n++) await new Promise(resolve => setTimeout(resolve, 0))
    return { controller, actions }
  }
  const withOpen = { ...base, openSession: id => { opened.push(id); return true } }
  let { controller, actions } = await open(withOpen, { profile_id: 'native-owner', stored_session_id: 'canonical-chat' })
  try {
    assert.equal(controller.canContinue(), true)
    assert.equal(controller.continueInChat(), true)
    assert.deepEqual(opened, ['canonical-chat'])
    assert.ok(actions.every(value => !JSON.stringify(value).includes('canonical-chat')), 'the stored session never rides on a bot status')
  } finally { await controller.destroy() }
  ;({ controller } = await open(base, { profile_id: 'native-owner', stored_session_id: 'canonical-chat' }))
  try {
    assert.equal(controller.canContinue(), false, 'a Desktop without openSession cannot continue')
    assert.equal(controller.continueInChat(), false)
  } finally { await controller.destroy() }
  ;({ controller } = await open(withOpen, null))
  try {
    assert.equal(controller.canContinue(), false, 'no maintainer, no chat to continue')
    assert.equal(controller.continueInChat(), false)
    assert.deepEqual(opened, ['canonical-chat'])
  } finally { await controller.destroy() }
})
