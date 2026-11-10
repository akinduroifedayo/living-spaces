import { html, useCollection, EmptyState } from 'spaces-kit'
export default function Library() {
  const { records, loading, error } = useCollection('papers', { order: 'title' })
  return html`<section><h2>Library</h2>${loading ? 'Loading' : error ? error.message : records.length ? html`<ul>${records.map(record => html`<li key=${record.id}>${space.field(record, 'title')}: ${space.field(record, 'note')}</li>`)}</ul>` : html`<${EmptyState} title="No papers yet" />`}</section>`
}
