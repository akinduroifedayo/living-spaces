import './env.mjs'
import { readdir } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'

async function filesUnder(path) {
  const entries = await readdir(path, { withFileTypes: true })
  return (await Promise.all(entries.map(entry => entry.isDirectory() ? filesUnder(path + '/' + entry.name) : [path + '/' + entry.name]))).flat()
}
const files = (await Promise.all(['src/desktop/sandbox', 'src/living-spaces/runtime/kit', 'tests/js/sandbox'].map(filesUnder))).flat()
const javascript = files.filter(path => /\.m?js$/.test(path))
for (const file of javascript) {
  const result = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' })
  if (result.status !== 0) throw new Error(result.stderr)
}
for (const file of [...files, 'LANE_REPORT.md']) {
  const result = spawnSync('git', ['diff', '--no-index', '--check', '/dev/null', file], { encoding: 'utf8' })
  if (![0, 1].includes(result.status) || result.stdout || result.stderr) throw new Error(`${file}: ${result.stdout}${result.stderr}`)
}
const tracked = spawnSync('git', ['diff', '--check'], { encoding: 'utf8' })
if (tracked.status !== 0) throw new Error(tracked.stdout + tracked.stderr)
console.log(`PASS syntax: ${javascript.length} JavaScript files`)
console.log(`PASS whitespace: ${files.length + 1} lane files, including untracked additions, and git diff --check`)
