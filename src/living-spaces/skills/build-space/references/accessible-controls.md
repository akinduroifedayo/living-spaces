# Add accessible behavior to your own markup

Import the optional DOM bindings from `spaces-kit`. They add no CSS or animation.
Use native buttons, `<dialog>` for a dialog or drawer, and `<details><summary>`
for a disclosure. Your app owns the layout, visible focus styles, contrast, and
button text. Do not replace a working inline control with a modal unnecessarily.

Bind after mounting and call `destroy()` during cleanup. Each binding owns the
open state and accessibility attributes of its elements. Keep those elements
stable while bound. Do not also render `open`, `hidden`, `inert`, `tabindex`, or
managed ARIA attributes from Preact state. Rebind when replacing elements.

```js
import { useLayoutEffect, useRef } from 'preact/hooks';
import { html, bindDrawer } from 'spaces-kit';

export function EditDrawer() {
  const trigger = useRef(null);
  const content = useRef(null);
  useLayoutEffect(() => {
    const drawer = bindDrawer({
      trigger: trigger.current, content: content.current, label: 'Edit record'
    });
    return drawer.destroy;
  }, []);
  return html`<section>
    <button ref=${trigger} type="button">Edit record</button>
    <dialog ref=${content}>
      <label>Notes<textarea></textarea></label>
      <button type="button" data-close>Close</button>
    </dialog>
  </section>`;
}
```

Style the dialog as a side drawer in your own CSS. No kit stylesheet is required.
Preserve native closed-dialog and `hidden` visibility. Do not override `inert`
or remove focus outlines without a visible replacement. The binding closes
immediately and does not wait for an exit animation. Compose Q06 motion on
visible content without taking ownership of open state or cleanup.

## Binding contracts

`bindDialog(options)`, `bindDrawer(options)`, and `bindMenu(options)` return
`{open(), close(), destroy()}`. `destroy()` is idempotent and disables the binding.
All three take DOM elements `trigger` and `content`. Supply a nonempty `label`
or `labelledBy`, a space-separated list of IDs of mounted naming elements.
An existing `aria-label` or `aria-labelledby` also supplies the content name.
`labelledBy` takes precedence. Triggers and menu items need visible text or an
accessible label supplied by the author. Generated content IDs connect triggers
through `aria-controls` and `aria-expanded`.

- Dialog and drawer require a closed native `<dialog>`. They call `showModal()`
  and `close()` where available. A DOM fallback sets `open` and supplies the same
  focus and blocking behavior for environments such as jsdom. Drawer has dialog
  semantics; positioning is entirely CSS. Optional `initialFocus` is a DOM
  descendant. Otherwise focus enters the first enabled visible tab stop, or the
  dialog itself when empty. Tab and Shift+Tab wrap inside the active modal.
  Use a button with `data-close` to dismiss. Native `cancel` and `close` events
  also release the layer. Form submission is unavailable in the Space sandbox;
  use explicit JavaScript actions for saving.
- Menu requires a container and native buttons with `role="menuitem"`. The
  binding sets `role="menu"`. Click opens it. ArrowDown on the trigger enters
  the first enabled item, and ArrowUp enters the last. Inside, Up and Down wrap,
  Home and End jump, and a printable character finds the next item whose text
  or `aria-label` starts with that character. Enter and Space click the item.
  Selection and Escape close the menu and return focus. Tab closes, focuses the
  trigger, and leaves the browser's normal Tab default enabled. Menu item
  callbacks own their actions and save feedback. Disabled items are skipped.
  This is an action menu, not a select, combobox, or menubar. Multi-character
  typeahead, hover opening, arrow-key submenus, and outside-click dismissal are
  not supplied.

The document shares one ordered stack for active bindings. Escape dismisses
only the newest layer. Closing an ancestor also closes its newer descendants.
Nest menu and dialog content in its parent content, including when using Preact.
Portals outside a native modal are not supported. A modal makes sibling branches
along its ancestry inert, including background added while open, and restores
the original inert attributes when closing. Focus cannot leave the modal, and
background clicks are refused. A nonmodal menu or disclosure leaves the rest of
the page interactive.

Closing or destroying a layer returns focus to a connected, visible trigger.
If that trigger was removed with its ancestor, the binding tries the enclosing
layers' triggers. If no trigger survives, the remaining modal retains focus;
otherwise the browser can focus the document body. A mutation observer releases
blocking when open content is removed even before author cleanup. Always call
`destroy()` to release the element listeners too. Mount each element pair once.

`bindTabs({list, tabs, panels, label, labelledBy, orientation})` takes a tablist
container and equally sized nonempty arrays of native tab buttons and panel
containers in matching order. It returns `{destroy()}`. Supply the list's name
as above. Button text names each tab, and each panel is labelled by its tab.
The binding preserves IDs or generates them and creates reciprocal links. It
selects a premarked enabled `aria-selected="true"` tab, or the first enabled tab.
Only the selected tab is in the Tab order, and unselected panels are hidden.
Left and Right wrap in the default `horizontal` orientation. Up and Down wrap
in `vertical` orientation. Home and End jump. Focus automatically selects the
target; click also selects. Disabled tabs are skipped. Use this for panels that
are immediately available, not delayed remote loading. The element arrays are
fixed for a binding's lifetime. Rebind after adding, removing, or reordering tabs.

`bindDisclosure({content})` takes a native `<details>` with a direct `<summary>`
and returns `{open(), close(), destroy()}`. Summary text supplies the native
name. Native click and keyboard activation toggle it. Opening keeps focus on
the summary; Escape and programmatic close return focus there. Details remains
nonmodal, without a focus trap or extra roles. Nested disclosures participate
in the same Escape stack as dialogs and menus.

These bindings do not read or write records, load dependencies, or dispatch
network or model work. Existing kit exports retain their contracts. Existing
Spaces keep their copied kit until explicitly upgraded. Keyboard and teardown
coverage here is jsdom fixture evidence. Native top-layer rendering, assistive
technology, visual accessibility, and actual-frame qualification need the parent
verification lanes. No external control library has been qualified.
