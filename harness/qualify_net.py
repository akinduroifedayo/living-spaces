"""Forge-only qualification of mediated HTTPS in the isolated Desktop's real frame."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

from cdp import _page, evaluate, screenshot
from guest_realm import guest


REPO = Path(__file__).resolve().parents[1]
OFF_NOTE = "Off is not a complete block. A browser feature called WebRTC can still send data this Space can read. It still can't reach Hermes, your credentials, your files or other Spaces."


def wait(probe, predicate, seconds=30):
    deadline = time.monotonic() + seconds
    value = None
    while time.monotonic() < deadline:
        value = probe()
        if predicate(value):
            return value
        time.sleep(.25)
    raise TimeoutError(value)


def press(selector):
    point = evaluate(f"""(() => {{
      const e = document.querySelector({json.dumps(selector)});
      if (!e || e.disabled) return null;
      e.scrollIntoView({{block:'center'}});
      const r = e.getBoundingClientRect();
      return {{x:r.x+r.width/2,y:r.y+r.height/2}};
    }})()""")
    if not point:
        raise AssertionError(f'Missing or disabled host control: {selector}')

    async def click(session):
        await session.call('Page.bringToFront')
        for kind in ('mousePressed', 'mouseReleased'):
            await session.call('Input.dispatchMouseEvent', type=kind, x=point['x'], y=point['y'], button='left', clickCount=1)
    asyncio.run(_page(click))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=Path(os.environ.get('LS_RUN_ROOT', '/Volumes/Expansion/Development/Build/living-spaces-r1')))
    parser.add_argument('--gateway-port', type=int, required=True)
    parser.add_argument('--public-url', default='https://example.com/')
    parser.add_argument('--lan-url', default='https://192.168.1.1/')
    args = parser.parse_args()
    home = (args.run_root / 'home').resolve()
    if home == Path.home() / '.hermes' or (Path.home() / '.hermes') in home.parents:
        raise SystemExit('Refusing a live Hermes home')
    if not (home / 'plugin-data/living-spaces/spaces.db').is_file():
        raise SystemExit('The isolated database must already exist')
    os.environ['HERMES_HOME'] = str(home)
    os.environ['LIVING_SPACES_DB'] = str(home / 'plugin-data/living-spaces/spaces.db')
    sys.path.insert(0, str(REPO / 'src/living-spaces'))
    import living_spaces_core as core

    out = args.run_root / 'evidence/net'
    out.mkdir(parents=True, exist_ok=True)
    report = {'evidence_class': 'real Space realm and bridge; native mouse input for host permissions', 'checks': [], 'completed': False}
    sid = None
    original_hash = evaluate('location.hash')

    def check(name, observed, expected=True):
        passed = observed == expected
        report['checks'].append({'name': name, 'passed': passed, 'observed': observed, 'expected': expected})
        print(('PASS ' if passed else 'FAIL ') + name)
        if not passed:
            raise AssertionError(report['checks'][-1])

    def net(url):
        return guest(f"space.net.fetch({json.dumps(url)}, {{as:'text'}}).then(r => ({{status:r.status,url:r.url,bytes:new TextEncoder().encode(r.text).length}})).catch(e => ({{code:e.code,reason:e.reason || null}}))")

    switch = '[role="dialog"] [role="switch"][aria-label="Internet access"]'
    try:
        fixture = core.create_space('Internet Qualification', owner='Public demo', author='harness',
                                    files={'index.html': '<h1>Internet qualification</h1><p>Public HTTPS content only.</p>'})
        sid = fixture['id']
        report['fixture_space'] = sid
        check('new Space defaults to Internet access On', next(g['status'] for g in core.list_grants(sid) if g['capability'] == 'net'), 'granted')
        evaluate(f'location.hash={json.dumps("/spaces?space=" + sid)}')
        wait(lambda: guest('({id:space.meta?.space?.id, granted:(space.meta?.grants||[]).some(g => g === "net" || (g?.capability === "net" && g?.status === "granted"))})'),
             lambda r: r and r.get('ok') and r.get('value') == {'id': sid, 'granted': True})
        check('integrated guest exposes space.net.fetch', guest('typeof space.net?.fetch'), {'ok': True, 'value': 'function'})
        public = net(args.public_url)
        report['public_fetch'] = public
        check('real guest fetch reaches public HTTPS', bool(public and public.get('ok') and 200 <= public.get('value', {}).get('status', 0) < 300))
        for name, url, reasons in (
            ('gateway', f'https://127.0.0.1:{args.gateway_port}/', ('port', 'private_address')),
            ('loopback on allowed port', 'https://127.0.0.1/', ('private_address',)),
            ('LAN', args.lan_url, ('private_address',)),
        ):
            result = net(url)
            report[name] = result
            error = (result or {}).get('value') or {}
            check(f'{name} is blocked through the real bridge', bool(result and result.get('ok') and error.get('code') == 'blocked' and error.get('reason') in reasons))
        direct = guest("fetch('https://example.com/').then(() => 'unexpected').catch(() => 'blocked')")
        check('ordinary guest fetch remains network-off', direct, {'ok': True, 'value': 'blocked'})
        evaluate("""(() => {const b=[...document.querySelectorAll('button')].find(b => b.textContent.trim()==='Permissions'); if(!b) throw Error('Permissions missing'); b.id='net-permissions-open';})()""")
        press('#net-permissions-open')
        wait(lambda: evaluate(f'document.querySelector({json.dumps(switch)})?.getAttribute("aria-checked")'), lambda v: v == 'true')
        check('Internet access is the first permission row', evaluate("document.querySelector('[role=dialog] article')?.getAttribute('data-testid')"), 'internet-access')
        check('On hides the WebRTC Off note', evaluate('document.querySelectorAll("[data-testid=webrtc-note]").length'), 0)
        screenshot(str(out / '01-on.png'))
        press(switch)
        wait(lambda: next(g['status'] for g in core.list_grants(sid) if g['capability'] == 'net'), lambda v: v == 'revoked')
        wait(lambda: evaluate(f'document.querySelector({json.dumps(switch)})?.getAttribute("aria-checked")'), lambda v: v == 'false')
        check('Off shows the exact WebRTC note', evaluate(f'document.body.innerText.includes({json.dumps(OFF_NOTE)})'))
        screenshot(str(out / '02-off.png'))
        wait(lambda: guest('({id:space.meta?.space?.id, granted:(space.meta?.grants||[]).some(g => g === "net" || (g?.capability === "net" && g?.status === "granted"))})'),
             lambda r: r and r.get('ok') and r.get('value') == {'id': sid, 'granted': False})
        denied = net(args.public_url)
        check('revoked guest fetch returns not_granted', (denied or {}).get('value', {}).get('code'), 'not_granted')
        press(switch)
        wait(lambda: next(g['status'] for g in core.list_grants(sid) if g['capability'] == 'net'), lambda v: v == 'granted')
        wait(lambda: evaluate(f'document.querySelector({json.dumps(switch)})?.getAttribute("aria-checked")'), lambda v: v == 'true')
        wait(lambda: guest('({id:space.meta?.space?.id, granted:(space.meta?.grants||[]).some(g => g === "net" || (g?.capability === "net" && g?.status === "granted"))})'),
             lambda r: r and r.get('ok') and r.get('value') == {'id': sid, 'granted': True})
        resumed = net(args.public_url)
        check('host reapproval restores public HTTPS', bool(resumed and resumed.get('ok') and 200 <= resumed.get('value', {}).get('status', 0) < 300))
        report['completed'] = True
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        if sid:
            try:
                evaluate('location.hash="/spaces"')
                wait(lambda: evaluate('document.querySelectorAll("iframe").length'), lambda count: count == 0)
                core.delete_space(sid, actor='harness', confirm=sid)
                report['fixture_removed'] = True
            except Exception as exc:
                report['cleanup_error'] = str(exc)
        if isinstance(original_hash, str):
            evaluate(f'location.hash={json.dumps(original_hash)}')
        report['passed'] = sum(c['passed'] for c in report['checks'])
        report['total'] = len(report['checks'])
        report['verdict'] = 'PASS' if report['completed'] and 'cleanup_error' not in report else 'ISSUES'
        (out / 'net.json').write_text(json.dumps(report, indent=2))
        print(json.dumps({k: report[k] for k in ('verdict', 'passed', 'total')}))
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
