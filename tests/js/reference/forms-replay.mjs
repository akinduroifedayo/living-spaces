import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';

export async function replayForms({host, app, cdp, sessionId, example = 'research-desk'}) {
  const checks = [];
  const result = {evidence_class: 'Chrome DOM activation with synthetic in-memory backend', example, checks};
  const check = (name, value) => { assert.ok(value, name); checks.push(name); };
  const until = async (read, name) => {
    const end = Date.now() + 8000;
    while (Date.now() < end) {
      if (await read()) return;
      await delay(40);
    }
    throw new Error('Timed out: ' + name);
  };
  const mouse = async expression => {
    await host('document.querySelector("#space > iframe").scrollIntoView({block: "center"})');
    const outer = await host('(() => { const r = document.querySelector("#space > iframe").getBoundingClientRect(); return {x:r.x,y:r.y}; })()');
    const point = await app(`(() => { const el = ${expression}; el.scrollIntoView({block:'center'}); const r = el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
    const coordinates = {x: outer.x + point.x, y: outer.y + point.y};
    const target = await host(`document.elementFromPoint(${coordinates.x}, ${coordinates.y})?.tagName`);
    const innerTarget = await app(`(() => {const e=document.elementFromPoint(${point.x},${point.y});const b=${button};const i=${input};return {tag:e?.tagName,text:e?.textContent?.slice(0,100),disabled:b?.disabled,title:i?.value,active:document.activeElement?.tagName}})()`);
    (result.mouseTargets ??= []).push({expression, outer, point, coordinates, target, innerTarget});
    assert.equal(target, 'IFRAME', 'native mouse coordinates must hit the Space frame');
    await cdp('Input.dispatchMouseEvent', {type: 'mouseMoved', ...coordinates}, sessionId);
    await cdp('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...coordinates}, sessionId);
    await cdp('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...coordinates}, sessionId);
  };
  const enter = async (modifiers = 0) => {
    await cdp('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13,
      modifiers, ...(modifiers ? {} : {text: '\r'})}, sessionId);
    await cdp('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13,
      modifiers: 0}, sessionId);
  };
  const type = text => cdp('Input.insertText', {text}, sessionId);
  const input = 'document.querySelector("input[required]:not([type=date])")';
  const label = example === 'research-desk' ? 'Add to library' : 'Add habit';
  const button = `[...document.querySelectorAll('button')].find(el => el.textContent.trim() === ${JSON.stringify(label)})`;
  const writes = () => host('reference.calls.filter(call => call.op === "data.put").length');
  const rows = () => host(`reference.rows.size`);
  const created = value => host(`[...reference.rows.values()].some(row => row.collection === ${JSON.stringify(example === 'research-desk' ? 'papers' : 'habits')} && row.data[${JSON.stringify(example === 'research-desk' ? 'title' : 'name')}] === ${JSON.stringify(value)})`);
  try {
    check('allow-scripts-only outer frame', await host('document.querySelector("#space > iframe").getAttribute("sandbox") === "allow-scripts"'));
    check('form-action CSP remains blocked', await app('document.querySelector("meta[http-equiv=Content-Security-Policy]").content.includes("form-action \'none\'")'));
    if (example === 'research-desk') {
      await mouse(`document.querySelector('a[href="#/library"]')`);
    }
    await until(() => app(`Boolean(${input})`), 'creation input');
    await app(`window.formReplayEvents = []; for (const type of ['click','pointerdown','pointerup','mousedown','mouseup','keydown','input','submit','invalid']) document.addEventListener(type, event => formReplayEvents.push({type, trusted:event.isTrusted, tag:event.target.tagName, key:event.key, composing:event.isComposing, modifiers:!!(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)}), true)`);
    const before = await writes();
    const beforeRows = await rows();
    await mouse(input);
    await enter();
    await mouse(button);
    check('empty input cannot write', await writes() === before);
    await mouse(input);
    await type('Public click fixture');
    await until(() => app(`!(${button}).disabled`), 'enabled add action');
    for (const modifier of [1, 2, 4, 8]) await enter(modifier);
    check('modified Enter cannot write', await writes() === before);
    await host('reference.holdSaves = true');
    await mouse(button);
    await until(async () => await writes() === before + 1, 'native mouse produces a write request');
    check('creation pending retains input and disables action', await app(`(${input}).value === 'Public click fixture' && (${input}).disabled && (${button}).disabled`));
    check('pending request has not created a row', await rows() === beforeRows);
    await mouse(button);
    await enter();
    check('repeat activation cannot duplicate pending write', await writes() === before + 1);
    await host('reference.holdSaves = false; reference.releaseSaves()');
    await until(() => created('Public click fixture'), 'mouse save confirmation');
    await until(() => app(`(${input}).value === '' && !(${input}).disabled`), 'confirmed input clearing');
    check('click creates exactly one row', await rows() === beforeRows + 1);
    await mouse(input);
    await type('Public Enter fixture');
    await enter();
    await until(() => created('Public Enter fixture'), 'Enter save confirmation');
    await until(() => app(`(${input}).value === '' && !(${input}).disabled`), 'Enter input clearing');
    check('single-line Enter creates exactly one row', await writes() === before + 2 && await rows() === beforeRows + 2);
    if (example === 'research-desk') {
      await until(() => app('Boolean(document.querySelector("textarea"))'), 'selected paper editor');
      await mouse('document.querySelector("textarea")');
      await type('First line'); await enter(); await type('Second line');
      check('textarea Enter inserts newline without saving', await app('document.querySelector("textarea").value === "First line\\nSecond line"') && await writes() === before + 2);
      await mouse('[...document.querySelectorAll("button")].find(el => el.textContent.trim() === "Save changes")');
      await until(() => host('[...reference.rows.values()].some(row => row.data.notes === "First line\\nSecond line")'), 'explicit editor save');
      check('explicit editor click saves multiline notes once', await writes() === before + 3);
    }
    result.domEvents = await app('formReplayEvents');
    check('trusted DOM clicks and Enter were observed', result.domEvents.some(event => event.type === 'click' && event.trusted) && result.domEvents.some(event => event.type === 'keydown' && event.key === 'Enter' && event.trusted));
    check('actions never needed a native submit event', result.domEvents.every(event => event.type !== 'submit'));
    result.calls = await host('reference.calls.filter(call => call.op === "data.put")');
    result.status = 'PASS';
    return result;
  } catch (error) {
    result.status = 'ISSUES';
    result.error = error.message;
    result.domEvents = await app('window.formReplayEvents || []').catch(() => []);
    result.calls = await host('reference.calls.filter(call => call.op === "data.put")').catch(() => []);
    error.receipt = result;
    throw error;
  } finally {
    await host('reference.holdSaves = false; reference.releaseSaves()');
  }
}
