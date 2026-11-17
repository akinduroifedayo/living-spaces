## JavaScript-controlled forms

The accepted frame has `sandbox="allow-scripts"` and CSP `form-action 'none'`.
Native form submission is unavailable, including a form's `onSubmit` callback.
Use labeled inputs in a `div role="group"` or a section, and explicit
`type="button"` actions with `onClick`. Keep the sandbox and CSP unchanged.
Do not use `requestSubmit()`, submit buttons, or a global form handler as a fix.

Validate required controls with `reportValidity()` inside the action and reject
blank trimmed values. Use a ref lock as well as disabled controls so repeated
activation before rerender cannot write twice. Import `useRef` from
`preact/hooks`. For example, inside a component with `title`, `setTitle`,
`reload`, and `save = useSaveState()`:

```js
const titleInput = useRef(null);
const saving = useRef(false);
const add = async () => {
  if (saving.current || titleInput.current?.reportValidity() === false || !title.trim()) return;
  saving.current = true;
  try {
    await save.run(async () => {
      const created = await space.put('papers', null, {title: title.trim()}, {baseRev: 0});
      setTitle('');
      reload();
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
return html`<div role="group" aria-label="Add a paper">
  <label>Title<input ref=${titleInput} required value=${title} disabled=${save.state === 'saving'}
    onInput=${e => setTitle(e.target.value)} onKeyDown=${addOnEnter} /></label>
  <button type="button" onClick=${add} disabled=${save.state === 'saving' || !title.trim()}>Add paper</button>
  <${SaveIndicator} state=${title.trim() && save.state === 'saved' ? 'idle' : save.state}
    message=${title.trim() && save.state === 'saved' ? 'Draft not saved' : save.message} />
</div>`;
```

Attach Enter activation only to single-line creation fields. Ignore composition,
key repeats, and modifier keys. Leave textarea Enter available for newlines;
do not put this handler on the group or editor. Save editor changes with its
explicit button. Preserve drafts on failure and existing explicit conflict
choices. Only confirmed writes may clear input or show Saved.
