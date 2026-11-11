// node shoot.mjs <outdir> "<query>|<width>|<height>|<file>[|reduced|motion][|js run inside the Space frame]" ...
// Captures PNGs of showcase Spaces through the harness (PORT, default 8781).
// The Space runs in an opaque-origin sandbox iframe (out-of-process), so we
// auto-attach to it to read its height and run interaction scripts inside it.
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdir, mkdtemp} from 'node:fs/promises';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
const [outDir, ...jobs] = process.argv.slice(2);
await mkdir(outDir, {recursive: true});
const tmp = process.env.SHOOT_TMP || '/Volumes/Expansion/Development/Projects/living-spaces-wt/.tmp';
await mkdir(tmp, {recursive: true});
const profile = await mkdtemp(resolve(tmp, 'chrome-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', '--remote-debugging-port=0', '--user-data-dir=' + profile, '--no-first-run', '--hide-scrollbars', 'about:blank'], {stdio: 'ignore'});
const until = async (fn, ms = 15000) => { const end = Date.now() + ms; while (Date.now() < end) { const v = await fn(); if (v) return v; await delay(80); } throw Error('timeout'); };
const port = await until(async () => { try { return (await readFile(resolve(profile, 'DevToolsActivePort'), 'utf8')).trim().split('\n'); } catch { return null; } });
const ws = new WebSocket(`ws://127.0.0.1:${port[0]}${port[1]}`); await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map(); const logs = []; let frameSession = null;
const send = (method, params = {}, sessionId) => new Promise((yes, no) => { const n = ++id; pending.set(n, {yes, no}); ws.send(JSON.stringify({id: n, method, params, ...(sessionId ? {sessionId} : {})})); });
ws.onmessage = e => { const m = JSON.parse(e.data);
  if (m.id) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.no(Error(JSON.stringify(m.error))) : p.yes(m.result); }
  if (m.method === 'Target.attachedToTarget' && m.params.targetInfo.type === 'iframe') {
    frameSession = m.params.sessionId;
    send('Runtime.enable', {}, frameSession).catch(() => {});
    send('Runtime.runIfWaitingForDebugger', {}, frameSession).catch(() => {});
  }
  if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.type + ': ' + m.params.args.map(a => a.value ?? a.description).join(' '));
  if (m.method === 'Runtime.exceptionThrown') logs.push('EXC: ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
};
const base = 'http://127.0.0.1:' + (process.env.PORT || 8781) + '/';
const report = [];
for (const job of jobs) {
  const [query, w, h, file, flag = '', script] = job.split('|');
  const {targetId} = await send('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten: true});
  frameSession = null; logs.length = 0;
  await send('Target.setAutoAttach', {autoAttach: true, waitForDebuggerOnStart: false, flatten: true}, sessionId);
  await send('Runtime.enable', {}, sessionId);
  await send('Page.enable', {}, sessionId);
  const metrics = hh => send('Emulation.setDeviceMetricsOverride', {width: +w, height: hh, deviceScaleFactor: 2, mobile: +w < 600}, sessionId);
  await metrics(+h);
  await send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-color-scheme', value: 'dark'}, {name: 'prefers-reduced-motion', value: flag === 'reduced' ? 'reduce' : 'no-preference'}]}, sessionId);
  await send('Page.navigate', {url: base + '?' + query}, sessionId);
  await delay(+(process.env.SETTLE || 5000));
  const evalIn = async expr => {
    const s = frameSession || sessionId;
    const r = await send('Runtime.evaluate', {expression: expr, returnByValue: true, awaitPromise: true}, s).catch(e => ({error: e.message}));
    if (r.exceptionDetails) logs.push('SCRIPT: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result?.value;
  };
  if (script) { await evalIn(`(async()=>{ ${script} })()`); await delay(+(process.env.AFTER || 1600)); }
  const info = await evalIn(`(()=>{ const d=document.documentElement; return {sh:d.scrollHeight, sw:d.scrollWidth, cw:d.clientWidth, href:location.href.slice(0,20)}; })()`);
  const fullH = Math.max(+h, Math.min(info?.sh || +h, 5000));
  if (fullH !== +h) { await metrics(fullH); await delay(900); }
  const shot = await send('Page.captureScreenshot', {format: 'png'}, sessionId);
  await writeFile(resolve(outDir, file), Buffer.from(shot.data, 'base64'));
  report.push({file, query, width: +w, height: fullH, frame: !!frameSession, overflowX: info ? info.sw > info.cw : null, logs: logs.filter(l => !/^debug/.test(l)).slice(0, 12)});
  await send('Target.closeTarget', {targetId});
}
console.log(JSON.stringify(report));
ws.close(); chrome.kill();
