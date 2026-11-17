import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { resolveObjectURL } from 'node:buffer'
import { projectResolver, spaceLoader } from '../../../src/guest/loader.mjs'

const runtime = new URL('../../../src/living-spaces/runtime/', import.meta.url)
const shelf = JSON.parse(readFileSync(new URL('vendor/SHELF.json', runtime)))
const fonts = [
  ['newsreader', 'Newsreader'],
  ['bricolage-grotesque', 'Bricolage Grotesque'],
  ['jetbrains-mono', 'JetBrains Mono']
]
const read = path => readFileSync(new URL(path, runtime))

async function loadAssets(t, files) {
  const names = ['window', 'document', 'DOMParser', 'URL', 'console', 'setInterval', 'clearInterval']
  const original = Object.fromEntries(names.map(name => [name, globalThis[name]]))
  const events = new Map(), urls = []
  const element = () => ({ attributes: [], childNodes: [], append() {}, setAttribute() {} })
  const document = { head: element(), body: element(), documentElement: element(),
    addEventListener() {}, createElement: element, querySelector() { return null } }
  const parent = {}
  const window = { parent, addEventListener: (name, fn) => events.set(name, fn),
    removeEventListener: name => events.delete(name) }
  const DOMParser = class {
    parseFromString() {
      return { title: '', head: element(), body: element(), documentElement: element(), querySelectorAll: () => [] }
    }
  }
  const URL = class extends original.URL {
    static createObjectURL(blob) {
      const url = original.URL.createObjectURL(blob)
      urls.push(url)
      return url
    }
  }
  t.after(() => urls.forEach(url => original.URL.revokeObjectURL(url)))
  try {
    Object.assign(globalThis, { window, document, DOMParser, URL,
      console: { warn() {}, error() {} }, setInterval() { return 1 }, clearInterval() {} })
    spaceLoader(projectResolver())
    events.get('message')({ source: parent, data: { type: 'space-boot', v: 1, grants: [], bundle: {
      space: { id: 'font-source-fixture', name: 'Font source fixture' }, rev: 1,
      manifest: { entry: 'index.html', imports: {} },
      files: [{ path: 'index.html', mime: 'text/html', text: '<main>Font fixture</main>' }, ...files]
    } }, ports: [{ postMessage() {}, close() {} }] })
    await new Promise(resolve => setImmediate(resolve))
    return { asset: window.space.asset, urls }
  } finally {
    Object.assign(globalThis, original)
  }
}

