import { html, EmptyState } from 'spaces-kit';

function time(value) {
  return value ? new Date(value * 1000).toLocaleString() : 'Not available yet';
}

export function Overview({ records, runs }) {
  const status = record => window.space.field(record, 'status') || 'queued';
  const latest = runs[0];
  const success = runs.find(run => run.status === 'succeeded');
  const next = records.find(r => status(r) === 'reading') || records.find(r => status(r) === 'queued');
  return html`
    <section aria-labelledby="overview-heading">
      <h2 id="overview-heading">Overview</h2>
      <section class="desk-next space-stack" aria-label="Your reading">
        <h3>${next ? (status(next) === 'reading' ? 'Continue reading' : 'Next in your reading queue') : 'Your reading library'}</h3>
        ${next && html`<p class="desk-next-title">${window.space.field(next, 'title') || 'Untitled'}</p>`}
        <div><a class="space-button space-button--primary" href=${next ? '#/queue' : '#/library'}>${next ? 'Open queue' : 'Open library'}</a></div>
      </section>
      <div class="counts space-stat-grid">
        ${[['In library', records.length], ['Queued', records.filter(r => status(r) === 'queued').length],
          ['Reading', records.filter(r => status(r) === 'reading').length],
          ['Completed', records.filter(r => status(r) === 'done').length]].map(([label, count]) => html`
          <div class="count space-card space-stat" key=${label}><strong class="space-stat-value">${count}</strong><span class="space-stat-label">${label}</span><span class="space-tile space-tile--small" data-accent=${label === 'Completed' ? 'green' : label === 'Reading' ? 'amber' : 'blue'} aria-hidden="true"><span class="space-icon" data-icon=${label === 'Completed' ? 'check' : label === 'Reading' ? 'book' : 'list'}></span></span></div>`)}
      </div>
      <section class="panel space-card" aria-labelledby="freshness-heading">
        <details><summary><h3 id="freshness-heading">Public source freshness</h3></summary>
        <dl class="space-facts">
          <dt>Last attempt</dt><dd>${latest ? `${time(latest.started_at || latest.queued_at)} (${latest.status})` : 'Never run'}</dd>
          <dt>Last successful refresh</dt><dd>${success ? time(success.ended_at) : 'No success in recent history'}</dd>
          <dt>Source as of</dt><dd>${success ? time(success.source_as_of) : 'Not available yet'}</dd>
        </dl>
        <p>Approve Refresh in the Space's Permissions before retrieving public papers.</p>
        <p>This view uses the latest 50 runs. The host shows complete freshness information.</p>
        </details>
        ${latest && ['failed', 'blocked', 'canceled'].includes(latest.status) && html`
          <p role="alert">Refresh ${latest.status}. ${latest.error || latest.detail?.reason || 'Open run details in the host.'}
            Existing records and notes remain available.</p>`}
      </section>
      ${!records.length && html`<${EmptyState} title="Start your reading library">
        <p>Add a paper in Library, or approve Refresh in Permissions and refresh the public feed.</p><//>`}
    </section>`;
}
