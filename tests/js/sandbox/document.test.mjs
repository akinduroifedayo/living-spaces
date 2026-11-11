import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { SPACE_CSP, spaceSrcdoc, shellSrcdoc } from '../../../src/guest/document.mjs'
import { checkRendererGraph } from '../../../scripts/check-renderer-graph.mjs'

const installed = readFileSync('src/living-spaces/guest/space-host.html', 'utf8')

test('the shipped plaintext document equals deterministic producer output', () => {
  assert.equal(installed, shellSrcdoc())
  assert.equal(shellSrcdoc(), shellSrcdoc())
  assert.equal(spaceSrcdoc(), spaceSrcdoc())
  for (const source of [installed, spaceSrcdoc()]) {
    assert.ok(source.indexOf(`content="${SPACE_CSP}"`) < source.indexOf('<script>'))
    assert.ok(!source.includes('allow-forms'))
  }
})

test('the shipped shell admits one parent boot and retains the inner policy and reload signal', () => {
  const events = new Map(), frames = [], relays = [], signals = []
  const parent = { postMessage: (...args) => signals.push(args) }
  const window = { parent, addEventListener: (name, fn) => events.set(name, fn), removeEventListener: name => events.delete(name) }
  const document = {
    body: { append: frame => frames.push(frame) },
    createElement(tag) {
      assert.equal(tag, 'iframe')
      const frame = { attributes: {}, style: {}, setAttribute(name, value) { this.attributes[name] = value },
        addEventListener(name, fn) { this[name] = fn }, contentWindow: { postMessage: (...args) => relays.push(args) } }
      return frame
    }
  }
  vm.runInNewContext(installed.match(/<script>([\s\S]*)<\/script>/)[1], { window, document })
  const receive = message => events.get('message')?.(message)
  const port = {}, boot = { type: 'space-boot', v: 1, bundle: { files: [] }, grants: ['data'] }
  receive({ source: {}, data: boot, ports: [port] })
  receive({ source: parent, data: { ...boot, v: 2 }, ports: [port] })
  receive({ source: parent, data: boot, ports: [] })
  assert.equal(frames.length, 0)
  receive({ source: parent, data: boot, ports: [port] })
  receive({ source: parent, data: boot, ports: [port] })
  assert.equal(frames.length, 1)
  assert.equal(events.size, 0)
  const frame = frames[0]
  assert.deepEqual(frame.attributes, { sandbox: 'allow-scripts', referrerpolicy: 'no-referrer' })
  assert.equal(frame.srcdoc, spaceSrcdoc())
  frame.load()
  assert.equal(relays.length, 1)
  assert.equal(relays[0][0], boot)
  assert.equal(relays[0][1], '*')
  assert.equal(relays[0][2][0], port)
  frame.load()
  assert.equal(relays.length, 1)
  assert.equal(signals[0][0].type, 'space-reloaded')
  assert.equal(signals[0][0].v, 1)
})

test('the renderer graph gate rejects guest modules, guest HTML and the removed loader', () => {
  const graph = inputs => ({ inputs: Object.fromEntries(inputs.map(path => [path, {}])), outputs: { 'plugin.js': {} } })
  checkRendererGraph(graph(['src/desktop/plugin.src.js', 'src/desktop/sandbox/index.js']))
  for (const path of ['src/guest/loader.mjs', 'src/guest/document.mjs', 'src/living-spaces/guest/space-host.html', 'src/desktop/sandbox/loader.js']) {
    assert.throws(() => checkRendererGraph(graph([path])), /Guest code in renderer graph/)
  }
  assert.throws(() => checkRendererGraph({ inputs: {}, outputs: {} }), /must contain inputs and outputs/)
  checkRendererGraph(JSON.parse(readFileSync('.run/package/desktop-metafile.json', 'utf8')))
})

const ordinaryRendererInputs = ['src/desktop/plugin.src.js', 'src/desktop/sandbox/index.js', 'src/desktop/ui/space.jsx']
const canonicalGuestInputs = ['src/guest/loader.mjs', 'src/guest/document.mjs', 'src/living-spaces/guest/space-host.html', 'src/desktop/sandbox/loader.js']
const caseVariantGuestInputs = ['src/Guest/loader.mjs', 'src/GUEST/document.mjs', 'src/Living-Spaces/Guest/space-host.html', 'src/living-spaces/GUEST/space-host.html']
const metafileOf = inputs => ({ inputs: Object.fromEntries(inputs.map(path => [path, {}])), outputs: { 'plugin.js': {} } })
const rejectsGuest = path => error => /Guest code in renderer graph/.test(error.message) && error.message.includes(path)

async function inForeignDirectory(run) {
  const { mkdtempSync, rmSync } = await import('node:fs')
  const { tmpdir } = await import('node:os')
  const { join } = await import('node:path')
  const origin = process.cwd()
  const scratch = mkdtempSync(join(tmpdir(), 'renderer-graph-'))
  try {
    process.chdir(scratch)
    return await run(scratch)
  } finally {
    process.chdir(origin)
    rmSync(scratch, { recursive: true, force: true })
  }
}

test('the renderer graph gate judges root-relative inputs identically from a foreign working directory', async () => {
  const verdicts = () => {
    checkRendererGraph(metafileOf(ordinaryRendererInputs))
    for (const path of canonicalGuestInputs) {
      assert.throws(() => checkRendererGraph(metafileOf([...ordinaryRendererInputs, path])), rejectsGuest(path), path)
    }
  }
  verdicts()
  await inForeignDirectory(async () => verdicts())
})

test('the renderer graph gate rejects case-variant guest paths from the root and from a foreign working directory', async () => {
  const verdicts = () => {
    checkRendererGraph(metafileOf(ordinaryRendererInputs))
    for (const path of caseVariantGuestInputs) {
      assert.throws(() => checkRendererGraph(metafileOf([...ordinaryRendererInputs, path])), rejectsGuest(path), path)
    }
  }
  verdicts()
  await inForeignDirectory(async () => verdicts())
})

test('the renderer graph command exits nonzero for guest metafile inputs and zero for ordinary ones from any working directory', async () => {
  const { spawnSync } = await import('node:child_process')
  const { writeFileSync } = await import('node:fs')
  const { join } = await import('node:path')
  const { fileURLToPath } = await import('node:url')
  const script = fileURLToPath(new URL('../../../scripts/check-renderer-graph.mjs', import.meta.url))
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  await inForeignDirectory(async scratch => {
    const run = (inputs, cwd) => {
      const metafile = join(scratch, 'renderer.meta.json')
      writeFileSync(metafile, JSON.stringify(metafileOf(inputs)))
      return spawnSync(process.execPath, [script, metafile], { cwd, encoding: 'utf8', env: { PATH: process.env.PATH, HOME: scratch, TMPDIR: scratch } })
    }
    for (const cwd of [scratch, root]) {
      const accepted = run(ordinaryRendererInputs, cwd)
      assert.equal(accepted.status, 0, `ordinary inputs from ${cwd}: ${accepted.stderr}`)
      assert.match(accepted.stdout, /Renderer graph excludes guest code and guest HTML/)
      for (const path of [...canonicalGuestInputs, ...caseVariantGuestInputs]) {
        const rejected = run([...ordinaryRendererInputs, path], cwd)
        assert.equal(rejected.status, 1, `${path} from ${cwd}: ${rejected.stdout}`)
        assert.match(rejected.stderr, /Guest code in renderer graph/)
        assert.ok(rejected.stderr.includes(path), `${path} named in the failure from ${cwd}`)
      }
    }
  })
})
