import { mkdir, writeFile } from 'node:fs/promises'
import { shellSrcdoc, partitionSrcdoc } from '../src/guest/document.mjs'

const asset = new URL('../src/living-spaces/guest/space-host.html', import.meta.url)
await mkdir(new URL('.', asset), { recursive: true })
await writeFile(asset, shellSrcdoc(), 'utf8')
await writeFile(new URL('../src/living-spaces/guest/partition-off.html', import.meta.url), partitionSrcdoc(false), 'utf8')
await writeFile(new URL('../src/living-spaces/guest/partition-https.html', import.meta.url), partitionSrcdoc(true), 'utf8')
console.log('Built src/living-spaces/guest/space-host.html')
