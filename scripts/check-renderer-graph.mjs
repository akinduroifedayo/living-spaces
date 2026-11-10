import { readFile } from 'node:fs/promises'
import { resolve, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))

export function checkRendererGraph(metafile) {
  if (!metafile.inputs || !Object.keys(metafile.inputs).length || !metafile.outputs || !Object.keys(metafile.outputs).length) {
    throw new Error('Renderer metafile must contain inputs and outputs')
  }
  const forbidden = Object.keys(metafile.inputs).filter(input => {
    const path = relative(root, resolve(input)).split(sep).join('/')
    return path.startsWith('src/guest/') || path.startsWith('src/living-spaces/guest/') || path === 'src/desktop/sandbox/loader.js'
  })
  if (forbidden.length) throw new Error(`Guest code in renderer graph: ${forbidden.join(', ')}`)
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  checkRendererGraph(JSON.parse(await readFile(process.argv[2], 'utf8')))
  console.log('Renderer graph excludes guest code and guest HTML')
}
