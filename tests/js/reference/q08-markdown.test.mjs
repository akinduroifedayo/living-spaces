import assert from 'node:assert/strict'
import test from 'node:test'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Offline DOM fixtures over the real vendored bundle. Not native or visual evidence.
const require = createRequire(resolve(homedir(), '.hermes/hermes-agent/apps/desktop/node_modules/react/package.json'))
const { JSDOM } = require('jsdom')
const md = await import('markdown')
const win = () => new JSDOM('<!doctype html><body></body>').window
const render = (source, options = {}) => {
  const window = win(), host = window.document.createElement('article')
  host.append(md.renderMarkdown(source, { window, ...options }))
  window.document.body.append(host)
  return { window, host }
}

test('the markdown bundle is self-contained and exposes only the safe renderer', () => {
  const source = readFileSync('src/living-spaces/runtime/vendor/markdown.mjs', 'utf8')
  assert.doesNotMatch(source, /\bimport\s*[\s{*"'(]|\brequire\(|\bfetch\(|XMLHttpRequest|sendBeacon/)
  assert.deepEqual(Object.keys(md).sort(), ['renderMarkdown', 'versions'])
  assert.deepEqual(md.versions, { marked: '18.2.1', dompurify: '3.4.18' })
  assert.throws(() => md.renderMarkdown('# x', { window: {} }), TypeError)
})

test('hostile Markdown keeps no script, handler, frame, form or style', () => {
  const hostile = [
    '<script>globalThis.pwned = 1</script>',
    '<img src="x.png" onerror="globalThis.pwned = 2">',
    '<a href="#" onclick="globalThis.pwned = 3">click</a>',
    '<iframe src="https://example.com"></iframe><object data="x"></object><embed src="x">',
    '<form action="https://example.com"><input name="q"><button formaction="javascript:alert(1)">go</button></form>',
    '<style>body{display:none}</style><p style="position:fixed">styled</p>',
    '<svg><script>alert(1)</script><a xlink:href="javascript:alert(1)">s</a></svg>',
    '<math><mi xlink:href="javascript:alert(1)">m</mi></math>',
    '<details open ontoggle="globalThis.pwned = 4">d</details>',
    '<meta http-equiv="refresh" content="0;url=https://example.com"><base href="https://example.com/">',
    '<div data-x="1" srcset="a.png 1x">data</div>',
  ].join('\n\n')
  const { window, host } = render(hostile)
  for (const tag of ['script', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'style', 'svg', 'math', 'meta', 'base'])
    assert.equal(host.querySelector(tag), null, tag)
  for (const element of host.querySelectorAll('*'))
    for (const { name } of element.attributes)
      assert.ok(!/^on|^style$|^srcset$|^data-|^formaction$|^action$/i.test(name), `${element.tagName} kept ${name}`)
  assert.equal(window.pwned, undefined)
  assert.equal(host.querySelector('img').getAttribute('src'), 'x.png')
})

test('only web, mail, in-document and in-Space relative links survive', () => {
  const links = {
    'https://example.com/a': true, 'http://example.com': true, 'mailto:demo@example.com': true,
    '#section-2': true, 'notes/chapter.md': true, './a b.html': true,
    'javascript:alert(1)': false, 'JaVaScRiPt:alert(1)': false, ' javascript:alert(1)': false,
    'java&#x09;script:alert(1)': false, 'data:text/html,<script>alert(1)</script>': false,
    'vbscript:msgbox(1)': false, 'file:///etc/passwd': false, '//evil.example/x': false, 'blob:https://x/y': false,
  }
  for (const [href, kept] of Object.entries(links)) {
    const { host } = render(`<a href="${href}">link</a>`)
    const anchor = host.querySelector('a')
    assert.equal(anchor?.hasAttribute('href') ?? false, kept, href)
    if (kept && !href.startsWith('#')) assert.equal(anchor.getAttribute('rel'), 'noopener noreferrer', href)
    assert.equal(anchor?.hasAttribute('target') ?? false, false, href)
  }
  const { host } = render('[safe](https://example.com) and [bad](javascript:alert(1)) and <https://example.org>')
  assert.deepEqual([...host.querySelectorAll('a[href]')].map(a => a.getAttribute('href')), ['https://example.com', 'https://example.org'])
})

test('images come only from Space files or inline raster data', () => {
  const png = 'data:image/png;base64,iVBORw0KGgo='
  const cases = {
    'images/figure.png': true, [png]: true,
    'https://cdn.example.com/x.png': false, '//cdn.example.com/x.png': false, '/abs/x.png': false,
    'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=': false, 'javascript:alert(1)': false, 'file:///x.png': false,
  }
  for (const [src, kept] of Object.entries(cases)) {
    const { host } = render(`![Figure 1](${src})`)
    const img = host.querySelector('img')
    assert.equal(Boolean(img), kept, src)
    if (kept) assert.equal(img.getAttribute('alt'), 'Figure 1')
  }
})

test('headings, code, citations and footnote-style references keep their structure and destination', () => {
  const { host } = render([
    '# Title', '## Methods', '### Sampling',
    'As shown by [Smith 2024](https://doi.org/10.1000/xyz)[^1] and in [the appendix](#appendix).',
    '> Quoted claim', '> — Source',
    '```js', 'const x = "<b>not html</b>"', '```',
    'Inline `<script>` stays text.',
    '[^1]: Smith, J. (2024). A study.',
  ].join('\n\n'))
  assert.deepEqual([...host.querySelectorAll('h1, h2, h3')].map(h => `${h.tagName}:${h.textContent}`), ['H1:Title', 'H2:Methods', 'H3:Sampling'])
  assert.equal(host.querySelector('a[href="https://doi.org/10.1000/xyz"]').textContent, 'Smith 2024')
  assert.equal(host.querySelector('a[href="#appendix"]').textContent, 'the appendix')
  assert.equal(host.querySelector('blockquote').textContent.includes('Quoted claim'), true)
  assert.equal(host.querySelector('pre code').textContent.trim(), 'const x = "<b>not html</b>"')
  assert.equal(host.querySelector('pre code b'), null)
  assert.equal(host.querySelector('p code').textContent, '<script>')
})

test('wide tables get a focusable, labelled scroll region', () => {
  const header = '| ' + Array.from({ length: 14 }, (_, i) => `Column ${i + 1} long heading`).join(' | ') + ' |'
  const rule = '|' + ' --- |'.repeat(14)
  const row = '| ' + Array.from({ length: 14 }, (_, i) => `value ${i}`).join(' | ') + ' |'
  const { host } = render(`${header}\n${rule}\n${row}\n\ntext\n\n| a |\n| - |\n| 1 |`, { tableLabel: 'Data table' })
  const regions = host.querySelectorAll('div.md-table')
  assert.equal(regions.length, 2)
  assert.equal(regions[0].getAttribute('role'), 'region')
  assert.equal(regions[0].getAttribute('tabindex'), '0')
  assert.equal(regions[0].getAttribute('aria-label'), 'Data table 1')
  assert.equal(regions[0].querySelectorAll('th').length, 14)
  assert.equal(regions[1].getAttribute('aria-label'), 'Data table 2')
})

test('a long document renders completely and in order', () => {
  const sections = Array.from({ length: 120 }, (_, i) => `## Section ${i + 1}\n\n${'Paragraph text. '.repeat(60)}`)
  const started = performance.now()
  const { host } = render(sections.join('\n\n'))
  const elapsed = performance.now() - started
  const headings = [...host.querySelectorAll('h2')].map(h => h.textContent)
  assert.equal(headings.length, 120)
  assert.equal(headings[0], 'Section 1')
  assert.equal(headings.at(-1), 'Section 120')
  assert.ok(elapsed < 5000, `rendered in ${elapsed} ms`)
})

test('empty and non-string input render an empty fragment', () => {
  for (const value of ['', null, undefined]) assert.equal(render(value).host.childNodes.length, 0)
  assert.equal(render(42).host.textContent.trim(), '42')
})
