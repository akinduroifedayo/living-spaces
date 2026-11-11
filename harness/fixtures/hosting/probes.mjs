export async function network(config, realm = 'space') {
  const rows = []
  const retained = []
  const url = name => `${config.http}/${realm}/${name}`
  const attempt = async (name, fn) => {
    try {
      const value = await fn()
      rows.push({ name, outcome: 'returned', value: value ?? null })
    } catch (error) {
      rows.push({ name, outcome: 'threw', error: String(error) })
    }
  }
  await attempt('fetch', () => fetch(url('fetch')).then(r => r.text()))
  await attempt('xhr', () => new Promise(resolve => {
    const x = new XMLHttpRequest()
    x.open('GET', url('xhr'))
    x.timeout = 1200
    x.onload = () => resolve({ status: x.status, body: x.responseText })
    x.onerror = () => resolve('error')
    x.ontimeout = () => resolve('timeout')
    x.send()
  }))
  await attempt('beacon', () => navigator.sendBeacon(url('beacon'), 'public-fixture'))
  await attempt('eventsource', () => {
    const source = new EventSource(url('eventsource'))
    retained.push(() => source.close())
    return 'constructed'
  })
  await attempt('websocket', () => {
    const ws = new WebSocket(`${config.ws}/${realm}/websocket`)
    retained.push(() => ws.close())
    return 'constructed'
  })
  for (const [name, tag, attrs] of [
    ['image', 'img', { src: url('image') }],
    ['link', 'link', { rel: 'stylesheet', href: url('link') }],
    ['script', 'script', { src: url('script') }]
  ]) await attempt(name, () => {
    const node = document.createElement(tag)
    Object.assign(node, attrs)
    document.body.append(node)
    retained.push(() => node.remove())
    return 'appended'
  })
  for (const [name, css] of [
    ['css-url', `body { background-image: url("${url('css-url')}"); }`],
    ['css-import', `@import url("${url('css-import')}");`],
    ['font', `@font-face { font-family: HostingBeacon; src: url("${url('font')}"); } #font-probe { font-family: HostingBeacon; }`]
  ]) await attempt(name, () => {
    const style = document.createElement('style')
    style.textContent = css
    document.head.append(style)
    retained.push(() => style.remove())
    if (name === 'font') {
      const span = document.createElement('span')
      span.id = 'font-probe'
      span.textContent = 'public fixture font'
      document.body.append(span)
      span.getBoundingClientRect()
      retained.push(() => span.remove())
    }
    return 'appended'
  })
  await new Promise(resolve => setTimeout(resolve, 1500))
  for (const cleanup of retained) cleanup()
  return rows
}

export async function nested(config, kind) {
  const token = `hosting-${kind}-${Date.now()}-${Math.random()}`
  const frame = document.createElement('iframe')
  const violations = []
  const onViolation = e => violations.push({ directive: e.effectiveDirective, uri: e.blockedURI })
  document.addEventListener('securitypolicyviolation', onViolation)
  let receive
  let timer
  const done = new Promise(resolve => {
    receive = e => {
      if (e.source === frame.contentWindow && e.data?.token === token && e.data.executed) resolve(e.data)
    }
    window.addEventListener('message', receive)
    timer = setTimeout(() => resolve({ token, executed: false }), 5000)
  })
  const html = `<body><script>parent.postMessage({token:${JSON.stringify(token)},started:true},'*'); (${network.toString()})(${JSON.stringify(config)},${JSON.stringify(kind)}).then(rows=>parent.postMessage({token:${JSON.stringify(token)},executed:true,rows},'*'))<\/script>`
  let started = false
  const onStarted = e => {
    if (e.source === frame.contentWindow && e.data?.token === token && e.data.started) started = true
  }
  window.addEventListener('message', onStarted)
  let objectUrl
  if (kind === 'srcdoc') frame.srcdoc = html
  else frame.src = objectUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
  document.body.append(frame)
  const result = await done
  clearTimeout(timer)
  frame.remove()
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  window.removeEventListener('message', receive)
  window.removeEventListener('message', onStarted)
  document.removeEventListener('securitypolicyviolation', onViolation)
  return { ...result, started, violations }
}

