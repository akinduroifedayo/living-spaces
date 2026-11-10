import { mkdir, writeFile } from 'node:fs/promises'
import { shellSrcdoc } from '../src/guest/document.mjs'

const asset = new URL('../src/living-spaces/guest/space-host.html', import.meta.url)
await mkdir(new URL('.', asset), { recursive: true })
await writeFile(asset, shellSrcdoc(), 'utf8')
console.log('Built src/living-spaces/guest/space-host.html')
