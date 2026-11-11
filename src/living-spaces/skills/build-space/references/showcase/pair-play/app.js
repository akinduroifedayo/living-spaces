// Pair Play — premium showcase reference (mini game).
// Concept: a deck of letterpress cards dealt on green baize under a warm lamp.
// Signature: the generated card back (art/card-back.webp), a real 3D flip, and
// hand-drawn SVG fruit faces printed in two inks. A finished round is a record.
// No kit CSS and no framework, to show the kit is optional. Uses the kit's
// record rules: create-only writes with baseRev 0, and persistent save text.

const space = window.space;
const $ = id => document.getElementById(id);
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- faces: two-ink letterpress fruit, 100×100 ----------
const R = '#8a2432', O = '#c4892b', G = '#4d6a3a';
const FRUIT = {
  pear: {name: 'Pear', svg: `<path d="M50 22c-4 0-6 4-6 10 0 8-14 14-14 34a20 20 0 0 0 40 0c0-20-14-26-14-34 0-6-2-10-6-10Z" fill="${O}"/><path d="M50 22c1-6 4-9 8-10" stroke="${G}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M58 14c8-4 16 0 18 4-8 3-15 2-18-4Z" fill="${G}"/><path d="M40 70c2 8 8 12 14 12" stroke="${R}" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".7"/>`},
  cherry: {name: 'Cherries', svg: `<path d="M52 18c-2 16-10 30-20 40M52 18c4 16 10 28 18 36" stroke="${G}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M52 18c8-6 18-6 22 0-8 4-16 4-22 0Z" fill="${G}"/><circle cx="32" cy="68" r="15" fill="${R}"/><circle cx="68" cy="64" r="15" fill="${R}"/><path d="M26 62a7 7 0 0 1 6-5M62 58a7 7 0 0 1 6-5" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round"/>`},
  lemon: {name: 'Lemon', svg: `<path d="M18 52c0-16 14-26 32-26s32 10 32 26-14 26-32 26-32-10-32-26Z" fill="${O}" transform="rotate(-18 50 52)"/><path d="M14 58l-4 2M86 46l4-2" stroke="${O}" stroke-width="5" stroke-linecap="round"/><path d="M34 44c6-6 16-8 24-6" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".8"/><path d="M58 22c6-6 14-6 18-2-6 4-12 4-18 2Z" fill="${G}"/>`},
  plum: {name: 'Plum', svg: `<path d="M50 28c-18 0-28 14-28 28 0 16 12 26 28 26s28-10 28-26c0-14-10-28-28-28Z" fill="${R}"/><path d="M50 30c-4 14-4 34 0 50" stroke="#5e1420" stroke-width="2" fill="none"/><path d="M50 28c0-6 2-10 6-12" stroke="${G}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M56 16c10-6 20-2 22 4-10 4-18 2-22-4Z" fill="${G}"/><path d="M34 46a14 14 0 0 1 8-8" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".75"/>`},
  fig: {name: 'Fig', svg: `<path d="M50 20c-6 6-8 12-12 18-8 10-16 18-16 30a28 28 0 0 0 56 0c0-12-8-20-16-30-4-6-6-12-12-18Z" fill="${G}"/><path d="M36 64c4-2 8 2 14 0s10-2 14 0" stroke="${O}" stroke-width="2.5" fill="none" stroke-linecap="round"/><ellipse cx="50" cy="70" rx="14" ry="9" fill="${R}"/><path d="M44 70h.1M50 67h.1M56 71h.1M48 74h.1" stroke="${O}" stroke-width="3" stroke-linecap="round"/>`},
  pomegranate: {name: 'Pomegranate', svg: `<circle cx="50" cy="56" r="27" fill="${R}"/><path d="M40 30l4-10 6 8 6-8 4 10Z" fill="${R}"/><path d="M42 30h16" stroke="#5e1420" stroke-width="2"/><path d="M36 46a16 16 0 0 1 10-8" stroke="#f3ead6" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".75"/><circle cx="58" cy="62" r="3" fill="${O}"/><circle cx="50" cy="68" r="3" fill="${O}"/><circle cx="62" cy="54" r="2.5" fill="${O}"/>`}
};
const KINDS = Object.keys(FRUIT);

// ---------- state ----------
let deck = [], open = [], found = new Set(), turns = 0, startedAt = 0, locked = false, rounds = [], saving = false;
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

function deal() {
  deck = shuffle([...KINDS, ...KINDS]);
  open = []; found = new Set(); turns = 0; startedAt = 0; locked = false;
  $('win').hidden = true;
  const board = $('board');
  board.replaceChildren(...deck.map((kind, i) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'card'; b.dataset.i = i;
    b.style.setProperty('--i', i);
    b.style.setProperty('--tilt', `${(Math.random() * 3 - 1.5).toFixed(2)}deg`);
    b.setAttribute('aria-label', `Card ${i + 1}, face down`);
    b.innerHTML = `<span class="inner"><span class="back" aria-hidden="true"></span><span class="face" aria-hidden="true"><svg viewBox="0 0 100 100">${FRUIT[kind].svg}</svg><em>${FRUIT[kind].name}</em></span></span>`;
    b.addEventListener('click', () => flip(i));
    return b;
  }));
  board.classList.remove('dealt'); void board.offsetWidth; board.classList.add('dealt');
  paint();
}

