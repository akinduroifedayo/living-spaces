import { host, useValue } from '@hermes/plugin-sdk'
import { useMemo } from 'react'
import { scopedRest } from './model.mjs'

const currentScope = () => JSON.stringify([host.state.connectionId.get(), host.state.profile.get()])
export function useScopedContext(ctx) {
  const connection = useValue(host.state.connectionId)
  const profile = useValue(host.state.profile)
  const queryScope = JSON.stringify([connection, profile])
  return useMemo(() => ({ ...ctx, queryScope, rest: scopedRest((path, options) => ctx.rest(path, options), currentScope, queryScope) }), [ctx, queryScope])
}
