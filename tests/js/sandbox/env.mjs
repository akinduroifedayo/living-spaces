import { registerHooks } from 'node:module'
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

mkdirSync('.run', { recursive: true })
const home = mkdtempSync(resolve('.run/sandbox-unit-'))
process.env.HERMES_HOME = home
process.env.LIVING_SPACES_DB = resolve(home, 'spaces.db')
process.on('exit', () => rmSync(home, { recursive: true, force: true }))
registerHooks({
  resolve(specifier, context, next) {
    const vendors = { preact: 'preact.mjs', 'preact/hooks': 'hooks.mjs' }
    if (vendors[specifier]) return { url: pathToFileURL(resolve('src/living-spaces/runtime/vendor', vendors[specifier])).href, shortCircuit: true }
    return next(specifier, context)
  }
})
