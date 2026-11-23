import test, { before, after } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import * as model from '../../../src/desktop/ui/model.mjs'
import * as markdown from '../../../src/desktop/ui/markdown.mjs'
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
  const controller = { options, links: [], checks: 0, retries: 0, ready: Promise.resolve(), postEvent() {}, destroy: async () => {},
    checkAction() { controller.checks++ }, retryAction() { controller.retries++ }, openLink(url) { controller.links.push(url) } }
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
test('answerSummary is the first non-empty line without markdown markers', () => {
  assert.equal(markdown.answerSummary('\n\n## **Key** findings\nmore'), 'Key findings')
  assert.equal(markdown.answerSummary('   \n- see [docs](https://x.test) and `code`'), 'see docs and code')
  assert.equal(markdown.answerSummary(''), '')
})
test('botBanner derives visibility, tone, collapse, retry and dismiss from the action', () => {
  assert.equal(model.botBanner(null), null)
  assert.equal(model.botBanner(completed(), { dismissed: true }), null)
  assert.deepEqual(model.botBanner(completed('click-1', '**Done**\n- a')), { title: 'Bot request: completed', message: 'The maintaining bot completed this request.', tone: 'info', answer: '**Done**\n- a', summary: 'Done', collapsible: true, expanded: false, canRetry: false, canDismiss: true })
  assert.equal(model.botBanner(completed(), { expanded: true }).expanded, true)
  for (const status of ['failed', 'offline', 'unknown']) {
    assert.deepEqual(model.botBanner({ activationId: 'a', status, message: 'm' }), { title: `Bot request: ${status}`, message: 'm', tone: 'failed', answer: null, summary: '', collapsible: false, expanded: false, canRetry: true, canDismiss: true })
    assert.equal(model.botBanner({ status, message: 'm' }).canRetry, false)
  }
  for (const status of ['submitted', 'queued', 'busy']) assert.equal(model.botBanner({ activationId: 'a', status }).canDismiss, false)
  assert.equal(model.botDismissKey({ activationId: 'a', status: 'failed' }), 'a:failed')
  assert.equal(model.botDismissKey({ status: 'failed' }), null)
  assert.equal(model.botDismissKey(null), null)
})

test('a long completed answer starts collapsed and expands into rendered markdown', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed())
    const summary = document.querySelector('.ls-answer-summary')
    assert.equal(summary.textContent, 'Here is the summary of three findings.')
    assert.equal(document.querySelector('.ls-answer'), null)
    assert.doesNotMatch(text(), /Line 39 of a long answer/)
    assert.equal(button('Show answer').getAttribute('aria-expanded'), 'false')
    await click('Show answer')
    const answer = document.querySelector('.ls-answer')
    assert.equal(button('Hide answer').getAttribute('aria-expanded'), 'true')
    assert.equal(button('Hide answer').getAttribute('aria-controls'), answer.id)
    assert.equal(answer.getAttribute('tabindex'), '0')
    assert.ok(answer.getAttribute('aria-label'))
    assert.deepEqual([...answer.querySelectorAll('li')].map(li => li.textContent), ['First item with bold text', 'Second item continued here', 'Third docs'])
    assert.deepEqual([...answer.querySelectorAll('strong')].map(node => node.textContent), ['three', 'bold'])
    assert.match(answer.textContent, /Line 39 of a long answer/)
    const link = answer.querySelector('a')
    assert.equal(link.getAttribute('href'), 'https://example.com/docs')
    const event = new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })
    await act(async () => link.dispatchEvent(event))
    assert.equal(event.defaultPrevented, true)
    assert.deepEqual(controller.links, ['https://example.com/docs'])
    await click('Hide answer')
    assert.equal(document.querySelector('.ls-answer'), null)
    assert.ok(document.querySelector('.ls-answer-summary'))
  } finally { await unmount() }
})
test('raw HTML in an answer renders as text, not elements', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed('click-1', 'Intro\n\n<script>window.pwned = 1</script><img src=x onerror=alert(1)>\n[bad](javascript:alert(1))'))
    await click('Show answer')
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
    assert.doesNotMatch(text(), /Bot request/)
    assert.equal(localStorage.getItem('living-spaces:bot-dismissed:demo-backend:demo-profile:demo-space'), 'click-1:completed')
    await publish(controller, completed())
    await act(async () => view.render(React.createElement(SpaceView, props())))
    assert.doesNotMatch(text(), /Bot request/)
    await unmount()
    controller = await mount()
    await publish(controller, completed())
    assert.doesNotMatch(text(), /Bot request/)
    await publish(controller, { activationId: 'click-1', status: 'failed', message: 'Native request failed.' })
    assert.match(text(), /Bot request: failed/)
    await publish(controller, completed('click-2', 'Another answer'))
    assert.match(text(), /Bot request: completed/)
    assert.match(document.querySelector('.ls-answer-summary').textContent, /Another answer/)
  } finally { await unmount() }
})
test('expanded state resets when the activation changes', async () => {
  fresh()
  const controller = await mount()
  try {
    await publish(controller, completed())
    await click('Show answer')
    await publish(controller, completed('click-2', 'Second answer'))
    assert.equal(document.querySelector('.ls-answer'), null)
    assert.ok(button('Show answer'))
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
    assert.doesNotMatch(text(), /Bot request/)
    assert.equal(localStorage.length, 0)
    await unmount()
    controller = await mount()
    await publish(controller, { ...refused })
    assert.match(text(), /Bot request: failed/)
  } finally { await unmount() }
})
for (const status of ['failed', 'offline', 'unknown']) {
  test(`${status} bot status keeps Retry same request and Check bot status`, async () => {
    fresh()
    const controller = await mount()
    try {
      await publish(controller, { activationId: 'click-1', status, message: `Status ${status}. No automatic resend.` })
      assert.equal(document.querySelector('.ls-banner').getAttribute('role'), 'alert')
      await click('Retry same request')
      await click('Check bot status')
      assert.equal(controller.retries, 1)
      assert.equal(controller.checks, 1)
      assert.ok(button('Dismiss'))
      assert.equal(button('Show answer'), undefined)
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
      assert.equal(button('Dismiss'), undefined)
      assert.ok(button('Check bot status'))
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
    assert.doesNotMatch(text(), /Bot request/)
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
