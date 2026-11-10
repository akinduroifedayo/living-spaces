import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { html, hashRouter, SaveIndicator, ConflictBanner, EmptyState } from '../../../src/living-spaces/runtime/kit/spaces-kit.mjs'

const children = node => node.props.children

test('html parses nested elements, attributes and literal text', () => {
  const node = html`<section id="main"><h1>Hello</h1><p title='a > b'>World</p></section>`
  assert.equal(node.type, 'section')
  assert.equal(node.props.id, 'main')
  assert.equal(children(node)[0].type, 'h1')
  assert.equal(children(children(node)[1]), 'World')
  assert.equal(children(node)[1].props.title, 'a > b')
})
test('html preserves interpolated strings as data, numbers, booleans and arrays', () => {
  const value = '<script>bad()</script>'
  const node = html`<div>${value}${0}${false}${null}${[html`<b>A</b>`, html`<i>B</i>`]}</div>`
  assert.equal(children(node)[0], value)
  assert.equal(children(node)[1], 0)
  assert.equal(children(node)[2], false)
  assert.equal(children(node)[3], null)
  assert.equal(children(node)[4][1].type, 'i')
})
test('html handles components, props, generic closing and self-closing components', () => {
  const Comp = () => null
  const data = { note: 'public demo' }
  const node = html`<${Comp} record=${data}><b>Child</b><//>`
  assert.equal(node.type, Comp)
  assert.equal(node.props.record, data)
  assert.equal(children(node).type, 'b')
  assert.equal(html`<${Comp} />`.type, Comp)
})
test('html handles spreads, override order, event handlers and boolean attrs', () => {
  const click = () => {}
  const node = html`<button ...${{ title: 'old', disabled: false }} title="new" disabled onClick=${click}>Save</button>`
  assert.equal(node.props.title, 'new')
  assert.equal(node.props.disabled, true)
  assert.equal(node.props.onClick, click)
  assert.equal(html`<input disabled=${false} />`.props.disabled, false)
})
test('html handles quoted interpolation and mixed attribute parts', () => {
  assert.equal(html`<div class="item ${'active'} ${2}" data-id=${42}></div>`.props.class, 'item active 2')
  assert.equal(html`<div data-id=${42}></div>`.props['data-id'], 42)
  assert.equal(html`<div title="${null}"></div>`.props.title, null)
})
test('html accepts void tags, multiple roots, comments, entities and indentation', () => {
  const nodes = html`<br><input value="&quot;hello&quot;"><p>&amp; &#65; &#x42;</p>`
  assert.equal(nodes.length, 3)
  assert.equal(nodes[1].props.value, '"hello"')
  assert.equal(children(nodes[2]), '& A B')
  assert.equal(children(html`
    <p>
      Hello world
    </p>
  `), 'Hello world')
  assert.equal(children(html`<p>A<!-- comment -->B</p>`).join(''), 'AB')
})
test('html rejects malformed tags and attributes', () => {
  assert.throws(() => html`<p>`, /unclosed/)
  assert.throws(() => html`<p></div>`, /does not match/)
  assert.throws(() => html`</p>`, /unexpected/)
  assert.throws(() => html`<p title="unterminated>`, /unclosed attribute/)
  assert.throws(() => html`<p ...literal />`, /spread/)
})
test('html nested templates and mapped children remain VNodes', () => {
  const node = html`<ul>${['A', 'B'].map(text => html`<li key=${text}>${text}</li>`)}</ul>`
  assert.equal(children(node)[1].key, 'B')
  assert.equal(children(children(node)[0]), 'A')
})
test('status and conflict components expose accessible status and explicit actions', () => {
  const status = SaveIndicator({ state: 'saved' })
  assert.equal(status.props.role, 'status')
  assert.ok(children(status).includes('Saved'))
  const current = { rev: 3 }
  const actions = []
  const banner = ConflictBanner({ current, onKeepMine: r => actions.push(['mine', r]), onUseUpdated: r => actions.push(['updated', r]) })
  assert.equal(banner.props.role, 'alert')
  const buttons = children(banner).filter(node => node?.type === 'button')
  buttons[0].props.onClick()
  buttons[1].props.onClick()
  assert.deepEqual(actions, [['mine', current], ['updated', current]])
  assert.equal(EmptyState({}).type, 'section')
})
test('hashRouter matches parameters, fallback, escaping and encoded ids', () => {
  const original = globalThis.location
  globalThis.location = { hash: '#/item/a%3Ab' }
  const Item = () => null
  const Missing = () => null
  const router = hashRouter({ '/item/:id': Item, '/a.b': Item, '*': Missing })
  assert.deepEqual(router.route.params, { id: 'a:b' })
  assert.equal(router.route.component, Item)
  router.navigate('/axb')
  assert.equal(router.route.component, Missing)
  globalThis.location.hash = '#/item/%zz'
  assert.equal(router.route.component, Missing)
  router.destroy()
  globalThis.location = original
})
