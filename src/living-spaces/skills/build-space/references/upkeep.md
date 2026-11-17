## Keep the Space current

Declare upkeep in the manifest. Two handlers exist:

- `upkeep: {handler:'feed', sources:[{id,url,collection,purpose}]}` reads public
  HTTPS RSS or Atom feeds in-process with no model calls. It needs Internet access,
  which is on by default; the user can turn it off in Permissions.
- `upkeep: {handler:'agent', prompt:'...'}` runs a Hermes agent turn that uses
  `spaces_*` tools, writes results with `source_owned=true`, and preserves user
  fields. Each run uses model calls; tell the user so.

Put credentials nowhere in files, records, tool results, or logs.

`spaces_refresh` is Refresh now. A feed Space returns a run: `queued` and
`running` mean in progress; check `spaces_get` recent runs and report success
only for `succeeded`. A successful no-change run is valid. On `blocked`, explain
the reason and the action needed. On `failed`, keep last-good records visible and
describe the error. Show last attempt, last success, and source-as-of separately.
None implies either of the others. An agent Space returns
`{kind:'cron', cron_job_id, dispatch}`: it triggers the linked Hermes cron
job, or starts a one-time Hermes cron agent run when none is linked. The dispatch response is not proof of execution or delivery.
`spaces_upkeep` action `status` reports public native job metadata. Execution
history and manual dispatch outcomes are unavailable.
The app's `space.refresh()` runs only the feed handler. For an agent Space it
returns `blocked` with reason `agent_from_guest`; agent upkeep runs from Refresh
now in Hermes, from chat, or from the linked cron job.
The frame has `space.runs()`, not a freshness-summary method. Research Desk uses
recent runs and labels that limited window. If no success appears there, say
"No success in recent history", not "Never refreshed". Keep last-good collection
records and mounted editors visible through refresh or query errors.

When the user asks for scheduled upkeep, call `spaces_schedule_upkeep` with
`kind`, `cadence`, an IANA `timezone`, and for `agent` the `prompt`. It creates an
ordinary Hermes cron job now; the user's request is the consent, as for any cron
job. It replaces any existing upkeep job for the Space. The result contains public native job metadata and a prompt preview.
Report its schedule, next run, and warnings exactly as returned. Full prompts
and execution history are unavailable. Changing the
manifest prompt later does not change the job; schedule again when the user asks.
Use `spaces_upkeep` with `status`, `pause`, `resume`, `run`, or `remove` to read
or control the job. `missing: true` means the linked job no longer exists.
Archiving pauses the job and unarchiving does not resume it. Scheduled upkeep
needs Hermes available. Catch-up runs one current refresh when Hermes wakes,
without replaying missed intervals.
