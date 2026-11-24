#!/Users/ifedayoakinduro/.hermes/hermes-agent/venv/bin/python
"""Gallery host chrome and notices in an existing, manifest-owned disposable Desktop.

Drives the Gallery card (fallback, snapshot, pin marker, create card), the floating island, the Details sheet and its
routes, the notice dock (unbound bot failure, Copy details, pill, auto-collapse, focus and hover pause, Escape, canvas
minimise), the user-initiated bot notice and the storage notice. Every gesture is native CDP input. The Notebook's
Ask Hermes and Fill storage buttons are fixture controls that call the real guest bridge.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

import control as c

OUT = None
RESULTS = []
CARD = 'a[href="#/spaces?space=verification-notebook"]'
DOCK = 'document.querySelector(".ls-notices")?.dataset.minimised ? "pill" : "expanded"'


def visible(selector):
    return c.evaluate(OUT, f'!![...document.querySelectorAll({json.dumps(selector)})].find(e=>e.getClientRects().length)')


def text():
    return c.evaluate(OUT, 'document.body.innerText')


def wait(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except AssertionError:
            pass
        time.sleep(.2)
    raise AssertionError(f'Native observable did not arrive; last={last}')


def focused():
    return c.evaluate(OUT, '(() => { const e=document.activeElement; return (e?.className||"") + "|" + (e?.innerText||"").trim() })()')


def dock():
    return c.evaluate(OUT, DOCK)


def leave_pointer_and_focus():
    """Pointer to a corner and focus to the body: the dock is left alone."""
    c.hover(OUT, 'corner')
    c.evaluate(OUT, 'document.activeElement?.blur()')


def collapse_seconds(timeout=15):
    started = time.monotonic()
    while dock() == 'expanded' and time.monotonic() - started < timeout:
        time.sleep(.1)
    return round(time.monotonic() - started, 1)


def gallery():
    if visible('[data-testid="space-view"]'):
        c.click(OUT, c.BACK)
    elif not visible('[data-testid="spaces-index"]'):
        c.click(OUT, 'text=Spaces')
    wait(lambda: visible('[data-testid="spaces-index"]'))


def open_notebook():
    gallery()
    wait(lambda: visible(CARD))
    c.click(OUT, CARD)
    wait(lambda: visible('[data-testid="space-view"]'))
    wait(lambda: c.guest_read(OUT, 'button#save'))


def run_case(name, fn):
    started = time.time()
    try:
        result = fn()
        c.capture(OUT, name + '-result')
        row = dict(feature=name, status='passed', started=started, ended=time.time(), observed=result)
    except Exception as error:
        c.capture(OUT, name + '-failed')
        row = dict(feature=name, status='failed', started=started, ended=time.time(), error=str(error))
    RESULTS.append(row)
    c.dump(OUT / 'chrome-journeys.json', RESULTS)
    print(json.dumps(row))


def gallery_card():
    gallery()
    if not visible(CARD):
        c.fixture(OUT)
    wait(lambda: visible(CARD))
    box = c.target(OUT, CARD + ':has([data-preview="fallback"])')
    assert 'Verification Notebook' in box['label'] and 'owner' in box['label']
    assert visible('.ls-newcard') and 'Build a Space in chat' in text()
    for label in ['Recent', 'Needs attention · 0', 'Archived', 'Pinned first, then recently opened']:
        assert label in text(), label
    return dict(fallback_preview=True, card_label=box['label'], create_card=True)


def island():
    open_notebook()
    for selector in [c.BACK, 'button[aria-label="More Space actions"]']:
        assert visible(selector), selector
    assert 'Details' in text() and 'Internet on' in text()
    assert not c.evaluate(OUT, '[...document.querySelectorAll(".ls-frame-actions button")].some(e=>/Refresh/.test(e.textContent))')
    phrase = c.evaluate(OUT, 'document.querySelector(".ls-frame-meta-text").innerText')
    assert phrase.startswith('Changed in chat by'), phrase
    return dict(freshness_phrase=phrase, refresh_absent=True, mode=c.evaluate(OUT, 'document.querySelector("[data-testid=space-view]").dataset.headerMode'))


def unbound_notice(clipboard):
    open_notebook()
    if dock() == 'pill':
        c.click(OUT, '.ls-notice-pill')
    wait(lambda: "Hermes didn't receive the request" in text())
    assert 'No chat is keeping this Space. Ask Hermes in chat to bind it.' in text()
    assert c.evaluate(OUT, '!!document.querySelector(".ls-banner[role=alert]")')
    result = dict(title="Hermes didn't receive the request", copy_details='Copy details' in text())
    if clipboard:
        saved = subprocess.run(['pbpaste'], capture_output=True).stdout
        try:
            c.click(OUT, 'text=Copy details')
            time.sleep(1)
            copied = subprocess.run(['pbpaste'], capture_output=True, text=True).stdout
        finally:
            subprocess.run(['pbcopy'], input=saved)
        (OUT / 'copy-details.txt').write_text(copied)
        assert '"reason":"unbound"' in copied and not any(w in copied.lower() for w in ['bearer', 'token', 'api_key', 'password', 'cookie'])
        result['copied'] = copied
    return result


def dock_timing():
    open_notebook()
    if dock() == 'pill':
        c.click(OUT, '.ls-notice-pill')
    leave_pointer_and_focus()
    idle = collapse_seconds()
    time.sleep(.5)   # let the pill finish its entrance transition before measuring it
    pill = c.target(OUT, '.ls-notice-pill')
    assert dock() == 'pill' and round(pill['height']) == 32 and pill['text'] == '1 failed', pill
    c.click(OUT, '.ls-notice-pill')
    assert 'ls-notice-minimise' in focused(), focused()
    c.hover(OUT, 'corner')
    time.sleep(10)
    focus_paused = dock() == 'expanded'
    c.key(OUT, 'Escape')
    time.sleep(.5)
    escape = dock() == 'pill' and 'ls-notice-pill' in focused()
    c.click(OUT, '.ls-notice-pill')
    c.hover(OUT, '.ls-banner')
    c.evaluate(OUT, 'document.activeElement?.blur()')
    time.sleep(10)
    hover_paused = dock() == 'expanded'
    c.hover(OUT, 'corner')
    after_leave = collapse_seconds()
    c.click(OUT, '.ls-notice-pill')
    c.guest_click(OUT, 'input#note')
    canvas = wait(lambda: dock() == 'pill', 5)
    assert focus_paused and escape and hover_paused and canvas and 7 <= idle <= 10 and 7 <= after_leave <= 10
    return dict(idle_collapse_s=idle, pill=dict(width=pill['width'], height=pill['height'], label=pill['label']),
                focus_paused=focus_paused, escape_to_pill_with_focus=escape, hover_paused=hover_paused,
                collapse_after_pointer_leave_s=after_leave, canvas_click_minimises=canvas)


def bot_and_storage():
    open_notebook()
    # Read-only precondition: a storage hide survives deleting and recreating a Space with the same id.
    hidden = c.evaluate(OUT, 'Object.keys(localStorage).filter(k=>k.startsWith("living-spaces:storage-dismissed:")).map(k=>localStorage.getItem(k))')
    assert not hidden, f'Run on a fresh instance: an earlier storage hide is stored ({hidden})'
    if dock() == 'pill':
        c.click(OUT, '.ls-notice-pill')
    c.click(OUT, 'text=Dismiss')
    wait(lambda: "didn't receive" not in text())
    c.guest_click(OUT, 'button#ask')
    wait(lambda: "Hermes didn't receive the request" in text())
    c.guest_click(OUT, 'button#fill')
    wait(lambda: 'Storage 92% full' in text(), 15)
    assert '234.4 KB of 256 KB used by records. Writes stop at the limit.' in text()
    assert wait(lambda: c.evaluate(OUT, 'document.querySelector(".ls-frame-meta-text").innerText').startswith('Edited in this Space'))
    c.capture(OUT, 'storage-notice')
    if dock() == 'pill':
        c.click(OUT, '.ls-notice-pill')
    c.click(OUT, 'text=Hide until it changes')
    wait(lambda: 'Storage 92% full' not in text())
    open_notebook()
    time.sleep(3)
    hidden_after_reopen = 'Storage 92% full' not in text()
    unbound_after_reopen = "didn't receive" in text()
    assert hidden_after_reopen
    return dict(dismissed=True, user_initiated_ask_shows_again=True, storage_title='Storage 92% full',
                hide_persists_across_reopen=hidden_after_reopen, unbound_notice_returns_on_reopen=unbound_after_reopen)


def details():
    open_notebook()
    c.click(OUT, 'text=Details')
    c.wait_text(OUT, 'Space details')
    body = text()
    for words in ['Freshness, storage, access, history and runtime for Verification Notebook', 'Latest change',
                  'This Space has no refresh of its own.', 'Upkeep', 'Storage', 'Internet', 'Records', 'Diagnostic log',
                  'Revision', 'Host', 'Available', 'Space app', 'Loaded']:
        assert words in body, words
    assert '|Close' in focused()
    c.key(OUT, 'Escape')
    routes = {}
    for button, want in [('Manage upkeep', 'No upkeep yet'), ('Manage access', 'Internet access'), ('Open history', 'No refresh runs yet.')]:
        c.click(OUT, 'text=Details')
        c.wait_text(OUT, 'Space details')
        c.click(OUT, 'text=' + button)
        c.wait_text(OUT, want)
        routes[button] = want
        c.key(OUT, 'Escape')
        wait(lambda: 'Space details' not in text() and want not in text())
    return dict(sections=['Freshness', 'Storage', 'Access', 'History', 'Runtime'], routes=routes)


def pin_and_snapshot():
    open_notebook()
    c.click(OUT, 'button[aria-label="More Space actions"]')
    c.click(OUT, 'text=Pin Space')
    wait(lambda: next(r for r in c.records(OUT)['spaces'] if r['id'] == 'verification-notebook')['pinned'] == 1)
    gallery()
    wait(lambda: visible(CARD + ':has([data-preview="snapshot"] img)'), 10)
    assert visible(CARD + ' .ls-pin') and 'Pinned' in c.target(OUT, CARD)['label']
    c.capture(OUT, 'gallery-snapshot-pinned')
    open_notebook()
    c.click(OUT, 'button[aria-label="More Space actions"]')
    c.click(OUT, 'text=Unpin Space')
    wait(lambda: next(r for r in c.records(OUT)['spaces'] if r['id'] == 'verification-notebook')['pinned'] == 0)
    gallery()
    return dict(snapshot_preview=True, pin_marker=True, unpinned=True)


def main():
    global OUT
    p = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--clipboard', action='store_true',
                   help='Also read Copy details from the system pasteboard (text is saved and restored)')
    a = p.parse_args()
    OUT = a.out.resolve()
    assert OUT is not None
    c.owned(OUT)
    for name, fn in [('gallery-card', gallery_card), ('space-island', island),
                     ('notice-unbound-bot', lambda: unbound_notice(a.clipboard)), ('notice-dock-timing', dock_timing),
                     ('notice-bot-and-storage', bot_and_storage), ('details-sheet', details),
                     ('gallery-pin-snapshot', pin_and_snapshot)]:
        run_case(name, fn)


if __name__ == '__main__':
    main()
