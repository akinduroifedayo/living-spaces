import { ROUTES_AREA, SIDEBAR_NAV_AREA, TRANSCRIPT_DIRECTIVE_AREA, ErrorState, host, useQuery } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'
import { SpacesIndex } from './ui/index.jsx'
import { SpaceView } from './ui/space.jsx'
import { Action, OwnerChip, SpaceTile, StatusPill } from './ui/components.jsx'
import { isSpaceId, routeSpace, spacePath, spaceRoute, spaceStatus } from './ui/model.mjs'
import { styles } from './ui/styles.js'
import { useScopedContext } from './ui/context.jsx'

export function SpacesPage({ ctx }) {
  const scoped = useScopedContext(ctx)
  const [hash, setHash] = useState(() => typeof location === 'undefined' ? '' : location.hash)
  useEffect(() => {
    const changed = () => setHash(location.hash)
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const sid = routeSpace(hash)
  return jsxs('div', { className: 'ls-root', children: [jsx('style', { children: styles }), sid ? jsx(SpaceView, { ctx: scoped, sid }, `${scoped.queryScope}:${sid}`) : jsx(SpacesIndex, { ctx: scoped }, scoped.queryScope)] })
}
function OpenSpaceCard({ ctx, sid }) {
  const scoped = useScopedContext(ctx)
  const query = useQuery({ queryKey: ['living-spaces', scoped.queryScope, sid, 'detail'], queryFn: () => scoped.rest(spacePath(sid)), refetchInterval: 2000 })
  if (!query.data) return query.error ? jsx(ErrorState, { title: 'This Space could not be loaded', description: query.error.message }) : jsx('span', { role: 'status', children: 'Loading Space…' })
  const space = query.data
  return jsxs('div', { className: 'ls-root ls-directive', children: [jsx('style', { children: styles }), jsxs('div', { className: 'ls-card-top', children: [jsx(SpaceTile, { space }), jsxs('div', { children: [jsx('strong', { children: space.name }), jsx(OwnerChip, { owner: space.owner })] })] }), jsxs('div', { className: 'ls-actions', children: [jsx(StatusPill, { status: spaceStatus(space) }), jsx('span', { children: `Revision ${space.head_rev}` }), jsx(Action, { primary: true, onClick: () => host.navigate(spaceRoute(sid)), children: 'Open Space' })] })] })
}
export function renderDirective(ctx, attrs) { return isSpaceId(attrs?.id) ? jsx(OpenSpaceCard, { ctx, sid: attrs.id }) : null }
export default {
  id: 'living-spaces', name: 'Spaces',
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/spaces' }, render: () => jsx(SpacesPage, { ctx }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, order: 60, data: { path: '/spaces', label: 'Spaces', codicon: 'layers' } },
      { id: 'open-space', area: TRANSCRIPT_DIRECTIVE_AREA, data: { name: 'living-space', render: ({ attrs }) => renderDirective(ctx, attrs) } }
    ])
  }
}
