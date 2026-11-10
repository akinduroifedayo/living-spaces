import { Button, EmptyState, ErrorState, ROUTES_AREA, SIDEBAR_NAV_AREA, useQuery } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

import { mountSpace, V1_GRANTS } from '../core/sandbox-core.js'

const ID = 'living-spaces'
let rest = null
let navigate = () => {}
const enc = encodeURIComponent

function bridgeCall(sid) {
  const base = `/spaces/${enc(sid)}`
  return async (op, args) => {
    switch (op) {
      case 'data.get':
        return (await rest(`${base}/data`)).data
      case 'data.set':
        return rest(`${base}/data/set`, { method: 'POST', body: { key: args.key, value: args.value, base_rev: args.base_rev } })
      case 'data.delete':
        return rest(`${base}/data/delete`, { method: 'POST', body: { key: args.key } })
      case 'refresh':
        return rest(`${base}/refresh`, { method: 'POST', body: {} })
      case 'log':
        return rest(`${base}/logs`, { method: 'POST', body: { entries: args.entries } })
      default:
        throw new Error(`unknown op ${op}`)
    }
  }
}

function SpaceView({ sid }) {
  const host = useRef(null)
  const mounted = useRef(null)
  const seen = useRef({ code: null, data: null })
  const [status, setStatus] = useState('loading')
  const [denied, setDenied] = useState(0)

  const rev = useQuery({ queryKey: [ID, 'rev', sid], queryFn: () => rest(`/spaces/${enc(sid)}/rev`), refetchInterval: 2000 })

  useEffect(() => {
    const r = rev.data
    if (!r || !host.current) return
    let cancelled = false
    ;(async () => {
      if (r.code_rev !== seen.current.code) {
        const bundle = await rest(`/spaces/${enc(sid)}/bundle`)
        if (cancelled) return
        mounted.current?.destroy()
        mounted.current = mountSpace(host.current, {
          bundle,
          grants: V1_GRANTS,
          call: bridgeCall(sid),
          onEvent: e => e.kind === 'denied' && setDenied(n => n + 1)
        })
        seen.current = { code: bundle.code_rev, data: bundle.data_rev }
        setStatus(`rev ${bundle.code_rev}`)
      } else if (r.data_rev !== seen.current.data) {
        const { data } = await rest(`/spaces/${enc(sid)}/data`)
        if (cancelled) return
        seen.current.data = r.data_rev
        mounted.current?.pushData(data)
      }
    })().catch(err => setStatus(`error: ${err.message || err}`))
    return () => {
      cancelled = true
    }
  }, [rev.data, sid])

  useEffect(() => () => mounted.current?.destroy(), [])

  return jsxs('div', {
    className: 'flex h-full flex-col',
    'data-testid': 'space-view',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-3 border-b border-(--ui-stroke-secondary) px-4 py-2 text-sm',
        children: [
          jsx(Button, { variant: 'ghost', size: 'sm', onClick: () => navigate('/spaces'), children: '← Spaces' }),
          jsx('span', { className: 'font-medium', children: sid }),
          jsx('span', { className: 'text-(--ui-text-tertiary)', children: status }),
          jsx('span', { className: 'text-(--ui-text-tertiary)', children: `grants: ${V1_GRANTS.join(', ')}` }),
          denied ? jsx('span', { className: 'text-(--ui-text-warning)', children: `${denied} denied` }) : null,
          jsx('span', { className: 'flex-1' }),
          jsx(Button, {
            size: 'sm',
            onClick: () => bridgeCall(sid)('refresh', {}).then(() => rev.refetch()),
            children: 'Refresh now'
          })
        ]
      }),
      jsx('div', { ref: host, className: 'min-h-0 flex-1', 'data-testid': 'space-host' })
    ]
  })
}

function SpacesPage() {
  const [sid, setSid] = useState(() => new URLSearchParams(location.hash.split('?')[1] || '').get('space'))
  const list = useQuery({ queryKey: [ID, 'spaces'], queryFn: () => rest('/spaces'), refetchInterval: 3000 })
  useEffect(() => {
    navigate = path => (path === '/spaces' ? setSid(null) : null)
  }, [])
  if (sid) return jsx(SpaceView, { sid }, sid)
  if (list.error) return jsx(ErrorState, { title: 'Spaces backend unreachable', description: String(list.error?.message || list.error) })
  const spaces = list.data?.spaces || []
  return jsxs('div', {
    className: 'flex h-full flex-col gap-3 overflow-auto p-6 text-sm',
    'data-testid': 'spaces-index',
    children: [
      jsx('h1', { className: 'text-lg font-semibold', children: 'Spaces' }),
      spaces.length === 0
        ? jsx(EmptyState, { title: 'No Spaces yet', description: 'Ask Hermes to build one.' })
        : jsx('ul', {
            className: 'flex flex-col gap-1',
            children: spaces.map(s =>
              jsx(
                'li',
                {
                  children: jsxs('button', {
                    className: 'w-full rounded border border-(--ui-stroke-secondary) px-3 py-2 text-left hover:bg-(--ui-bg-hover)',
                    'data-space': s.id,
                    onClick: () => setSid(s.id),
                    children: [
                      jsx('span', { className: 'font-medium', children: s.name }),
                      jsx('span', { className: 'ml-2 text-(--ui-text-quaternary)', children: `${s.id} · code rev ${s.code_rev} · data rev ${s.data_rev}` })
                    ]
                  })
                },
                s.id
              )
            )
          })
    ]
  })
}

export default {
  id: ID,
  name: 'Spaces (sandbox spike)',
  register(ctx) {
    rest = ctx.rest
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/spaces' }, render: () => jsx(SpacesPage, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, order: 60, data: { path: '/spaces', label: 'Spaces', codicon: 'layers' } }
    ])
  }
}
