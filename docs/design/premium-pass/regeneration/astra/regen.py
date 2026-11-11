"""Submit one exact prompt via a NEW ordinary Desktop chat session (native input), record route + before store.
Usage: regen.py submit N   -> prints session id
       regen.py collect N SESSION -> writes trace/after/route files (non-blocking snapshot)"""
import sys, json, sqlite3, time, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import ui
from cdp import evaluate

ROOT = Path('/Volumes/Expansion/Development/Projects/living-spaces')
HOME = Path('/Volumes/Expansion/Development/Build/living-spaces-r1/home')
OUT = ROOT / 'docs/design/premium-pass/regeneration/astra'
OUT.mkdir(parents=True, exist_ok=True)
ITEMS = json.loads((ROOT / 'docs/design/premium-pass/regeneration-prompts.json').read_text())['prompts']
SLUGS = ['sky-window', 'research-desk', 'pair-play']


def store(slug):
    c = sqlite3.connect(f'file:{HOME}/plugin-data/living-spaces/spaces.db?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    out = {}
    for t in ['spaces', 'records', 'revisions', 'grants']:
        col = 'id' if t == 'spaces' else 'space'
        out[t] = [dict(r) for r in c.execute(f'select * from {t} where {col}=?', (slug,))]
    return out


def state():
    c = sqlite3.connect(f'file:{HOME}/state.db?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


def submit(n):
    slug, prompt = SLUGS[n], ITEMS[n]['prompt']
    (OUT / f'{slug}-before.json').write_text(json.dumps(store(slug), indent=2, default=str))
    xy = evaluate("""(()=>{const b=[...document.querySelectorAll('button,a,[role=button]')].find(b=>/^New session/.test((b.innerText||'').trim()));const r=b.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()""")
    ui.click(*xy)
    time.sleep(2.5)
    picker = evaluate("""[...document.querySelectorAll('button')].map(b=>(b.innerText||'').trim()).filter(s=>/astra|sonnet|gpt|claude|opus/i.test(s))""")
    box = evaluate("""(()=>{const e=document.querySelector('[contenteditable=true][aria-label=Message]');e.focus();const r=e.getBoundingClientRect();return [r.x+20,r.y+r.height/2]})()""")
    ui.click(*box)
    t0 = time.time()
    ui.page(lambda s: s.call('Input.insertText', text=prompt))
    time.sleep(.6)
    ui.key('Enter')
    sid = None
    for _ in range(40):
        time.sleep(1.5)
        r = state().execute("select session_id from messages where role='user' and content=? and timestamp>=? order by timestamp desc limit 1", (prompt, t0 - 1)).fetchone()
        if r:
            sid = r[0]; break
    rec = {'space': slug, 'prompt': prompt, 'session': sid, 'submitted_at': t0, 'ui_picker_label_before_send': picker,
           'route': 'new ordinary Desktop chat session, native CDP click/insertText/Enter on composer'}
    (OUT / f'{slug}-submission.json').write_text(json.dumps(rec, indent=2))
    print(json.dumps(rec, indent=2))


def collect(n, sid):
    slug = SLUGS[n]
    sub = json.loads((OUT / f'{slug}-submission.json').read_text())
    c = state()
    s = dict(c.execute('select id,source,model,model_config,billing_provider,billing_base_url,billing_mode,started_at,ended_at,end_reason,message_count,tool_call_count,input_tokens,output_tokens,reasoning_tokens,title from sessions where id=?', (sid,)).fetchone())
    trace = [dict(r) for r in c.execute('select role,content,tool_calls,tool_call_id,tool_name,timestamp,finish_reason from messages where session_id=? order by timestamp', (sid,))]
    (OUT / f'{slug}-trace.json').write_text(json.dumps(trace, indent=2))
    (OUT / f'{slug}-route.json').write_text(json.dumps({'requested': {'model': 'gpt-6-astra', 'provider': 'openai-codex', 'service_tier': 'priority'}, 'observed_session_row': s, 'ui_picker_label_before_send': sub['ui_picker_label_before_send']}, indent=2))
    (OUT / f'{slug}-after.json').write_text(json.dumps(store(slug), indent=2, default=str))
    last = trace[-1] if trace else {}
    tools = [m['tool_name'] for m in trace if m['tool_name']]
    print(json.dumps({'model': s['model'], 'provider': s['billing_provider'], 'msgs': len(trace), 'tools': tools[-12:], 'ntools': len(tools),
                      'last_role': last.get('role'), 'finish': last.get('finish_reason'), 'last': (last.get('content') or '')[:600]}, indent=1))


if __name__ == '__main__':
    if sys.argv[1] == 'submit': submit(int(sys.argv[2]))
    else: collect(int(sys.argv[2]), sys.argv[3])
