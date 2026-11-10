import { html, EmptyState } from 'spaces-kit';

function time(value) {
  return value ? new Date(value * 1000).toLocaleString() : 'Not available yet';
}

export function Overview({ records, runs }) {
  const status = record => window.space.field(record, 'status') || 'queued';
  const latest = runs[0];
  const success = runs.find(run => run.status === 'succeeded');
  return html`
    <section aria-labelledby="overview-heading">
      <h2 id="overview-heading">Overview</h2>
      <div class="counts">
        ${[['In library', records.length], ['Queued', records.filter(r => status(r) === 'queued').length],
          ['Reading', records.filter(r => status(r) === 'reading').length],
          ['Completed', records.filter(r => status(r) === 'done').length]].map(([label, count]) => html`
          <div class="count" key=${label}><strong>${count}</strong><span>${label}</span></div>`)}
      </div>
      <section class="panel" aria-labelledby="freshness-heading">
        <h3 id="freshness-heading">Public source freshness</h3>
        <dl>
          <dt>Last attempt</dt><dd>${latest ? `${time(latest.started_at || latest.queued_at)} (${latest.status})` : 'Never run'}</dd>
          <dt>Last successful refresh</dt><dd>${success ? time(success.ended_at) : 'No success in recent history'}</dd>
          <dt>Source as of</dt><dd>${success ? time(success.source_as_of) : 'Not available yet'}</dd>
        </dl>
        ${latest && ['failed', 'blocked', 'canceled'].includes(latest.status) && html`
          <p role="alert">Refresh ${latest.status}. ${latest.error || latest.detail?.reason || 'Open run details in the host.'}
            Existing records and notes remain available.</p>`}
        <p>Approve Refresh in the Space's Permissions before retrieving public papers.</p>
        <p>This view uses the latest 50 runs. The host shows complete freshness information.</p>
      </section>
      ${!records.length && html`<${EmptyState} title="Start your reading library">
        <p>Add a paper in Library, or approve Refresh in Permissions and refresh the public feed.</p><//>`}
    </section>`;
}
