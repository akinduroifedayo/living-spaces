import { useState } from 'preact/hooks';
import { html, EmptyState } from 'spaces-kit';
import { Editor } from './editor.js';

export function Queue({ records, reload }) {
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const detail = records.find(record => record.id === selected?.id) || selected;
  const priority = { high: 0, normal: 1, low: 2 };
  const queue = records.filter(record => record.data.status !== 'done' &&
    (filter === 'all' || (record.data.priority || 'normal') === filter))
    .sort((a, b) => (priority[a.data.priority || 'normal'] ?? 1) - (priority[b.data.priority || 'normal'] ?? 1));
  return html`
    <section aria-labelledby="queue-heading">
      <h2 id="queue-heading">Reading queue</h2>
      <label>Priority filter<select value=${filter} onChange=${e => setFilter(e.target.value)}>
        <option value="all">All priorities</option><option value="high">High</option>
        <option value="normal">Normal</option><option value="low">Low</option>
      </select></label>
      <p>Save a status, priority, or note on each item. Completed papers stay in Library.</p>
      ${queue.length ? html`<ul class="paper-list space-list">${queue.map(record => html`
        <li key=${record.id}><button class="space-list-button" type="button" aria-pressed=${record.id === selected?.id}
          onClick=${() => setSelected(record)}>${window.space.field(record, 'title') || 'Untitled'}</button>
          <small>${record.data.status || 'queued'} · ${record.data.priority || 'normal'}</small></li>`)}</ul>` :
        html`<${EmptyState} title="Nothing waiting here"><p>Add papers in Library or choose another priority.</p><//>`}
      ${detail && html`
        ${!queue.some(record => record.id === detail.id) && html`
          <p role="status">This item is outside the current queue filter. Its editor and draft remain below.</p>`}
        <${Editor} key=${detail.id} record=${detail} reload=${reload} />`}
    </section>`;
}
