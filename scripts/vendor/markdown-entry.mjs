// Source of runtime/vendor/markdown.mjs: marked 18.2.1 parses, DOMPurify 3.4.18 sanitizes, always in
// that order. The only export is renderMarkdown; there is deliberately no raw-HTML helper.
// Build: esbuild scripts/vendor/markdown-entry.mjs --bundle --format=esm --minify --legal-comments=inline
//        --platform=browser (marked and dompurify resolved from verified tarballs, see THIRD-PARTY.md).
import { Marked } from 'marked'
import createDOMPurify from 'dompurify'

const parser = new Marked({ gfm: true, breaks: false, async: false })

// Links: web, mail, in-document and in-Space relative targets. Anything with another scheme is dropped.
const SAFE_LINK = /^(?:https?:|mailto:|#|(?![a-z][a-z0-9+.-]*:)(?!\/\/))/i
// Images: Space files by relative path, or inline raster data. No remote, protocol-relative or SVG data.
const SAFE_IMAGE = /^(?:data:image\/(?:png|jpeg|gif|webp);base64,[a-z0-9+/=\s]+$|(?![a-z][a-z0-9+.-]*:)(?!\/\/)(?!\/))/i
const FORBID_TAGS = ['script', 'style', 'iframe', 'frame', 'object', 'embed', 'form', 'input', 'button', 'textarea',
  'select', 'option', 'link', 'meta', 'base', 'svg', 'math', 'template', 'video', 'audio', 'source', 'track']
const purifiers = new WeakMap()

function purifier(win) {
  if (purifiers.has(win)) return purifiers.get(win)
  const purify = createDOMPurify(win)
  purify.addHook('uponSanitizeAttribute', (node, data) => {
    const value = String(data.attrValue || '').trim()
    if (data.attrName === 'href' && !SAFE_LINK.test(value)) data.keepAttr = false
    if (data.attrName === 'src' && !(node.nodeName === 'IMG' && SAFE_IMAGE.test(value))) data.keepAttr = false
    if (data.attrName === 'srcset' || data.attrName === 'target' || data.attrName === 'ping') data.keepAttr = false
  })
  purify.addHook('afterSanitizeAttributes', node => {
    if (node.nodeName === 'IMG' && !node.getAttribute('src')) node.remove()
    if (node.nodeName === 'A' && node.getAttribute('href') && !node.getAttribute('href').startsWith('#')) {
      node.setAttribute('rel', 'noopener noreferrer')
    }
  })
  purifiers.set(win, purify)
  return purify
}

/**
 * Render untrusted Markdown into a sanitized DocumentFragment. Raw HTML in the source is sanitized,
 * never executed. Links still open only through the host (the Space loader routes link clicks to
 * link.open). Wide tables are wrapped in a focusable, labelled horizontal scroll region.
 */
export function renderMarkdown(markdown, { window: win = globalThis.window, tableLabel = 'Table' } = {}) {
  if (!win?.document) throw new TypeError('renderMarkdown needs a window')
  const html = parser.parse(String(markdown ?? ''))
  const fragment = purifier(win).sanitize(html, {
    RETURN_DOM_FRAGMENT: true,
    FORBID_TAGS,
    FORBID_ATTR: ['style', 'srcset', 'target', 'ping', 'formaction', 'action'],
    ALLOW_DATA_ATTR: false,
    ALLOW_UNKNOWN_PROTOCOLS: false,
  })
  let index = 0
  for (const table of [...fragment.querySelectorAll('table')]) {
    const region = win.document.createElement('div')
    region.className = 'md-table'
    region.setAttribute('role', 'region')
    region.setAttribute('tabindex', '0')
    region.setAttribute('aria-label', `${tableLabel} ${++index}`)
    table.replaceWith(region)
    region.append(table)
  }
  return fragment
}

export const versions = Object.freeze({ marked: '18.2.1', dompurify: '3.4.18' })
