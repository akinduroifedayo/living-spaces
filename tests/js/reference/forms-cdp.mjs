import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {replayForms} from './forms-replay.mjs';

const evidence = resolve('.run/forms/chrome-' + Date.now());
await mkdir(evidence, {recursive: true});
const server = spawn(process.execPath, ['tests/js/reference/smoke-server.mjs'], {stdio: ['ignore', 'pipe', 'pipe']});
let serverOutput = '';
server.stdout.on('data', value => {serverOutput += value;});
server.stderr.on('data', value => {serverOutput += value;});
const until = async (read, name) => {
  const end = Date.now() + 10000;
  while (Date.now() < end) {
    const value = await read();
    if (value) return value;
    await delay(50);
  }
  throw Error('Timed out: ' + name);
};
const results = [];
try {
  const url = await until(() => serverOutput.match(/http:\/\/127\.0\.0\.1:\d+\//)?.[0], 'synthetic server');
  for (const example of ['research-desk', 'habit-planner']) {
    const profile = resolve(evidence, example);
    await mkdir(profile);
    const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
      '--headless=new', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
      '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check', 'about:blank'
    ], {stdio: ['ignore', 'ignore', 'pipe']});
    let stderr = '', socket, cdp, pageSessionId;
    chrome.stderr.on('data', chunk => {stderr = (stderr + chunk).slice(-8000);});
    try {
      const endpoint = await until(async () => {
        try {return (await readFile(resolve(profile, 'DevToolsActivePort'), 'utf8')).trim().split('\n');} catch {return null;}
      }, 'Chrome endpoint');
      socket = new WebSocket(`ws://127.0.0.1:${endpoint[0]}${endpoint[1]}`);
      await new Promise((yes, no) => {socket.onopen = yes; socket.onerror = no;});
      const pending = new Map(), contexts = new Map();
      let id = 0;
      socket.onmessage = event => {
        const message = JSON.parse(event.data);
        if (message.id) {
          const job = pending.get(message.id); pending.delete(message.id);
          if (message.error) job.reject(Error(JSON.stringify(message.error))); else job.resolve(message.result);
        }
        if (message.method === 'Runtime.executionContextCreated') contexts.set(message.sessionId + ':' + message.params.context.id, {...message.params.context, sessionId: message.sessionId});
        if (message.method === 'Runtime.executionContextDestroyed') contexts.delete(message.sessionId + ':' + message.params.executionContextId);
      };
      cdp = (method, params = {}, sessionId) => new Promise((yes, no) => {
        const next = ++id; pending.set(next, {resolve: yes, reject: no});
        socket.send(JSON.stringify({id: next, method, params, ...(sessionId ? {sessionId} : {})}));
      });
      const {targetId} = await cdp('Target.createTarget', {url: url + '?example=' + example});
      const {sessionId} = await cdp('Target.attachToTarget', {targetId, flatten: true});
      pageSessionId = sessionId;
      await cdp('Runtime.enable', {}, sessionId);
      await cdp('Page.enable', {}, sessionId);
      await cdp('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false}, sessionId);
      const evaluate = async (expression, context) => {
        const r = await cdp('Runtime.evaluate', {expression, contextId: context?.id, awaitPromise: true, returnByValue: true}, context?.sessionId || sessionId);
        if (r.exceptionDetails) throw Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
        return r.result.value;
      };
      const attached = new Set();
      const inner = await until(async () => {
        for (const target of (await cdp('Target.getTargets')).targetInfos.filter(t => t.type === 'iframe' && !attached.has(t.targetId))) {
          attached.add(target.targetId);
          const child = await cdp('Target.attachToTarget', {targetId: target.targetId, flatten: true});
          await cdp('Runtime.enable', {}, child.sessionId);
        }
        for (const context of contexts.values()) {
          if (!context.auxData?.isDefault) continue;
          try {if (await evaluate('Boolean(window.space?.meta)', context)) return context;} catch {}
        }
      }, 'inner Space context');
      const host = expression => evaluate(expression);
      const app = expression => evaluate(expression, inner);
      await until(() => app(example === 'research-desk' ? '!!document.querySelector(\'a[href="#/library"]\')' : '!!document.querySelector("input[required]")'), 'reference render');
      const result = await replayForms({host, app, cdp, sessionId, example});
      result.browser = (await cdp('Browser.getVersion')).product;
      assert.equal(result.status, 'PASS');
      results.push(result);
      await writeFile(resolve(evidence, example + '.json'), JSON.stringify(result, null, 2));
      console.log(JSON.stringify({example, status: result.status, checks: result.checks.length, browser: result.browser}));
    } catch (error) {
      if (cdp && pageSessionId) {
        const capture = await cdp('Page.captureScreenshot', {format: 'png'}, pageSessionId);
        await writeFile(resolve(evidence, example + '-failure.png'), Buffer.from(capture.data, 'base64'));
      }
      await writeFile(resolve(evidence, example + '-failure.json'), JSON.stringify({error: error.message, receipt: error.receipt, stderr}, null, 2));
      throw error;
    } finally {
      if (cdp && socket?.readyState === WebSocket.OPEN) {try {await cdp('Browser.close');} catch {}}
      socket?.close();
      if (chrome.exitCode === null) {chrome.kill('SIGTERM'); await Promise.race([new Promise(r => chrome.once('exit', r)), delay(3000)]);}
      if (chrome.exitCode === null) chrome.kill('SIGKILL');
    }
  }
  await writeFile(resolve(evidence, 'results.json'), JSON.stringify({evidence_class: 'real Chrome, synthetic backend, not Desktop acceptance', results}, null, 2));
  console.log('Evidence ' + evidence);
} finally {
  server.kill('SIGTERM');
  await Promise.race([new Promise(r => server.once('exit', r)), delay(3000)]);
  if (server.exitCode === null) server.kill('SIGKILL');
}
