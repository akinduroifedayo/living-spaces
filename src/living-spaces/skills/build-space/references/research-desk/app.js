import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { html, useCollection, hashRouter, useRoute, Nav, RefreshButton } from 'spaces-kit';
import { Overview } from './views/overview.js';
import { Library } from './views/library.js';
import { Queue } from './views/queue.js';

hashRouter({ '/': Overview, '/overview': Overview, '/library': Library, '/queue': Queue, '*': Overview });
const items = [
  { path: '/overview', label: 'Overview' },
  { path: '/library', label: 'Library' },
  { path: '/queue', label: 'Queue' }
];

function App() {
  const collection = useCollection('papers', { limit: 500 });
  const route = useRoute();
  const View = route.component;
  const [runs, setRuns] = useState([]);
  const [runError, setRunError] = useState('');
  useEffect(() => {
    let mounted = true;
    const update = async () => {
      try {
        const result = await window.space.runs();
        if (mounted) { setRuns(result); setRunError(''); }
      } catch (error) {
        if (mounted) setRunError(error.message);
      }
    };
    update();
    const unsubscribe = window.space.on('run', update);
    return () => { mounted = false; unsubscribe(); };
  }, []);
  return html`
    <main class="desk space-app">
      <header class="desk-header space-header">
        <div class="space-heading"><span class="space-tile" data-accent="blue" aria-hidden="true"><span class="space-icon" data-icon="book"></span></span><div><h1>Research Desk</h1><p>Your reading workspace</p></div></div>
        <${RefreshButton} />
      </header>
      <${Nav} items=${route.path === '/' ? items.map((item, i) => i === 0 ? {...item, path: '/'} : item) : items} />
      ${runError && html`<p class="space-notice space-notice--error" role="alert">Could not read refresh history. ${runError}</p>`}
      ${collection.error && html`<p class="space-notice space-notice--error" role="alert">Could not load papers. ${collection.error.message}</p>`}
      ${collection.loading && html`<p class="space-loading" role="status">Loading your library...</p>`}
      <${View} records=${collection.records} runs=${runs} reload=${collection.reload} />
      ${collection.records.length === 500 && html`<p>Showing the first 500 papers. Ask chat to narrow the collection query.</p>`}
    </main>`;
}

render(html`<${App} />`, document.getElementById('app'));
