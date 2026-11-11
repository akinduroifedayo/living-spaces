# A daily habit planner

Create these three files with the default libraries. This app has no upkeep or
external permission request. It stores habits and daily check-ins as records.
The selected day is UI state. Check-ins survive closing the app.

## space.json

```json
{
  "schema": 1,
  "name": "Daily Practice",
  "description": "Small daily habits with durable check-ins.",
  "entry": "index.html",
  "imports": {
    "preact": "vendor/preact.mjs",
    "preact/hooks": "vendor/hooks.mjs",
    "spaces-kit": "kit/spaces-kit.mjs"
  },
  "accent": "green",
  "icon": "checklist",
  "data": {"version": 1, "collections": {
    "habits": {"description": "Habits the user wants to practice"},
    "checkins": {"description": "One check-in per habit and local calendar day"}
  }, "migrations": []}
}
```

## index.html

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Practice</title>
  <link rel="stylesheet" href="./kit/spaces-kit.css">
  <style>
    main { max-width: 720px; margin: auto; }
    .practice-day { max-width: 240px; margin: 0; }
    .practice-add { padding-block: var(--space-4); border-block: 1px solid var(--space-line); }
    .practice-list label { margin: 0; }
    .practice-list label:has(:checked) { color: var(--space-success); }
  </style>
</head>
<body><main id="app" class="space-app"></main><script type="module" src="./app.js"></script></body>
</html>
```

## app.js

```js
import { render } from 'preact';
import { useRef, useState } from 'preact/hooks';
import { html, useCollection, useSaveState, SaveIndicator, ConflictBanner, EmptyState } from 'spaces-kit';

function localDay() {
  const date = new Date();
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0')].join('-');
}

function Planner() {
  const [day, setDay] = useState(localDay);
  const [name, setName] = useState('');
  const [pending, setPending] = useState(null);
  const nameInput = useRef(null);
  const saving = useRef(false);
  const habits = useCollection('habits', {limit: 500});
  const checkins = useCollection('checkins', {where: {day}, limit: 500});
  const save = useSaveState();
  const add = async () => {
    if (saving.current || pending || nameInput.current?.reportValidity() === false || !name.trim()) return;
    saving.current = true;
    try {
      await save.run(async () => {
        const created = await window.space.put('habits', null, {name: name.trim()}, {baseRev: 0});
        setName('');
        habits.reload();
        return created;
      });
    } finally { saving.current = false; }
  };
  const addOnEnter = event => {
    if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229 || event.repeat ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault();
    return add();
  };
  const persist = async draft => {
    if (saving.current) return;
    saving.current = true;
    setPending(draft);
    try {
      const saved = await save.run(() => window.space.put('checkins', draft.id,
        draft.data, {baseRev: draft.baseRev}));
      if (saved) {
        setPending(null);
        checkins.reload();
      }
    } finally { saving.current = false; }
  };
  const toggle = async habit => {
    if (pending || save.state === 'saving') return;
    const id = `${habit.id}:${day}`;
    const current = checkins.records.find(record => record.id === id);
    const draft = {id, data: {habit: habit.id, day, done: !current?.data.done}, baseRev: current?.rev ?? 0};
    await persist(draft);
  };
  const useUpdated = () => {
    setPending(null);
    checkins.reload();
  };
  const resolvedConflict = save.state === 'conflict' && !pending;
  return html`
    <header class="space-header"><div class="space-heading"><span class="space-tile" data-accent="green" aria-hidden="true"><span class="space-icon" data-icon="checklist"></span></span><h1>Daily Practice</h1></div></header>
    ${(habits.loading || checkins.loading) && html`<p class="space-loading" role="status">Loading your practice...</p>`}
    ${(habits.error || checkins.error) && html`<p class="space-notice space-notice--error" role="alert">Could not load your habits.
      ${(habits.error || checkins.error).message}</p>`}
    <label class="practice-day">Day<input type="date" required disabled=${save.state === 'saving' || !!pending} value=${day} onChange=${event => {
      if (event.target.value) setDay(event.target.value);
    }} /></label>
    <div class="practice-add space-form-row" role="group" aria-label="Add a habit">
      <label>New habit<input ref=${nameInput} required disabled=${save.state === 'saving' || !!pending} value=${name}
        onInput=${e => setName(e.target.value)} onKeyDown=${addOnEnter} /></label>
      <button class="space-button--primary" type="button" onClick=${add} disabled=${save.state === 'saving' || !!pending || !name.trim()}>Add habit</button>
    </div>
    <${SaveIndicator} state=${resolvedConflict || name.trim() && save.state === 'saved' ? 'idle' : save.state}
      message=${resolvedConflict ? 'Updated check-in loaded' : name.trim() && save.state === 'saved' ? 'Draft not saved' : save.message} />
    ${pending && html`<p role="status">Unsaved check-in for ${pending.data.day}.
      Intended value: ${pending.data.done ? 'done' : 'not done'}.</p>`}
    ${pending && save.state === 'conflict' && html`
      <${ConflictBanner} current=${save.current}
        onKeepMine=${current => persist({...pending, baseRev: current.rev})} onUseUpdated=${useUpdated}
        message="A newer check-in was saved. Keep mine explicitly retries your intended value against that revision. Use updated discards the draft." />`}
    ${pending && save.state === 'failed' && html`
      <button type="button" onClick=${() => persist(pending)}>Retry check-in</button>
      <button type="button" onClick=${useUpdated}>Discard check-in draft</button>`}
    ${habits.records.length ? html`<ul class="practice-list space-list">${habits.records.map(habit => {
      const current = checkins.records.find(record => record.id === `${habit.id}:${day}`);
      return html`<li key=${habit.id}><label class="space-check"><input type="checkbox" checked=${!!current?.data.done}
        disabled=${save.state === 'saving' || !!pending || checkins.loading || !!checkins.error} onChange=${() => toggle(habit)} />${habit.data.name}</label></li>`;
    })}</ul>` : html`<${EmptyState} title="Choose your first habit"><p>Add something small you want to do each day.</p><//>`}
    ${habits.records.length === 500 && html`<p>Showing the first 500 habits.</p>`}`;
}

render(html`<${Planner} />`, document.getElementById('app'));
```

An evolution request such as "Add a weekly view" reuses `habits` and `checkins`.
Read the current records, query each day, and add a view without replacing data.
Changing only presentation does not need a data migration.
