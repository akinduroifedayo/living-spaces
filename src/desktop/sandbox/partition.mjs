export function mountPartition(container, { document: shell, boot, port, onReady, onReload, onError }) {
  const frame = document.createElement('webview')
  if (typeof frame.executeJavaScript !== 'function') throw new Error('Living Spaces requires Desktop partition support for direct HTTPS')
  let state = 'loading'
  let deliveries = 0
  const timer = setTimeout(() => fail(new Error('Space partition did not become ready')), 10000)
  const evaluate = expression => frame.executeJavaScript(expression)
  const argument = value => `JSON.parse(${JSON.stringify(JSON.stringify(value))})`
  const stop = () => {
    if (state === 'closed') return
    state = 'closed'
    clearTimeout(timer)
    port.onmessage = null
    port.close()
    frame.remove()
  }
  const fail = error => {
    if (state === 'closed') return
    stop()
    onError(error)
  }
  const reload = () => {
    if (state === 'closed') return
    stop()
    onReload()
  }
  port.onmessage = async event => {
    if (state !== 'active') return
    if (++deliveries > 64) return fail(new Error('Space reply queue exceeded its limit'))
    try {
      const accepted = await evaluate(`window.__lsDeliver(${argument(event.data)})`)
      if (state === 'active' && accepted !== true) fail(new Error('Space transport refused a reply'))
    } catch (error) { fail(error) }
    finally { deliveries-- }
  }
  const drain = async () => {
    while (state !== 'closed') {
      const items = await evaluate('window.__lsDrain()')
      if (state === 'closed') return
      if (!Array.isArray(items) || items.length > 64) throw new Error('Invalid Space transport batch')
      for (const item of items) {
        if (state === 'closed') return
        if (item?.kind === 'booted' && state === 'booting') {
          state = 'active'
          clearTimeout(timer)
          onReady()
        } else if (item?.kind === 'request' && state === 'active') port.postMessage(item.message)
        else if (item?.kind === 'reloaded') return reload()
        else throw new Error(item?.kind === 'fatal' ? item.message : 'Invalid Space transport event')
      }
    }
  }
  frame.addEventListener('dom-ready', async () => {
    if (state === 'closed') return
    if (state !== 'loading') return reload()
    state = 'booting'
    try {
      const accepted = await evaluate(`window.__lsBoot(${argument(boot)})`)
      if (state === 'closed') return
      if (accepted !== true) throw new Error('Space transport refused boot')
      await drain()
    } catch (error) { fail(error) }
  })
  frame.addEventListener('did-start-navigation', event => {
    if (state !== 'loading' && event.isMainFrame && !event.isInPlace) reload()
  })
  frame.addEventListener('render-process-gone', () => fail(new Error('Space partition stopped')))
  frame.addEventListener('destroyed', () => fail(new Error('Space partition was destroyed')))
  frame.setAttribute('partition', `living-spaces-${crypto.randomUUID()}`)
  frame.setAttribute('webpreferences', 'contextIsolation=yes,sandbox=yes,nodeIntegration=no,webSecurity=yes')
  frame.style.cssText = 'border:0;width:100%;height:100%;display:flex;background:transparent'
  frame.title = `Space: ${boot.bundle.space.name}`
  frame.src = `data:text/html,${encodeURIComponent(shell)}`
  try { container.append(frame) }
  catch (error) { stop(); throw error }
  return { frame, destroy: stop }
}
