import { createServer } from 'node:http'
import { readFile, mkdtemp, mkdir } from 'node:fs/promises'
import { resolve, extname, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('../../../', import.meta.url)))
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' }
export async function createSmokeServer() {
  await mkdir(resolve(root, '.run'), { recursive: true })
  const runDir = await mkdtemp(resolve(root, '.run/sandbox-smoke-'))
  process.env.HERMES_HOME = runDir
  process.env.LIVING_SPACES_DB = resolve(runDir, 'spaces.db')
  const paths = ['index.html', 'classic.js', 'theme.css', 'images/logo.svg', 'main.mjs', 'views/library.mjs']
  const files = await Promise.all(paths.map(async path => ({ path, mime: mime[extname(path)], text: await readFile(resolve(root, 'tests/js/sandbox/demo', path), 'utf8') })))
  for (const path of ['kit/spaces-kit.mjs', 'kit/spaces-kit.css', 'vendor/preact.mjs', 'vendor/hooks.mjs']) {
    files.push({ path, mime: mime[extname(path)], text: await readFile(resolve(root, 'src/living-spaces/runtime', path), 'utf8') })
  }
  const sandbox = { format: 1, shell_srcdoc: await readFile(resolve(root, 'src/living-spaces/guest/space-host.html'), 'utf8') }
  const bundle = { sandbox, space: { id: 'demo-desk', name: 'Demo Research Desk' }, rev: 1, manifest: { entry: 'index.html', imports: { preact: 'vendor/preact.mjs', 'preact/hooks': 'vendor/hooks.mjs', 'spaces-kit': 'kit/spaces-kit.mjs' } }, files }
  const requests = []
  const server = createServer(async (request, response) => {
    requests.push(request.url)
    try {
      const pathname = new URL(request.url, 'http://localhost').pathname
      if (pathname === '/bundle') { response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(bundle)); return }
      const path = resolve(root, '.' + decodeURIComponent(pathname === '/' ? '/tests/js/sandbox/smoke.html' : pathname))
      if (![resolve(root, 'src/desktop/sandbox') + sep, resolve(root, 'tests/js/sandbox') + sep].some(prefix => path.startsWith(prefix))) { response.writeHead(404).end(); return }
      response.setHeader('Content-Type', mime[extname(path)] || 'application/octet-stream')
      response.end(await readFile(path))
    } catch { response.writeHead(404).end() }
  })
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  return { server, url: `http://127.0.0.1:${server.address().port}`, runDir, requests }
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { url } = await createSmokeServer()
  console.log(url + '/tests/js/sandbox/smoke.html')
}
