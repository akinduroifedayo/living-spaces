import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveObjectURL } from 'node:buffer'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { spaceSrcdoc } from '../../../src/guest/document.mjs'

const require = createRequire(join(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const { JSDOM } = require('jsdom')

async function boot(t, { html = '<html><head></head><body></body></html>', manifest = {}, files = [] } = {}) {
  const dom = new JSDOM(spaceSrcdoc(), { runScripts: 'outside-only' })
  const { window } = dom
  const messages = [], warnings = [], urls = []
  window.console.warn = (...args) => warnings.push(args)
  window.Blob = Blob
  window.URL = class extends URL {
    static createObjectURL(blob) {
      const url = URL.createObjectURL(blob)
      urls.push(url)
      return url
    }
  }
  t.after(() => { dom.window.close(); urls.forEach(url => URL.revokeObjectURL(url)) })
  window.eval(window.document.querySelector('script').textContent)
  const port = { postMessage: message => messages.push(structuredClone(message)), close() {} }
  const bundle = {
    space: { id: 'guest-demo', name: 'Guest Demo' }, rev: 1, manifest,
    files: [{ path: manifest.entry || 'index.html', mime: 'text/html', text: html }, ...files]
  }
  window.dispatchEvent(new window.MessageEvent('message', {
    source: window.parent, data: { type: 'space-boot', v: 1, bundle, grants: ['data'] }, ports: [port]
  }))
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(window.document.querySelector('[role=alert]'), null, window.document.body.textContent)
  return { window, document: window.document, api: window.space, messages, warnings, port }
}

test('boot copies vetted html attributes, drops handlers, and retains body attributes', async t => {
  const { document } = await boot(t, { html: `
    <html lang="fr" dir="rtl" class="editorial-page" data-theme="editorial" data-view="library"
      style="--space-bg: ivory" onclick="bad()" ONLOAD="bad()" id="unvetted" title="unvetted">
    <head></head><body class="app" data-page="home" style="margin: 0"><main>Public demo</main></body></html>` })
  assert.deepEqual(Object.fromEntries([...document.documentElement.attributes].map(a => [a.name, a.value])), {
    lang: 'fr', dir: 'rtl', class: 'editorial-page', 'data-theme': 'editorial', 'data-view': 'library', style: '--space-bg: ivory'
  })
  assert.equal(document.body.className, 'app')
  assert.equal(document.body.dataset.page, 'home')
  assert.equal(document.body.style.margin, '0px')
  assert.equal(document.querySelector('main').textContent, 'Public demo')
})

test('manifest preset wins and one token style precedes every app stylesheet', async t => {
  const { document, warnings } = await boot(t, {
    html: '<html data-theme="editorial"><head><link rel="stylesheet" href="app.css"><style>:root{--space-bg:pink}</style></head><body><style>body{color:black}</style></body></html>',
    manifest: { theme: { preset: 'terminal', tokens: { bg: 'ivory', 'font-body': 'system-ui', radius: '12px' } } },
    files: [{ path: 'app.css', mime: 'text/css', text: ':root{--space-bg:plum}' }]
  })
  assert.equal(document.documentElement.dataset.theme, 'terminal')
  const styles = [...document.querySelectorAll('style,link[rel=stylesheet]')]
  assert.equal(document.querySelectorAll('style[data-space-theme]').length, 1)
  assert.equal(styles[0].hasAttribute('data-space-theme'), true)
  assert.equal(styles[0].textContent, ':root{--space-bg:ivory;--space-font-body:system-ui;--space-radius:12px;}')
  assert.equal(styles.length, 4)
  assert.match(styles[1].href, /^blob:/)
  assert.equal(styles[2].textContent, ':root{--space-bg:pink}')
  assert.equal(warnings.length, 0)
})

test('tokens alone preserve the entry html preset', async t => {
  const { document } = await boot(t, {
    html: '<html data-theme="journal"><body></body></html>', manifest: { theme: { tokens: { bg: 'ivory' } } }
  })
  assert.equal(document.documentElement.dataset.theme, 'journal')
  assert.equal(document.querySelector('[data-space-theme]').textContent, ':root{--space-bg:ivory;}')
})

test('all frozen presets are applied without requiring tokens', async t => {
  for (const preset of ['editorial', 'terminal', 'playful', 'minimal', 'data', 'journal', 'game']) {
    const { document, warnings } = await boot(t, { manifest: { theme: { preset } } })
    assert.equal(document.documentElement.dataset.theme, preset)
    assert.equal(warnings.length, 0)
  }
})

test('invalid tokens are skipped while valid boundary values survive, with one warning', async t => {
  const valid = { bg: '#fafafa', ['a'.repeat(40)]: 'x'.repeat(200), unicode: '😀'.repeat(200) }
  const tokens = { ...valid, Upper: 'red', '1bad': 'red', 'bad_name': 'red', 'trailing\n': 'red', 'trailing\r': 'red',
    'trailing\u2028': 'red', 'trailing\u2029': 'red', ['a'.repeat(41)]: 'red',
    long: 'x'.repeat(201), 'unicode-long': '😀'.repeat(201), number: 1, nil: null, object: {}, array: [] }
  for (const [i, value] of ['red;--space-bg:black', '{red', 'red}', '<red', 'red>', 'r\\ed', 'URL(demo)', '@IMPORT demo', 'ExPrEsSiOn(demo)'].entries()) tokens[`bad-${i}`] = value
  const { document, warnings } = await boot(t, { manifest: { theme: { tokens } } })
  assert.equal(document.querySelector('[data-space-theme]')?.textContent, `:root{${Object.entries(valid).map(([name, value]) => `--space-${name}:${value};`).join('')}}`)
  assert.equal(warnings.length, 1)
})

test('theme token count is bounded at 64 and overflow warns once', async t => {
  const tokens = Object.fromEntries(Array.from({ length: 65 }, (_, i) => [`token-${i}`, `${i}px`]))
  const { document, warnings } = await boot(t, { manifest: { theme: { tokens } } })
  const style = document.querySelector('[data-space-theme]')
  assert.ok(style)
  assert.equal(style.sheet.cssRules[0].style.length, 64)
  assert.equal(style.sheet.cssRules[0].style.getPropertyValue('--space-token-63'), '63px')
  assert.equal(style.sheet.cssRules[0].style.getPropertyValue('--space-token-64'), '')
  assert.equal(warnings.length, 1)
})

test('malformed theme fields cannot replace the entry preset or inject declarations', async t => {
  for (const theme of [null, [], 'terminal', { preset: 'unknown', tokens: { bad: 'red;' } }, { tokens: [] }, { tokens: 'red' }, { tokens: null }]) {
    const { document, warnings } = await boot(t, {
      html: '<html data-theme="minimal"><body></body></html>', manifest: { theme }
    })
    assert.equal(document.documentElement.dataset.theme, 'minimal')
    assert.equal(document.querySelector('[data-space-theme]'), null)
    assert.equal(warnings.length, 1)
  }
})

test('space.asset resolves a project-root image for DOM created after boot', async t => {
  const b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4u8AAAAASUVORK5CYII='
  const { api, document } = await boot(t, {
    manifest: { entry: 'views/home.html' }, files: [{ path: 'images/pixel.png', mime: 'image/png', b64 }]
  })
  const image = document.createElement('img')
  image.src = api.asset('./images/pixel.png')
  document.body.append(image)
  assert.match(image.src, /^blob:/)
  assert.equal(api.asset('images/pixel.png'), image.src)
  assert.equal(api.asset('././images/pixel.png'), image.src)
  const blob = resolveObjectURL(image.src)
  assert.equal(blob.type, 'image/png')
  assert.deepEqual(Buffer.from(await blob.arrayBuffer()), Buffer.from(b64, 'base64'))
  for (const path of ['missing.png', 'https://example.com/pixel.png', '//example.com/pixel.png', '#pixel', null, undefined, 42, '%zz']) {
    assert.equal(api.asset(path), null)
  }
})

test('space.net.fetch sends exactly the frozen operation and defined fields', async t => {
  const { api, messages, port } = await boot(t)
  const url = 'https://example.com/public-demo'
  const cases = [
    [undefined, { url }],
    [{ method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: 'demo', as: 'json', ignored: true },
      { url, method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: 'demo', as: 'json' }],
    [{ method: undefined, headers: undefined, body: '', as: undefined }, { url, body: '' }],
    [{ method: '', headers: null, body: false, as: null }, { url, method: '', headers: null, body: false, as: null }],
    [{ body: 0, as: 'bytes' }, { url, body: 0, as: 'bytes' }]
  ]
  for (const [options, args] of cases) {
    const result = api.net.fetch(url, options)
    const message = messages.at(-1)
    assert.deepEqual(message, { v: 1, id: messages.length, op: 'net.fetch', args })
    const response = { status: 200, url, headers: {}, text: 'Public demo' }
    port.onmessage({ data: { v: 1, id: message.id, ok: true, result: response } })
    assert.deepEqual(await result, response)
  }
})

test('space.net.fetch preserves host errors and session closure behavior', async t => {
  const { api, messages, port } = await boot(t)
  for (const code of ['not_granted', 'invalid', 'limit', 'blocked']) {
    const result = api.net.fetch('https://example.com/public-demo')
    port.onmessage({ data: { v: 1, id: messages.at(-1).id, ok: false, error: { code, message: 'Public demo refusal' } } })
    await assert.rejects(result, error => error.name === 'SpaceError' && error.code === code)
  }
  const pending = api.net.fetch('https://example.com/public-demo')
  port.onmessage({ data: { v: 1, type: 'event', event: 'session.closed', payload: { reason: 'Closed' } } })
  await assert.rejects(pending, error => error.code === 'session_invalid')
  await assert.rejects(api.net.fetch('https://example.com/public-demo'), error => error.code === 'session_invalid')
  assert.equal(messages.length, 5)
})
