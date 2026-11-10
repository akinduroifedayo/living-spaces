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
    main { max-width: 650px; padding: 24px; margin: auto; font-family: system-ui; }
    label { display: flex; align-items: center; gap: 12px; margin-block: 18px; }
    input, button { font: inherit; min-height: 32px; }
    li { list-style: none; } ul { padding: 0; }
  </style>
</head>
<body><main id="app"></main><script type="module" src="./app.js"></script></body>
</html>
```

## app.js

```js
import { render } from 'preact';
import { useState } from 'preact/hooks';
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
  const habits = useCollection('habits', {limit: 500});
  const checkins = useCollection('checkins', {where: {day}, limit: 500});
  const save = useSaveState();
  const add = async event => {
    event.preventDefault();
    if (!name.trim()) return;
    await save.run(async () => {
      const created = await window.space.put('habits', null, {name: name.trim()}, {baseRev: 0});
      setName('');
      habits.reload();
      return created;
    });
  };
  const persist = async draft => {
    setPending(draft);
    const saved = await save.run(() => window.space.put('checkins', draft.id,
      draft.data, {baseRev: draft.baseRev}));
    if (saved) {
      setPending(null);
      checkins.reload();
    }
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
    <h1>Daily Practice</h1>
    ${(habits.loading || checkins.loading) && html`<p role="status">Loading your practice...</p>`}
    ${(habits.error || checkins.error) && html`<p role="alert">Could not load your habits.
      ${(habits.error || checkins.error).message}</p>`}
    <label>Day<input type="date" required disabled=${save.state === 'saving' || !!pending} value=${day} onChange=${event => {
      if (event.target.value) setDay(event.target.value);
    }} /></label>
    <form onSubmit=${add}>
      <label>New habit<input required disabled=${save.state === 'saving' || !!pending} value=${name} onInput=${e => setName(e.target.value)} /></label>
      <button disabled=${save.state === 'saving' || !!pending || !name.trim()}>Add habit</button>
    </form>
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
    ${habits.records.length ? html`<ul>${habits.records.map(habit => {
      const current = checkins.records.find(record => record.id === `${habit.id}:${day}`);
      return html`<li key=${habit.id}><label><input type="checkbox" checked=${!!current?.data.done}
        disabled=${save.state === 'saving' || !!pending || checkins.loading || !!checkins.error} onChange=${() => toggle(habit)} />${habit.data.name}</label></li>`;
    })}</ul>` : html`<${EmptyState} title="Choose your first habit"><p>Add something small you want to do each day.</p><//>`}
    ${habits.records.length === 500 && html`<p>Showing the first 500 habits.</p>`}`;
}

render(html`<${Planner} />`, document.getElementById('app'));
```

An evolution request such as "Add a weekly view" reuses `habits` and `checkins`.
Read the current records, query each day, and add a view without replacing data.
Changing only presentation does not need a data migration.