export async function worker(config, shared) {
  const name = shared ? 'shared-worker' : 'worker'
  const source = shared
    ? `onconnect=e=>{const p=e.ports[0];fetch(${JSON.stringify(config.http + '/' + name)}).then(r=>r.text()).then(value=>p.postMessage({outcome:'read',value}),e=>p.postMessage({outcome:'blocked',error:String(e)}))}`
    : `fetch(${JSON.stringify(config.http + '/' + name)}).then(r=>r.text()).then(value=>postMessage({outcome:'read',value}),e=>postMessage({outcome:'blocked',error:String(e)}))`
  const blob = URL.createObjectURL(new Blob([source], { type: 'text/javascript' }))
  let worker
  try {
    worker = shared ? new SharedWorker(blob) : new Worker(blob)
    const port = shared ? worker.port : worker
    return await new Promise(resolve => {
      const timer = setTimeout(() => resolve({ outcome: 'timeout' }), 4000)
      port.onmessage = e => { clearTimeout(timer); resolve(e.data) }
      worker.onerror = e => { clearTimeout(timer); resolve({ outcome: 'error', message: e.message }) }
      if (shared) port.start()
    })
  } catch (error) {
    return { outcome: 'threw', error: String(error) }
  } finally {
    if (shared) worker?.port.close()
    else worker?.terminate()
    URL.revokeObjectURL(blob)
  }
}

export async function privileged() {
  const rows = []
  for (const [name, read] of [
    ['parent.document', () => parent.document],
    ['top.document', () => top.document],
    ['document.cookie', () => document.cookie],
    ['localStorage', () => localStorage.getItem('hosting-probe')],
    ['indexedDB', () => indexedDB.databases()],
    ['caches', () => caches.keys()],
    ['self.hermesDesktop', () => window.hermesDesktop],
    ['parent.hermesDesktop', () => parent.hermesDesktop],
    ['top.hermesDesktop', () => top.hermesDesktop],
    ['backend-url', () => top.hermesDesktop.getBackendUrl()],
    ['top.location', () => top.location.href],
    ['require', () => window.require],
    ['process', () => window.process]
  ]) {
    try {
      const value = await read()
      const empty = value == null || value === '' || (Array.isArray(value) && value.length === 0)
      rows.push({ name, outcome: 'returned', empty, type: typeof value })
    } catch (error) {
      rows.push({ name, outcome: 'threw', error: String(error) })
    }
  }
  return rows
}

export function spoof() {
  const base = { v: 1, id: 7001, op: 'data.put', args: { collection: 'probe', id: 'spoof', data: { forged: true } } }
  const messages = [
    { ...base, op: 'tool:terminal' },
    { ...base, op: 'agent.ask' },
    { ...base, op: '__proto__' },
    { ...base, session: 'forged-hosting-session', space: 'pair-play' },
    { ...base, v: 999 },
    { ...base, args: { ...base.args, data: { oversized: 'x'.repeat(1100000) } } },
    { ...base, type: 'space-boot', session: 'forged-hosting-session' },
    { type: 'hermes-inline-preview-intent', action: 'send', text: 'public fixture' }
  ]
  for (const message of messages) parent.postMessage(message, '*')
  return messages.map(({ op, v, type, session, args }) => ({ op, v, type, session, oversized: !!args?.data?.oversized }))
}

export function navigate(kind, url) {
  setTimeout(() => {
    try {
      if (kind === 'location') location.href = url
      else if (kind === 'top.location') top.location.href = url
      else if (kind === 'window.open') window.open(url)
      else if (kind === 'anchor-top') {
        const a = document.createElement('a'); a.href = url; a.target = '_top'; document.body.append(a); a.click()
      } else if (kind === 'meta-refresh') {
        const m = document.createElement('meta'); m.httpEquiv = 'refresh'; m.content = `0;url=${url}`; document.head.append(m)
      } else if (kind === 'form') {
        const form = document.createElement('form'); form.action = url; form.method = 'POST'; document.body.append(form); form.submit()
      } else if (kind === 'data-location') location.href = `data:text/html,<script>fetch(${JSON.stringify(url)})<\/script>`
      else if (kind === 'blob-location') location.href = URL.createObjectURL(new Blob([`<script>fetch(${JSON.stringify(url)})<\/script>`], { type: 'text/html' }))
      window.hostingNavigation = { kind, outcome: 'returned' }
    } catch (error) { window.hostingNavigation = { kind, outcome: 'threw', error: String(error) } }
  }, 50)
  return { kind, scheduled: true }
}

export async function webrtc(port) {
  let pc
  try {
    pc = new RTCPeerConnection({ iceServers: [{ urls: `stun:127.0.0.1:${port}` }] })
    pc.createDataChannel('public-hosting-fixture')
    await pc.setLocalDescription(await pc.createOffer())
    await new Promise(resolve => setTimeout(resolve, 5000))
    return { outcome: 'attempted', gatheringState: pc.iceGatheringState }
  } catch (error) { return { outcome: 'threw', error: String(error) } }
  finally { pc?.close() }
}