for (const [font, family] of fonts) {
  test(`${family} has an opt-in, pinned four-file group within the byte budget`, () => {
    const group = shelf.libraries[`font:${font}`]
    assert.ok(group, `font:${font} is absent from the base shelf`)
    assert.deepEqual(Object.keys(group).sort(), ['files', 'license', 'version'])
    assert.equal(group.version, '5.3.0')
    assert.equal(group.license, 'OFL-1.1')
    assert.deepEqual([...group.files].sort(), [
      `vendor/fonts/${font}.css`, `vendor/fonts/${font}-latin-400-normal.woff2`,
      `vendor/fonts/${font}-latin-700-normal.woff2`, `vendor/licenses/${font}-LICENSE`
    ].sort())
    let total = 0
    for (const path of group.files) {
      const bytes = read(path), metadata = shelf.files[path]
      assert.equal(metadata.package, `@fontsource/${font}`)
      assert.equal(metadata.version, '5.3.0')
      assert.equal(metadata.license, 'OFL-1.1')
      assert.equal(bytes.length, metadata.bytes)
      assert.equal(createHash('sha256').update(bytes).digest('hex'), metadata.sha256)
      if (path.endsWith('.woff2')) assert.equal(bytes.subarray(0, 4).toString(), 'wOF2')
      total += bytes.length
    }
    assert.ok(total <= 1024 * 1024, `${family} copies ${total} bytes including its license`)
    assert.match(read(`vendor/licenses/${font}-LICENSE`).toString(), /SIL OPEN FONT LICENSE Version 1\.1/)
    const source = shelf.sources.find(source => source.name === `@fontsource/${font}`)
    assert.equal(source.version, '5.3.0')
    assert.equal(source.url, `https://registry.npmjs.org/@fontsource/${font}/-/${font}-5.3.0.tgz`)
    assert.match(source.integrity, /^sha512-[A-Za-z0-9+/]{86}==$/)
  })

  test(`${family} declares Latin normal 400 and 700 and resolves WOFF2 through the real loader`, async t => {
    assert.ok(shelf.libraries[`font:${font}`], `font:${font} is absent from the base shelf`)
    const path = `vendor/fonts/${font}.css`, css = read(path).toString()
    assert.doesNotMatch(css, /@import|https?:|data:|local\(/i)
    const faces = [...css.matchAll(/@font-face\s*\{([^}]+)\}/g)]
    assert.equal(faces.length, 2)
    const resolver = projectResolver()
    const files = [{ path, mime: 'text/css', text: css }]
    for (const [index, weight] of [400, 700].entries()) {
      const declarations = Object.fromEntries(faces[index][1].split(';').filter(value => value.trim())
        .map(value => value.trim().split(/:\s*/)))
      assert.equal(declarations['font-family'], `'${family}'`)
      assert.equal(declarations['font-style'], 'normal')
      assert.equal(declarations['font-weight'], String(weight))
      assert.equal(declarations['font-display'], 'swap')
      assert.match(declarations['unicode-range'], /^U\+0000-00FF,/)
      assert.equal(declarations.src, `url('./${font}-latin-${weight}-normal.woff2') format('woff2')`)
      const ref = declarations.src.match(/url\('([^']+)'\)/)[1]
      const target = resolver.resolve(path, ref).path
      assert.equal(target, `vendor/fonts/${font}-latin-${weight}-normal.woff2`)
      files.push({ path: target, mime: 'font/woff2', b64: read(target).toString('base64') })
    }
    const loaded = await loadAssets(t, files)
    const cssBlob = resolveObjectURL(loaded.asset(path))
    assert.equal(cssBlob.type, 'text/css')
    const rewritten = await cssBlob.text()
    const refs = [...rewritten.matchAll(/url\("([^"]+)"\)/g)].map(match => match[1])
    assert.equal(refs.length, 2)
    for (const [index, ref] of refs.entries()) {
      assert.match(ref, /^blob:/)
      const fontBlob = resolveObjectURL(ref)
      assert.equal(fontBlob.type, 'font/woff2')
      assert.deepEqual(Buffer.from(await fontBlob.arrayBuffer()), Buffer.from(files[index + 1].b64, 'base64'))
    }
    assert.equal(loaded.asset('vendor/fonts/missing.woff2'), null)
  })
}

test('the opt-in specimen names each family and retains explicit fallback samples', () => {
  const path = new URL('kit/font-shelf.html', runtime)
  assert.ok(existsSync(path), 'The opt-in font specimen is absent at base')
  const html = readFileSync(path, 'utf8')
  for (const [font, family] of fonts) {
    assert.ok(html.includes(`href="../vendor/fonts/${font}.css"`))
    assert.ok(html.includes(`'${family}'`))
    assert.ok(html.includes(`font:${font}`))
  }
  assert.match(html, /Georgia, serif/)
  assert.match(html, /system-ui, sans-serif/)
  assert.match(html, /ui-monospace, monospace/)
  assert.match(html, /lang="th"/)
  assert.match(html, /Latin/)
  assert.match(html, /fallback/)
  assert.doesNotMatch(html, /<script|https?:\/\/|@import/i)
})

test('mandatory kit styles and modules retain their base bytes', () => {
  for (const [path, hash] of [
    ['kit/spaces-kit.css', 'cde2653ae11005b6b4cf98856bf2cba72cde83d1f5c1f2e2e7a36b26a1b90261'],
    ['kit/spaces-kit.mjs', '916ae9f9fdd6333260409b69df25cb7bcefff23164b08d3edc432ef631a175a2']
  ]) assert.equal(createHash('sha256').update(read(path)).digest('hex'), hash)
})
