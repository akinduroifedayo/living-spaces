import './env.mjs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const css = readFileSync('src/living-spaces/runtime/kit/spaces-kit.css', 'utf8')
function luminance(hex) {
  const expanded = hex.length === 3 ? [...hex].map(char => char + char).join('') : hex
  const [r, g, b] = expanded.match(/../g).map(channel => {
    const value = parseInt(channel, 16) / 255
    return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4
  })
  return .2126 * r + .7152 * g + .0722 * b
}
for (const [index, block] of [...css.matchAll(/:root\s*\{([^}]+)\}/g)].entries()) {
  test(`theme ${index === 0 ? 'light' : 'dark'} text color pairs meet 4.5:1 contrast`, () => {
    const colors = Object.fromEntries([...block[1].matchAll(/--space-([\w-]+): #([\da-f]+);/g)].map(([, name, hex]) => [name, hex]))
    for (const [front, back] of [['text', 'bg'], ['text', 'card'], ['muted', 'bg'], ['muted', 'card'], ['link', 'bg'], ['link', 'card'], ['alert', 'alert-bg'], ['alert', 'bg']]) {
      const a = luminance(colors[front]), b = luminance(colors[back])
      const contrast = (Math.max(a, b) + .05) / (Math.min(a, b) + .05)
      assert.ok(contrast >= 4.5, `${front} on ${back}: ${contrast.toFixed(2)}:1`)
    }
  })
}
test('theme supplies a two-pixel keyboard focus ring and reduced motion rules', () => {
  assert.match(css, /:focus-visible\s*\{[^}]*outline: 2px solid/)
  assert.match(css, /prefers-reduced-motion: reduce/)
  assert.match(css, /prefers-color-scheme: dark/)
})
