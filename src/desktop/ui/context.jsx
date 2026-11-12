import { host, useValue } from '@hermes/plugin-sdk'
import { useMemo } from 'react'
import { scopedRest } from './model.mjs'

const currentScope = () => JSON.stringify([host.state.connectionId.get(), host.state.profile.get()])
export function useScopedContext(ctx) {
  const connectionId = useValue(host.state.connectionId)
  const profile = useValue(host.state.profile)
  const scopeKey = JSON.stringify([connectionId, profile])
  return useMemo(() => ({
    ctx: { ...ctx, rest: scopedRest((path, options) => ctx.rest(path, options), currentScope, scopeKey) },
    scopeKey,
    scope: { connectionId, profile },
    openingSessionRest: (path, options) => ctx.rest(path, options)
  }), [ctx, scopeKey])
}
