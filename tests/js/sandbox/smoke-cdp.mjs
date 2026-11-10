import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { createSmokeServer } from './smoke-server.mjs'

const fixture = await createSmokeServer()
const profile = resolve(fixture.runDir, 'chrome')
await mkdir(profile)
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
  '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check', 'about:blank'
], { stdio: ['ignore', 'ignore', 'pipe'] })
let stderr = ''
chrome.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-8000) })
const results = []
let socket
let cdp
let hostDebug
let appDebug
async function until(fn, description, timeout = 8000) {
  const end = Date.now() + timeout
  while (Date.now() < end) {
    const value = await fn()
    if (value) return value
    await delay(40)
  }
  throw new Error('Timed out: ' + description)
}
function check(name, value) { assert.ok(value, name); results.push({ name, passed: true }); console.log('PASS ' + name) }
try {
  const active = await until(async () => {
    try { return (await readFile(resolve(profile, 'DevToolsActivePort'), 'utf8')).trim().split('\n') } catch { return null }
  }, 'Chrome debugging endpoint')
  socket = new WebSocket(`ws://127.0.0.1:${active[0]}${active[1]}`)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let id = 0
  const pending = new Map()
  const contexts = new Map()
  socket.onmessage = e => {
    const message = JSON.parse(e.data)
    if (message.id) {
      const job = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) job.reject(new Error(JSON.stringify(message.error)))
      else job.resolve(message.result)
    }
    if (message.method === 'Runtime.executionContextCreated') contexts.set(message.sessionId + ':' + message.params.context.id, { ...message.params.context, sessionId: message.sessionId })
    if (message.method === 'Runtime.executionContextDestroyed') contexts.delete(message.sessionId + ':' + message.params.executionContextId)
    if (message.method === 'Runtime.executionContextsCleared') { for (const [key, value] of contexts) if (value.sessionId === message.sessionId) contexts.delete(key) }
  }
  cdp = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const next = ++id
    pending.set(next, { resolve, reject })
    socket.send(JSON.stringify({ id: next, method, params, ...(sessionId ? { sessionId } : {}) }))
  })
  const { targetId } = await cdp('Target.createTarget', { url: fixture.url + '/tests/js/sandbox/smoke.html' })
  const { sessionId } = await cdp('Target.attachToTarget', { targetId, flatten: true })
  await cdp('Runtime.enable', {}, sessionId)
  await cdp('Page.enable', {}, sessionId)
  const evaluate = async (expression, contextId) => {
    const result = await cdp('Runtime.evaluate', { expression, contextId: contextId?.id, awaitPromise: true, returnByValue: true }, contextId?.sessionId || sessionId)
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
    return result.result.value
  }
  const host = expression => evaluate(expression)
  let inner
  async function findInner() {
    const attached = new Set()
    return until(async () => {
      const targets = await cdp('Target.getTargets')
      for (const target of targets.targetInfos.filter(t => t.type === 'iframe' && !attached.has(t.targetId))) {
        attached.add(target.targetId)
        const child = await cdp('Target.attachToTarget', {targetId: target.targetId, flatten: true})
        await cdp('Runtime.enable', {}, child.sessionId)
      }
      for (const [id, context] of contexts) {
        if (!context.auxData?.isDefault) continue
        try { if (await evaluate('typeof window.space?.query === "function" && Boolean(window.space.meta)', context)) return context } catch {}
      }
    }, 'Space execution context')
  }
  inner = await findInner()
  const app = expression => evaluate(expression, inner)
  hostDebug = host
  appDebug = app
  await until(() => app('Boolean(document.getElementById("save") && !document.getElementById("save").disabled)'), 'overview ready')
  check('two nested opaque frames mounted and overview rendered', await host('document.querySelector("iframe").getAttribute("sandbox") === "allow-scripts"') && await app('document.querySelector("h2").textContent === "Overview"'))
  check('classic scripts execute, including scripts nested in entry markup', await app('classicFile === "works" && classicInline === "works"'))
  check('query and fragment asset refs resolve to local blobs', await app('document.querySelector("link").href.startsWith("blob:") && getComputedStyle(document.querySelector(".demo-logo")).backgroundImage.includes("blob:") && getComputedStyle(document.querySelector(".demo-logo")).backgroundImage.includes("#mark")'))
  await app('document.getElementById("save").click()')
  await until(() => app('document.querySelector(".space-save").textContent.includes("Saving")'), 'saving state')
  check('save shows Saving before backend confirmation', await host('smoke.records.get("demo").rev === 1'))
  await until(() => app('document.querySelector(".space-save").textContent.includes("Saved")'), 'saved state')
  check('save shows Saved only after backend confirmation', await host('smoke.records.get("demo").rev === 2'))
  await app(`document.querySelector('a[href="#/library"]').click()`)
  await until(() => app('document.querySelector("h2")?.textContent === "Library" && document.querySelector("li")?.textContent.includes("Public demo note")'), 'library dynamic import')
  check('hash navigation loads a computed relative dynamic import with query and fragment', true)
  check('navigation marks current view accessibly', await app('document.querySelector("a[aria-current=page]").textContent === "Library"'))
  await host('smoke.agentWrite()')
  await until(() => app('document.querySelector("li")?.textContent.includes("Updated by demo chat")'), 'collection live update')
  check('useCollection re-queries matching change events', true)
  await app(`document.querySelector('a[href="#/"]').click()`)
  await until(() => app('document.getElementById("save")?.dataset.baseRev && !document.getElementById("save").disabled'), 'overview reopened')
  await host('smoke.agentWrite()')
  await until(() => app('document.getElementById("current-note").textContent === "Updated by demo chat"'), 'record live update')
  await app('document.getElementById("save").click()')
  await until(() => app('Boolean(document.querySelector(".space-conflict"))'), 'conflict banner')
  check('stale save shows a conflict banner and both resolution actions', await app('document.querySelector(".space-save").classList.contains("space-save-conflict") && [...document.querySelectorAll(".space-conflict button")].map(b => b.textContent).join("|") === "Keep mine|Use updated"'))
  await app('document.querySelector(".space-conflict button").click()')
  await until(() => app('document.querySelector(".space-save").textContent.includes("Saved")'), 'conflict retry confirmation')
  check('Keep mine retries using the current revision and confirms save', true)
  await app('document.querySelector(".space-refresh button").click()')
  await until(() => app('document.querySelector(".space-refresh").textContent.includes("Refresh queued")'), 'queued refresh')
  await host('smoke.run("running")')
  await until(() => app('document.querySelector(".space-refresh").textContent.includes("Refreshing")'), 'running refresh')
  await host('smoke.run("failed")')
  await until(() => app('document.querySelector(".space-refresh").textContent.includes("Demo fetch failed")'), 'failed refresh')
  check('refresh follows queued, running and failed run events', true)
  await host('smoke.denyRefresh = true')
  await app('document.querySelector(".space-refresh button").click()')
  await until(() => app('document.querySelector(".space-refresh").textContent.includes("approve Refresh in Permissions")'), 'not granted refresh')
  check('denied refresh gives an actionable unavailable state', true)
  check('parent document and hostile fetch are blocked', JSON.stringify(await app('demo.probe()')) === JSON.stringify({ parentBlocked: true, fetchBlocked: true }))
  await until(() => host('smoke.logs.some(entry => entry.msg.includes("connect-src") && entry.msg.includes("127.0.0.1:9"))'), 'CSP diagnostic forwarding')
  check('blocked fetch produces a forwarded CSP violation log', true)
  await app('for (let i = 0; i < 100; i++) console.debug("public flood fixture", i)')
  await until(() => host('smoke.events.some(e => e.kind === "log-overflow")'), 'log overflow')
  check('flooded console is bounded to fifty entries with one overflow event', await host('smoke.calls.filter(c => c.op === "log").every(c => c.args.entries.length <= 50) && smoke.events.filter(e => e.kind === "log-overflow").length === 1'))
  const api = await app(`(async () => {
    const created = await space.put('papers', 'temporary', { note: 'public fixture' }, {baseRev: 0})
    const found = await space.get('papers', 'temporary')
    const list = await space.query('papers')
    const batch = await space.batch([{op:'delete', collection:'papers', id:'temporary', base_rev:created.rev}])
    const deleted = await space.delete('papers', 'temporary', {baseRev:created.rev})
    const runs = await space.runs()
    return {created:created.id,found:found.id,count:list.length,batch:batch.results.length,deleted:deleted.deleted,runs:runs.length,meta:space.meta.space.id,field:space.field({data:{x:0},source:{x:3}},'x')}
  })()`)
  check('window.space exposes the collection API and metadata', JSON.stringify(api) === JSON.stringify({ created: 'temporary', found: 'temporary', count: 2, batch: 1, deleted: true, runs: 1, meta: 'demo-desk', field: 0 }))
  const beforeReload = await host('smoke.calls.length')
  await app('setTimeout(() => location.reload(), 0)')
  await until(() => host('smoke.events.some(e => e.kind === "reloaded")'), 'reload event')
  await delay(250)
  check('inner reload closes the old port and emits reloaded once', await host(`smoke.calls.length === ${beforeReload} && smoke.events.filter(e => e.kind === 'reloaded').length === 1`))
  const info = await cdp('Browser.getVersion')
  console.log(JSON.stringify({ browser: info.product, checks: results.length, passed: results.length, failed: 0, requests: fixture.requests }, null, 2))
  await writeFile(resolve(fixture.runDir, 'results.json'), JSON.stringify({ browser: info.product, results, requests: fixture.requests }, null, 2))
} catch (error) {
  console.error(error.stack)
  if (hostDebug) console.error('HOST_DIAGNOSTIC', await hostDebug('JSON.stringify({events:smoke.events, calls:smoke.calls, logs:smoke.logs})').catch(String))
  if (appDebug) console.error('APP_DIAGNOSTIC', await appDebug('document.body.innerText').catch(String))
  console.error('Chrome stderr tail:', stderr)
  process.exitCode = 1
} finally {
  if (cdp && socket?.readyState === WebSocket.OPEN) {
    try { await cdp('Browser.close') } catch {}
  }
  socket?.close()
  if (chrome.exitCode === null) {
    await Promise.race([new Promise(resolve => chrome.once('exit', resolve)), delay(2000)])
    if (chrome.exitCode === null) chrome.kill('SIGKILL')
  }
  await new Promise(resolve => fixture.server.close(resolve))
}
