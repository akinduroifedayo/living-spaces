import { h, render } from 'preact'
import { viewLabel } from './views/detail.mjs'
import * as probes from './probes.mjs'

const draw = () => {
  const view = location.hash === '#details' ? 'details' : 'overview'
  render(h('section', { 'data-view': view }, viewLabel(view)), document.getElementById('view'))
}
window.addEventListener('hashchange', draw)
draw()
window.hostingProbe = { ...probes, ready: true, module: viewLabel('details'), library: typeof h === 'function' }
