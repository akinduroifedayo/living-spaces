import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { setTimeout as delay } from 'node:timers/promises'
import { readFileSync } from 'node:fs'
import { linkTarget, mountSpace, checkGrant } from '../../../src/desktop/sandbox/index.js'

test('a public https source link is accepted and normalized for display', () => {
  assert.deepEqual(linkTarget('https://example.com/papers/42?page=2#fig-1'), { ok: true, url: 'https://example.com/papers/42?page=2#fig-1', host: 'example.com' })
  assert.deepEqual(linkTarget('https://EXAMPLE.org'), { ok: true, url: 'https://example.org/', host: 'example.org' })
  assert.equal(linkTarget('https://example.com/#section-token-docs').ok, true, 'an ordinary fragment is not a secret')
})

for (const [name, url] of [
  ['script', 'javascript:alert(1)'],
  ['file', 'file:///etc/hosts'],
  ['data', 'data:text/html,<script>alert(1)</script>'],
  ['blob', 'blob:https://example.com/1'],
  ['plain http', 'http://example.com/'],
  ['custom scheme', 'hermes://settings'],
  ['mailto', 'mailto:someone@example.com'],
  ['user and password', 'https://user:pass@example.com/'],
  ['user only', 'https://user@example.com/'],
  ['token query', 'https://example.com/?access_token=fixture'],
  ['signed url query', 'https://example.com/file?X-Amz-Signature=fixture'],
  ['api key query', 'https://example.com/?api_key=fixture'],
  ['localhost', 'https://localhost/'],
  ['localhost subdomain', 'https://app.localhost/'],
  ['loopback ip', 'https://127.0.0.1/'],
  ['private ip', 'https://192.168.1.10/'],
  ['ipv6 literal', 'https://[::1]/'],
  ['mdns name', 'https://printer.local/'],
  ['single label', 'https://intranet/'],
  ['malformed', 'https://'],
  ['relative', '/papers/42'],
  ['whitespace', 'https://example.com/a b'],
  ['control character', 'https://example.com/\u0000'],
  ['too long', `https://example.com/${'a'.repeat(2048)}`],
  ['token fragment', 'https://example.com/#access_token=fixture'],
  ['id token fragment after route', 'https://example.com/#/cb?id_token=fixture&state=1'],
  ['empty host label', 'https://foo..com/'],
  ['trailing dot host', 'https://example.com./'],
  ['non-string', 42],
  ['missing', undefined]
]) test(`unsafe destination is refused: ${name}`, () => {
  const result = linkTarget(url)
  assert.equal(result.ok, false)
  assert.equal(typeof result.reason, 'string')
  assert.ok(result.reason.length > 0)
})

test('link.open needs no capability grant, so it reaches the session where activation is checked', () => {
  assert.equal(checkGrant('link.open', []), null)
})

test('mounted guest link requests are forwarded to the session and the reply returns to the guest', async () => {
  const originalDocument = globalThis.document
  const originalWindow = globalThis.window
  globalThis.window = new EventTarget()
  let frame
  globalThis.document = {
    createElement() {
      frame = new EventTarget()
      frame.style = {}
      frame.setAttribute = () => {}
      frame.remove = () => {}
      frame.contentWindow = { postMessage(message, origin, ports) { frame.peer = structuredClone(ports[0], { transfer: [ports[0]] }) } }
      return frame
    }
  }
  const calls = []
  const sandbox = { format: 1, shell_srcdoc: readFileSync('src/living-spaces/guest/space-host.html', 'utf8') }
  const mount = mountSpace({ append() {} }, {
    bundle: { space: { id: 'demo', name: 'Demo' }, rev: 1, manifest: {}, files: [], sandbox }, grants: [],
    call: async (op, args) => { calls.push([op, args]); return { ok: true, result: { status: 'confirming' } } }
  })
  try {
    frame.dispatchEvent(new Event('load'))
    const replies = []
    frame.peer.onmessage = e => replies.push(e.data)
    frame.peer.postMessage({ v: 1, id: 3, op: 'link.open', args: { url: 'https://example.com/' } })
    const end = Date.now() + 2000
    while (!replies.length && Date.now() < end) await delay(5)
    assert.deepEqual(calls, [['link.open', { url: 'https://example.com/' }]])
    assert.deepEqual(replies[0], { v: 1, id: 3, ok: true, result: { status: 'confirming' } })
  } finally {
    mount.destroy()
    frame.peer.close()
    globalThis.document = originalDocument
    globalThis.window = originalWindow
  }
})
