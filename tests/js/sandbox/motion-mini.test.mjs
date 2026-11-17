import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const moduleURL = new URL('../../../src/living-spaces/runtime/vendor/motion-mini.mjs', import.meta.url)

test('optional mini exports only the pinned framework-independent browser entry', async () => {
  const mini = await import(moduleURL)
  assert.deepEqual(Object.keys(mini).sort(), ['animate', 'animateSequence'])
  assert.equal(typeof mini.animate, 'function')
  assert.equal(typeof mini.animateSequence, 'function')
  const source = await readFile(moduleURL, 'utf8')
  assert.doesNotMatch(source, /\bimport\s*(?:\(|["'{*])/)
  assert.doesNotMatch(source, /\beval\s*\(|\bnew\s+Function\s*\(/)
})
