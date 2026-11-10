import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { html, useCollection, hashRouter, useRoute, Nav, RefreshButton } from 'spaces-kit';
import { Overview } from './views/overview.js';
import { Library } from './views/library.js';
import { Queue } from './views/queue.js';

const routes = { '/overview': Overview, '/library': Library, '/queue': Queue };
const router = hashRouter(routes);
const items = [
  { path: '/overview', label: 'Overview' },
  { path: '/library', label: 'Library' },
  { path: '/queue', label: 'Queue' }
];

function App() {
  const collection = useCollection('papers', { limit: 500 });
  const route = useRoute(router);
  const View = routes[route.path] || Overview;
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
    <main class="desk">
      <header class="desk-header">
        <div><p class="eyebrow">Your reading workspace</p><h1>Research Desk</h1></div>
        <${RefreshButton} />
      </header>
      <${Nav} items=${items} router=${router} />
      ${runError && html`<p role="alert">Could not read refresh history. ${runError}</p>`}
      ${collection.error && html`<p role="alert">Could not load papers. ${collection.error.message}</p>`}
      ${collection.loading ? html`<p role="status">Loading your library...</p>` : html`
        <${View} records=${collection.records} runs=${runs} reload=${collection.reload} />
        ${collection.records.length === 500 && html`<p>Showing the first 500 papers. Ask chat to narrow the collection query.</p>`}
      `}
    </main>`;
}

render(html`<${App} />`, document.getElementById('app'));
