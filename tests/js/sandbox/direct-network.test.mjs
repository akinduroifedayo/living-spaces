import test from 'node:test'
import assert from 'node:assert/strict'
import * as documents from '../../../src/guest/document.mjs'

test('partition documents choose a static HTTPS or offline policy before boot', () => {
  assert.equal(typeof documents.partitionSrcdoc, 'function')
  const off = documents.partitionSrcdoc(false)
  const on = documents.partitionSrcdoc(true)
  assert.match(off, /connect-src 'none'/)
  assert.match(on, /connect-src https:/)
  for (const directive of ['script-src', 'style-src', 'img-src', 'font-src', 'media-src']) {
    assert.match(on, new RegExp(`${directive}[^;]+https:`))
  }
  assert.match(on, /frame-src 'none'/)
  assert.doesNotMatch(on, /wss:|connect-src http:/)
  assert.match(on, /__lsDrain/)
  assert.match(on, /__lsDeliver/)
})
