import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import assert from 'node:assert/strict'

const root = fileURLToPath(new URL('../../../', import.meta.url))
// Rebuild with: esbuild src/inspection/runner.mjs --bundle --format=iife --outfile=src/living-spaces/inspection/runner.js
const build = () => execFileSync('esbuild', ['src/inspection/runner.mjs', '--bundle', '--format=iife', '--log-level=error'],
  { cwd: root, encoding: 'utf8' })

test('packaged inspection runner matches its source', () => {
  const packaged = readFileSync(new URL('src/living-spaces/inspection/runner.js', `file://${root}`), 'utf8')
  assert.equal(packaged.replace(/\r\n/g, '\n'), build())
})

test('runner bundles the unchanged sandbox host and nothing from the guest', () => {
  const output = build()
  const sandbox = readFileSync(new URL('src/desktop/sandbox/index.js', `file://${root}`), 'utf8')
  assert.match(output, /var MAX_REQUEST_SIZE = 1024 \* 1024/)
  assert.ok(output.includes("frame.setAttribute(\"sandbox\", \"allow-scripts\")"))
  assert.ok(sandbox.includes("frame.setAttribute('sandbox', 'allow-scripts')"))
  assert.doesNotMatch(output, /spaceLoader|projectResolver|shellRelay/)
  assert.doesNotMatch(output, /fetch\(|XMLHttpRequest|WebSocket/)
})