function flip(i) {
  if (locked || found.has(i) || open.includes(i)) return;
  if (!startedAt) startedAt = performance.now();
  open.push(i);
  cardEl(i).classList.add('is-up');
  cardEl(i).setAttribute('aria-label', `Card ${i + 1}, ${FRUIT[deck[i]].name}`);
  if (open.length < 2) return paint();
  turns++;
  const [a, b] = open;
  if (deck[a] === deck[b]) {
    found.add(a); found.add(b); open = [];
    for (const n of [a, b]) { const c = cardEl(n); c.classList.add('is-found'); c.setAttribute('aria-label', `Card ${n + 1}, ${FRUIT[deck[n]].name}, matched`); }
    paint(`Pair of ${FRUIT[deck[a]].name.toLowerCase()}.`);
    if (found.size === deck.length) finish();
  } else {
    locked = true; paint('Not a pair.');
    setTimeout(() => {
      for (const n of [a, b]) { const c = cardEl(n); c.classList.remove('is-up'); c.setAttribute('aria-label', `Card ${n + 1}, face down`); }
      open = []; locked = false; paint();
    }, reduced ? 500 : 950);
  }
}
const cardEl = i => $('board').children[i];

async function finish() {
  const seconds = Math.round((performance.now() - startedAt) / 1000);
  const prevBest = best();
  const isBest = prevBest === null || turns < prevBest;
  $('win-title').textContent = 'All six pairs';
  $('win-line').textContent = `${turns} turns · ${seconds} s`;
  $('win-best').textContent = isBest ? (prevBest === null ? 'First round on the books' : `New best, by ${prevBest - turns}`) : `Best is still ${prevBest} turns`;
  setTimeout(() => { $('win').hidden = false; $('again').focus(); confetti(); }, reduced ? 0 : 520);
  // Persist the finished round. Create-only: baseRev 0.
  saving = true; $('save').textContent = 'Saving round…';
  try {
    const rec = await space.put('rounds', null, {turns, seconds, finished_at: new Date().toISOString()}, {baseRev: 0});
    rounds = [rec, ...rounds];
    $('save').textContent = 'Round saved';
  } catch (e) {
    $('save').textContent = 'This round couldn’t be saved. Your scorecard is unchanged.';
  } finally { saving = false; paint(); }
}

const best = () => rounds.length ? Math.min(...rounds.map(r => space.field(r, 'turns'))) : null;

function paint(say) {
  $('pairs').textContent = found.size / 2;
  $('turns').textContent = turns;
  const b = best();
  $('best').textContent = b === null ? '—' : `${b} turns`;
  $('pips').replaceChildren(...KINDS.map((k, n) => { const s = document.createElement('span'); s.className = n < found.size / 2 ? 'on' : ''; return s; }));
  $('pips').setAttribute('aria-label', `${found.size / 2} of 6 pairs found`);
  if (say) $('board').setAttribute('aria-label', say);
  // History as a strip of bars: shorter is better, best marked.
  const recent = [...rounds].sort((x, y) => String(space.field(y, 'finished_at')).localeCompare(String(space.field(x, 'finished_at')))).slice(0, 8);
  const max = Math.max(12, ...recent.map(r => space.field(r, 'turns')));
  $('history').replaceChildren(...recent.map(r => {
    const t = space.field(r, 'turns'), li = document.createElement('li');
    if (t === b) li.className = 'is-best';
    const when = new Date(space.field(r, 'finished_at'));
    li.innerHTML = `<span class="when">${when.toLocaleDateString([], {month: 'short', day: 'numeric'})}</span><span class="bar"><i style="width:${(t / max * 100).toFixed(1)}%"></i></span><span class="t">${t}</span>`;
    li.setAttribute('aria-label', `${when.toLocaleDateString()} ${t} turns${t === b ? ', best' : ''}`);
    return li;
  }));
  $('history-empty').hidden = recent.length > 0;
}

function confetti() {
  if (reduced) return;
  const layer = document.createElement('div'); layer.className = 'confetti'; layer.setAttribute('aria-hidden', 'true');
  const inks = [R, O, G, '#f3ead6'];
  for (let n = 0; n < 70; n++) {
    const p = document.createElement('i');
    p.style.cssText = `--x:${Math.random() * 100}%;--d:${(Math.random() * 0.6).toFixed(2)}s;--r:${Math.round(Math.random() * 720 - 360)}deg;--c:${inks[n % 4]};--s:${0.6 + Math.random() * 0.8}`;
    layer.append(p);
  }
  document.querySelector('.play').append(layer);
  setTimeout(() => layer.remove(), 2600);
}

async function boot() {
  deal();
  $('save').textContent = 'Loading your scorecard…';
  try { rounds = await space.query('rounds', {limit: 500}); $('save').textContent = ''; }
  catch { $('save').textContent = 'Your scorecard couldn’t load. You can still play.'; }
  paint();
}
$('again').addEventListener('click', deal);
$('restart').addEventListener('click', deal);
addEventListener('keydown', e => { if (e.key === 'Escape' && !$('win').hidden) deal(); });
boot();
