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
import { html, useCollection, useSaveState, SaveIndicator, EmptyState } from 'spaces-kit';

function localDay() {
  const date = new Date();
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0')].join('-');
}

function Planner() {
  const [day, setDay] = useState(localDay);
  const [name, setName] = useState('');
  const habits = useCollection('habits', {limit: 500});
  const checkins = useCollection('checkins', {where: {day}, limit: 500});
  const save = useSaveState();
  const add = async event => {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await save.save(async () => {
        await window.space.put('habits', null, {name: name.trim()}, {baseRev: 0});
        setName('');
        habits.reload();
      });
    } catch (_) {}
  };
  const toggle = async habit => {
    const id = `${habit.id}:${day}`;
    const current = checkins.records.find(record => record.id === id);
    try {
      await save.save(() => window.space.put('checkins', id,
        {habit: habit.id, day, done: !current?.data.done}, {baseRev: current?.rev ?? 0}));
      checkins.reload();
    } catch (_) {}
  };
  if (habits.loading || checkins.loading) return html`<p role="status">Loading your practice...</p>`;
  if (habits.error || checkins.error) return html`<p role="alert">Could not load your habits.
    ${(habits.error || checkins.error).message}</p>`;
  return html`
    <h1>Daily Practice</h1>
    <label>Day<input type="date" required value=${day} onChange=${event => {
      if (event.target.value) setDay(event.target.value);
    }} /></label>
    <form onSubmit=${add}>
      <label>New habit<input required value=${name} onInput=${e => setName(e.target.value)} /></label>
      <button disabled=${save.state === 'saving' || !name.trim()}>Add habit</button>
    </form>
    <${SaveIndicator} state=${name.trim() && save.state === 'saved' ? 'idle' : save.state}
      message=${name.trim() && save.state === 'saved' ? 'Draft not saved' : save.message} />
    ${save.state === 'conflict' && html`<p role="alert">A newer check-in was saved.
      Review the current checkbox, then click again only if you still want to change it.</p>`}
    ${habits.records.length ? html`<ul>${habits.records.map(habit => {
      const current = checkins.records.find(record => record.id === `${habit.id}:${day}`);
      return html`<li key=${habit.id}><label><input type="checkbox" checked=${!!current?.data.done}
        disabled=${save.state === 'saving'} onChange=${() => toggle(habit)} />${habit.data.name}</label></li>`;
    })}</ul>` : html`<${EmptyState} title="Choose your first habit" message="Add something small you want to do each day." />`}
    ${habits.records.length === 500 && html`<p>Showing the first 500 habits.</p>`}`;
}

render(html`<${Planner} />`, document.getElementById('app'));
```

An evolution request such as "Add a weekly view" reuses `habits` and `checkins`.
Read the current records, query each day, and add a view without replacing data.
Changing only presentation does not need a data migration.
