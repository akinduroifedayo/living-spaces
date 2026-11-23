// A deliberately small Markdown subset for bot answers. It returns plain data, never HTML:
// renderers turn blocks and spans into elements, so raw tags in the source stay literal text.

const FENCE = /^\s*```/
const HEADING = /^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/
const ITEM = /^\s*([-*+]|\d{1,9}[.)])\s+(.*)$/
// A line that is only bold text ('**Heading**' or '**Heading:**') is a heading in chat replies.
const BOLD_HEADING = /^\s*(?:\*\*([^*\n]+?)\*\*|__([^_\n]+?)__)\s*$/
const INLINE = new RegExp([
  /`([^`\n]+)`/.source,
  /\*\*([^*\n]+?)\*\*/.source,
  /__([^_\n]+?)__/.source,
  /\[([^\]\n]+)\]\(([^)\s]+)\)/.source,
  /(https:\/\/[^\s<>()]*[^\s<>().,;:!?'"])/.source,
  /(?<![\w*])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?![\w*])/.source,
  /(?<![\w_])_(?![\s_])([^_\n]+?)(?<![\s_])_(?![\w_])/.source
].join('|'), 'g')

const isHttps = href => /^https:\/\/[^\s]+$/i.test(href)

export function parseInline(line) {
  const spans = []
  const push = span => {
    const last = spans.at(-1)
    if (span.type === 'text' && last?.type === 'text') last.text += span.text
    else if (span.type !== 'text' || span.text) spans.push(span)
  }
  let index = 0
  for (const match of line.matchAll(INLINE)) {
    push({ type: 'text', text: line.slice(index, match.index) })
    const [, code, strong, strongAlt, label, href, url, em, emAlt] = match
    if (code != null) push({ type: 'code', text: code })
    else if (strong != null || strongAlt != null) push({ type: 'strong', text: strong ?? strongAlt })
    else if (label != null) push(isHttps(href) ? { type: 'link', text: label, href } : { type: 'text', text: label })
    else if (url != null) push({ type: 'link', text: url, href: url })
    else push({ type: 'em', text: em ?? emAlt })
    index = match.index + match[0].length
  }
  push({ type: 'text', text: line.slice(index) })
  return spans
}

const startsBlock = line => FENCE.test(line) || HEADING.test(line) || BOLD_HEADING.test(line) || ITEM.test(line)

export function parseMarkdown(text) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    if (FENCE.test(line)) {
      const body = []
      for (i++; i < lines.length && !FENCE.test(lines[i]); i++) body.push(lines[i])
      i++
      blocks.push({ type: 'code', text: body.join('\n') })
      continue
    }
    const heading = HEADING.exec(line)
    if (heading) { blocks.push({ type: 'heading', spans: parseInline(heading[2]) }); i++; continue }
    const bold = BOLD_HEADING.exec(line)
    if (bold) { blocks.push({ type: 'heading', spans: [{ type: 'text', text: (bold[1] ?? bold[2]).trim() }] }); i++; continue }
    const item = ITEM.exec(line)
    if (item) {
      const ordered = /\d/.test(item[1])
      const items = []
      while (i < lines.length) {
        const next = ITEM.exec(lines[i])
        if (!next || /\d/.test(next[1]) !== ordered) break
        let content = next[2]
        // Indented lines that do not start another item continue the current one.
        for (i++; i < lines.length && /^\s+\S/.test(lines[i]) && !ITEM.test(lines[i]) && !FENCE.test(lines[i]); i++) content += ` ${lines[i].trim()}`
        items.push(parseInline(content))
      }
      blocks.push({ type: 'list', ordered, items })
      continue
    }
    const spans = []
    for (; i < lines.length && lines[i].trim() && (spans.length === 0 || !startsBlock(lines[i])); i++) {
      if (spans.length) spans.push({ type: 'break' })
      spans.push(...parseInline(lines[i].trim()))
    }
    blocks.push({ type: 'paragraph', spans })
  }
  return blocks
}

const plain = spans => spans.map(span => span.type === 'break' ? ' ' : span.text).join('').replace(/\s+/g, ' ').trim()
const SUMMARY_MAX = 160
// The first sentence of the reply's first prose block (a paragraph, else a list item, else a heading),
// without markdown markers, capped at 160 characters.
export function answerSummary(text) {
  const blocks = parseMarkdown(text)
  const block = blocks.find(b => b.type === 'paragraph') || blocks.find(b => b.type === 'list') || blocks.find(b => b.type === 'heading')
  if (!block) return ''
  const line = plain(block.type === 'list' ? block.items[0] : block.spans)
  const sentence = /^.*?[.!?](?=\s|$)/.exec(line)?.[0] ?? line
  return sentence.length > SUMMARY_MAX ? `${sentence.slice(0, SUMMARY_MAX - 1).trimEnd()}…` : sentence
}
