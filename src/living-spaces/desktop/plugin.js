// src/desktop/plugin.src.js
import { ROUTES_AREA, SIDEBAR_NAV_AREA, TRANSCRIPT_DIRECTIVE_AREA, ErrorState as ErrorState6, host as host4, useQuery as useQuery6 } from "@hermes/plugin-sdk";
import { useEffect as useEffect4, useState as useState7 } from "react";
import { jsx as jsx7, jsxs as jsxs7 } from "react/jsx-runtime";

// src/desktop/ui/index.jsx
import { EmptyState, ErrorState, SearchField, SegmentedControl, Skeleton, host, useQuery } from "@hermes/plugin-sdk";
import { useState as useState2 } from "react";

// src/desktop/ui/components.jsx
import { Badge, Button, Codicon, CopyButton, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, fmtDateTime, relativeTime, Tip } from "@hermes/plugin-sdk";
import { useLayoutEffect, useMemo, useRef, useState } from "react";

// src/desktop/ui/markdown.mjs
var FENCE = /^\s*```/;
var HEADING = /^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/;
var ITEM = /^\s*([-*+]|\d{1,9}[.)])\s+(.*)$/;
var BOLD_HEADING = /^\s*(?:\*\*([^*\n]+?)\*\*|__([^_\n]+?)__)\s*$/;
var INLINE = new RegExp([
  /`([^`\n]+)`/.source,
  /\*\*([^*\n]+?)\*\*/.source,
  /__([^_\n]+?)__/.source,
  /\[([^\]\n]+)\]\(([^)\s]+)\)/.source,
  /(https:\/\/[^\s<>()]*[^\s<>().,;:!?'"])/.source,
  /(?<![\w*])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?![\w*])/.source,
  /(?<![\w_])_(?![\s_])([^_\n]+?)(?<![\s_])_(?![\w_])/.source
].join("|"), "g");
var isHttps = (href) => /^https:\/\/[^\s]+$/i.test(href);
function parseInline(line) {
  const spans = [];
  const push = (span) => {
    const last = spans.at(-1);
    if (span.type === "text" && last?.type === "text") last.text += span.text;
    else if (span.type !== "text" || span.text) spans.push(span);
  };
  let index = 0;
  for (const match of line.matchAll(INLINE)) {
    push({ type: "text", text: line.slice(index, match.index) });
    const [, code, strong, strongAlt, label, href, url, em, emAlt] = match;
    if (code != null) push({ type: "code", text: code });
    else if (strong != null || strongAlt != null) push({ type: "strong", text: strong ?? strongAlt });
    else if (label != null) push(isHttps(href) ? { type: "link", text: label, href } : { type: "text", text: label });
    else if (url != null) push({ type: "link", text: url, href: url });
    else push({ type: "em", text: em ?? emAlt });
    index = match.index + match[0].length;
  }
  push({ type: "text", text: line.slice(index) });
  return spans;
}
var startsBlock = (line) => FENCE.test(line) || HEADING.test(line) || BOLD_HEADING.test(line) || ITEM.test(line);
function parseMarkdown(text) {
  const lines = String(text ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (FENCE.test(line)) {
      const body = [];
      for (i++; i < lines.length && !FENCE.test(lines[i]); i++) body.push(lines[i]);
      i++;
      blocks.push({ type: "code", text: body.join("\n") });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({ type: "heading", spans: parseInline(heading[2]) });
      i++;
      continue;
    }
    const bold = BOLD_HEADING.exec(line);
    if (bold) {
      blocks.push({ type: "heading", spans: [{ type: "text", text: (bold[1] ?? bold[2]).trim() }] });
      i++;
      continue;
    }
    const item = ITEM.exec(line);
    if (item) {
      const ordered = /\d/.test(item[1]);
      const items = [];
      while (i < lines.length) {
        const next = ITEM.exec(lines[i]);
        if (!next || /\d/.test(next[1]) !== ordered) break;
        let content = next[2];
        for (i++; i < lines.length && /^\s+\S/.test(lines[i]) && !ITEM.test(lines[i]) && !FENCE.test(lines[i]); i++) content += ` ${lines[i].trim()}`;
        items.push(parseInline(content));
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }
    const spans = [];
    for (; i < lines.length && lines[i].trim() && (spans.length === 0 || !startsBlock(lines[i])); i++) {
      if (spans.length) spans.push({ type: "break" });
      spans.push(...parseInline(lines[i].trim()));
    }
    blocks.push({ type: "paragraph", spans });
  }
  return blocks;
}
var plain = (spans) => spans.map((span) => span.type === "break" ? " " : span.text).join("").replace(/\s+/g, " ").trim();
var SUMMARY_MAX = 160;
function answerSummary(text) {
  const blocks = parseMarkdown(text);
  const block = blocks.find((b) => b.type === "paragraph" || b.type === "list") || blocks.find((b) => b.type === "heading");
  if (!block) return "";
  const line = plain(block.type === "list" ? block.items[0] : block.spans);
  const sentence = /^.*?[.!?](?=\s|$)/.exec(line)?.[0] ?? line;
  return sentence.length > SUMMARY_MAX ? `${sentence.slice(0, SUMMARY_MAX - 1).trimEnd()}\u2026` : sentence;
}

// src/desktop/ui/model.mjs
var SPACE_ID = /^[a-z0-9][a-z0-9-]{1,47}$/;
var isSpaceId = (value) => typeof value === "string" && SPACE_ID.test(value);
var spacePath = (sid) => `/spaces/${encodeURIComponent(sid)}`;
var spaceRoute = (sid) => `/spaces?space=${encodeURIComponent(sid)}`;
function routeSpace(hash) {
  const id = new URLSearchParams((hash || "").split("?")[1] || "").get("space");
  return isSpaceId(id) ? id : null;
}
var ACCENTS = { blue: "#0053fd", green: "#55a583", amber: "#e0a06c", purple: "#9e94d5", teal: "#4c9fb0", rose: "#e75e78", orange: "#e08a64", grey: "#8a8a93" };
var accentColor = (accent) => Object.hasOwn(ACCENTS, accent) ? ACCENTS[accent] : ACCENTS.blue;
var iconName = (icon) => typeof icon === "string" && /^[a-z][a-z0-9-]{0,63}$/.test(icon) ? icon : "layers";
var PILLS = {
  ready: { label: "Available", icon: "check", border: "solid" },
  building: { label: "Building", icon: "tools", border: "dashed" },
  updating: { label: "Updating", icon: "refresh", border: "solid" },
  failed: { label: "Failed", icon: "error", border: "solid" },
  blocked: { label: "Blocked", icon: "circle-slash", border: "solid" },
  archived: { label: "Archived", icon: "archive", border: "dotted" },
  crashed: { label: "Crashed", icon: "error", border: "solid" },
  paused: { label: "Paused", icon: "debug-pause", border: "solid" },
  granted: { label: "Allowed", icon: "check", border: "solid" },
  requested: { label: "Needs your decision", icon: "warning", border: "dashed" },
  denied: { label: "Denied", icon: "circle-slash", border: "solid" },
  revoked: { label: "Revoked", icon: "circle-slash", border: "solid" },
  succeeded: { label: "Succeeded", icon: "check", border: "solid" },
  queued: { label: "Queued", icon: "watch", border: "solid" },
  running: { label: "Running", icon: "refresh", border: "solid" },
  canceled: { label: "Canceled", icon: "circle-slash", border: "solid" }
};
var inFlight = (status) => status === "queued" || status === "running";
function spaceStatus(space, frame = false) {
  if (space.status === "archived") return "archived";
  if (space.status === "building" || !space.head_rev) return "building";
  if (space.attention?.kind === "crashed") return frame ? "crashed" : "failed";
  if (inFlight(space.freshness?.last_attempt_status)) return "updating";
  if (space.attention?.kind) return space.attention.kind;
  if (["failed", "blocked"].includes(space.freshness?.last_attempt_status)) return space.freshness.last_attempt_status;
  return "ready";
}
function statusDimensions(space, { guest = "unknown", write = null, hostError = false } = {}) {
  const host5 = hostError ? "unavailable" : space.status === "archived" ? "archived" : space.status === "building" || !space.head_rev ? "building" : "available";
  return { host: host5, guest, save: write?.status || "idle", freshness: space.freshness };
}
var BOT_RETRY = ["unknown", "failed", "offline"];
var BOT_SETTLED = ["completed", "failed", "offline", "unknown"];
var botDismissKey = (action) => action?.activationId ? `${action.activationId}:${action.status}` : null;
function parseBotDismissal(value) {
  let record;
  try {
    record = JSON.parse(value);
  } catch {
    return null;
  }
  if (typeof record?.id !== "string" || !Array.isArray(record.statuses) || !record.statuses.every((status) => typeof status === "string")) return null;
  return { id: record.id, statuses: record.statuses };
}
function botDismissed(action, record) {
  if (!action?.activationId || action.userInitiated === true || record?.id !== action.activationId) return false;
  return record.statuses.includes(action.status) || ["offline", "unknown"].includes(action.status);
}
function dismissBot(record, action) {
  const statuses = record?.id === action.activationId ? record.statuses : [];
  return { id: action.activationId, statuses: [.../* @__PURE__ */ new Set([...statuses, action.status])] };
}
var botKind = (status) => status === "completed" ? "reply" : BOT_RETRY.includes(status) ? "failed" : "progress";
function botBanner(action, { dismissed = false, expanded = false } = {}) {
  if (!action || dismissed) return null;
  const kind = botKind(action.status);
  const answer = kind === "reply" && typeof action.answer === "string" && action.answer.trim() ? action.answer : null;
  return {
    status: action.status,
    kind,
    label: kind === "reply" ? "Hermes replied" : kind === "failed" ? "Bot request failed" : `Bot request: ${action.status}`,
    reason: answer ? null : action.message || null,
    summary: answer ? answerSummary(answer) : "",
    answer,
    at: Number.isFinite(action.at) ? action.at : null,
    expanded: !!answer && expanded,
    collapsible: !!answer,
    canRetry: !!action.activationId && kind === "failed",
    canDismiss: BOT_SETTLED.includes(action.status)
  };
}
var STORAGE_SUBJECT = { source_bytes: "source data", source_metadata_bytes: "source metadata", data_bytes: "records", records: "records", project_bytes: "project files", project_files: "project files", file_bytes: "the largest file" };
var trimmed = (value) => Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "");
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${trimmed(bytes / 1024)} KB`;
  return `${trimmed(bytes / 1024 / 1024)} MB`;
}
function storageNotice(storage2, hidden = null) {
  const percent = (row2) => Math.round(row2.used / row2.limit * 100);
  const rows = (storage2?.warnings || []).filter((row2) => Number.isFinite(row2?.used) && Number.isFinite(row2?.limit) && row2.limit > 0).map((row2) => ({ row: row2, id: `${row2.resource}:${percent(row2)}` }));
  const skip = new Set(String(hidden ?? "").split(","));
  const shown = rows.filter(({ id }) => !skip.has(id)).map(({ row: row2 }) => row2);
  if (!shown.length) return null;
  const row = shown.reduce((top, next) => next.used / next.limit > top.used / top.limit ? next : top);
  const pct = percent(row);
  const key = rows.map(({ id }) => id).sort().join(",");
  const bytes = /_bytes$/.test(row.resource);
  const amount = (value) => bytes ? formatBytes(value) : value.toLocaleString("en-US");
  const subject = STORAGE_SUBJECT[row.resource] || String(row.resource).replace(/_bytes$/, "").replace(/_/g, " ");
  return { pct, key, title: `Storage ${pct}% full`, line: `${amount(row.used)} of ${amount(row.limit)} used by ${subject}. Writes stop at the limit.` };
}
var GUEST_WORDS = { unknown: "not reported", starting: "starting", loaded: "loaded", failed: "failed", faulted: "faulted (uncaught error, still running)" };
var guestWord = (state) => GUEST_WORDS[state] || String(state);
function needsAttention(space) {
  return space.status !== "archived" && ["failed", "blocked", "crashed"].includes(spaceStatus(space, true));
}
function summaryCounts(spaces) {
  return { active: spaces.filter((s) => s.status !== "archived").length, attention: spaces.filter(needsAttention).length };
}
function visibleSpaces(spaces, search, filter) {
  const q = search.trim().toLocaleLowerCase();
  return spaces.filter((s) => filter === "archived" ? s.status === "archived" : s.status !== "archived" && (filter !== "attention" || needsAttention(s)) && (filter !== "pinned" || s.pinned)).filter((s) => `${s.name} ${s.owner}`.toLocaleLowerCase().includes(q)).sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || (b.last_opened_at ?? 0) - (a.last_opened_at ?? 0) || b.updated_at - a.updated_at || a.id.localeCompare(b.id));
}
function actorWords(actor) {
  const [kind, ...rest] = String(actor || "").split(":");
  const name = rest.join(":").trim();
  if (kind === "user") return { verb: "Edited by you" };
  if (kind === "app") return { verb: "Edited in this Space" };
  if (kind === "agent") return { verb: name ? `Edited in chat by ${name}` : "Edited in chat" };
  if (kind === "upkeep") return { verb: !name || name === "schedule" ? "Refreshed on schedule" : `Synced by ${name}` };
  return null;
}
var sourceHost = (url) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
};
function freshnessPhrase(space) {
  const f = space.freshness || {};
  const state = spaceStatus(space, true);
  if (state === "archived") return { key: "archive", label: "Archived", at: space.archived_at ?? space.updated_at };
  if (state === "building") return { key: "building", label: "Building the first version" };
  if (state === "updating") return { key: "updating", label: "Refreshing now\u2026" };
  if (state === "failed" || state === "blocked") {
    const verb = state === "failed" ? "Refresh failed" : "Refresh blocked";
    return f.last_success_at != null ? { key: state, label: `${verb} \xB7 data from`, at: f.last_success_at } : { key: state, label: `${verb} \xB7 no successful update yet` };
  }
  const activity = space.activity;
  const words = activity && Number.isFinite(activity.at) ? actorWords(activity.actor) : null;
  const host5 = (f.sources || []).map((source) => sourceHost(source?.url)).find(Boolean);
  const refreshed = f.last_success_at != null ? { key: "success", label: host5 ? `Refreshed from ${host5}` : "Updated", at: f.last_success_at } : null;
  if (words && (!refreshed || activity.at > refreshed.at + 60)) {
    const verb = activity.kind === "code" && activity.actor?.startsWith("agent:") ? words.verb.replace("Edited in chat", "Changed in chat") : words.verb;
    return { key: "activity", label: verb, at: activity.at };
  }
  if (refreshed) return refreshed;
  return { key: "success", label: f.last_attempt_status === "failed" || f.last_attempt_status === "blocked" ? "No successful update yet" : "Not refreshed yet" };
}
var ALERT_KINDS = ["failed", "blocked", "crashed", "conflict"];
function freshnessFacts(space, format) {
  const f = space.freshness || {};
  return [
    { key: "success", label: "Last successful update", at: f.last_success_at },
    { key: "attempt", label: "Last attempt", at: f.last_attempt_at },
    { key: "source", label: "Source data from", at: f.source_as_of },
    { key: "next", label: "Next refresh", at: f.next_run_at }
  ].filter((fact) => fact.at != null).map((fact) => ({ ...fact, value: `${format(fact.at)}${fact.key === "attempt" && f.last_attempt_status ? ` \xB7 ${f.last_attempt_status}` : ""}` }));
}
function cardLines(space, format) {
  const f = space.freshness || {};
  const at = (value) => value == null ? "" : ` ${format(value)}`;
  const state = spaceStatus(space);
  if (state === "building") return [`${space.owner} is building the first version`, space.created_at != null ? `Started${at(space.created_at)}` : ""];
  if (state === "archived") return [`Archived${at(space.archived_at ?? space.updated_at)}`, "Future upkeep paused"];
  if (space.attention?.kind === "crashed") return [`Stopped working${at(f.last_attempt_at)}`, space.attention.message || ""];
  if (state === "updating") return ["Refreshing now\u2026", f.last_success_at != null ? `Last good update${at(f.last_success_at)}` : ""];
  if (state === "failed") return [`Refresh failed${at(f.last_attempt_at)}`, f.last_success_at != null ? `Showing last good data from${at(f.last_success_at)}` : "No successful update yet"];
  if (state === "blocked") return [`Refresh blocked${at(f.last_attempt_at)}`, space.attention?.message || "Review the last run for details"];
  return [f.last_success_at == null ? "Not refreshed yet" : `Updated${at(f.last_success_at)}`, space.upkeep?.enabled === false ? "Upkeep paused" : f.next_run_at != null ? `Next refresh${at(f.next_run_at)}` : ""];
}
function advanceCursor(cursor, page) {
  const changes = (page?.changes || []).filter((c) => Number.isSafeInteger(c.seq) && c.seq > cursor).sort((a, b) => a.seq - b.seq);
  const seq = changes.length ? changes.at(-1).seq : cursor;
  return { seq, changes };
}
function refreshReason(space) {
  if (space.status === "archived") return "This Space is archived. Restore it to refresh.";
  if (!space.manifest?.upkeep) return "No refresh handler is declared. Ask the owner in chat to add one.";
  if (spaceStatus(space) === "blocked") return space.attention?.message || "Refresh is blocked. Review Permissions.";
  return "";
}
function runResult(run) {
  if (run.status === "failed") return run.error || "Refresh failed";
  if (run.status === "blocked") return `Blocked: ${run.detail?.reason || "Review Permissions"}`;
  if (run.status === "canceled") return "Refresh canceled";
  if (inFlight(run.status)) return run.status === "queued" ? "Waiting to start" : "Refreshing now\u2026";
  const c = run.changed || {};
  return c.added || c.updated || c.removed ? `${c.added || 0} added \xB7 ${c.updated || 0} updated \xB7 ${c.unchanged || 0} unchanged` : `no change \xB7 ${c.unchanged || 0} unchanged`;
}
function dispatchText(dispatch, format) {
  if (!dispatch) return "";
  const at = (value) => value == null ? "" : format(typeof value === "number" ? value : Date.parse(value) / 1e3);
  const catchUp = dispatch.kind === "catch_up";
  const delay = ["late", "catch_up"].includes(dispatch.kind) && dispatch.lateness_seconds != null ? ` Delayed by ${dispatch.lateness_seconds} s.` : "";
  const scheduled = at(dispatch.scheduled_at);
  const actual = at(dispatch.dispatched_at);
  return `${catchUp ? "Catch-up refresh. " : ""}${scheduled ? `${catchUp ? "Missed scheduled time" : "Scheduled time"} ${scheduled}. ` : ""}${actual ? `Actual dispatch ${actual}.` : ""}${delay}${catchUp ? " Missed intervals were not replayed." : ""}`.trim();
}
var CATCH_UP = "Missed runs follow native Hermes cron policy. Current catch-up settings are unavailable here.";
var EXECUTION_LABELS = { succeeded: "Succeeded", failed: "Failed", running: "Running", claimed: "Claimed", queued: "Queued", unknown: "Outcome unknown, side effects may have run" };
var executionLabel = (status) => EXECUTION_LABELS[status] || String(status ?? "");
var toSeconds = (value) => value == null ? null : typeof value === "number" ? value : Number.isFinite(Date.parse(value)) ? Date.parse(value) / 1e3 : null;
var PROMPTS = [
  "Build Research Desk: an overview, a searchable library and a reading queue. Keep my notes and reading status.",
  "Build a weekly fitness planner with a progress chart. Refresh it every Monday."
];
function dataVersionCompatibility(current, target) {
  if (!Number.isInteger(current) || current <= 0 || !Number.isInteger(target) || target <= 0) return "unknown";
  return current === target ? "compatible" : "incompatible";
}
function revisionCompatibility(space, revision) {
  return dataVersionCompatibility(space.data_version, revision?.manifest?.data?.version);
}
function recoveryCompatibility(space, point) {
  return dataVersionCompatibility(space.data_version, point.data_version);
}
function restoreCopy(space, rev) {
  const kept = space.head_rev > rev + 1 ? `Revisions ${rev + 1}\u2013${space.head_rev} stay in history.` : `Revision ${space.head_rev} stays in history.`;
  return `Restore revision ${rev}? This brings back the Space's earlier code as a new revision ${space.head_rev + 1}. ${kept} Your records, notes and statuses stay as they are now. Migration undo and data downgrades are not supported.`;
}
function errorText(error) {
  let detail = error?.error || error?.body?.error || error;
  if (!detail?.code && typeof detail?.message === "string") {
    const json = detail.message.indexOf("{");
    if (json >= 0) {
      try {
        detail = JSON.parse(detail.message.slice(json)).error || detail;
      } catch {
      }
    }
  }
  const message = detail?.message || String(error);
  if (detail?.code === "incompatible" || /incompatible/.test(message)) {
    const versions = detail.from_version != null && detail.to_version != null ? ` Current data version ${detail.from_version}; target data version ${detail.to_version}.` : "";
    return `Incompatible revision: ${message}.${versions} Your current code and records are unchanged.`;
  }
  if (detail?.code === "limit") return `limit: ${message}${detail.limit != null ? ` \xB7 limit ${detail.limit}` : ""}${detail.actual != null ? ` \xB7 actual ${detail.actual}` : ""}`;
  return message;
}
function diagnosticText(value) {
  return String(value).replace(/\b(Bearer)\s+\S+/gi, "$1 [redacted]").replace(/\b(api[_-]?key|token|password|secret|authorization)(["']?\s*[:=]\s*["']?)[^\s,"';}]+/gi, "$1$2[redacted]").slice(0, 2e3);
}
function scopedRest(rest, currentScope2, expected) {
  const requireScope = () => {
    if (currentScope2() !== expected) throw new Error("The active Hermes backend changed. Reopen this Space.");
  };
  return async (path, options) => {
    requireScope();
    const result = await rest(path, options);
    requireScope();
    return result;
  };
}

// src/desktop/ui/components.jsx
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
var relative = (seconds) => relativeTime(seconds * 1e3);
function absolute(seconds) {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  const date = new Date(seconds * 1e3);
  const zone = new Intl.DateTimeFormat(void 0, { timeZoneName: "short" }).formatToParts(date).find((p) => p.type === "timeZoneName")?.value || "";
  return `${fmtDateTime.format(date)} ${zone}`.trim();
}
function Time({ at, children, relative: asRelative = false }) {
  if (!absolute(at)) return null;
  return /* @__PURE__ */ jsx("time", { dateTime: new Date(at * 1e3).toISOString(), title: absolute(at), children: children ?? (asRelative ? relative(at) : absolute(at)) });
}
function Icon({ name, spin = false }) {
  return /* @__PURE__ */ jsx(Codicon, { name, "aria-hidden": "true", className: spin ? "ls-spin" : void 0 });
}
function StatusPill({ status, label }) {
  const pill = PILLS[status] || { label: status, icon: "info", border: "solid" };
  return /* @__PURE__ */ jsxs(Badge, { variant: "outline", className: `ls-pill ls-${status}`, style: { borderStyle: pill.border }, children: [
    /* @__PURE__ */ jsx(Icon, { name: pill.icon, spin: ["updating", "running"].includes(status) }),
    label || pill.label
  ] });
}
function SpaceIcon({ icon }) {
  const name = iconName(icon);
  const [missing, setMissing] = useState(null);
  const ref = useRef(null);
  useLayoutEffect(() => {
    const element = ref.current?.querySelector(".codicon") || ref.current?.firstElementChild;
    if (!element || typeof getComputedStyle !== "function") return;
    const content = getComputedStyle(element, "::before").content;
    setMissing(content === "none" ? name : null);
  }, [name]);
  return /* @__PURE__ */ jsx("span", { ref, className: "ls-icon-slot", children: /* @__PURE__ */ jsx(Icon, { name: missing === name ? "layers" : name }) });
}
function SpaceTile({ space, small = false }) {
  return /* @__PURE__ */ jsx("span", { className: `ls-tile${small ? " ls-tile-small" : ""}`, style: { "--ls-accent": accentColor(space.accent) }, children: /* @__PURE__ */ jsx(SpaceIcon, { icon: space.icon }) });
}
function OwnerChip({ owner = "Hermes" }) {
  return /* @__PURE__ */ jsxs("span", { className: "ls-owner", children: [
    /* @__PURE__ */ jsx("span", { className: "ls-avatar", "aria-hidden": "true", children: owner.slice(0, 1).toUpperCase() }),
    /* @__PURE__ */ jsx("span", { children: owner })
  ] });
}
function Action({ children, icon, primary = false, danger = false, ...props }) {
  return /* @__PURE__ */ jsxs(Button, { type: "button", size: "sm", variant: primary ? "default" : danger ? "outline" : "secondary", className: danger ? "ls-action ls-danger" : "ls-action", ...props, children: [
    icon && /* @__PURE__ */ jsx(Icon, { name: icon, spin: icon === "refresh" && props["aria-busy"] }),
    children
  ] });
}
function DisabledReason({ reason, children }) {
  return /* @__PURE__ */ jsx(Tip, { label: reason || "Refresh this Space", children });
}
function CopyPrompt({ text, label = "Copy" }) {
  const [error, setError] = useState("");
  return /* @__PURE__ */ jsxs("div", { className: "ls-prompt", children: [
    /* @__PURE__ */ jsx(Icon, { name: "comment-discussion" }),
    /* @__PURE__ */ jsx("q", { children: text }),
    /* @__PURE__ */ jsx(CopyButton, { text, label, showLabel: true, buttonSize: "sm", onCopyError: () => setError("Copy failed. Select and copy the prompt.") }),
    error && /* @__PURE__ */ jsx("span", { role: "alert", children: error })
  ] });
}
function Banner({ kind = "info", title, children, actions }) {
  return /* @__PURE__ */ jsxs("div", { className: `ls-banner ls-${kind}`, role: ALERT_KINDS.includes(kind) ? "alert" : "status", children: [
    /* @__PURE__ */ jsx(Icon, { name: kind === "info" ? "info" : kind === "storage" ? "database" : "warning" }),
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("strong", { children: title }),
      children && /* @__PURE__ */ jsx("div", { className: "ls-secondary", children }),
      actions && /* @__PURE__ */ jsx("div", { className: "ls-actions", children: actions })
    ] })
  ] });
}
function Spans({ spans, onOpenLink }) {
  return spans.map((span, index) => span.type === "break" ? /* @__PURE__ */ jsx("br", {}, index) : span.type === "strong" ? /* @__PURE__ */ jsx("strong", { children: span.text }, index) : span.type === "em" ? /* @__PURE__ */ jsx("em", { children: span.text }, index) : span.type === "code" ? /* @__PURE__ */ jsx("code", { children: span.text }, index) : span.type === "link" ? /* @__PURE__ */ jsx("a", { href: span.href, onClick: (event) => {
    event.preventDefault();
    onOpenLink?.(span.href);
  }, children: span.text }, index) : span.text);
}
function Answer({ text, onOpenLink }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return blocks.map((block, index) => block.type === "code" ? /* @__PURE__ */ jsx("pre", { children: /* @__PURE__ */ jsx("code", { children: block.text }) }, index) : block.type === "heading" ? /* @__PURE__ */ jsx("h5", { children: /* @__PURE__ */ jsx(Spans, { spans: block.spans, onOpenLink }) }, index) : block.type === "list" ? (() => {
    const List = block.ordered ? "ol" : "ul";
    return /* @__PURE__ */ jsx(List, { children: block.items.map((item, n) => /* @__PURE__ */ jsx("li", { children: /* @__PURE__ */ jsx(Spans, { spans: item, onOpenLink }) }, n)) }, index);
  })() : /* @__PURE__ */ jsx("p", { children: /* @__PURE__ */ jsx(Spans, { spans: block.spans, onOpenLink }) }, index));
}
function Drawer({ title, description, children, onClose, note, returnFocus, heading }) {
  const trigger = useRef(returnFocus || (typeof document === "undefined" ? null : document.activeElement));
  const close = useRef(null);
  return /* @__PURE__ */ jsx(Dialog, { open: true, onOpenChange: (open) => !open && onClose(), children: /* @__PURE__ */ jsxs(
    DialogContent,
    {
      className: "ls-sheet",
      bodyClassName: "ls-sheet-body",
      showCloseButton: false,
      onOpenAutoFocus: (event) => {
        event.preventDefault();
        close.current?.focus();
      },
      onCloseAutoFocus: (event) => {
        event.preventDefault();
        trigger.current?.focus();
      },
      children: [
        /* @__PURE__ */ jsxs(DialogHeader, { className: "ls-sheet-header", children: [
          heading,
          /* @__PURE__ */ jsx(DialogTitle, { children: title }),
          /* @__PURE__ */ jsxs(Button, { ref: close, onClick: onClose, variant: "ghost", size: "sm", className: "ls-action", children: [
            /* @__PURE__ */ jsx(Icon, { name: "close" }),
            "Close"
          ] }),
          /* @__PURE__ */ jsx(DialogDescription, { className: "ls-sr", children: description || title })
        ] }),
        note,
        /* @__PURE__ */ jsx("div", { className: "ls-sheet-scroll", children })
      ]
    }
  ) });
}
function DecisionDialog({ title, description, confirmLabel, cancelLabel = "Cancel", danger = false, onClose, onConfirm, returnFocus, successFocus }) {
  const cancel = useRef(null);
  const trigger = useRef(returnFocus || (typeof document === "undefined" ? null : document.activeElement));
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const completed = useRef(false);
  const [error, setError] = useState("");
  async function confirm() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await onConfirm();
      completed.current = true;
      onClose();
    } catch (e) {
      setError(errorText(e));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return /* @__PURE__ */ jsx(Dialog, { open: true, onOpenChange: (open) => !open && !busy && onClose(), children: /* @__PURE__ */ jsxs(
    DialogContent,
    {
      role: danger ? "alertdialog" : "dialog",
      className: "ls-confirm",
      showCloseButton: false,
      onOpenAutoFocus: (event) => {
        event.preventDefault();
        cancel.current?.focus();
      },
      onCloseAutoFocus: (event) => {
        event.preventDefault();
        (completed.current && successFocus?.current ? successFocus.current : trigger.current)?.focus();
      },
      children: [
        /* @__PURE__ */ jsxs(DialogHeader, { children: [
          /* @__PURE__ */ jsx(DialogTitle, { children: title }),
          /* @__PURE__ */ jsx(DialogDescription, { children: description })
        ] }),
        error && /* @__PURE__ */ jsx(Banner, { kind: "failed", title: error }),
        /* @__PURE__ */ jsxs(DialogFooter, { children: [
          /* @__PURE__ */ jsx(Button, { ref: cancel, variant: "ghost", className: "ls-action", disabled: busy, onClick: onClose, children: cancelLabel }),
          /* @__PURE__ */ jsx(Action, { primary: !danger, danger, "aria-busy": busy, "aria-disabled": busy, onClick: confirm, children: busy ? "Working\u2026" : confirmLabel })
        ] })
      ]
    }
  ) });
}

// src/desktop/ui/snapshots.mjs
var PREFIX = "living-spaces:snapshot:";
var INDEX = "living-spaces:snapshot-index";
var SNAPSHOT_LIMITS = Object.freeze({ maxChars: 2e5, budgetChars: 12e5, maxEntries: 24, width: 480, minSide: 16, maxSide: 1024 });
var IMAGE = /^data:image\/(?:webp|png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/;
var side = (value) => Number.isInteger(value) && value >= SNAPSHOT_LIMITS.minSide && value <= SNAPSHOT_LIMITS.maxSide;
var snapshotKey = (scopeKey, sid) => PREFIX + JSON.stringify([scopeKey ?? null, sid]);
function parseSnapshot(value) {
  let snapshot = value;
  if (typeof value === "string") {
    try {
      snapshot = JSON.parse(value);
    } catch {
      return null;
    }
  }
  if (!snapshot || typeof snapshot !== "object") return null;
  const { image, width, height, at, rev } = snapshot;
  if (typeof image !== "string" || image.length > SNAPSHOT_LIMITS.maxChars || !IMAGE.test(image)) return null;
  if (!side(width) || !side(height) || !Number.isFinite(at) || !(rev == null || Number.isSafeInteger(rev))) return null;
  return { image, width, height, at, rev: rev ?? null };
}
var storage = () => {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
};
var readIndex = (store) => {
  try {
    const keys = JSON.parse(store.getItem(INDEX) || "[]");
    return Array.isArray(keys) ? keys.filter((key) => typeof key === "string" && key.startsWith(PREFIX)) : [];
  } catch {
    return [];
  }
};
function readSnapshot(scopeKey, sid, rev) {
  const store = storage();
  if (!store) return null;
  let snapshot;
  try {
    snapshot = parseSnapshot(store.getItem(snapshotKey(scopeKey, sid)));
  } catch {
    return null;
  }
  if (!snapshot || rev != null && snapshot.rev != null && snapshot.rev !== rev) return null;
  return snapshot;
}
function writeSnapshot(scopeKey, sid, value) {
  const snapshot = parseSnapshot(value);
  const store = storage();
  if (!snapshot || !store) return false;
  const key = snapshotKey(scopeKey, sid);
  const serialised = JSON.stringify(snapshot);
  const keys = readIndex(store).filter((entry) => entry !== key);
  try {
    const sizes = new Map(keys.map((entry) => [entry, store.getItem(entry)?.length ?? 0]));
    let total = serialised.length + [...sizes.values()].reduce((sum, size) => sum + size, 0);
    while (keys.length && (keys.length + 1 > SNAPSHOT_LIMITS.maxEntries || total > SNAPSHOT_LIMITS.budgetChars)) {
      const oldest = keys.shift();
      total -= sizes.get(oldest);
      store.removeItem(oldest);
    }
    store.setItem(key, serialised);
    store.setItem(INDEX, JSON.stringify([...keys, key]));
    return true;
  } catch {
    try {
      store.removeItem(key);
    } catch {
    }
    return false;
  }
}
function forgetSnapshot(scopeKey, sid) {
  const store = storage();
  if (!store) return;
  const key = snapshotKey(scopeKey, sid);
  try {
    store.removeItem(key);
    store.setItem(INDEX, JSON.stringify(readIndex(store).filter((entry) => entry !== key)));
  } catch {
  }
}

// src/desktop/ui/index.jsx
import { Fragment as Fragment2, jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
function CardPreview({ space, scopeKey = null }) {
  const snapshot = readSnapshot(scopeKey, space.id, space.head_rev || null);
  const [failed, setFailed] = useState2(null);
  const usable = !!snapshot && failed !== snapshot.image;
  return /* @__PURE__ */ jsx2("div", { className: `ls-thumb${usable ? "" : " ls-thumb-fallback"}`, style: { "--ls-accent": accentColor(space.accent) }, "data-preview": usable ? "snapshot" : "fallback", children: usable ? /* @__PURE__ */ jsx2("img", { src: snapshot.image, width: snapshot.width, height: snapshot.height, alt: "", decoding: "async", draggable: false, onError: () => setFailed(snapshot.image) }) : /* @__PURE__ */ jsx2("span", { className: "ls-thumb-mark", "aria-hidden": "true", children: /* @__PURE__ */ jsx2(SpaceIcon, { icon: space.icon }) }) });
}
function SpaceCard({ space, scopeKey = null }) {
  const status = spaceStatus(space);
  const lines = cardLines(space, relative);
  const facts = freshnessFacts(space, absolute);
  const phrase = freshnessPhrase(space);
  return /* @__PURE__ */ jsxs2(
    "a",
    {
      className: `ls-card ls-${status}`,
      style: { "--ls-accent": accentColor(space.accent) },
      href: `#${spaceRoute(space.id)}`,
      onClick: (e) => {
        if (!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {
          e.preventDefault();
          host.navigate(spaceRoute(space.id));
        }
      },
      "aria-label": `${space.name}, ${status[0].toUpperCase() + status.slice(1)}, owner ${space.owner}. ${lines.filter(Boolean).join(". ")}. ${facts.map((f) => `${f.label} ${f.value}`).join(". ")}${space.pinned ? ". Pinned" : ""}`,
      children: [
        /* @__PURE__ */ jsxs2("div", { className: "ls-card-media", children: [
          /* @__PURE__ */ jsx2(CardPreview, { space, scopeKey }),
          status !== "ready" && /* @__PURE__ */ jsx2("span", { className: "ls-card-state", children: /* @__PURE__ */ jsx2(StatusPill, { status }) }),
          space.pinned ? /* @__PURE__ */ jsxs2("span", { className: "ls-pin", title: "Pinned", children: [
            /* @__PURE__ */ jsx2(Icon, { name: "pinned" }),
            /* @__PURE__ */ jsx2("span", { className: "ls-sr", children: "Pinned" })
          ] }) : null
        ] }),
        /* @__PURE__ */ jsxs2("div", { className: "ls-card-caption", children: [
          /* @__PURE__ */ jsx2(SpaceTile, { space, small: true }),
          /* @__PURE__ */ jsxs2("div", { className: "ls-card-text", children: [
            /* @__PURE__ */ jsx2("div", { className: "ls-card-name", children: space.name }),
            space.description && /* @__PURE__ */ jsx2("p", { className: "ls-card-description", children: space.description }),
            /* @__PURE__ */ jsx2("div", { className: "ls-card-freshness", children: phrase.at != null ? /* @__PURE__ */ jsxs2(Fragment2, { children: [
              phrase.label,
              " \xB7 ",
              /* @__PURE__ */ jsx2(Time, { at: phrase.at, relative: true })
            ] }) : phrase.label })
          ] })
        ] })
      ]
    }
  );
}
function newChatAction(ctx) {
  const actions = ctx.listActions?.() || [];
  return actions.find((a) => a.id === "session.new") || actions.find((a) => /new.*chat|new.*session/i.test(`${a.id} ${a.label}`));
}
function useNewChat(ctx) {
  const [notice, setNotice] = useState2("");
  const action = newChatAction(ctx);
  const start = () => {
    const result = action && ctx.runAction?.(action.id);
    if (!result?.ok) setNotice("A new chat is unavailable. Copy an example prompt and paste it into a normal Hermes chat.");
  };
  return { action, start, notice };
}
function NewSpaceCard({ ctx }) {
  const { action, start, notice } = useNewChat(ctx);
  return /* @__PURE__ */ jsx2("div", { role: "listitem", className: "ls-newcard", children: /* @__PURE__ */ jsxs2("div", { children: [
    /* @__PURE__ */ jsx2(Icon, { name: "comment-discussion" }),
    /* @__PURE__ */ jsx2("strong", { children: "Build a Space in chat" }),
    /* @__PURE__ */ jsx2("span", { className: "ls-secondary", children: "Describe it to Hermes. It appears here as Building." }),
    /* @__PURE__ */ jsx2("div", { className: "ls-actions", children: action ? /* @__PURE__ */ jsx2(Action, { icon: "add", onClick: start, children: "Start a new chat" }) : /* @__PURE__ */ jsx2(CopyPrompt, { text: PROMPTS[0], label: "Copy prompt" }) }),
    notice && /* @__PURE__ */ jsx2("p", { role: "status", children: notice })
  ] }) });
}
function FirstSpace({ ctx }) {
  const { action, start, notice } = useNewChat(ctx);
  return /* @__PURE__ */ jsxs2("div", { className: "ls-empty", children: [
    /* @__PURE__ */ jsxs2("div", { className: "ls-empty-tiles", "aria-hidden": "true", children: [
      /* @__PURE__ */ jsx2(SpaceTile, { space: { accent: "blue", icon: "book" } }),
      /* @__PURE__ */ jsx2(SpaceTile, { space: { accent: "green", icon: "calendar" } }),
      /* @__PURE__ */ jsx2(SpaceTile, { space: { accent: "purple", icon: "graph" } })
    ] }),
    /* @__PURE__ */ jsx2(EmptyState, { title: "Build your first Space in chat", description: "A Space is a canvas your bots keep alive. Describe one in a normal Hermes chat and it appears here." }),
    PROMPTS.map((text) => /* @__PURE__ */ jsx2(CopyPrompt, { text }, text)),
    /* @__PURE__ */ jsxs2("div", { className: "ls-actions", children: [
      action ? /* @__PURE__ */ jsx2(Action, { primary: true, icon: "add", onClick: start, children: "Start a new chat" }) : /* @__PURE__ */ jsx2(CopyPrompt, { text: PROMPTS[0], label: "Start a new chat" }),
      /* @__PURE__ */ jsx2("span", { className: "ls-secondary", children: "New Spaces appear here, labelled Building until ready." })
    ] }),
    !action && /* @__PURE__ */ jsx2("p", { role: "status", children: "This host cannot start a new chat here. The action copies the example prompt to paste into a normal Hermes chat." }),
    notice && /* @__PURE__ */ jsx2("p", { role: "status", children: notice })
  ] });
}
function SpacesIndex({ ctx, scopeKey = null }) {
  const [search, setSearch] = useState2("");
  const [filter, setFilter] = useState2("all");
  const list = useQuery({ queryKey: ["living-spaces", scopeKey, "spaces"], queryFn: () => ctx.rest("/spaces"), refetchInterval: 2e3, notifyOnChangeProps: ["data", "error", "isLoading", "dataUpdatedAt"] });
  const spaces = list.data?.spaces || [];
  const counts = summaryCounts(spaces);
  const visible = visibleSpaces(spaces, search, filter);
  const pinned = spaces.some((s) => s.pinned && s.status !== "archived");
  const browsing = !search && filter === "all";
  return /* @__PURE__ */ jsxs2("div", { className: "ls-page ls-gallery", "data-testid": "spaces-index", children: [
    /* @__PURE__ */ jsxs2("div", { className: "ls-page-heading", children: [
      /* @__PURE__ */ jsxs2("div", { className: "ls-page-title", children: [
        /* @__PURE__ */ jsx2("h1", { children: "Spaces" }),
        list.data && /* @__PURE__ */ jsxs2("span", { className: "ls-secondary ls-num", children: [
          counts.active,
          " active \xB7 ",
          counts.attention,
          " need attention"
        ] })
      ] }),
      list.data && spaces.length > 0 && /* @__PURE__ */ jsx2(SearchField, { value: search, onChange: setSearch, placeholder: "Search Spaces or owner", "aria-label": "Search Spaces or owner", variant: "box", containerClassName: "ls-search" })
    ] }),
    list.error && /* @__PURE__ */ jsx2(ErrorState, { title: "Spaces could not be loaded", description: list.error.message, children: /* @__PURE__ */ jsx2(Action, { onClick: () => list.refetch(), children: "Try again" }) }),
    list.isLoading ? /* @__PURE__ */ jsx2("div", { className: "ls-grid", "aria-label": "Loading Spaces", children: [1, 2, 3].map((n) => /* @__PURE__ */ jsx2(Skeleton, { className: "ls-thumb" }, n)) }) : list.data && !spaces.length ? /* @__PURE__ */ jsx2(FirstSpace, { ctx }) : list.data ? /* @__PURE__ */ jsxs2(Fragment2, { children: [
      /* @__PURE__ */ jsxs2("div", { className: "ls-toolbar", children: [
        /* @__PURE__ */ jsx2(SegmentedControl, { value: filter, onChange: setFilter, sizing: "content", options: [{ id: "all", label: "Recent" }, ...pinned ? [{ id: "pinned", label: "Pinned" }] : [], { id: "attention", label: `Needs attention \xB7 ${counts.attention}` }, { id: "archived", label: "Archived" }] }),
        /* @__PURE__ */ jsx2("span", { className: "ls-sort", children: "Pinned first, then recently opened" })
      ] }),
      visible.length || browsing ? /* @__PURE__ */ jsxs2("div", { className: "ls-grid", role: "list", "aria-label": "Spaces", children: [
        visible.map((s) => /* @__PURE__ */ jsx2("div", { role: "listitem", children: /* @__PURE__ */ jsx2(SpaceCard, { space: s, scopeKey }) }, s.id)),
        browsing && /* @__PURE__ */ jsx2(NewSpaceCard, { ctx })
      ] }) : /* @__PURE__ */ jsx2("div", { role: "status", children: /* @__PURE__ */ jsx2(EmptyState, { title: search ? `No Spaces match \u201C${search}\u201D. Try another name or owner.` : filter === "attention" ? "Nothing needs attention." : filter === "pinned" ? "No pinned Spaces." : "No archived Spaces." }) })
    ] }) : null,
    /* @__PURE__ */ jsx2("p", { className: "ls-footer", children: "Spaces are built and changed in a normal chat. Ask your agent to \u201Cbuild\u2026\u201D, \u201Cchange\u2026\u201D or \u201Ckeep \u2026 current\u201D." })
  ] });
}

// src/desktop/ui/space.jsx
import { CopyButton as CopyButton2, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, ErrorState as ErrorState5, Skeleton as Skeleton5, host as host2, useQuery as useQuery5, useQueryClient } from "@hermes/plugin-sdk";
import { useEffect as useEffect3, useId, useLayoutEffect as useLayoutEffect2, useMemo as useMemo2, useRef as useRef5, useState as useState6 } from "react";

// src/desktop/ui/dismissal.mjs
var memory = /* @__PURE__ */ new Map();
function readDismissed(key) {
  if (memory.has(key)) return memory.get(key);
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}
function writeDismissed(key, value) {
  try {
    if (!globalThis.localStorage) throw new Error("No storage");
    globalThis.localStorage.setItem(key, value);
    memory.delete(key);
  } catch {
    memory.set(key, value);
  }
}

// src/desktop/ui/history.jsx
import { Badge as Badge2, EmptyState as EmptyState2, ErrorState as ErrorState2, Skeleton as Skeleton2, Tabs, TabsList, TabsTrigger, useQuery as useQuery2 } from "@hermes/plugin-sdk";
import { useEffect, useRef as useRef2, useState as useState3 } from "react";
import { Fragment as Fragment3, jsx as jsx3, jsxs as jsxs3 } from "react/jsx-runtime";
function RunRow({ run }) {
  const duration = run.ended_at != null && run.started_at != null ? `${Math.max(0, run.ended_at - run.started_at).toFixed(1)} s` : run.status === "queued" ? "Not started" : run.status === "running" ? "In progress" : "No duration reported";
  return /* @__PURE__ */ jsxs3("article", { className: "ls-row", children: [
    /* @__PURE__ */ jsxs3("div", { className: "ls-row-top", children: [
      /* @__PURE__ */ jsxs3("strong", { children: [
        /* @__PURE__ */ jsx3(Icon, { name: run.status === "succeeded" ? "check" : ["failed", "blocked"].includes(run.status) ? "warning" : "watch" }),
        run.status === "succeeded" ? "Refresh succeeded" : `Refresh ${run.status}`
      ] }),
      /* @__PURE__ */ jsx3(StatusPill, { status: run.status })
    ] }),
    /* @__PURE__ */ jsxs3("p", { className: "ls-secondary", children: [
      run.trigger,
      " \xB7 ",
      /* @__PURE__ */ jsx3(Time, { at: run.started_at ?? run.queued_at }),
      " \xB7 ",
      duration
    ] }),
    /* @__PURE__ */ jsx3("p", { children: runResult(run) }),
    run.detail?.dispatch && /* @__PURE__ */ jsx3("p", { className: "ls-secondary", children: dispatchText(run.detail.dispatch, absolute) })
  ] });
}
function RevisionRow({ revision, space, onRestore }) {
  const compatibility = revisionCompatibility(space, revision);
  return /* @__PURE__ */ jsxs3("article", { className: "ls-row", children: [
    /* @__PURE__ */ jsxs3("div", { className: "ls-row-top", children: [
      /* @__PURE__ */ jsxs3("strong", { children: [
        "Revision ",
        revision.rev
      ] }),
      revision.rev === space.head_rev ? /* @__PURE__ */ jsx3(Badge2, { variant: "outline", children: "Current" }) : compatibility !== "incompatible" && /* @__PURE__ */ jsx3(Action, { onClick: () => onRestore(revision.rev), children: "Restore\u2026" })
    ] }),
    /* @__PURE__ */ jsx3("p", { className: "ls-secondary", children: /* @__PURE__ */ jsx3(Time, { at: revision.created_at }) }),
    /* @__PURE__ */ jsxs3("p", { children: [
      revision.author,
      " \xB7 ",
      revision.summary
    ] }),
    /* @__PURE__ */ jsxs3("p", { className: "ls-secondary", children: [
      "Compatibility: ",
      compatibility === "incompatible" ? `incompatible. Current data version ${space.data_version}; target data version ${revision.manifest.data.version}. Cross-version code restore is not supported.` : compatibility === "compatible" ? `compatible with current data version ${space.data_version}.` : "unknown. The backend will check data versions before restoring code."
    ] })
  ] });
}
function RecoveryPointRow({ point, space }) {
  const compatibility = recoveryCompatibility(space, point);
  return /* @__PURE__ */ jsxs3("article", { className: "ls-row", "data-testid": `recovery-point-${point.id}`, children: [
    /* @__PURE__ */ jsxs3("strong", { children: [
      "Recovery point ",
      point.id
    ] }),
    /* @__PURE__ */ jsx3("p", { children: point.reason }),
    /* @__PURE__ */ jsxs3("p", { className: "ls-secondary", children: [
      /* @__PURE__ */ jsx3(Time, { at: point.created_at }),
      " \xB7 Code revision ",
      point.head_rev
    ] }),
    /* @__PURE__ */ jsxs3("p", { children: [
      "Compatibility: ",
      compatibility,
      ". ",
      compatibility === "incompatible" ? `Current data version ${space.data_version}; point data version ${point.data_version}. Cross-version restore is not supported.` : compatibility === "compatible" ? `Same data version ${space.data_version}. Use code revision history below for code-only restore.` : "Data-version compatibility cannot be established.",
      " Data restore is not supported here. Migration undo and data downgrades are not supported. Current records, notes and statuses stay as they are."
    ] })
  ] });
}
function HistorySheet({ ctx, scopeKey = null, space, onClose, onChanged, initialTab = "runs", returnFocus }) {
  const [tab, setTab] = useState3(initialTab);
  const [restore, setRestore] = useState3(null);
  const base = spacePath(space.id);
  const runs = useQuery2({ queryKey: ["living-spaces", scopeKey, space.id, "runs"], queryFn: () => ctx.rest(`${base}/runs`), refetchInterval: 2e3 });
  const revisions = useQuery2({ queryKey: ["living-spaces", scopeKey, space.id, "revisions"], queryFn: () => ctx.rest(`${base}/revisions`), refetchInterval: 2e3 });
  const points = useQuery2({ queryKey: ["living-spaces", scopeKey, space.id, "recovery-points"], queryFn: () => ctx.rest(`${base}/recovery-points`), refetchInterval: 2e3 });
  const query = tab === "runs" ? runs : revisions;
  const restoreCompatibility = revisionCompatibility(space, revisions.data?.find((row) => row.rev === restore));
  return /* @__PURE__ */ jsxs3(Fragment3, { children: [
    /* @__PURE__ */ jsxs3(Drawer, { title: "History & revisions", description: `History and code revisions for ${space.name}`, onClose, returnFocus, children: [
      /* @__PURE__ */ jsx3(StorageSection, { ctx, space, onChanged }, `${scopeKey}:${space.id}`),
      /* @__PURE__ */ jsx3(Tabs, { value: tab, onValueChange: setTab, className: "ls-tabs", children: /* @__PURE__ */ jsxs3(TabsList, { "aria-label": "History & revisions", children: [
        /* @__PURE__ */ jsx3(TabsTrigger, { id: "ls-runs-tab", "aria-controls": "ls-runs-panel", value: "runs", children: "Run history" }),
        /* @__PURE__ */ jsx3(TabsTrigger, { id: "ls-revisions-tab", "aria-controls": "ls-revisions-panel", value: "revisions", children: "Revisions" })
      ] }) }),
      /* @__PURE__ */ jsxs3("div", { role: "tabpanel", tabIndex: 0, id: `ls-${tab === "runs" ? "runs" : "revisions"}-panel`, "aria-labelledby": `ls-${tab === "runs" ? "runs" : "revisions"}-tab`, children: [
        tab === "revisions" && /* @__PURE__ */ jsxs3(Fragment3, { children: [
          /* @__PURE__ */ jsx3("p", { className: "ls-secondary", children: "Restoring code does not rewind records. Your records, notes and statuses stay as they are now. Migration undo and data downgrades are not supported." }),
          /* @__PURE__ */ jsxs3("section", { "aria-label": "Recovery points", children: [
            /* @__PURE__ */ jsx3("h3", { children: "Recovery points" }),
            points.error ? /* @__PURE__ */ jsx3(ErrorState2, { title: "Recovery points could not be loaded", description: errorText(points.error), children: /* @__PURE__ */ jsx3(Action, { onClick: () => points.refetch(), children: "Try again" }) }) : points.isLoading ? /* @__PURE__ */ jsx3(Skeleton2, { style: { height: 80 } }) : !points.data?.length ? /* @__PURE__ */ jsx3("p", { className: "ls-secondary", children: "No recovery points recorded." }) : points.data.map((point) => /* @__PURE__ */ jsx3(RecoveryPointRow, { point, space }, point.id))
          ] }),
          /* @__PURE__ */ jsx3("h3", { children: "Code revisions" })
        ] }),
        query.error ? /* @__PURE__ */ jsx3(ErrorState2, { title: "History could not be loaded", description: errorText(query.error), children: /* @__PURE__ */ jsx3(Action, { onClick: () => query.refetch(), children: "Try again" }) }) : query.isLoading ? /* @__PURE__ */ jsx3(Skeleton2, { style: { height: 180 } }) : !query.data?.length ? /* @__PURE__ */ jsx3(EmptyState2, { title: tab === "runs" ? "No refresh runs yet." : "No revisions yet." }) : query.data.map((row) => tab === "runs" ? /* @__PURE__ */ jsx3(RunRow, { run: row }, row.id) : /* @__PURE__ */ jsx3(RevisionRow, { revision: row, space, onRestore: setRestore }, row.rev))
      ] })
    ] }),
    restore != null && restoreCompatibility !== "incompatible" && /* @__PURE__ */ jsx3(DecisionDialog, { danger: true, title: `Restore revision ${restore}?`, description: restoreCopy(space, restore), confirmLabel: "Restore as new revision", onClose: () => setRestore(null), onConfirm: async () => {
      await ctx.rest(`${base}/revisions/${restore}/restore`, { method: "POST" });
      await revisions.refetch();
      await onChanged();
    } })
  ] });
}
function StorageNotice({ storage: storage2, onReview, storageKey }) {
  const [stored, setStored] = useState3(() => ({ storageKey, value: storageKey ? readDismissed(storageKey) : null }));
  const hidden = !storageKey ? null : stored.storageKey === storageKey ? stored.value : readDismissed(storageKey);
  const notice = storageNotice(storage2, hidden);
  if (!notice) return null;
  const dismiss = () => {
    writeDismissed(storageKey, notice.key);
    setStored({ storageKey, value: notice.key });
  };
  return /* @__PURE__ */ jsxs3(Banner, { kind: "storage", title: notice.title, actions: (onReview || storageKey) && /* @__PURE__ */ jsxs3(Fragment3, { children: [
    onReview && /* @__PURE__ */ jsx3(Action, { onClick: onReview, children: "Review" }),
    storageKey && /* @__PURE__ */ jsx3(Action, { onClick: dismiss, children: "Hide until it changes" })
  ] }), children: [
    /* @__PURE__ */ jsx3("span", { className: "ls-oneline", title: notice.line, children: notice.line }),
    /* @__PURE__ */ jsx3("div", { className: "ls-meter", "aria-hidden": "true", children: /* @__PURE__ */ jsx3("i", { style: { width: `${notice.pct}%` } }) })
  ] });
}
function StorageSection({ ctx, space, onChanged }) {
  const [categories, setCategories] = useState3(["revisions", "logs", "runs"]);
  const [before, setBefore] = useState3(() => new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10));
  const [proposal, setProposal] = useState3(null);
  const [confirming, setConfirming] = useState3(false);
  const [busy, setBusy] = useState3(false);
  const [error, setError] = useState3("");
  const [receipt, setReceipt] = useState3(null);
  const lifetime = useRef2(null);
  useEffect(() => {
    const current = { active: true };
    lifetime.current = current;
    return () => {
      current.active = false;
    };
  }, [ctx, space.id]);
  const storage2 = space.storage;
  if (!storage2) return null;
  const base = spacePath(space.id);
  const reset = () => {
    setProposal(null);
    setReceipt(null);
    setError("");
  };
  async function preview() {
    if (busy) return;
    const request = lifetime.current;
    setBusy(true);
    reset();
    try {
      const result = await ctx.rest(`${base}/retention/propose`, { method: "POST", body: { scope: { categories, before: (/* @__PURE__ */ new Date(`${before}T00:00:00Z`)).getTime() / 1e3 } } });
      if (request?.active) setProposal(result);
    } catch (failure2) {
      if (request?.active) setError(errorText(failure2));
    } finally {
      if (request?.active) setBusy(false);
    }
  }
  return /* @__PURE__ */ jsxs3("section", { "aria-label": "Storage", children: [
    /* @__PURE__ */ jsx3("h3", { children: "Storage" }),
    /* @__PURE__ */ jsx3(StorageNotice, { storage: storage2 }),
    /* @__PURE__ */ jsx3("ul", { children: Object.entries(storage2.categories).map(([name, row]) => /* @__PURE__ */ jsxs3("li", { children: [
      name,
      ": ",
      row.count,
      " \xB7 ",
      row.bytes,
      " bytes",
      row.fields != null && ` \xB7 ${row.fields} source fields`,
      row.source_details != null && ` \xB7 ${row.source_details} source run details`
    ] }, name)) }),
    /* @__PURE__ */ jsxs3("p", { className: "ls-secondary", children: [
      storage2.bytes_basis,
      " Native history is native-owned, excluded from these counts and never deleted here. No automatic cleanup is scheduled."
    ] }),
    /* @__PURE__ */ jsxs3("details", { children: [
      /* @__PURE__ */ jsx3("summary", { children: "Propose cleanup" }),
      /* @__PURE__ */ jsx3("p", { children: "Choose categories and a cutoff. Preview lists the exact items to remove and protected work. This does not delete anything." }),
      /* @__PURE__ */ jsxs3("fieldset", { disabled: busy, children: [
        /* @__PURE__ */ jsx3("legend", { children: "Categories to review" }),
        ["revisions", "records", "logs", "runs"].map((name) => /* @__PURE__ */ jsxs3("label", { children: [
          /* @__PURE__ */ jsx3("input", { type: "checkbox", checked: categories.includes(name), onChange: (event) => {
            reset();
            setCategories(event.target.checked ? [...categories, name] : categories.filter((value) => value !== name));
          } }),
          name,
          " "
        ] }, name)),
        /* @__PURE__ */ jsxs3("label", { children: [
          "Older than UTC date ",
          /* @__PURE__ */ jsx3("input", { type: "date", value: before, onChange: (event) => {
            reset();
            setBefore(event.target.value);
          } })
        ] })
      ] }),
      /* @__PURE__ */ jsx3(Action, { disabled: busy || !categories.length || !before, "aria-busy": busy, onClick: preview, children: "Preview cleanup" }),
      error && /* @__PURE__ */ jsx3("p", { role: "alert", children: error }),
      receipt && /* @__PURE__ */ jsxs3("p", { role: "status", children: [
        "Cleanup completed for ",
        receipt.proposal_id,
        ". Audit receipt ",
        receipt.audit_id,
        "."
      ] }),
      proposal && /* @__PURE__ */ jsxs3("div", { children: [
        /* @__PURE__ */ jsxs3("p", { children: [
          "Proposal ",
          /* @__PURE__ */ jsx3("code", { style: { overflowWrap: "anywhere" }, children: proposal.id })
        ] }),
        proposal.truncated.length > 0 && /* @__PURE__ */ jsxs3("p", { children: [
          "Bounded batch. More items remain in ",
          proposal.truncated.join(", "),
          ". Review a new proposal after this batch."
        ] }),
        ["remove", "protected"].map((kind) => /* @__PURE__ */ jsxs3("div", { children: [
          /* @__PURE__ */ jsx3("h4", { children: kind === "remove" ? "Would remove" : "Protected, kept" }),
          Object.entries(proposal[kind]).map(([name, rows]) => /* @__PURE__ */ jsxs3("details", { children: [
            /* @__PURE__ */ jsxs3("summary", { children: [
              name,
              ": ",
              rows.length
            ] }),
            /* @__PURE__ */ jsx3("ul", { children: rows.map((row, index) => /* @__PURE__ */ jsxs3("li", { style: { overflowWrap: "anywhere" }, children: [
              row.collection ? `${row.collection}/` : "",
              row.id ?? row.rev ?? row.sha,
              row.reason ? ` \xB7 ${row.reason}` : ""
            ] }, index)) })
          ] }, name))
        ] }, kind)),
        /* @__PURE__ */ jsx3(Action, { danger: true, disabled: !Object.values(proposal.remove).some((rows) => rows.length), onClick: () => setConfirming(true), children: "Review deletion\u2026" })
      ] })
    ] }),
    confirming && proposal && /* @__PURE__ */ jsx3(DecisionDialog, { danger: true, title: "Execute retention proposal?", description: `Permanently delete only the listed items in ${space.name} for proposal ${proposal.id}. Protected work and native history stay. Any changed state requires a new preview.`, confirmLabel: /* @__PURE__ */ jsx3("span", { style: { overflowWrap: "anywhere", whiteSpace: "normal" }, children: `Delete ${proposal.id}` }), onClose: () => setConfirming(false), onConfirm: async () => {
      const request = lifetime.current;
      const result = await ctx.rest(`${base}/retention/execute`, { method: "POST", body: { scope: proposal.scope, proposal_id: proposal.id, confirm: proposal.confirmation } });
      if (!request?.active) return;
      setReceipt(result);
      setProposal(null);
      await onChanged();
    } })
  ] });
}

// src/desktop/ui/permissions.jsx
import { ErrorState as ErrorState3, Skeleton as Skeleton3, useQuery as useQuery3 } from "@hermes/plugin-sdk";
import { useRef as useRef3, useState as useState4 } from "react";
import { Fragment as Fragment4, jsx as jsx4, jsxs as jsxs4 } from "react/jsx-runtime";
var NET_DESCRIPTION = "This Space can load content from and send data to the internet. It can't reach your Hermes app, your files or other Spaces.";
var NET_OFF_DESCRIPTION = "This Space can't load content from or send data to the internet through Internet access.";
var NET_OFF_NOTE = "Off is not a complete block. A browser feature called WebRTC can still send data this Space can read. It still can't reach Hermes, your credentials, your files or other Spaces.";
var CAPABILITIES = {
  data: { name: "Own data", icon: "folder", scope: "This Space's records only. Cannot see other Spaces.", purpose: "Store your records, notes and statuses.", leaves: "This grant stays on device. Space-readable data can leave through Internet access or the WebRTC limit when Internet access is off." },
  logs: { name: "Diagnostics", icon: "info", scope: "Error logs from this Space, secrets redacted. Only the latest 2,000 log entries are retained.", purpose: "Let the owner see crashes and repair them.", leaves: "No ordinary network access. The owner can read these logs in chat." }
};
function WebRTCNote() {
  return /* @__PURE__ */ jsxs4("p", { className: "ls-disclosure ls-secondary", id: "ls-net-note", "data-testid": "webrtc-note", children: [
    /* @__PURE__ */ jsx4(Icon, { name: "info" }),
    " ",
    NET_OFF_NOTE
  ] });
}
function InternetAccess({ grant, owner, onDecide, busy, pending }) {
  const enabled = grant.status === "granted";
  const requested = grant.status === "requested";
  return /* @__PURE__ */ jsx4("section", { className: "ls-section", children: /* @__PURE__ */ jsxs4("article", { className: "ls-grant ls-internet", "data-testid": "internet-access", "aria-busy": busy, children: [
    /* @__PURE__ */ jsxs4("div", { className: "ls-row-top", children: [
      /* @__PURE__ */ jsx4("strong", { id: "ls-net-title", children: "Internet access" }),
      /* @__PURE__ */ jsxs4("div", { className: "ls-switch-value", children: [
        /* @__PURE__ */ jsx4("span", { "aria-hidden": "true", children: enabled ? "On" : "Off" }),
        /* @__PURE__ */ jsx4("button", { type: "button", className: "ls-switch", role: "switch", "aria-labelledby": "ls-net-title", "aria-checked": enabled, "aria-describedby": `ls-net-description${!enabled ? " ls-net-note" : ""}`, "aria-busy": busy, "aria-disabled": busy || requested, onClick: () => !busy && !requested && onDecide(grant, enabled ? "revoke" : "grant"), children: /* @__PURE__ */ jsx4("span", { className: "ls-switch-track", children: /* @__PURE__ */ jsx4("span", { className: "ls-switch-thumb" }) }) })
      ] })
    ] }),
    /* @__PURE__ */ jsx4("p", { id: "ls-net-description", className: "ls-secondary", children: enabled ? NET_DESCRIPTION : NET_OFF_DESCRIPTION }),
    !enabled && /* @__PURE__ */ jsx4(WebRTCNote, {}),
    busy && pending?.capability === "net" && /* @__PURE__ */ jsx4("p", { role: "status", children: pending.decision === "grant" ? "Turning on\u2026" : pending.decision === "revoke" ? "Turning off\u2026" : "Denying request\u2026" }),
    requested && /* @__PURE__ */ jsxs4(Fragment4, { children: [
      /* @__PURE__ */ jsxs4("p", { children: [
        owner,
        " is asking to turn this on."
      ] }),
      /* @__PURE__ */ jsxs4("div", { className: "ls-actions", children: [
        /* @__PURE__ */ jsx4(Action, { primary: true, "aria-disabled": busy, onClick: () => !busy && onDecide(grant, "grant"), children: "Approve" }),
        /* @__PURE__ */ jsx4(Action, { "aria-disabled": busy, onClick: () => !busy && onDecide(grant, "deny"), children: "Deny" })
      ] })
    ] })
  ] }) });
}
function GrantCard({ grant, onDecide, busy }) {
  const model = CAPABILITIES[grant.capability];
  if (!model) return null;
  const scopeText = model.scope;
  return /* @__PURE__ */ jsxs4("article", { className: `ls-grant${grant.status === "requested" ? " ls-pending" : ""}`, children: [
    /* @__PURE__ */ jsxs4("div", { className: "ls-row-top", children: [
      /* @__PURE__ */ jsxs4("strong", { children: [
        /* @__PURE__ */ jsx4(Icon, { name: model.icon }),
        model.name
      ] }),
      /* @__PURE__ */ jsx4(StatusPill, { status: grant.status })
    ] }),
    /* @__PURE__ */ jsxs4("dl", { className: "ls-facts", children: [
      /* @__PURE__ */ jsxs4("div", { children: [
        /* @__PURE__ */ jsx4("dt", { children: "Scope" }),
        /* @__PURE__ */ jsx4("dd", { children: scopeText })
      ] }),
      /* @__PURE__ */ jsxs4("div", { children: [
        /* @__PURE__ */ jsx4("dt", { children: "Purpose" }),
        /* @__PURE__ */ jsx4("dd", { children: grant.purpose || model.purpose })
      ] }),
      /* @__PURE__ */ jsxs4("div", { children: [
        /* @__PURE__ */ jsx4("dt", { children: "Data leaves device" }),
        /* @__PURE__ */ jsx4("dd", { children: model.leaves })
      ] }),
      /* @__PURE__ */ jsxs4("div", { children: [
        /* @__PURE__ */ jsx4("dt", { children: "Access" }),
        /* @__PURE__ */ jsx4("dd", { children: "Continuing" })
      ] })
    ] }),
    /* @__PURE__ */ jsx4("div", { className: "ls-actions", children: grant.status === "granted" ? /* @__PURE__ */ jsx4(Action, { danger: true, disabled: busy, onClick: () => onDecide(grant, "revoke"), children: "Revoke" }) : grant.status === "requested" ? /* @__PURE__ */ jsxs4(Fragment4, { children: [
      /* @__PURE__ */ jsx4(Action, { primary: true, disabled: busy, onClick: () => onDecide(grant, "grant"), children: "Approve" }),
      /* @__PURE__ */ jsx4(Action, { disabled: busy, onClick: () => onDecide(grant, "deny"), children: "Deny" })
    ] }) : /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: grant.status === "denied" ? `Denied. The Space shows \u201C${model.name} isn't available\u201D instead of prompting again.` : `${model.name} was revoked. Ask in chat to request access again.` }) })
  ] });
}
function PermissionsContent({ space, grants: all, audit = [], onDecide, busy = false, pending: pendingAction }) {
  const grants = all.filter((g) => g.capability === "net" || CAPABILITIES[g.capability]);
  const net = grants.find((g) => g.capability === "net");
  const pending = grants.filter((g) => g.capability !== "net" && g.status === "requested");
  const settled = grants.filter((g) => g.capability !== "net" && g.status !== "requested");
  return /* @__PURE__ */ jsxs4(Fragment4, { children: [
    net && /* @__PURE__ */ jsx4(InternetAccess, { grant: net, owner: space.owner, onDecide, busy, pending: pendingAction }),
    /* @__PURE__ */ jsxs4("section", { className: "ls-section", children: [
      /* @__PURE__ */ jsxs4("h2", { className: "ls-section-title", children: [
        "Granted to ",
        space.name
      ] }),
      settled.map((g) => /* @__PURE__ */ jsx4(GrantCard, { grant: g, onDecide, busy }, g.capability)),
      !settled.length && /* @__PURE__ */ jsx4("p", { children: "No grants approved yet." })
    ] }),
    /* @__PURE__ */ jsxs4("section", { className: "ls-section", children: [
      /* @__PURE__ */ jsx4("h2", { className: "ls-section-title", children: "Waiting for your decision" }),
      pending.map((g) => /* @__PURE__ */ jsx4(GrantCard, { grant: g, onDecide, busy }, g.capability)),
      !pending.length && /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: "Nothing waiting for your decision." })
    ] }),
    /* @__PURE__ */ jsxs4("section", { className: "ls-section", children: [
      /* @__PURE__ */ jsx4("h2", { className: "ls-section-title", children: "Your canvas and its bot" }),
      /* @__PURE__ */ jsxs4("p", { children: [
        "Ask ",
        space.owner,
        " in a normal Hermes chat to build or change this canvas, use connected tools, or bring in files. Bot actions follow Hermes's native rules, not extra per-site, per-tool or device permissions here."
      ] }),
      /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: "Canvas controls that ask their maintaining bot need a working native bot connection. This panel does not submit a bot request." })
    ] }),
    /* @__PURE__ */ jsxs4("section", { className: "ls-section", children: [
      /* @__PURE__ */ jsx4("h2", { className: "ls-section-title", children: "Owner" }),
      /* @__PURE__ */ jsx4(OwnerChip, { owner: space.owner }),
      /* @__PURE__ */ jsx4("h2", { className: "ls-section-title", children: "Audit" }),
      audit.length ? /* @__PURE__ */ jsx4("ul", { className: "ls-audit", children: audit.slice(0, 10).map((a) => /* @__PURE__ */ jsxs4("li", { children: [
        /* @__PURE__ */ jsx4(Time, { at: a.at }),
        " \xB7 ",
        a.actor,
        " \xB7 ",
        a.action,
        " ",
        a.capability || "",
        " \xB7 ",
        a.outcome
      ] }, a.id)) }) : /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: "No permission decisions recorded." })
    ] })
  ] });
}
function PermissionsSheet({ ctx, scopeKey = null, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id);
  const query = useQuery3({ queryKey: ["living-spaces", scopeKey, space.id, "grants"], queryFn: () => ctx.rest(`${base}/grants`), refetchInterval: 2e3 });
  const [revoke, setRevoke] = useState4(null);
  const [pending, setPending] = useState4(null);
  const busy = !!pending;
  const [feedback, setFeedback] = useState4("");
  const [error, setError] = useState4("");
  const lock = useRef3(false);
  async function decide(grant, decision) {
    if (decision === "revoke" && grant.capability !== "net") {
      setRevoke(grant);
      return;
    }
    await change(grant, `${base}/grants/${grant.capability}`, { decision, ...decision === "grant" ? { requested_scope: grant.requested_scope ?? grant.scope ?? {} } : {} });
  }
  async function change(grant, path, body) {
    if (lock.current) return;
    lock.current = true;
    setPending({ capability: grant.capability, decision: body.decision });
    setError("");
    setFeedback("");
    try {
      await ctx.rest(path, { method: "POST", body });
      const [current] = await Promise.all([query.refetch(), onChanged()]);
      if (current?.error) throw current.error;
      const state = current?.data?.grants?.find((item) => item.capability === grant.capability)?.status;
      if (current?.data && state !== { grant: "granted", revoke: "revoked", deny: "denied" }[body.decision]) throw new Error("Hermes has not confirmed the requested setting.");
      setFeedback(grant.capability === "net" ? body.decision === "deny" ? "Internet access request denied." : `Internet access turned ${body.decision === "grant" ? "on" : "off"} for ${space.name}.` : "Access updated.");
    } catch (e) {
      if ((e?.error || e?.body?.error || e)?.code === "conflict") setError("Permission request changed. Review the new request before approving.");
      else {
        const [current] = await Promise.all([query.refetch(), onChanged()]);
        const net = current?.data?.grants?.find((item) => item.capability === "net");
        const still = grant.capability === "net" && !current?.error && net ? ` It's ${net.status === "granted" ? "on" : "off"}.` : "";
        setError(`${grant.capability === "net" ? body.decision === "deny" ? "Couldn't deny the Internet access request. " : `Couldn't turn Internet access ${body.decision === "grant" ? "on" : "off"}. ` : ""}${errorText(e)}${still} Review the current setting before trying again.`);
        return;
      }
      await Promise.all([query.refetch(), onChanged()]);
    } finally {
      lock.current = false;
      setPending(null);
    }
  }
  return /* @__PURE__ */ jsxs4(Fragment4, { children: [
    /* @__PURE__ */ jsxs4(Drawer, { title: `Permissions \xB7 ${space.name}`, description: "Review this Space's access.", onClose, returnFocus, children: [
      error && /* @__PURE__ */ jsx4(Banner, { kind: "failed", title: error }),
      /* @__PURE__ */ jsx4("div", { role: "status", "aria-live": "polite", children: feedback }),
      query.error && query.data && /* @__PURE__ */ jsx4(Banner, { kind: "failed", title: "Showing the last loaded access settings. Controls are unavailable until Hermes responds.", actions: /* @__PURE__ */ jsx4(Action, { onClick: () => query.refetch(), children: "Try again" }), children: errorText(query.error) }),
      query.error && !query.data ? /* @__PURE__ */ jsx4(ErrorState3, { title: "Permissions could not be loaded", description: errorText(query.error), children: /* @__PURE__ */ jsx4(Action, { onClick: () => {
        query.refetch();
      }, children: "Try again" }) }) : query.isLoading ? /* @__PURE__ */ jsx4(Skeleton3, { style: { height: 180 } }) : /* @__PURE__ */ jsx4(PermissionsContent, { space, grants: query.data?.grants || [], audit: query.data?.audit || [], onDecide: decide, busy: busy || !!query.error, pending })
    ] }),
    revoke && /* @__PURE__ */ jsx4(DecisionDialog, { danger: true, title: `Revoke ${CAPABILITIES[revoke.capability].name} for ${space.name}?`, description: `The Space loses ${CAPABILITIES[revoke.capability].name.toLowerCase()} access. Data already delivered to the Space can't be recalled, and completed requests can't be undone.`, cancelLabel: "Keep access", confirmLabel: "Revoke", onClose: () => setRevoke(null), onConfirm: async () => {
      await ctx.rest(`${base}/grants/${revoke.capability}`, { method: "POST", body: { decision: "revoke" } });
      await query.refetch();
      await onChanged();
    } })
  ] });
}

// src/desktop/ui/upkeep.jsx
import { ErrorState as ErrorState4, Skeleton as Skeleton4, useQuery as useQuery4 } from "@hermes/plugin-sdk";
import { useEffect as useEffect2, useRef as useRef4, useState as useState5 } from "react";
import { Fragment as Fragment5, jsx as jsx5, jsxs as jsxs5 } from "react/jsx-runtime";
function UpkeepCost({ job, expanded = false, unavailable }) {
  if (job?.uses_model === false) return /* @__PURE__ */ jsx5("p", { children: "Refreshes from public sources. No model calls." });
  if (job?.uses_model !== true) return null;
  const prompt = unavailable ? job.prompt_preview : job.prompt;
  return /* @__PURE__ */ jsxs5("div", { className: "ls-upkeep-prompt", children: [
    prompt && /* @__PURE__ */ jsxs5(Fragment5, { children: [
      /* @__PURE__ */ jsx5("h3", { children: unavailable ? "Prompt preview" : "What Hermes does each run" }),
      /* @__PURE__ */ jsx5("p", { id: "ls-upkeep-prompt", className: expanded ? "" : "ls-clamp-six", children: prompt })
    ] }),
    unavailable && /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: unavailable }),
    /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: "Uses model calls." })
  ] });
}
function Executions({ executions, unavailable }) {
  if (unavailable) return /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: unavailable });
  if (!executions?.length) return /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: "No runs recorded yet." });
  return /* @__PURE__ */ jsx5("ul", { className: "ls-audit", "aria-label": "Upkeep executions", children: executions.map((run) => {
    const at = toSeconds(run.finished_at ?? run.started_at ?? run.claimed_at ?? run.scheduled_instant);
    return /* @__PURE__ */ jsxs5("li", { "data-status": run.status, children: [
      at != null && /* @__PURE__ */ jsxs5(Fragment5, { children: [
        /* @__PURE__ */ jsx5(Time, { at }),
        " \xB7 "
      ] }),
      /* @__PURE__ */ jsx5("strong", { children: executionLabel(run.status) }),
      run.error ? ` \xB7 ${run.error}` : ""
    ] }, run.id);
  }) });
}
var isRunning = (data) => data?.job?.state === "running" || data?.executions?.some((run) => ["running", "claimed"].includes(run.status)) === true;
function UpkeepSheet({ ctx, scopeKey = null, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id);
  const [busy, setBusy] = useState5(null);
  const [feedback, setFeedback] = useState5("");
  const [error, setError] = useState5("");
  const [confirm, setConfirm] = useState5(false);
  const [recentAction, setRecentAction] = useState5(0);
  const [slow, setSlow] = useState5(false);
  const [fullError, setFullError] = useState5(false);
  const [fullPrompt, setFullPrompt] = useState5(false);
  const [visible, setVisible] = useState5(() => typeof document === "undefined" || !document.hidden);
  const lock = useRef4(false);
  const feedbackNode = useRef4(null);
  const query = useQuery4({
    queryKey: ["living-spaces", scopeKey, space.id, "upkeep"],
    queryFn: () => ctx.rest(`${base}/upkeep`),
    refetchInterval: (native) => !visible ? false : isRunning(native.state?.data) || recentAction ? 2e3 : 5e3,
    refetchIntervalInBackground: false,
    notifyOnChangeProps: ["data", "error", "dataUpdatedAt"]
  });
  const data = query.data;
  const link = data?.link;
  const job = data?.job;
  const orphans = data?.orphan_jobs || [];
  const uncertain = !!data?.recovery;
  const aid = data?.recovery_aid?.settings;
  const hasRecovery = uncertain || orphans.length > 0 || !!data?.one_shots?.length;
  const ownedJobs = (state) => [state?.job, ...state?.orphan_jobs || [], ...state?.one_shots || []].filter(Boolean);
  const archived = space.status === "archived";
  const running = isRunning(data);
  const unavailable = !!data?.error || !!query.error || !!link && !job && !data?.missing;
  const blocked = archived || unavailable || !!busy;
  const cleanupBlocked = !data || unavailable || !!busy || archived && !hasRecovery;
  useEffect2(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  useEffect2(() => {
    if (data || query.error) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), 8e3);
    return () => clearTimeout(timer);
  }, [!!data, !!query.error]);
  useEffect2(() => {
    if (!recentAction) return;
    const timer = setTimeout(() => setRecentAction(0), 6e4);
    return () => clearTimeout(timer);
  }, [recentAction]);
  useEffect2(() => {
    if (!feedback || busy) return;
    const timer = setTimeout(() => setFeedback(""), 8e3);
    return () => clearTimeout(timer);
  }, [feedback, busy]);
  async function act(action) {
    if (lock.current) return;
    if ((["pause", "remove", "recover"].includes(action) ? cleanupBlocked : blocked || uncertain) || action === "run" && running) {
      if (["remove", "recover"].includes(action)) throw new Error("Upkeep is unavailable. Reload the native state before removing it.");
      return;
    }
    lock.current = true;
    let refreshRequested = false;
    setBusy(action);
    setError("");
    setFeedback(action === "run" ? "Starting\u2026" : "Working\u2026");
    setRecentAction(Date.now());
    try {
      const response = await ctx.rest(`${base}/upkeep`, { method: "POST", body: { action, ...action === "recover" ? { confirm: space.id } : {} } });
      if (action === "run" && response?.dispatch?.job?.execution_success === false) throw new Error(response.dispatch.job.execution_error || "Hermes reports that this execution failed.");
      refreshRequested = true;
      const [current] = await Promise.all([query.refetch(), onChanged?.()]);
      if (current?.error || current?.data?.error) throw new Error(`The action was submitted, but the current native state couldn't be loaded. ${errorText(current.error || current.data.error)}`);
      if (!current?.data || response?.error) throw new Error("Hermes has not confirmed the requested state.");
      const currentJobs = ownedJobs(current.data);
      const returnedJobs = ownedJobs(response);
      if (action === "pause" && (currentJobs.some((target) => target.enabled !== false) || returnedJobs.some((target) => target.enabled !== false) || [...ownedJobs(data), ...returnedJobs].some((target) => !currentJobs.some((job2) => job2.id === target.id && job2.enabled === false))) || action === "resume" && current.data.job?.enabled !== true || ["remove", "recover"].includes(action) && (current.data.link || response?.link || currentJobs.length || returnedJobs.length) || action === "recover" && (current.data.recovery || response?.recovery)) throw new Error("Hermes has not confirmed the requested state.");
      const next = toSeconds(current?.data?.job?.next_run_at);
      setFeedback(action === "recover" ? "Recovery verified. Native upkeep jobs are absent. No run was replayed. Use the settings aid for a separate scheduling request." : action === "pause" && current.data.recovery ? "Native jobs are paused. The earlier action remains uncertain. Confirm recovery to clear the barrier." : action === "run" ? "Run requested. Execution and delivery are not confirmed by this request; review the last-result metadata below." : action === "pause" ? "Paused. Future runs stop until you resume. Already-running work may finish." : action === "resume" ? `Resumed.${next != null ? ` Next run ${absolute(next)}.` : ""}` : `Upkeep removed. ${space.name} is unchanged.`);
    } catch (e) {
      setFeedback("");
      setError(`${action === "run" ? "Couldn't start the run." : action === "pause" ? "Couldn't pause upkeep." : action === "resume" ? "Couldn't resume upkeep." : "Couldn't remove upkeep."} ${errorText(e)} Review the current native state before trying again.`);
      if (!refreshRequested) await query.refetch();
      if (["remove", "recover"].includes(action)) throw e;
    } finally {
      lock.current = false;
      setBusy(null);
    }
  }
  const removeButton = /* @__PURE__ */ jsx5(Action, { danger: true, "aria-disabled": cleanupBlocked, onClick: () => !cleanupBlocked && setConfirm(true), children: data?.missing && !hasRecovery ? "Remove link" : "Remove" });
  const ask = /* @__PURE__ */ jsx5(CopyPrompt, { text: `${space.owner}, schedule upkeep for ${space.name}. Please confirm the cadence and timezone, then create it as a Hermes cron job.`, label: "Copy prompt" });
  const lastAt = toSeconds(job?.last_run_at);
  const lastResult = running ? "Running now\u2026" : job?.last_status ? executionLabel(["ok", "success"].includes(job.last_status) ? "succeeded" : job.last_status === "error" ? "failed" : job.last_status) : null;
  let body;
  if (query.error && !data) body = /* @__PURE__ */ jsx5(ErrorState4, { title: "Upkeep couldn't be loaded", description: `Hermes didn't respond. ${errorText(query.error)}`, children: /* @__PURE__ */ jsx5(Action, { onClick: () => query.refetch(), children: "Try again" }) });
  else if (!data) body = /* @__PURE__ */ jsxs5("div", { "aria-busy": "true", "aria-label": "Loading upkeep", children: [
    /* @__PURE__ */ jsx5(Skeleton4, { style: { width: 80, height: 24 } }),
    [1, 2, 3].map((row) => /* @__PURE__ */ jsx5(Skeleton4, { style: { height: 32, marginTop: 12 } }, row)),
    /* @__PURE__ */ jsx5(Skeleton4, { style: { height: 32, marginTop: 20 } }),
    /* @__PURE__ */ jsx5("p", { role: "status", children: slow ? "Still waiting for Hermes\u2026" : "Loading upkeep\u2026" })
  ] });
  else body = /* @__PURE__ */ jsxs5(Fragment5, { children: [
    query.error && /* @__PURE__ */ jsx5(Banner, { title: `Showing the last loaded state${query.dataUpdatedAt ? ` from ${relative(query.dataUpdatedAt / 1e3)}` : ""}.`, actions: /* @__PURE__ */ jsx5(Action, { onClick: () => query.refetch(), children: "Try again" }), children: errorText(query.error) }),
    data.error && /* @__PURE__ */ jsx5(Banner, { kind: "failed", title: "Hermes cron is unavailable", children: errorText(data.error) }),
    data.warning && /* @__PURE__ */ jsx5(Banner, { kind: "blocked", title: "Hermes cron notice", children: data.warning }),
    aid && /* @__PURE__ */ jsxs5("section", { className: "ls-section", "aria-label": "Recovery settings aid", children: [
      /* @__PURE__ */ jsx5("h3", { children: "Recovery settings aid" }),
      /* @__PURE__ */ jsx5("p", { children: "Last requested settings only. These do not describe the current native schedule or enabled state. Hermes cron remains authoritative." }),
      /* @__PURE__ */ jsx5("dl", { className: "ls-facts", children: ["kind", "cadence", "timezone", "prompt"].map((key) => /* @__PURE__ */ jsxs5("div", { children: [
        /* @__PURE__ */ jsx5("dt", { children: key }),
        /* @__PURE__ */ jsx5("dd", { children: aid[key] ?? "None" })
      ] }, key)) }),
      /* @__PURE__ */ jsx5(CopyPrompt, { text: `${space.owner}, review these last requested upkeep settings for ${space.name} and confirm before scheduling again: ${JSON.stringify(aid)}`, label: "Copy recovery settings" })
    ] }),
    archived && /* @__PURE__ */ jsxs5("p", { children: [
      "Run and Resume are unavailable while this Space is archived. ",
      hasRecovery && "Use Pause or Remove to clean up recovery jobs. ",
      "Already-running work may finish."
    ] }),
    uncertain ? /* @__PURE__ */ jsxs5(Banner, { kind: "blocked", title: "Upkeep outcome unknown", children: [
      /* @__PURE__ */ jsx5("p", { children: data.recovery.cause }),
      /* @__PURE__ */ jsxs5("p", { children: [
        "Uncertain action: ",
        data.recovery.operations.map((op) => op.action).join(", ")
      ] }),
      /* @__PURE__ */ jsx5("p", { children: data.recovery.options }),
      /* @__PURE__ */ jsx5("p", { children: data.recovery.evidence }),
      job && /* @__PURE__ */ jsxs5("p", { children: [
        "Native inventory currently shows job ",
        /* @__PURE__ */ jsx5("code", { children: job.id }),
        ", ",
        job.enabled === true ? "enabled" : job.enabled === false ? "disabled" : "enabled state unknown",
        ". This does not confirm the earlier effect."
      ] }),
      /* @__PURE__ */ jsx5(Action, { primary: true, "aria-disabled": cleanupBlocked, onClick: () => !cleanupBlocked && setConfirm("recover"), children: "Recover upkeep" })
    ] }) : !link ? hasRecovery ? /* @__PURE__ */ jsx5(Banner, { kind: "blocked", title: "No primary upkeep link", children: "Space-owned jobs below may still run. Pause or remove them before scheduling upkeep again." }) : /* @__PURE__ */ jsxs5(Fragment5, { children: [
      /* @__PURE__ */ jsx5("h3", { children: "No upkeep yet" }),
      /* @__PURE__ */ jsxs5("p", { children: [
        "This Space isn't updated automatically. Ask ",
        space.owner,
        " in chat to set up upkeep as a Hermes cron job."
      ] }),
      ask
    ] }) : data.missing ? /* @__PURE__ */ jsxs5(Fragment5, { children: [
      /* @__PURE__ */ jsx5(StatusPill, { status: "blocked", label: "Job missing" }),
      /* @__PURE__ */ jsx5(Banner, { kind: "blocked", title: "Hermes no longer has this job", actions: removeButton, children: hasRecovery ? "Other Space-owned jobs below may still run. Pause or remove them before scheduling upkeep again." : `Nothing will run. Ask ${space.owner} in chat to schedule upkeep again.` }),
      !hasRecovery && ask
    ] }) : job ? /* @__PURE__ */ jsxs5(Fragment5, { children: [
      /* @__PURE__ */ jsx5(StatusPill, { status: running ? "running" : !job.enabled ? "paused" : data.gateway_running === false ? "blocked" : "ready", label: running ? "Running now" : !job.enabled ? "Paused" : data.gateway_running === false ? "Scheduler offline" : "Active" }),
      /* @__PURE__ */ jsx5(UpkeepCost, { job, expanded: fullPrompt, unavailable: data.unavailable?.prompt }),
      /* @__PURE__ */ jsxs5("dl", { className: "ls-facts", children: [
        (job.schedule_display || job.cadence || job.timezone) && /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Runs" }),
          /* @__PURE__ */ jsxs5("dd", { children: [
            job.schedule_display || job.cadence,
            job.timezone && /* @__PURE__ */ jsx5("div", { className: "ls-secondary", children: job.timezone })
          ] })
        ] }),
        data.unavailable?.timezone && /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Timezone" }),
          /* @__PURE__ */ jsx5("dd", { children: data.unavailable.timezone })
        ] }),
        /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Next run" }),
          /* @__PURE__ */ jsx5("dd", { children: !job.enabled ? "Paused. Future runs stop until resumed. Already-running work may finish." : toSeconds(job.next_run_at) != null ? /* @__PURE__ */ jsxs5(Fragment5, { children: [
            /* @__PURE__ */ jsx5(Time, { at: toSeconds(job.next_run_at) }),
            " \xB7 ",
            /* @__PURE__ */ jsx5(Time, { at: toSeconds(job.next_run_at), relative: true })
          ] }) : "Waiting for Hermes to schedule it" })
        ] }),
        (lastResult || lastAt == null) && /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Last result" }),
          /* @__PURE__ */ jsxs5("dd", { children: [
            lastResult || (data.unavailable?.executions ? "No last-result metadata available" : "Hasn't run yet"),
            !running && lastAt != null && /* @__PURE__ */ jsxs5(Fragment5, { children: [
              " \xB7 ",
              /* @__PURE__ */ jsx5(Time, { at: lastAt })
            ] })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsx5("p", { className: "ls-upkeep-note ls-secondary", children: CATCH_UP }),
      /* @__PURE__ */ jsxs5("div", { className: "ls-actions ls-upkeep-actions", children: [
        /* @__PURE__ */ jsx5(Action, { "aria-busy": busy === "run", "aria-disabled": blocked || running, title: running ? "Already running" : void 0, icon: "run", onClick: () => act("run"), children: "Run now" }),
        /* @__PURE__ */ jsx5(Action, { primary: !job.enabled, "aria-busy": busy === (job.enabled ? "pause" : "resume"), "aria-disabled": job.enabled ? cleanupBlocked : blocked, icon: job.enabled ? "debug-pause" : "play", onClick: () => act(job.enabled ? "pause" : "resume"), children: job.enabled ? "Pause" : "Resume" }),
        removeButton
      ] })
    ] }) : !data.error && /* @__PURE__ */ jsx5(Banner, { kind: "blocked", title: "Waiting for the native job state", actions: /* @__PURE__ */ jsx5(Action, { onClick: () => query.refetch(), children: "Try again" }), children: "Controls are unavailable until Hermes responds." })
  ] });
  return /* @__PURE__ */ jsxs5(Fragment5, { children: [
    /* @__PURE__ */ jsxs5(Drawer, { title: `Upkeep \xB7 ${space.name}`, description: "The Hermes cron job that keeps this Space current", onClose, returnFocus, children: [
      body,
      !!orphans.length && /* @__PURE__ */ jsxs5("section", { className: "ls-section", "data-testid": "orphan-jobs", children: [
        /* @__PURE__ */ jsx5("h3", { className: "ls-section-title", children: "Unlinked upkeep jobs" }),
        /* @__PURE__ */ jsx5("p", { children: "These native jobs belong to this Space but are not its primary upkeep link. Enabled jobs may run, including duplicate upkeep." }),
        /* @__PURE__ */ jsx5("ul", { className: "ls-audit", children: orphans.map((orphan) => /* @__PURE__ */ jsxs5("li", { children: [
          /* @__PURE__ */ jsx5("code", { children: orphan.id }),
          " \xB7 ",
          orphan.state || "Unknown native state",
          " \xB7 ",
          orphan.enabled === true ? "Enabled" : orphan.enabled === false ? "Disabled" : "Enabled state unknown"
        ] }, orphan.id)) })
      ] }),
      hasRecovery && /* @__PURE__ */ jsxs5("div", { className: "ls-actions ls-upkeep-actions", children: [
        /* @__PURE__ */ jsx5(Action, { "aria-busy": busy === "pause", "aria-disabled": cleanupBlocked, icon: "debug-pause", onClick: () => act("pause"), children: "Pause" }),
        removeButton
      ] }),
      /* @__PURE__ */ jsx5("div", { ref: feedbackNode, tabIndex: -1, role: "status", "aria-live": "polite", className: "ls-upkeep-feedback", children: feedback }),
      error && /* @__PURE__ */ jsx5(Banner, { kind: "failed", title: error }),
      job?.uses_model === true && job.prompt && !data?.unavailable?.prompt && /* @__PURE__ */ jsx5("div", { className: "ls-section", children: /* @__PURE__ */ jsx5(Action, { "aria-expanded": fullPrompt, "aria-controls": "ls-upkeep-prompt", onClick: () => setFullPrompt(!fullPrompt), children: fullPrompt ? "Show less" : "Show full prompt" }) }),
      job?.last_error && ["failed", "error"].includes(job.last_status) && /* @__PURE__ */ jsxs5(Banner, { kind: "failed", title: `Last run failed${lastAt != null ? ` ${absolute(lastAt)}` : ""}`, actions: /* @__PURE__ */ jsxs5(Fragment5, { children: [
        !uncertain && /* @__PURE__ */ jsx5(Action, { "aria-disabled": blocked || running, onClick: () => act("run"), children: "Run now" }),
        !data?.unavailable?.executions && /* @__PURE__ */ jsx5(Action, { onClick: () => document.getElementById("ls-upkeep-executions")?.focus(), children: "View history" })
      ] }), children: [
        /* @__PURE__ */ jsx5("p", { id: "ls-upkeep-error", className: fullError ? "" : "ls-clamp-three", children: job.last_error }),
        /* @__PURE__ */ jsx5(Action, { "aria-expanded": fullError, "aria-controls": "ls-upkeep-error", onClick: () => setFullError(!fullError), children: fullError ? "Show less" : "Show more" })
      ] }),
      link && /* @__PURE__ */ jsxs5("section", { className: "ls-section", id: "ls-upkeep-executions", tabIndex: -1, children: [
        /* @__PURE__ */ jsx5("h3", { className: "ls-section-title", children: "Executions" }),
        /* @__PURE__ */ jsx5(Executions, { executions: data.executions, unavailable: data.unavailable?.executions }),
        data.unavailable?.dispatch && /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: data.unavailable.dispatch })
      ] }),
      !!data?.one_shots?.length && /* @__PURE__ */ jsxs5("section", { className: "ls-section", "data-testid": "one-shots", children: [
        /* @__PURE__ */ jsx5("h3", { className: "ls-section-title", children: data.unavailable?.executions ? "Refresh now jobs" : "Refresh now runs" }),
        /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: "One-time Hermes jobs requested with Refresh now. Each uses model calls. A saved job is not proof that it ran." }),
        /* @__PURE__ */ jsx5(Executions, { executions: data.one_shots.flatMap((shot) => shot.executions || []), unavailable: data.unavailable?.executions })
      ] })
    ] }),
    confirm && /* @__PURE__ */ jsx5(DecisionDialog, { danger: true, successFocus: feedbackNode, title: `${confirm === "recover" ? "Recover" : "Remove"} upkeep for ${space.name}?`, description: `This checks native state and deletes this Space's linked job, unlinked upkeep jobs and Refresh now jobs. Future runs stop, but already-running work may finish. The Space and its data are kept. ${confirm === "recover" ? "No run will be replayed. Settings remain an aid for a separate scheduling request." : ""}`, cancelLabel: "Keep upkeep", confirmLabel: confirm === "recover" ? "Confirm recovery" : "Remove", onClose: () => setConfirm(false), onConfirm: () => act(confirm === "recover" ? "recover" : "remove") })
  ] });
}

// src/desktop/ui/actions.mjs
var routeFields = ["connectionId", "profile", "targetProfile", "mode"];
var sameRoute = (a, b) => routeFields.every((key) => a?.[key] === b?.[key]);
var publicStatus = (action, status, message, answer) => ({ activationId: action?.activation_id, status, message, ...answer ? { answer } : {} });
var failure = (message, status = "failed") => Object.assign(new Error(message), { actionStatus: status });
var refusalReasons = /* @__PURE__ */ new Set(["permission_denied", "invalid_params", "not_found", "profile_mismatch", "queue_full", "runtime_draining"]);
async function profileRoute(host5, backend, expected) {
  if (!backend || typeof backend.profile !== "string" || !backend.profile || backend.connectionId != null && (typeof backend.connectionId !== "string" || !backend.connectionId) || typeof host5?.profileRoutes !== "function" || typeof host5?.requestProfile !== "function") {
    throw failure("Native profile routing is unavailable in this Desktop", "offline");
  }
  const routes = await host5.profileRoutes();
  const matches = routes.filter((route) => route.profile === backend.profile && (backend.connectionId == null ? route.primary === true : route.connectionId === backend.connectionId) && (!expected || sameRoute(route, expected)));
  if (matches.length !== 1 || routeFields.some((key) => typeof matches[0][key] !== "string" || !matches[0][key])) {
    throw failure("The exact maintaining profile route is unavailable or ambiguous", "offline");
  }
  return matches[0];
}
function createBotActions({ host: host5, backend, post, onStatus, isActive, userActivation = () => globalThis.navigator?.userActivation?.isActive === true }) {
  let current = null;
  let binding = null;
  let release = null;
  let heldRoute = null;
  let timer = null;
  let closed = false;
  let requestInFlight = null;
  let chain = Promise.resolve();
  const alive = () => {
    if (closed || !isActive()) throw failure("This Space view is closed", "unknown");
  };
  const publish = (value) => {
    if (!closed && isActive()) onStatus(value);
    return value;
  };
  const serial = (work) => {
    const next = chain.then(work);
    chain = next.catch(() => {
    });
    return next;
  };
  async function registered(expected) {
    alive();
    if (typeof host5?.retainProfile !== "function") throw failure("Native profile routing is unavailable in this Desktop", "offline");
    const route = await profileRoute(host5, backend, expected);
    alive();
    return route;
  }
  async function rpc(route, method, params = {}) {
    const fresh = await registered(route);
    alive();
    const value = await host5.requestProfile(fresh, method, params).catch((error) => {
      const reason = error?.data?.reason;
      if (method === "prompt.submit" && refusalReasons.has(reason)) {
        throw Object.assign(failure(`Native request refused: ${reason}`), { refusalReason: reason });
      }
      if (["permission_denied", "invalid_params", "not_found", "profile_mismatch"].includes(reason)) {
        throw failure(`Native request refused: ${reason}`);
      }
      if (reason === "admission_conflict") throw failure("Native admission identity is conflicted; admission may already exist", "unknown");
      if (reason === "runtime_draining") throw failure("The native runtime is busy shutting down", "busy");
      throw error;
    });
    alive();
    return value;
  }
  async function connect(target) {
    const route = await registered(target?.route);
    if (!heldRoute || !sameRoute(route, heldRoute)) {
      release?.();
      release = null;
      heldRoute = null;
      const lease = await host5.retainProfile(route, { spawnPriority: "foreground" });
      if (closed || !isActive()) {
        lease();
        alive();
      }
      release = lease;
      heldRoute = route;
    }
    const identity = await rpc(route, "runtime.describe");
    if (identity.profile_id !== binding.profile_id || !identity.capabilities?.includes("durable-admission-v1")) {
      throw failure("Native profile identity does not match this Space\u2019s maintaining bot");
    }
    return route;
  }
  async function context(activationId) {
    alive();
    const value = await post("context", activationId ? { activation_id: activationId } : {});
    alive();
    binding = value.maintainer;
    return value.action;
  }
  function validateReceipt(receipt) {
    if (!receipt || typeof receipt.admission_id !== "string" || !receipt.admission_id || receipt.ref?.profile_id !== current.target.profile_id || receipt.ref?.session_id !== current.target.session_id || current.admission_id && receipt.admission_id !== current.admission_id || !["queued", "started", "unknown", "terminal"].includes(receipt.status)) {
      throw failure("Native admission outcome could not be correlated", "unknown");
    }
  }
  async function observe(receipt) {
    validateReceipt(receipt);
    current.admission_id = receipt.admission_id;
    const recorded = await post("observe", { activation_id: current.activation_id, receipt: {
      admission_id: receipt.admission_id,
      ref: receipt.ref,
      status: receipt.status,
      outcome: receipt.outcome
    } });
    alive();
    const settled = recorded.settled && receipt.status === "terminal";
    current.settled = settled;
    let status = { queued: "queued", started: "busy", unknown: "unknown" }[receipt.status] || "unknown";
    let message = { queued: "Queued for the maintaining bot. Uses model calls.", busy: "The maintaining bot is working.", unknown: "Native outcome is unknown. No automatic resend." }[status];
    let answer;
    if (settled) {
      status = receipt.outcome === "completed" ? "completed" : "failed";
      message = status === "completed" ? "The maintaining bot completed this request." : `Native request ${receipt.outcome}.`;
      const text = receipt.result?.final_response;
      if (typeof text === "string") {
        if (new TextEncoder().encode(text).length <= 16384) answer = text;
        else message += " The answer exceeds the 16 KiB canvas display limit; read it in the native conversation.";
      }
      release?.();
      release = null;
      heldRoute = null;
    }
    const value = publish(publicStatus(current, status, message, answer));
    if (!settled && status !== "unknown") schedule();
    return value;
  }
  function schedule() {
    clearTimeout(timer);
    if (!closed) timer = setTimeout(() => {
      serial(check).catch(report);
    }, 2e3);
  }
  function report(error) {
    release?.();
    release = null;
    heldRoute = null;
    const status = error.actionStatus || (current ? "unknown" : "offline");
    return publish(publicStatus(current, status, `${error.message || "Native request unavailable"}. No automatic resend.`));
  }
  async function attach(route, sessionId) {
    const resumed = await rpc(route, "session.resume", { session_id: sessionId, omit_messages: true });
    if (typeof resumed.session_id !== "string" || !resumed.session_id || resumed.session_id !== resumed.stored_session_id) {
      throw failure("This native session does not provide canonical durable admission");
    }
    return resumed;
  }
  async function check() {
    clearTimeout(timer);
    current = await context(current?.activation_id);
    if (!current) return null;
    if (current.refusal_reason) return publish(publicStatus(current, "failed", `Native request refused: ${current.refusal_reason}. No request was admitted.`));
    const route = await connect(current.target);
    const resumed = await attach(route, current.target.session_id);
    if (resumed.session_id !== current.target.session_id) throw failure("The native activation target changed", "unknown");
    if (!current.admission_id) {
      const pending = resumed.pending?.find((item) => item.input_id === current.input_id);
      if (!pending) return publish(publicStatus(current, "unknown", "Admission was not observed. Check again or explicitly retry this same request."));
      await observe(pending);
    }
    const receipt = await rpc(route, "prompt.receipt", { session_id: current.target.session_id, admission_id: current.admission_id, include_result: true });
    return observe(receipt);
  }
  async function submit(route, attempt) {
    const identity = await rpc(route, "runtime.describe");
    if (identity.profile_id !== current.target.profile_id) throw failure("Maintaining profile changed before submission", "unknown");
    alive();
    publish(publicStatus(current, "submitted", "Requesting native admission. Uses model calls."));
    let receipt;
    try {
      receipt = await rpc(route, "prompt.submit", {
        session_id: current.target.session_id,
        input_id: current.input_id,
        text: current.text
      });
    } catch (error) {
      if (!error.refusalReason) throw error;
      alive();
      if (attempt === "retry") throw failure(`${error.message}. The earlier admission remains unknown`, "unknown");
      try {
        const recorded = await post("reject", {
          activation_id: current.activation_id,
          input_id: current.input_id,
          reason: error.refusalReason
        });
        alive();
        if (!recorded.recorded || !recorded.settled || !recorded.action?.settled || recorded.action.activation_id !== current.activation_id || recorded.action.input_id !== current.input_id || recorded.action.admission_id !== null || recorded.action.refusal_reason !== error.refusalReason) {
          throw new Error("The refusal record did not match this activation");
        }
        current = recorded.action;
      } catch (persistenceError) {
        throw failure(`${error.message}. Refusal persistence could not be confirmed: ${persistenceError.message}`);
      }
      throw error;
    }
    return observe(receipt);
  }
  return {
    // The maintainer's stored chat session, for the host's Continue in chat; never sent to the guest.
    sessionId: () => binding?.stored_session_id || null,
    restore: () => serial(check).catch(report),
    check: () => serial(check).catch(report),
    request(args) {
      if (!userActivation()) return Promise.resolve(publish(publicStatus(null, "failed", "Bot requests need a current user activation. No request was sent.")));
      const payload = JSON.stringify({ text: args.text, records: args.records || [] }, ["text", "records", "collection", "id"]);
      if (requestInFlight) {
        const conflict = requestInFlight.activationId === args.activation_id && requestInFlight.payload !== payload;
        return Promise.resolve(publish(publicStatus(args, conflict ? "failed" : "busy", conflict ? "This activation ID already belongs to a different request. No request was sent." : "An earlier request is already being handled. This activation did not send a new request.")));
      }
      requestInFlight = { activationId: args.activation_id, payload };
      return serial(async () => {
        clearTimeout(timer);
        current = await context();
        const route = await connect(current?.target);
        const resumed = await attach(route, current?.target.session_id || binding.stored_session_id);
        if (current && resumed.session_id !== current.target.session_id) throw failure("The native activation target changed", "unknown");
        const target = current?.target || { route: Object.fromEntries(routeFields.map((key) => [key, route[key]])), profile_id: binding.profile_id, session_id: resumed.session_id };
        const claim = await post("claim", { ...args, records: args.records || [], target }).catch((error) => {
          throw failure(error.message || "The activation was rejected");
        });
        alive();
        current = claim.action;
        if (!claim.dispatch) {
          const status = await check();
          return claim.coalesced ? publish({ ...status, message: `An earlier request is already pending or finished. This activation did not send a new request. ${status.message}` }) : status;
        }
        return submit(route, "initial");
      }).catch(report).finally(() => {
        requestInFlight = null;
      });
    },
    retry() {
      if (!userActivation()) return Promise.resolve(publish(publicStatus(current, "failed", "Activate Retry to request native admission again.")));
      return serial(async () => {
        const status = await check();
        if (!current || current.admission_id || current.settled) return status;
        const route = await connect(current.target);
        return submit(route, "retry");
      }).catch(report);
    },
    destroy() {
      closed = true;
      clearTimeout(timer);
      release?.();
      release = null;
      heldRoute = null;
    }
  };
}

// src/desktop/sandbox/index.js
var BRIDGE_VERSION = 1;
var OP_GRANT = Object.freeze({
  meta: null,
  "net.fetch": "net",
  "data.query": "data",
  "data.get": "data",
  "data.put": "data",
  "data.delete": "data",
  "data.batch": "data",
  "draft.get": "data",
  "draft.put": "data",
  "draft.delete": "data",
  "editor.save": "data",
  "outcome.get": "data",
  "bot.request": null,
  "link.open": null,
  refresh: null,
  "runs.list": null,
  freshness: null,
  log: "logs"
});
var MAX_REQUEST_SIZE = 1024 * 1024;
var MAX_LINK_LENGTH = 2048;
var SECRET_PARAM = /^(access_token|id_token|refresh_token|token|api[-_]?key|apikey|secret|client_secret|password|passwd|pwd|auth|authorization|sessionid|sig|signature|x-amz-signature|x-amz-credential|x-amz-security-token|x-goog-signature|x-goog-credential)$/i;
function linkTarget(value) {
  const refuse = (reason) => ({ ok: false, reason });
  if (typeof value !== "string" || !value) return refuse("The link has no destination");
  if (value.length > MAX_LINK_LENGTH) return refuse(`Links longer than ${MAX_LINK_LENGTH} characters are not opened`);
  if (/[\s\x00-\x1f\x7f]/.test(value)) return refuse("The link contains spaces or control characters");
  let url;
  try {
    url = new URL(value);
  } catch {
    return refuse("The link is not a complete web address");
  }
  if (url.protocol !== "https:") return refuse("Only https links can be opened");
  if (url.username || url.password) return refuse("Links containing sign-in details are not opened");
  const host5 = url.hostname;
  const labels = host5.split(".");
  if (labels.length < 2 || !labels.every(Boolean) || host5.startsWith("[") || /^[\d.]+$/.test(host5) || /(^|\.)(localhost|local|internal|home\.arpa)$/i.test(host5)) {
    return refuse("Only public website addresses can be opened");
  }
  const keys = [...url.searchParams.keys(), ...[...url.hash.matchAll(/(?:^#|[?&;/])([^=?&;/#]+)=/g)].map((match) => match[1])];
  if (keys.some((key) => {
    try {
      return SECRET_PARAM.test(decodeURIComponent(key));
    } catch {
      return true;
    }
  })) {
    return refuse("Links carrying access tokens or signatures are not opened");
  }
  return { ok: true, url: url.href, host: host5 };
}
function requestError(message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) return { code: "invalid", message: "request must be an object" };
  if (message.v !== BRIDGE_VERSION) return { code: "invalid", message: "unsupported bridge version" };
  if (!Number.isSafeInteger(message.id)) return { code: "invalid", message: "id must be an integer" };
  if (typeof message.op !== "string") return { code: "invalid", message: "op must be a string" };
  if (message.op === "editor.save" && (typeof message.request_id !== "string" || !/^[A-Za-z0-9_.:-]{1,128}$/.test(message.request_id))) return { code: "invalid", message: "Editor saves require a request_id" };
  if (!message.args || typeof message.args !== "object" || Array.isArray(message.args)) return { code: "invalid", message: "args must be an object" };
  try {
    const actual = new TextEncoder().encode(JSON.stringify(message)).byteLength;
    if (actual > MAX_REQUEST_SIZE) return { code: "limit", message: "request exceeds 1 MB", limit: MAX_REQUEST_SIZE, actual };
  } catch {
    return { code: "invalid", message: "request is not JSON serializable" };
  }
  return null;
}
function checkGrant(op, grants) {
  if (!Object.hasOwn(OP_GRANT, op)) return { code: "not_granted", message: `Operation isn't available: ${op}` };
  const capability = OP_GRANT[op];
  if (capability === null) return null;
  if (grants.some((g) => typeof g === "string" ? g === capability : g.capability === capability && g.status === "granted")) return null;
  return { code: "not_granted", message: `Approve ${capability} in Permissions`, capability };
}
function parseBundle(value) {
  const sandbox = value?.sandbox;
  if (!sandbox || typeof sandbox !== "object" || Array.isArray(sandbox) || Object.keys(sandbox).length !== 2 || !Object.hasOwn(sandbox, "format") || !Object.hasOwn(sandbox, "shell_srcdoc") || sandbox.format !== 1 || typeof sandbox.shell_srcdoc !== "string" || !sandbox.shell_srcdoc.trim()) {
    throw new Error("Living Spaces Desktop and backend are incompatible. Reinstall Living Spaces to load the packaged sandbox.");
  }
  const { space, rev, manifest, files } = value;
  return { project: { space, rev, manifest, files }, document: sandbox.shell_srcdoc };
}
function mountSpace(container, { bundle, grants = [], call, onEvent = () => {
} }) {
  const { project, document: shellDocument } = parseBundle(bundle);
  const channel = new MessageChannel();
  const port = channel.port1;
  let frame;
  let state = "created";
  let lastLog = -Infinity;
  let overflowReported = false;
  let faults = 0;
  let snapshotId = 0;
  const snapshots = /* @__PURE__ */ new Map();
  const overflow = () => {
    if (overflowReported) return;
    overflowReported = true;
    onEvent({ kind: "log-overflow" });
  };
  const stop = () => {
    if (state === "closed") return;
    state = "closed";
    for (const settle of snapshots.values()) settle(null);
    frame?.removeEventListener("load", onLoad);
    port.onmessage = null;
    port.close();
    channel.port2.close();
    window.removeEventListener("message", onShellMessage);
  };
  const reloaded = () => {
    if (state !== "booted") return;
    stop();
    onEvent({ kind: "reloaded" });
  };
  function onShellMessage(e) {
    if (e.source === frame.contentWindow && e.data?.v === 1 && e.data.type === "space-reloaded") reloaded();
  }
  function onLoad() {
    if (state === "closed") return;
    if (state === "booted") return reloaded();
    state = "booted";
    frame.contentWindow.postMessage({ type: "space-boot", v: 1, bundle: project, grants }, "*", [channel.port2]);
    onEvent({ kind: "booted" });
  }
  port.onmessage = async (e) => {
    if (state !== "booted") return;
    const m = e.data;
    if (m?.type === "snapshot") {
      const settle = snapshots.get(m.id);
      if (!settle) return;
      const valid = !Array.isArray(m) && m.v === 1 && m.ok === true && typeof m.image === "string" && m.image.length <= 35e4 && /^data:image\/(?:webp|png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/.test(m.image) && [m.width, m.height].every((size) => Number.isInteger(size) && size >= 16 && size <= 1024);
      settle(valid ? { image: m.image, width: m.width, height: m.height } : null);
      return;
    }
    const reply = (body) => {
      if (state === "booted" && Number.isSafeInteger(m?.id)) port.postMessage({ v: 1, id: m.id, ...body });
    };
    const reject = (error) => {
      const op = typeof m?.op === "string" ? m.op : null;
      onEvent({ kind: "denied", op, reason: error.message });
      if (["data.put", "data.delete", "data.batch"].includes(op)) onEvent({ kind: "write-rejected", op, error });
      reply({ ok: false, error });
    };
    const invalid = requestError(m);
    if (invalid) return reject(invalid);
    const denied = checkGrant(m.op, grants);
    if (denied) return reject(denied);
    let args = m.args;
    if (m.op === "log") {
      if (args.lifecycle !== void 0 && !["loaded", "failed"].includes(args.lifecycle) || ["dropped", "unconfirmed", "faults"].some((key) => args[key] !== void 0 && (!Number.isSafeInteger(args[key]) || args[key] < 0))) {
        return reject({ code: "invalid", message: "Invalid log metadata" });
      }
      if (!Array.isArray(args.entries) || Array.from(args.entries).some((entry) => !entry || typeof entry.level !== "string" || typeof entry.msg !== "string")) {
        return reject({ code: "invalid", message: "Invalid log entries" });
      }
      if (args.entries.length > 50) return reject({ code: "limit", message: "Log batch exceeds 50 entries", limit: 50, actual: args.entries.length });
      const oversized = args.entries.find((entry) => entry.msg.length > 4e3);
      if (oversized) return reject({ code: "limit", message: "Log message exceeds 4000 characters", limit: 4e3, actual: oversized.msg.length });
      if (args.entries.some((entry) => entry.level === "warn" && entry.msg.startsWith("Space log overflow:"))) overflow();
      const now = performance.now();
      if (now - lastLog < 500) {
        reply({ ok: true, result: { stored: 0, throttled: true } });
        return;
      }
      if (args.faults > faults) {
        faults = args.faults;
        onEvent({ kind: "fault", count: faults });
      }
      lastLog = now;
      args = { entries: args.entries };
      for (const key of ["lifecycle", "dropped", "unconfirmed"]) if (m.args[key] !== void 0) args[key] = m.args[key];
    }
    try {
      const result = m.op === "editor.save" ? await call(m.op, args, void 0, m.request_id) : await call(m.op, args);
      const revoked = checkGrant(m.op, grants);
      if (revoked && result.ok) reject(revoked);
      else reply(result);
    } catch (error) {
      onEvent({ kind: "error", message: String(error.message || error) });
      reply({ ok: false, error: { code: error.code || "blocked", message: String(error.message || error) } });
    }
  };
  try {
    frame = document.createElement("iframe");
    frame.setAttribute("sandbox", "allow-scripts");
    frame.setAttribute("referrerpolicy", "no-referrer");
    frame.style.cssText = "border:0;width:100%;height:100%;display:block;background:transparent";
    frame.title = `Space: ${project.space.name}`;
    window.addEventListener("message", onShellMessage);
    frame.addEventListener("load", onLoad);
    frame.srcdoc = shellDocument;
    container.append(frame);
  } catch (error) {
    stop();
    frame?.remove();
    throw error;
  }
  return {
    snapshot({ width = 640, timeoutMs = 2500 } = {}) {
      if (state !== "booted" || !Number.isInteger(width) || width < 64 || width > 1024 || !Number.isFinite(timeoutMs) || timeoutMs < 0 || timeoutMs > 2147483647 || snapshotId === Number.MAX_SAFE_INTEGER) return Promise.resolve(null);
      return new Promise((resolve) => {
        const id = ++snapshotId;
        const timer = setTimeout(() => snapshots.get(id)?.(null), timeoutMs);
        const settle = (result) => {
          clearTimeout(timer);
          snapshots.delete(id);
          resolve(result);
        };
        snapshots.set(id, settle);
        try {
          port.postMessage({ v: 1, type: "snapshot", id, width });
        } catch {
          settle(null);
        }
      });
    },
    postEvent(event, payload) {
      if (state !== "booted") return;
      if (event === "data.changed" && checkGrant("data.query", grants)) return;
      port.postMessage({ v: 1, type: "event", event, payload });
      if (event === "session.closed") stop();
    },
    destroy() {
      stop();
      frame.remove();
    }
  };
}

// src/desktop/ui/session.mjs
var errorCode = (error) => [error?.error?.code, error?.body?.error?.code, error?.message, String(error)].filter(Boolean).join(" ");
var freezeDraft = (value) => {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freezeDraft);
    Object.freeze(value);
  }
  return value;
};
var requestId = () => "write_" + Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join("");
var desktopOs = null;
function bindDesktopOs(os) {
  desktopOs = os ?? null;
}
var hasActivation = () => globalThis.navigator?.userActivation?.isActive === true;
function createSpaceSession({ rest, backend, sid, container, mount, onEvent, host: host5, os = desktopOs, userActivation = hasActivation, onAction = () => {
}, onWrite = () => {
}, onCloseError = (error) => console.warn("Space session cleanup failed", error) }) {
  const base = spacePath(sid);
  const scope = backend ? Object.freeze({ connectionId: backend.connectionId, profile: backend.profile }) : null;
  const active = () => !scope || host5?.state?.connectionId?.get() === scope.connectionId && host5?.state?.profile?.get() === scope.profile;
  const requireActive = () => {
    if (!active()) throw new Error("The active backend changed. Reopen this Space.");
  };
  const scopedRequest = async (path, options) => {
    requireActive();
    const value = await rest(path, options);
    requireActive();
    return value;
  };
  let closed = false;
  let session = null;
  let mounted = null;
  let closePromise = null;
  let nextWrite = 0;
  let pendingWrites = 0;
  let editorWrite = null;
  const failures = /* @__PURE__ */ new Map();
  const retries = /* @__PURE__ */ new Map();
  const publish = (event) => {
    if (!closed && active()) onWrite(failures.values().next().value || (pendingWrites ? { status: "saving" } : event));
  };
  let userCalls = 0;
  const byUser = async (work) => {
    userCalls++;
    try {
      return await work();
    } finally {
      userCalls--;
    }
  };
  const actions = host5 ? createBotActions({
    host: host5,
    backend: scope,
    isActive: () => !closed && active(),
    post: (operation, body) => scopedRequest(`${base}/actions/${operation}`, { method: "POST", body: { ...body, session } }),
    onStatus: (status) => {
      if (closed) return;
      onAction(userCalls ? { ...status, userInitiated: true } : status);
      mounted?.postEvent?.("bot.status", status);
    }
  }) : null;
  const linkNotice = `living-spaces:link:${sid}`;
  let linkGeneration = null;
  const showNotice = (input, label, run) => {
    const generation = linkGeneration = {};
    const action = run && { label, onClick: () => {
      if (linkGeneration === generation && !closed && active()) run();
    } };
    host5.notify({ id: linkNotice, ...input, action });
  };
  const openLink = (args) => {
    if (!userActivation()) return { ok: false, error: { code: "blocked", message: "Links open only from a click in the Space. Nothing was opened." } };
    if (!args || Object.keys(args).length !== 1 || typeof args.url !== "string") return { ok: false, error: { code: "invalid", message: "A link request needs exactly one url" } };
    if (typeof os?.openExternal !== "function" || typeof host5?.notify !== "function") return { ok: false, error: { code: "blocked", message: "This Desktop cannot open links from a Space" } };
    const target = linkTarget(args.url);
    if (!target.ok) {
      showNotice({ kind: "warning", title: "Link not opened", message: target.reason });
      return { ok: false, error: { code: "invalid", message: target.reason } };
    }
    showNotice({
      kind: "info",
      title: `Open ${target.host} in your browser?`,
      message: target.url,
      detail: "This Space asked to open the link above outside Hermes.",
      durationMs: 15e3
    }, "Open link", async () => {
      const handoff = linkGeneration = {};
      const opened = await os.openExternal(target.url).catch(() => false);
      if (opened === true || linkGeneration !== handoff || closed || !active()) return;
      showNotice({
        kind: "error",
        title: "Your browser could not open this link",
        message: target.url,
        detail: "Nothing was opened. Copy the link to open it yourself."
      }, "Copy link", () => {
        os.writeClipboard?.(target.url)?.catch?.(() => {
        });
      });
    });
    return { ok: true, result: { status: "confirming", url: target.url, host: target.host } };
  };
  const close = () => {
    if (!session) return Promise.resolve();
    closePromise ??= (async () => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          if (active()) return await rest(`${base}/sessions/${encodeURIComponent(session)}`, { method: "DELETE", timeoutMs: 5e3 });
          const route = await profileRoute(host5, scope);
          const identity = await host5.requestProfile(route, "runtime.describe", {}, 5e3);
          if (!identity?.capabilities?.includes("plugin-rpc-v1")) {
            throw Object.assign(new Error("The owning gateway does not advertise plugin-rpc-v1, so this Space session stays open until the Space is archived or deleted"), { final: true });
          }
          const result = await host5.requestProfile(route, "plugin.living-spaces.close_session", { space_id: sid, session }, 5e3);
          if (result?.closed !== true) throw new Error(result?.error?.message || "Space session cleanup was not confirmed");
          return result;
        } catch (error) {
          if (/session_invalid/.test(errorCode(error))) return { closed: true };
          onCloseError(error);
          if (attempt === 3 || error.final) throw error;
          await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
        }
      }
    })().catch((error) => {
      closePromise = null;
      throw error;
    });
    return closePromise;
  };
  const invalidSession = () => ({ ok: false, error: { code: "session_invalid", message: "This Space session is closed" } });
  const send = async (body) => {
    try {
      return await scopedRequest(`${base}/bridge`, { method: "POST", body });
    } catch (error) {
      const reply = error?.body || error;
      if (reply?.outcome?.status) return reply;
      return { ok: false, error: { code: "unavailable", message: error.message || String(error) }, outcome: { status: "unknown" } };
    }
  };
  const finishWrite = (attempt, reply, lookup = false) => {
    const certainty = reply?.outcome?.status;
    const saved = reply?.ok === true && (certainty == null || ["success", "confirmed"].includes(certainty)) && (!lookup || ["success", "confirmed"].includes(certainty));
    const status = certainty === "unknown" || lookup && !saved ? "unknown" : saved ? "saved" : certainty !== "busy" && reply?.error?.code === "conflict" ? "conflict" : "failed";
    attempt.unknown = status === "unknown";
    if (saved) attempt.confirmed = reply;
    const retry = (next) => {
      if (closed || !active()) return Promise.resolve(invalidSession());
      if (retries.has(attempt.token)) return retries.get(attempt.token);
      let current = attempt;
      while (current.next) current = current.next;
      if (current.confirmed) return Promise.resolve(current.confirmed);
      const promise = (current.unknown ? reconcile(current) : call(current.op, next || current.args, current.token, void 0, current)).finally(() => retries.delete(attempt.token));
      retries.set(attempt.token, promise);
      return promise;
    };
    const event = { ...attempt.op === "editor.save" ? { editorManaged: true } : {}, status, token: attempt.token, op: attempt.op, args: attempt.args, reply, at: Date.now() / 1e3, retry };
    editorWrite = event.editorManaged ? attempt : null;
    if (saved || event.editorManaged) failures.delete(attempt.token);
    else failures.set(attempt.token, event);
    publish(event);
  };
  const reconcile = async (attempt) => {
    if (closed || !active()) return invalidSession();
    pendingWrites++;
    const reply = await send({ session: attempt.session, op: "outcome.get", args: { request_id: attempt.request_id } });
    pendingWrites--;
    if (closed || !active()) return invalidSession();
    finishWrite(attempt, reply, true);
    return reply;
  };
  const call = async (op, args, retryToken, editorRequestId, supersedes) => {
    if (closed || !active()) return invalidSession();
    if (op === "link.open") return openLink(args);
    if (op === "bot.request") {
      if (!actions) return { ok: false, error: { code: "blocked", message: "Native bot actions are unavailable" } };
      const result = await byUser(() => actions.request(args));
      if (closed || !active()) return invalidSession();
      return { ok: true, result };
    }
    const writing = ["data.put", "data.delete", "data.batch", "editor.save"].includes(op);
    let attempt;
    if (writing) {
      args = structuredClone(args);
      const identify = (put) => {
        if (put.id == null) {
          put.id = "r_" + Array.from(crypto.getRandomValues(new Uint8Array(6)), (byte) => byte.toString(16).padStart(2, "0")).join("");
          put.base_rev = 0;
        }
      };
      if (retryToken == null && op === "data.put") identify(args);
      if (retryToken == null && op === "data.batch" && Array.isArray(args.ops)) args.ops.forEach((item) => {
        if (item?.op === "put") identify(item);
      });
      attempt = { token: retryToken ?? ++nextWrite, op, args: freezeDraft(args), session, request_id: op === "editor.save" ? editorRequestId : requestId(), unknown: false };
      if (supersedes) supersedes.next = attempt;
      pendingWrites++;
      publish({ status: "saving", op, args });
    }
    const reply = await send({ session, op, args, ...attempt ? { request_id: attempt.request_id } : {} });
    if (writing) pendingWrites--;
    if (closed || !active()) return invalidSession();
    if (attempt) finishWrite(attempt, reply);
    else if (editorWrite && args.editor === editorWrite.args.editor && args.schema === editorWrite.args.schema && args.collection === editorWrite.args.collection && args.id === editorWrite.args.id) {
      if (op === "outcome.get" && args.request_id === editorWrite.request_id) finishWrite(editorWrite, reply, true);
      else if (op === "draft.delete" && reply.ok) {
        editorWrite = null;
        publish(null);
      }
    }
    return reply;
  };
  const ready = (async () => {
    requireActive();
    const opened = await rest(`${base}/sessions`, { method: "POST" });
    session = opened.session;
    if (closed || !active()) {
      closed = true;
      return close();
    }
    try {
      const bundle = await scopedRequest(`${base}/bundle`);
      if (closed) return close();
      if (bundle.rev !== opened.head_rev) throw new Error("The Space changed while opening. Reload Space to open the current revision.");
      mounted = mount(container, { bundle, grants: opened.grants, call, onEvent: (event) => {
        if (closed || !active()) return;
        if (event.kind === "write-rejected" && ["data.put", "data.delete", "data.batch"].includes(event.op)) {
          const failure2 = { status: "failed", token: ++nextWrite, op: event.op, reply: { ok: false, error: event.error } };
          failures.set(failure2.token, failure2);
          publish(failure2);
        }
        onEvent(event);
      } });
      actions?.restore();
    } catch (error) {
      closed = true;
      await close().catch(() => {
      });
      throw error;
    }
  })();
  return {
    ready,
    async snapshot(options) {
      if (closed || !active() || !mounted) return null;
      try {
        const result = await mounted.snapshot(options);
        return closed || !active() ? null : result;
      } catch {
        return null;
      }
    },
    checkAction() {
      return actions && byUser(() => actions.check());
    },
    openLink(url) {
      return openLink({ url });
    },
    canContinue() {
      return !!actions?.sessionId() && typeof host5?.openSession === "function";
    },
    continueInChat() {
      const id = actions?.sessionId();
      if (!id || typeof host5?.openSession !== "function") return false;
      return host5.openSession(id);
    },
    retryAction() {
      return actions && byUser(() => actions.retry());
    },
    dismissWrite(token) {
      failures.delete(token);
      publish(null);
    },
    postEvent(event, payload) {
      if (!closed && active()) mounted?.postEvent?.(event, payload);
    },
    destroy() {
      closed = true;
      actions?.destroy();
      mounted?.destroy();
      mounted = null;
      return close();
    }
  };
}

// src/desktop/ui/space.jsx
import { Fragment as Fragment6, jsx as jsx6, jsxs as jsxs6 } from "react/jsx-runtime";
function useHeaderMode(hasSpace) {
  const frame = useRef5(null);
  const [mode, setMode] = useState6("narrow");
  useLayoutEffect2(() => {
    const element = frame.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const width = element.getBoundingClientRect().width;
      setMode(width < 600 ? "narrow" : width < 900 ? "compact" : "wide");
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [hasSpace]);
  return [frame, mode];
}
function BotBanner({ action, storageKey, controller }) {
  const replyId = useId();
  const key = botDismissKey(action);
  const [stored, setStored] = useState6(() => ({ storageKey, value: readDismissed(storageKey) }));
  const record = parseBotDismissal(stored.storageKey === storageKey ? stored.value : readDismissed(storageKey));
  const [dismissedAction, setDismissedAction] = useState6(null);
  const [expandedFor, setExpandedFor] = useState6(null);
  const identity = key ?? action;
  const banner = botBanner(action, { dismissed: dismissedAction === action || !!key && botDismissed(action, record), expanded: expandedFor === identity });
  if (!banner) return null;
  const dismiss = () => {
    setDismissedAction(action);
    if (!key) return;
    const value = JSON.stringify(dismissBot(record, action));
    writeDismissed(storageKey, value);
    setStored({ storageKey, value });
  };
  const failed = banner.kind === "failed";
  const canContinue = banner.collapsible && controller.current?.canContinue?.() === true;
  return /* @__PURE__ */ jsxs6(Banner, { kind: failed ? "failed" : "info", title: /* @__PURE__ */ jsxs6(Fragment6, { children: [
    banner.label,
    banner.at != null && /* @__PURE__ */ jsxs6(Fragment6, { children: [
      " \xB7 ",
      /* @__PURE__ */ jsx6(Time, { at: banner.at })
    ] })
  ] }), actions: /* @__PURE__ */ jsxs6(Fragment6, { children: [
    banner.collapsible && /* @__PURE__ */ jsx6(Action, { "aria-expanded": banner.expanded, "aria-controls": replyId, onClick: () => setExpandedFor(banner.expanded ? null : identity), children: banner.expanded ? "Collapse" : "Read reply" }),
    banner.kind !== "reply" && /* @__PURE__ */ jsx6(Action, { onClick: () => controller.current?.checkAction(), children: "Check status" }),
    banner.canRetry && /* @__PURE__ */ jsx6(Action, { onClick: () => controller.current?.retryAction(), children: "Retry same request" }),
    banner.canDismiss && /* @__PURE__ */ jsx6(Action, { "aria-label": banner.kind === "reply" ? "Dismiss reply" : void 0, onClick: dismiss, children: "Dismiss" })
  ] }), children: [
    banner.reason && /* @__PURE__ */ jsx6("span", { className: "ls-oneline", title: banner.reason, children: banner.reason }),
    banner.collapsible && /* @__PURE__ */ jsxs6(Fragment6, { children: [
      !banner.expanded && /* @__PURE__ */ jsx6("p", { className: "ls-oneline ls-answer-summary", title: banner.summary, children: banner.summary }),
      /* @__PURE__ */ jsx6("div", { id: replyId, className: "ls-collapse", "data-open": banner.expanded, children: /* @__PURE__ */ jsxs6("div", { inert: !banner.expanded || void 0, "aria-hidden": !banner.expanded, children: [
        /* @__PURE__ */ jsx6("div", { className: "ls-answer", tabIndex: 0, role: "region", "aria-label": "Hermes reply", children: /* @__PURE__ */ jsx6(Answer, { text: banner.answer, onOpenLink: (href) => controller.current?.openLink(href) }) }),
        /* @__PURE__ */ jsxs6("div", { className: "ls-actions", children: [
          canContinue && /* @__PURE__ */ jsx6(Action, { icon: "comment-discussion", onClick: () => controller.current?.continueInChat(), children: "Continue in chat" }),
          /* @__PURE__ */ jsx6(CopyButton2, { text: banner.answer, label: "Copy", showLabel: true, buttonSize: "sm" })
        ] })
      ] }) })
    ] })
  ] });
}
var GRANT_WORDS = { net: "Internet", data: "Records", logs: "Diagnostic log", bot: "Bot requests", files: "Files", tools: "Private tools" };
var sourceHost2 = (url) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
};
function SpaceDetails({ space, dimensions, upkeepLabel, building, onOpen, onClose, returnFocus }) {
  const phrase = freshnessPhrase(space);
  const facts = freshnessFacts(space, absolute);
  const reason = refreshReason(space);
  const notice = storageNotice(space.storage);
  const grants = space.grants || [];
  const net = grants.find((grant) => grant.capability === "net");
  const lastRun = space.recent_runs?.[0];
  const sources = space.freshness?.sources || [];
  return /* @__PURE__ */ jsxs6(Drawer, { returnFocus, title: "Space details", description: `Freshness, storage, access, history and runtime for ${space.name}`, onClose, heading: /* @__PURE__ */ jsx6(SpaceTile, { space, small: true }), children: [
    /* @__PURE__ */ jsxs6("section", { "aria-label": "Freshness", className: "ls-detail", children: [
      /* @__PURE__ */ jsx6("h3", { children: "Freshness" }),
      /* @__PURE__ */ jsxs6("dl", { className: "ls-facts", children: [
        /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Latest change" }),
          /* @__PURE__ */ jsxs6("dd", { children: [
            phrase.label,
            phrase.at != null && /* @__PURE__ */ jsxs6(Fragment6, { children: [
              " \xB7 ",
              /* @__PURE__ */ jsx6(Time, { at: phrase.at })
            ] })
          ] })
        ] }),
        facts.map((fact) => /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: fact.label }),
          /* @__PURE__ */ jsx6("dd", { children: fact.value })
        ] }, fact.key)),
        sources.map((source) => /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Source" }),
          /* @__PURE__ */ jsx6("dd", { children: [source.id, sourceHost2(source.url), source.failure_reason].filter(Boolean).join(" \xB7 ") })
        ] }, source.id)),
        !building && /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Refresh" }),
          /* @__PURE__ */ jsx6("dd", { children: reason || "Use Refresh now in the top bar." })
        ] }),
        !building && /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Upkeep" }),
          /* @__PURE__ */ jsx6("dd", { children: upkeepLabel })
        ] })
      ] }),
      !building && /* @__PURE__ */ jsx6("div", { className: "ls-actions", children: /* @__PURE__ */ jsx6(Action, { onClick: () => onOpen("upkeep"), children: "Manage upkeep" }) })
    ] }),
    space.storage && /* @__PURE__ */ jsxs6("section", { "aria-label": "Storage use", className: "ls-detail", children: [
      /* @__PURE__ */ jsx6("h3", { children: "Storage" }),
      notice ? /* @__PURE__ */ jsxs6(Fragment6, { children: [
        /* @__PURE__ */ jsx6("p", { children: notice.title }),
        /* @__PURE__ */ jsx6("p", { className: "ls-secondary", children: notice.line }),
        /* @__PURE__ */ jsx6("div", { className: "ls-meter", "aria-hidden": "true", children: /* @__PURE__ */ jsx6("i", { style: { width: `${notice.pct}%` } }) })
      ] }) : /* @__PURE__ */ jsx6("p", { className: "ls-secondary", children: "Within this Space's storage limits." }),
      /* @__PURE__ */ jsx6("div", { className: "ls-actions", children: /* @__PURE__ */ jsx6(Action, { onClick: () => onOpen("history"), children: "Review storage" }) })
    ] }),
    !building && /* @__PURE__ */ jsxs6("section", { "aria-label": "Access", className: "ls-detail", children: [
      /* @__PURE__ */ jsx6("h3", { children: "Access" }),
      /* @__PURE__ */ jsxs6("dl", { className: "ls-facts", children: [
        /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Internet" }),
          /* @__PURE__ */ jsx6("dd", { children: net?.status === "granted" ? "On" : net ? PILLS[net.status]?.label || net.status : "Not requested" })
        ] }),
        grants.filter((grant) => grant.capability !== "net").map((grant) => /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: GRANT_WORDS[grant.capability] || grant.capability }),
          /* @__PURE__ */ jsx6("dd", { children: PILLS[grant.status]?.label || grant.status })
        ] }, grant.capability))
      ] }),
      /* @__PURE__ */ jsx6("div", { className: "ls-actions", children: /* @__PURE__ */ jsx6(Action, { onClick: () => onOpen("permissions"), children: "Manage access" }) })
    ] }),
    /* @__PURE__ */ jsxs6("section", { "aria-label": "History", className: "ls-detail", children: [
      /* @__PURE__ */ jsx6("h3", { children: "History" }),
      /* @__PURE__ */ jsxs6("dl", { className: "ls-facts", children: [
        /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Revision" }),
          /* @__PURE__ */ jsx6("dd", { children: space.head_rev || "None yet" })
        ] }),
        lastRun && /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Last refresh" }),
          /* @__PURE__ */ jsxs6("dd", { children: [
            runResult(lastRun),
            (lastRun.ended_at ?? lastRun.queued_at) != null && /* @__PURE__ */ jsxs6(Fragment6, { children: [
              " \xB7 ",
              /* @__PURE__ */ jsx6(Time, { at: lastRun.ended_at ?? lastRun.queued_at })
            ] })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsx6("div", { className: "ls-actions", children: /* @__PURE__ */ jsx6(Action, { icon: "history", onClick: () => onOpen("history"), children: "Open history" }) })
    ] }),
    /* @__PURE__ */ jsxs6("section", { "aria-label": "Runtime", className: "ls-detail", children: [
      /* @__PURE__ */ jsx6("h3", { children: "Runtime" }),
      /* @__PURE__ */ jsxs6("dl", { className: "ls-facts", children: [
        /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Host" }),
          /* @__PURE__ */ jsx6("dd", { children: PILLS[dimensions.host === "available" ? "ready" : dimensions.host]?.label || dimensions.host })
        ] }),
        /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx6("dt", { children: "Space app" }),
          /* @__PURE__ */ jsx6("dd", { children: guestWord(dimensions.guest) })
        ] })
      ] }),
      /* @__PURE__ */ jsx6("p", { className: "ls-secondary ls-note", children: "Shown here only. Failures surface as a notice over the canvas." })
    ] })
  ] });
}
function SaveStatus({ write, announcement }) {
  const labels = { saving: "Saving\u2026", saved: `Saved ${write?.at ? absolute(write.at) : ""}`, failed: "Not saved \u2014 this change was rejected", unknown: "Save outcome unknown \u2014 the change may have been stored", conflict: "Conflict \u2014 this record changed elsewhere" };
  return /* @__PURE__ */ jsxs6("span", { className: "ls-save", "data-status": write?.status, role: "status", "aria-live": "polite", "aria-atomic": "true", children: [
    write && /* @__PURE__ */ jsxs6(Fragment6, { children: [
      /* @__PURE__ */ jsx6(Icon, { name: write.status === "saving" ? "refresh" : ["failed", "unknown", "conflict"].includes(write.status) ? "warning" : "check", spin: write.status === "saving" }),
      labels[write.status]
    ] }),
    announcement && /* @__PURE__ */ jsx6("span", { children: announcement })
  ] });
}
function WriteBanner({ write, setWrite, onCompare, onUpdated, onDismiss }) {
  if (!write || !["failed", "unknown", "conflict"].includes(write.status)) return null;
  if (write.editorManaged) return /* @__PURE__ */ jsx6(Banner, { kind: write.status === "conflict" ? "conflict" : "failed", title: write.status === "unknown" ? "Save outcome unknown" : write.status === "conflict" ? "Changes conflict" : "Not saved", children: "Your draft is preserved. Continue in the app editor to resolve this save." });
  const current = write.reply?.error?.current;
  const canKeep = write.op === "data.put" && current?.rev != null;
  return /* @__PURE__ */ jsx6(
    Banner,
    {
      kind: write.status === "conflict" ? "conflict" : "failed",
      title: write.status === "conflict" ? "Conflict \u2014 this record changed elsewhere" : write.status === "unknown" ? "Save outcome unknown \u2014 the change may have been stored" : "Not saved \u2014 this change was rejected",
      actions: write.status === "conflict" ? /* @__PURE__ */ jsxs6(Fragment6, { children: [
        canKeep && /* @__PURE__ */ jsx6(Action, { onClick: () => write.retry({ ...write.args, base_rev: current.rev }), children: "Keep my note" }),
        /* @__PURE__ */ jsx6(Action, { onClick: () => {
          setWrite(null);
          onUpdated(current);
        }, children: "Use updated record" }),
        /* @__PURE__ */ jsx6(Action, { onClick: onCompare, children: "Compare" })
      ] }) : write.retry ? /* @__PURE__ */ jsx6(Action, { onClick: () => write.retry(), children: "Retry save" }) : /* @__PURE__ */ jsx6(Action, { onClick: onDismiss, children: "Dismiss" }),
      children: write.reply?.error ? errorText(write.reply.error) : "Your change is kept in this view until you choose how to continue."
    }
  );
}
function NoticeDock({ children, minimiseSignal }) {
  const list = useRef5(null);
  const pill = useRef5(null);
  const minimiser = useRef5(null);
  const [minimised, setMinimised] = useState6(false);
  const [summary, setSummary] = useState6({ count: 0, alert: false, title: "", keys: "" });
  const seen = useRef5(/* @__PURE__ */ new Set());
  const id = useId();
  useLayoutEffect2(() => {
    const element = list.current;
    if (!element) return;
    const read = () => {
      const notices = [...element.querySelectorAll(".ls-banner")];
      const titles = notices.map((node) => node.querySelector("strong")?.textContent || "");
      const next = { count: notices.length, alert: notices.some((node) => node.getAttribute("role") === "alert"), title: titles[0] || "", keys: titles.join("\n") };
      setSummary((current) => current.keys === next.keys && current.count === next.count && current.alert === next.alert ? current : next);
      if (titles.some((title) => !seen.current.has(title))) setMinimised(false);
      seen.current = new Set(titles);
    };
    read();
    if (typeof MutationObserver === "undefined") return;
    const observer = new MutationObserver(read);
    observer.observe(element, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["role"] });
    return () => observer.disconnect();
  }, []);
  useEffect3(() => {
    if (minimiseSignal) setMinimised(true);
  }, [minimiseSignal]);
  const minimise = () => {
    const inside = list.current?.contains(document.activeElement);
    setMinimised(true);
    if (inside) requestAnimationFrame(() => pill.current?.focus());
  };
  const expand = () => {
    setMinimised(false);
    requestAnimationFrame(() => minimiser.current?.focus());
  };
  const empty = summary.count === 0;
  return /* @__PURE__ */ jsxs6("div", { className: "ls-notices", "data-minimised": minimised || void 0, "data-empty": empty || void 0, onKeyDown: (event) => {
    if (event.key === "Escape" && !minimised && !empty) {
      event.stopPropagation();
      minimise();
    }
  }, children: [
    minimised && !empty && /* @__PURE__ */ jsxs6("button", { ref: pill, type: "button", className: `ls-notice-pill${summary.alert ? " ls-alert" : ""}`, "aria-expanded": "false", "aria-controls": id, onClick: expand, children: [
      /* @__PURE__ */ jsx6(Icon, { name: summary.alert ? "warning" : "bell" }),
      /* @__PURE__ */ jsx6("span", { className: "ls-oneline", children: summary.count === 1 ? summary.title : `${summary.count} notices` }),
      summary.count > 1 && /* @__PURE__ */ jsx6("span", { className: "ls-notice-count ls-num", children: summary.count })
    ] }),
    /* @__PURE__ */ jsxs6("div", { id, className: "ls-notice-list", hidden: minimised || void 0, "aria-label": "Space notices", role: "group", children: [
      !empty && /* @__PURE__ */ jsx6("div", { className: "ls-notice-tools", children: /* @__PURE__ */ jsxs6("button", { ref: minimiser, type: "button", className: "ls-notice-minimise", "aria-expanded": "true", "aria-controls": id, onClick: minimise, children: [
        /* @__PURE__ */ jsx6(Icon, { name: "chevron-down" }),
        "Minimise"
      ] }) }),
      /* @__PURE__ */ jsx6("div", { ref: list, className: "ls-notice-stack", children })
    ] })
  ] });
}
function SpaceView({ ctx, scopeKey = null, scope, openingSessionRest, sid }) {
  const { connectionId, profile } = useMemo2(() => scope || { connectionId: host2.state.connectionId.get(), profile: host2.state.profile.get() }, [scope, ctx, scopeKey, sid]);
  const base = spacePath(sid);
  const queryClient = useQueryClient();
  const detail = useQuery5({ queryKey: ["living-spaces", scopeKey, sid, "detail"], queryFn: () => ctx.rest(base), refetchInterval: 2e3, notifyOnChangeProps: ["data", "error", "dataUpdatedAt"] });
  const space = detail.data;
  const [frame, headerMode] = useHeaderMode(!!space);
  const [sheet, setSheet] = useState6(null);
  const [confirmation, setConfirmation] = useState6(null);
  const [reload, setReload] = useState6(0);
  const [guest, setGuest] = useState6({ status: "unknown", diagnostic: null });
  const crash = guest.diagnostic;
  const [ignoredCrashRev, setIgnoredCrashRev] = useState6(null);
  const [write, setWrite] = useState6(null);
  const [announcement, setAnnouncement] = useState6("");
  const [actionError, setActionError] = useState6("");
  const [botAction, setBotAction] = useState6(null);
  const [refreshPending, setRefreshPending] = useState6(false);
  const [ready, setReady] = useState6(false);
  const [canvasFocus, setCanvasFocus] = useState6(0);
  const refreshLock = useRef5(null);
  const refreshLifetime = useRef5(null);
  const actionLock = useRef5(false);
  const content = useRef5(null);
  const overflow = useRef5(null);
  const confirmationTrigger = useRef5(null);
  const controller = useRef5(null);
  const cursor = useRef5(0);
  const seenRun = useRef5(null);
  const grantsKey = JSON.stringify(space?.grants || []);
  const hasData = space?.grants?.some((grant) => grant.capability === "data" && grant.status === "granted") === true;
  const building = !space || space.status === "building" || !space.head_rev;
  const archived = space?.status === "archived";
  const remoteCrash = space?.attention?.kind === "crashed" && ignoredCrashRev !== space?.head_rev;
  const status = crash || remoteCrash ? "crashed" : space ? spaceStatus(ignoredCrashRev === space.head_rev ? { ...space, attention: null } : space, true) : "building";
  const lastRun = space?.recent_runs?.[0];
  const runKey = JSON.stringify(lastRun || null);
  useEffect3(() => {
    let disposed = false;
    ctx.rest(`${base}/opened`, { method: "POST" }).catch((e) => {
      if (!disposed) setActionError(`Could not mark this Space as opened. ${errorText(e)}`);
    });
    return () => {
      disposed = true;
    };
  }, [ctx, base]);
  useLayoutEffect2(() => {
    const lifetime = { active: true };
    refreshLifetime.current = lifetime;
    return () => {
      lifetime.active = false;
      if (refreshLock.current?.lifetime === lifetime) {
        refreshLock.current = null;
        setRefreshPending(false);
        setAnnouncement("");
      }
    };
  }, [ctx, openingSessionRest, connectionId, profile, scopeKey, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload]);
  useEffect3(() => {
    if (building || archived || crash || remoteCrash || !content.current) return;
    let disposed = false;
    cursor.current = 0;
    setReady(false);
    setGuest({ status: "starting", diagnostic: null });
    setBotAction(null);
    const current = () => !disposed && host2.state.connectionId.get() === connectionId && host2.state.profile.get() === profile;
    const fail = (message) => setGuest({ status: "failed", diagnostic: diagnosticText(message || "The guest could not be loaded.") });
    const backend = { connectionId, profile };
    const session = createSpaceSession({
      backend,
      host: host2,
      onAction: (event) => current() && setBotAction({ ...event, at: Date.now() / 1e3 }),
      rest: openingSessionRest || ((path, options) => ctx.rest(path, options)),
      sid,
      container: content.current,
      mount: (container, options) => mountSpace(container, { ...options, call: async (op, args) => {
        const reply = await options.call(op, args);
        if (current() && op === "log" && reply?.ok === true) {
          if (args.lifecycle === "failed") fail("The guest reported a load or runtime failure. Review this Space's diagnostic log for details.");
          if (args.lifecycle === "loaded") setGuest((value) => ["failed", "faulted"].includes(value.status) ? value : { status: "loaded", diagnostic: null });
        }
        return reply;
      } }),
      onWrite: (event) => current() && setWrite(event),
      onEvent: (event) => {
        if (!current()) return;
        if (event.kind === "reloaded") setReload((n) => n + 1);
        if (event.kind === "booted") setReady(true);
        if (event.kind === "denied") setAnnouncement("A Space request was denied. Review Permissions for access details.");
        if (event.kind === "log-overflow") setAnnouncement("Some diagnostic entries were dropped because the log limit was reached.");
        if (event.kind === "fault") setGuest((value) => value.status === "failed" ? value : { status: "faulted", diagnostic: null });
      }
    });
    controller.current = session;
    session.ready.then(() => {
      if (current()) setReady(true);
    }).catch((e) => {
      if (disposed) return;
      if (current()) fail(errorText(e));
      else setActionError(errorText(e));
    });
    return () => {
      disposed = true;
      setReady(false);
      session.postEvent("session.closed", { reason: "Space view closed or reloaded" });
      session.destroy().catch((e) => host2.notifyError(e, "A Space session could not be closed after retries."));
      if (controller.current === session) controller.current = null;
    };
  }, [ctx, openingSessionRest, connectionId, profile, scopeKey, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload]);
  const changes = useQuery5({ queryKey: ["living-spaces", scopeKey, sid, "changes", space?.head_rev, grantsKey, reload], queryFn: () => ctx.rest(`${base}/changes?since=${cursor.current}`), enabled: hasData && ready && !building && !archived && !crash, refetchInterval: 1500 });
  useEffect3(() => {
    if (!hasData || !ready || !changes.data || !controller.current) return;
    const page = advanceCursor(cursor.current, changes.data);
    if (page.changes.length) {
      controller.current.postEvent("data.changed", page);
      cursor.current = page.seq;
    }
  }, [hasData, ready, changes.data, changes.dataUpdatedAt]);
  useEffect3(() => {
    if (!lastRun) return;
    if (ready) controller.current?.postEvent("run.updated", lastRun);
    if (seenRun.current && seenRun.current !== runKey && !inFlight(lastRun.status)) setAnnouncement(lastRun.status === "succeeded" ? `Refresh succeeded: ${runResult(lastRun)}` : `Refresh ${lastRun.status}: ${runResult(lastRun)}`);
    seenRun.current = runKey;
  }, [runKey, ready]);
  useLayoutEffect2(() => {
    setGuest({ status: "unknown", diagnostic: null });
    setIgnoredCrashRev(null);
  }, [connectionId, profile, scopeKey, sid, space?.head_rev]);
  const capture = useRef5(null);
  capture.current = async () => {
    const session = controller.current;
    const rev = space?.head_rev;
    if (!session?.snapshot || !ready || !rev || ["failed", "faulted"].includes(guest.status)) return;
    const shot = await session.snapshot({ width: SNAPSHOT_LIMITS.width, timeoutMs: 2500 });
    if (shot && controller.current === session && host2.state.connectionId.get() === connectionId && host2.state.profile.get() === profile) writeSnapshot(scopeKey, sid, { ...shot, at: Date.now() / 1e3, rev });
  };
  useEffect3(() => {
    if (!ready || building || archived || crash || remoteCrash || ["failed", "faulted"].includes(guest.status)) return;
    const settle = setTimeout(() => capture.current?.(), 2500);
    const again = setInterval(() => {
      if (document.visibilityState !== "hidden") capture.current?.();
    }, 6e4);
    return () => {
      clearTimeout(settle);
      clearInterval(again);
    };
  }, [ready, building, archived, crash, remoteCrash, guest.status, space?.head_rev]);
  useEffect3(() => {
    const onBlur = () => setTimeout(() => {
      const active = document.activeElement;
      if (active?.tagName === "IFRAME" && content.current?.contains(active)) setCanvasFocus((n) => n + 1);
    }, 0);
    window.addEventListener("blur", onBlur);
    return () => window.removeEventListener("blur", onBlur);
  }, []);
  const leaving = useRef5(false);
  async function leave() {
    if (leaving.current) return;
    leaving.current = true;
    try {
      await Promise.race([capture.current?.(), new Promise((resolve) => setTimeout(resolve, 700))]);
    } catch {
    }
    host2.navigate("/spaces");
  }
  async function refresh() {
    if (refreshLock.current || refreshPending || status === "updating" || inFlight(lastRun?.status) || refreshReason(space)) return;
    const request = { lifetime: refreshLifetime.current, controller: controller.current };
    const current = () => request.lifetime?.active && refreshLifetime.current === request.lifetime && controller.current === request.controller && host2.state.connectionId.get() === connectionId && host2.state.profile.get() === profile;
    if (!current()) return;
    refreshLock.current = request;
    setRefreshPending(true);
    setActionError("");
    setAnnouncement("Refreshing\u2026");
    try {
      let reply;
      try {
        reply = await ctx.rest(`${base}/refresh`, { method: "POST" });
      } catch (error) {
        reply = error?.body || error;
        if (!reply?.outcome?.status) reply = { outcome: { status: "unknown" } };
      }
      if (!current()) return;
      const certainty = reply?.outcome?.status;
      if (certainty === "unknown") {
        setAnnouncement("Refresh outcome unknown");
        return;
      }
      if (certainty === "busy" || certainty === "rejected") {
        setActionError(errorText(reply.error || reply));
        setAnnouncement(certainty === "busy" ? "Refresh busy" : "Refresh failed");
        return;
      }
      const run = reply?.result || reply;
      if (reply?.ok === false || !run?.id && run?.kind !== "cron") {
        setAnnouncement("Refresh outcome unknown");
        return;
      }
      if (run.kind === "cron") setAnnouncement("Refresh started in Hermes");
      else {
        request.controller?.postEvent("run.updated", run);
        if (!inFlight(run.status) && run.status) setAnnouncement(`Refresh ${run.status}: ${runResult(run)}`);
      }
      await detail.refetch().catch((error) => {
        if (current()) setActionError(errorText(error));
      });
    } finally {
      if (refreshLock.current === request) {
        refreshLock.current = null;
        setRefreshPending(false);
      }
    }
  }
  const listKey = ["living-spaces", scopeKey, "spaces"];
  const fresh = (result) => result?.status === "success" ? result.data : null;
  async function syncList(fresh2) {
    if (fresh2) {
      await queryClient.cancelQueries({ queryKey: listKey });
      queryClient.setQueryData(listKey, (list) => list?.spaces ? { ...list, spaces: list.spaces.map((row) => row.id === sid ? Object.fromEntries(Object.keys(row).map((key) => [key, key in fresh2 ? fresh2[key] : row[key]])) : row) } : list);
    }
    queryClient.invalidateQueries({ queryKey: listKey, refetchType: "all" });
  }
  async function act(path, body) {
    if (actionLock.current) return;
    actionLock.current = true;
    setActionError("");
    try {
      await ctx.rest(`${base}/${path}`, { method: "POST", ...body ? { body } : {} });
      await syncList(fresh(await detail.refetch()));
    } catch (e) {
      setActionError(errorText(e));
    } finally {
      actionLock.current = false;
    }
  }
  if (!space) return /* @__PURE__ */ jsx6("div", { className: "ls-page", children: detail.error ? /* @__PURE__ */ jsxs6(ErrorState5, { title: "This Space could not be opened", description: errorText(detail.error), children: [
    /* @__PURE__ */ jsx6(Action, { onClick: () => detail.refetch(), children: "Try again" }),
    /* @__PURE__ */ jsx6(Action, { onClick: () => host2.navigate("/spaces"), children: "Spaces" })
  ] }) : /* @__PURE__ */ jsx6(Skeleton5, { style: { height: 400 } }) });
  const dimensions = statusDimensions(space, { guest: remoteCrash ? "failed" : guest.status, write });
  const upkeep = space.upkeep;
  const busy = refreshPending || inFlight(lastRun?.status) || status === "updating";
  const reason = refreshReason(space);
  const opener = () => {
    const element = document.activeElement?.getAttribute("role") === "menuitem" ? overflow.current : document.activeElement;
    return { focus: () => {
      if (element?.isConnected) {
        element.focus();
        if (document.activeElement === element) return;
      }
      overflow.current?.focus();
    } };
  };
  const openSheet = (kind, tab) => setSheet({ kind, tab, returnFocus: opener() });
  const openHistory = (tab) => {
    detail.refetch();
    openSheet("history", tab || "runs");
  };
  const askConfirmation = (kind) => {
    confirmationTrigger.current = opener();
    setConfirmation(kind);
  };
  const crashMessage = diagnosticText(crash || space.attention?.message || "The guest reported a fatal error.");
  const phrase = freshnessPhrase(space);
  const upkeepLabel = !upkeep ? "None" : upkeep.missing ? "Job missing" : upkeep.enabled === true ? "On" : upkeep.enabled === false ? "Paused" : "Linked";
  const netOn = space.grants?.some((grant) => grant.capability === "net" && grant.status === "granted");
  const refreshable = !building && !!space.manifest?.upkeep;
  const tone = ["failed", "blocked", "crashed"].includes(status) ? "danger" : status === "updating" ? "busy" : phrase.key === "success" && !space.freshness?.last_success_at ? "idle" : "good";
  return /* @__PURE__ */ jsxs6("div", { ref: frame, className: "ls-frame", "data-header-mode": headerMode, "data-testid": "space-view", children: [
    /* @__PURE__ */ jsxs6("header", { className: "ls-framebar", children: [
      /* @__PURE__ */ jsxs6("div", { className: "ls-island ls-island-identity", children: [
        /* @__PURE__ */ jsx6(Action, { className: "ls-action ls-icon-button", icon: "arrow-left", "aria-label": "Back to Spaces", title: "Back to Spaces", onClick: leave }),
        /* @__PURE__ */ jsxs6("div", { className: "ls-identity", children: [
          /* @__PURE__ */ jsx6(SpaceTile, { space, small: true }),
          /* @__PURE__ */ jsx6("h1", { title: space.name, children: space.name }),
          status !== "ready" && /* @__PURE__ */ jsx6(StatusPill, { status })
        ] })
      ] }),
      /* @__PURE__ */ jsxs6("div", { className: "ls-island ls-frame-actions", children: [
        /* @__PURE__ */ jsxs6("span", { className: "ls-frame-meta", title: phrase.at != null ? `${phrase.label} \xB7 ${absolute(phrase.at)}` : phrase.label, children: [
          /* @__PURE__ */ jsx6("span", { className: "ls-dot", "data-tone": tone, "aria-hidden": "true" }),
          /* @__PURE__ */ jsxs6("span", { className: "ls-frame-meta-text", children: [
            phrase.label,
            phrase.at != null && /* @__PURE__ */ jsxs6(Fragment6, { children: [
              " \xB7 ",
              /* @__PURE__ */ jsx6(Time, { at: phrase.at, relative: true })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsx6(SaveStatus, { write, announcement }),
        netOn && /* @__PURE__ */ jsx6(Action, { className: "ls-action ls-island-button", icon: "globe", title: "Internet access is on. Manage it in Permissions.", onClick: () => openSheet("permissions"), children: /* @__PURE__ */ jsx6("span", { className: "ls-label", children: "Internet on" }) }),
        refreshable && /* @__PURE__ */ jsx6(DisabledReason, { reason, children: /* @__PURE__ */ jsx6(Action, { className: "ls-action ls-island-button", icon: "refresh", "aria-busy": busy, "aria-disabled": !!reason || busy, title: reason || void 0, onClick: refresh, children: /* @__PURE__ */ jsx6("span", { className: "ls-label", children: busy ? "Refreshing\u2026" : "Refresh now" }) }) }),
        /* @__PURE__ */ jsx6(Action, { className: "ls-action ls-island-button", icon: "settings", onClick: () => openSheet("details"), children: /* @__PURE__ */ jsx6("span", { className: "ls-label", children: "Details" }) }),
        /* @__PURE__ */ jsxs6(DropdownMenu, { children: [
          /* @__PURE__ */ jsx6(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsx6(Action, { ref: overflow, className: "ls-action ls-overflow", "aria-label": "More Space actions", icon: "ellipsis" }) }),
          /* @__PURE__ */ jsxs6(DropdownMenuContent, { align: "end", children: [
            /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openHistory(), children: "History" }),
            !building && /* @__PURE__ */ jsxs6(Fragment6, { children: [
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openSheet("upkeep"), children: "Upkeep" }),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openSheet("permissions"), children: "Permissions" }),
              /* @__PURE__ */ jsx6(DropdownMenuSeparator, {}),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => act("pin", { pinned: !space.pinned }), children: space.pinned ? "Unpin Space" : "Pin Space" }),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => archived ? act("unarchive") : askConfirmation("archive"), children: archived ? "Restore Space" : "Archive Space\u2026" }),
              archived && /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => askConfirmation("delete"), children: "Delete\u2026" })
            ] })
          ] })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs6("section", { className: "ls-content", "aria-label": "Space content", children: [
      /* @__PURE__ */ jsx6("div", { className: `ls-sandbox${status === "failed" ? " ls-stale" : ""}`, children: building ? /* @__PURE__ */ jsxs6("div", { className: "ls-building", children: [
        /* @__PURE__ */ jsxs6("p", { role: "status", children: [
          space.owner,
          " is building the first version. This opens automatically when it's ready."
        ] }),
        /* @__PURE__ */ jsx6(Skeleton5, { style: { height: 100 } }),
        /* @__PURE__ */ jsx6(Skeleton5, { style: { height: 180 } })
      ] }) : status === "crashed" ? /* @__PURE__ */ jsxs6("div", { className: "ls-crash", children: [
        /* @__PURE__ */ jsx6(ErrorState5, { title: `${space.name} stopped working`, description: "The guest hit an error and was stopped. Already-written records remain; stopping the guest does not undo changes. Check the save status for any pending change." }),
        /* @__PURE__ */ jsx6("pre", { className: "ls-diagnostic", children: `Revision ${space.head_rev}
${crashMessage}
Logged to this Space only. Common credential values redacted.` }),
        /* @__PURE__ */ jsxs6("div", { className: "ls-actions", children: [
          /* @__PURE__ */ jsx6(Action, { primary: true, onClick: () => {
            setGuest({ status: "unknown", diagnostic: null });
            setIgnoredCrashRev(space.head_rev);
            setReload((n) => n + 1);
          }, children: "Reload Space" }),
          /* @__PURE__ */ jsx6(Action, { onClick: () => openHistory("revisions"), children: "Restore revision\u2026" })
        ] }),
        /* @__PURE__ */ jsx6(CopyPrompt, { text: `${space.owner}, ${space.name} crashed. Please read its error log and fix it.` }),
        /* @__PURE__ */ jsxs6("p", { className: "ls-secondary", children: [
          "Repairs happen in chat. ",
          space.owner,
          " can read this error and apply a new revision."
        ] })
      ] }) : archived ? /* @__PURE__ */ jsx6("div", { className: "ls-building", children: /* @__PURE__ */ jsx6("p", { children: "Restore Space to open its content. Your records and revisions are kept." }) }) : /* @__PURE__ */ jsx6("div", { ref: content, className: "ls-mount", "data-testid": "space-host" }) }),
      /* @__PURE__ */ jsxs6(NoticeDock, { minimiseSignal: canvasFocus, children: [
        /* @__PURE__ */ jsx6(StorageNotice, { storage: space.storage, onReview: () => openHistory(), storageKey: `living-spaces:storage-dismissed:${connectionId}:${profile}:${sid}` }),
        botAction && /* @__PURE__ */ jsx6(BotBanner, { action: botAction, controller, storageKey: `living-spaces:bot-dismissed:${connectionId}:${profile}:${sid}` }),
        guest.status === "faulted" && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: "This Space hit an uncaught error", children: /* @__PURE__ */ jsx6("span", { role: "status", children: "It is still open and may keep working. Saved records are unaffected. Review this Space's diagnostic log for details." }) }),
        actionError && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: actionError }),
        detail.error && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: "Space status could not be refreshed. You're seeing the last loaded state.", actions: /* @__PURE__ */ jsx6(Action, { onClick: () => detail.refetch(), children: "Try again" }), children: errorText(detail.error) }),
        changes.error && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: "Live record updates are delayed. Your displayed data may be out of date.", actions: /* @__PURE__ */ jsx6(Action, { onClick: () => changes.refetch(), children: "Retry live updates" }), children: errorText(changes.error) }),
        /* @__PURE__ */ jsx6(WriteBanner, { write, setWrite, onDismiss: () => controller.current?.dismissWrite(write.token), onCompare: () => openSheet("compare"), onUpdated: () => {
          controller.current?.dismissWrite(write.token);
          setReload((n) => n + 1);
        } }),
        archived ? /* @__PURE__ */ jsx6(Banner, { title: "This Space is archived. Future upkeep is paused.", actions: /* @__PURE__ */ jsxs6(Fragment6, { children: [
          /* @__PURE__ */ jsx6(Action, { onClick: () => act("unarchive"), children: "Restore Space" }),
          /* @__PURE__ */ jsx6(Action, { danger: true, onClick: () => askConfirmation("delete"), children: "Delete\u2026" })
        ] }), children: "Restore it to open the canvas, then resume upkeep separately. Already-running work may finish. Delete removes it and its data permanently." }) : status === "failed" ? /* @__PURE__ */ jsxs6(Banner, { kind: "failed", title: `Refresh failed${space.freshness?.last_attempt_at != null ? ` at ${absolute(space.freshness.last_attempt_at)}` : ""}. ${space.freshness?.last_success_at != null ? `You're seeing data from ${absolute(space.freshness.last_success_at)}.` : "No successful update yet."}`, actions: /* @__PURE__ */ jsxs6(Fragment6, { children: [
          /* @__PURE__ */ jsx6(Action, { onClick: () => openHistory(), children: "View run details" }),
          /* @__PURE__ */ jsx6(Action, { onClick: refresh, children: "Try again" })
        ] }), children: [
          lastRun?.error || space.attention?.message || "The source did not respond.",
          " Your notes and statuses are unchanged. ",
          space.freshness?.next_run_at ? `Next automatic try ${absolute(space.freshness.next_run_at)}.` : "No automatic try is scheduled."
        ] }) : status === "blocked" ? /* @__PURE__ */ jsxs6(Banner, { kind: "blocked", title: `Refresh is blocked: ${space.attention?.message || reason || "Review Permissions"}`, actions: /* @__PURE__ */ jsx6(Action, { onClick: () => openSheet("permissions"), children: "Review permissions" }), children: [
          "The Space still opens and your data is safe. ",
          /* @__PURE__ */ jsx6(CopyPrompt, { text: `${space.owner}, ${space.name} is blocked. Please review its last run and help me restore upkeep.` })
        ] }) : null
      ] })
    ] }),
    sheet?.kind === "details" && /* @__PURE__ */ jsx6(SpaceDetails, { returnFocus: sheet.returnFocus, space, dimensions, upkeepLabel, building, onOpen: (kind) => {
      if (kind === "history") detail.refetch();
      setSheet({ kind, tab: kind === "history" ? "runs" : void 0, returnFocus: sheet.returnFocus });
    }, onClose: () => setSheet(null) }),
    sheet?.kind === "permissions" && /* @__PURE__ */ jsx6(PermissionsSheet, { returnFocus: sheet.returnFocus, ctx, scopeKey, space, onClose: () => setSheet(null), onChanged: () => detail.refetch() }),
    sheet?.kind === "history" && /* @__PURE__ */ jsx6(HistorySheet, { returnFocus: sheet.returnFocus, ctx, scopeKey, space, initialTab: sheet.tab, onClose: () => setSheet(null), onChanged: () => detail.refetch() }),
    sheet?.kind === "upkeep" && /* @__PURE__ */ jsx6(UpkeepSheet, { returnFocus: sheet.returnFocus, ctx, scopeKey, space, onClose: () => setSheet(null), onChanged: () => detail.refetch() }),
    sheet?.kind === "compare" && write && /* @__PURE__ */ jsx6(Drawer, { returnFocus: sheet.returnFocus, title: "Compare record changes", description: "Your submitted change and the latest stored record", onClose: () => setSheet(null), children: /* @__PURE__ */ jsxs6("div", { className: "ls-compare", children: [
      /* @__PURE__ */ jsx6("h2", { children: "Your change" }),
      /* @__PURE__ */ jsx6("pre", { className: "ls-diagnostic", children: JSON.stringify(write.args, null, 2) }),
      /* @__PURE__ */ jsx6("h2", { children: "Updated record" }),
      /* @__PURE__ */ jsx6("pre", { className: "ls-diagnostic", children: JSON.stringify(write.reply?.error?.current, null, 2) })
    ] }) }),
    confirmation && /* @__PURE__ */ jsx6(DecisionDialog, { returnFocus: confirmationTrigger.current, danger: true, title: confirmation === "delete" ? `Delete ${space.name}?` : `Archive ${space.name}?`, description: confirmation === "delete" ? "Delete removes this Space, all its records and revisions permanently and stops future upkeep. Already-running work may finish. Exported copies aren't recalled." : "Archiving pauses future upkeep. Already-running work may finish. Your records and revisions are kept. Restoring this Space does not resume upkeep.", confirmLabel: confirmation === "delete" ? "Delete Space" : "Archive Space", onClose: () => setConfirmation(null), onConfirm: async () => {
      if (confirmation === "delete") {
        await ctx.rest(`${base}?confirm=${encodeURIComponent(sid)}`, { method: "DELETE" });
        forgetSnapshot(scopeKey, sid);
        await queryClient.cancelQueries({ queryKey: ["living-spaces", scopeKey, "spaces"] });
        queryClient.setQueryData(["living-spaces", scopeKey, "spaces"], (list) => list?.spaces ? { ...list, spaces: list.spaces.filter((row) => row.id !== sid) } : list);
        queryClient.invalidateQueries({ queryKey: ["living-spaces", scopeKey, "spaces"] });
        host2.navigate("/spaces");
      } else {
        await ctx.rest(`${base}/archive`, { method: "POST" });
        await syncList(fresh(await detail.refetch()));
      }
    } })
  ] });
}

// src/desktop/ui/styles.js
var styles = `
.ls-root,.ls-sheet,.ls-confirm{--ls-ease-out:cubic-bezier(.23,1,.32,1);--ls-glass:color-mix(in srgb,Canvas 78%,transparent);--ls-glass-strong:color-mix(in srgb,Canvas 92%,transparent);--ls-ease-drawer:cubic-bezier(.32,.72,0,1);--ls-island-shadow:0 0 0 1px rgba(20,20,24,.07),0 1px 0 rgba(255,255,255,.9) inset,0 10px 30px -10px rgba(20,20,24,.25);font:14px/1.5 var(--font-sans,system-ui,sans-serif);color:var(--ui-text-primary);--ls-surface:var(--ui-bg-card,var(--ui-bg-secondary));--ls-line:var(--ui-stroke-secondary);--ls-danger:var(--ui-text-danger,var(--destructive));--ls-warning:var(--ui-text-warning,var(--ui-text-primary));--ls-good:var(--ui-text-success,var(--ui-text-primary))}
.ls-root{height:100%;min-height:0;overflow:auto;background:var(--ui-bg-primary)}
.ls-root *,.ls-sheet *,.ls-confirm *{box-sizing:border-box}
.ls-root :is(button,a,input):focus-visible,.ls-sheet :is(button,a,input):focus-visible,.ls-confirm button:focus-visible{outline:2px solid var(--ui-accent-lit,var(--ui-accent));outline-offset:2px}
.ls-root h1{font-size:20px;font-weight:600;margin:0;letter-spacing:-.01em}.ls-root h2,.ls-sheet h2{font-size:14px;font-weight:600;margin:0}.ls-root p,.ls-sheet p{margin:8px 0}
.ls-page{padding:22px 28px 40px;max-width:1236px;margin:0 auto}.ls-page-heading{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.ls-page-title{display:flex;align-items:baseline;gap:14px;flex:1;min-width:0;flex-wrap:wrap}.ls-gallery h1{font-size:28px;font-weight:600;letter-spacing:-.03em}.ls-secondary{color:var(--ui-text-secondary)}.ls-num{font-variant-numeric:tabular-nums}.ls-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:18px 0 16px}.ls-search{width:260px;max-width:100%;min-height:34px;border-radius:10px!important;background:var(--ls-glass);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow)}.ls-sort{margin-left:auto;font-size:12px;color:var(--ui-text-tertiary,var(--ui-text-secondary))}.ls-toolbar button{min-height:32px}
.ls-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr));gap:22px 18px}.ls-card{display:block;color:inherit;text-decoration:none;border-radius:16px;outline-offset:4px}.ls-card-media{position:relative}.ls-thumb{display:block;aspect-ratio:16/10;width:100%;height:auto;border-radius:14px;overflow:hidden;position:relative;background:var(--ui-bg-secondary);box-shadow:0 0 0 1px var(--ui-stroke-secondary),0 1px 2px rgba(0,0,0,.08);transition:transform 220ms var(--ls-ease-out),box-shadow 220ms var(--ls-ease-out)}.ls-thumb img{display:block;width:100%;height:100%;object-fit:cover;object-position:top left}.ls-thumb-fallback{background:radial-gradient(120% 95% at 0% 0%,color-mix(in srgb,var(--ls-accent) 34%,transparent),transparent 62%),radial-gradient(90% 80% at 100% 100%,color-mix(in srgb,var(--ls-accent) 18%,transparent),transparent 70%),color-mix(in srgb,var(--ls-accent) 7%,var(--ui-bg-secondary))}.ls-thumb-fallback::before{content:'';position:absolute;inset:0;background-image:linear-gradient(color-mix(in srgb,var(--ls-accent) 12%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--ls-accent) 12%,transparent) 1px,transparent 1px);background-size:28px 28px;-webkit-mask-image:radial-gradient(80% 80% at 30% 30%,#000,transparent);mask-image:radial-gradient(80% 80% at 30% 30%,#000,transparent)}.ls-thumb-mark{position:absolute;left:50%;top:50%;translate:-50% -50%;display:grid;place-items:center;width:64px;height:64px;border-radius:18px;color:color-mix(in srgb,var(--ls-accent) 75%,var(--ui-text-primary));background:color-mix(in srgb,var(--ls-accent) 16%,var(--ui-bg-elevated,var(--ui-bg-primary)));box-shadow:0 0 0 1px color-mix(in srgb,var(--ls-accent) 30%,transparent),0 12px 28px -14px color-mix(in srgb,var(--ls-accent) 70%,transparent)}.ls-thumb-mark .codicon{font-size:30px!important}@media(hover:hover) and (pointer:fine){.ls-card:hover .ls-thumb{transform:translateY(-2px);box-shadow:0 0 0 1px var(--ui-stroke-primary,var(--ui-stroke-secondary)),0 14px 30px -12px rgba(0,0,0,.45)}}.ls-card:active .ls-thumb{transform:scale(.99)}.ls-card-state{position:absolute;left:10px;bottom:10px}.ls-card-state .ls-pill{border:0!important;background:var(--ls-glass);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow)}.ls-pin{position:absolute;right:10px;top:10px;display:grid;place-items:center;width:26px;height:26px;border-radius:999px;background:var(--ls-glass);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow)}.ls-card-caption{display:flex;align-items:flex-start;gap:10px;padding:12px 2px 0}.ls-card-caption .ls-tile-small{width:26px;height:26px;border-radius:7px;margin-top:1px}.ls-card-caption .ls-tile .codicon{font-size:14px}.ls-card-text{min-width:0;flex:1}.ls-card-name{font-weight:600;font-size:14.5px;letter-spacing:-.012em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ls-card-description{margin:1px 0 0!important;font-size:12.5px;color:var(--ui-text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ls-card-freshness{margin-top:2px;font-size:12px;color:var(--ui-text-tertiary,var(--ui-text-secondary));overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ls-card.ls-failed .ls-thumb,.ls-card.ls-blocked .ls-thumb{box-shadow:0 0 0 1px color-mix(in srgb,var(--ls-danger) 55%,var(--ui-stroke-secondary))}.ls-card.ls-archived .ls-thumb{filter:saturate(.4);opacity:.85}.ls-newcard{aspect-ratio:16/10;border-radius:14px;border:1px dashed var(--ui-stroke-primary,var(--ui-stroke-secondary));display:grid;place-items:center;text-align:center;padding:16px;font-size:12.5px}.ls-newcard>div{display:grid;justify-items:center;gap:4px}.ls-newcard strong{font-size:14px;font-weight:600}.ls-newcard>div>.codicon{font-size:20px;color:var(--ui-text-secondary)}.ls-newcard .ls-actions{margin-top:8px;justify-content:center}.ls-newcard .ls-prompt{max-width:260px;text-align:left}.ls-facts{margin:10px 0;display:grid;gap:8px;font-size:13px}.ls-facts>div{display:grid;grid-template-columns:118px 1fr;gap:12px}.ls-facts dt{color:var(--ui-text-secondary)}.ls-facts dd{margin:0;overflow-wrap:anywhere}
.ls-tile{display:inline-flex;align-items:center;justify-content:center;flex:none;width:40px;height:40px;border-radius:10px;border:1px solid color-mix(in srgb,var(--ls-accent) 48%,transparent);background:color-mix(in srgb,var(--ls-accent) 22%,var(--ui-bg-primary));color:color-mix(in srgb,var(--ls-accent) 70%,var(--ui-text-primary))}.ls-tile .codicon{font-size:20px}.ls-tile-small{width:32px;height:32px;border-radius:8px}.ls-owner{display:inline-flex;gap:5px;align-items:center;font-size:12px;color:var(--ui-text-secondary)}.ls-avatar{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;font-size:10px;background:var(--ui-bg-quaternary);color:var(--ui-text-primary)}.ls-pin{margin-left:auto}
.ls-pill{display:inline-flex;gap:5px;align-items:center;min-height:22px;padding:2px 8px!important;border:1px solid var(--ls-line);border-radius:999px!important;background:transparent!important;color:var(--ui-text-primary)!important;font-size:12px!important;font-weight:500}.ls-pill.ls-ready,.ls-pill.ls-succeeded,.ls-pill.ls-granted{color:var(--ls-good)!important}.ls-pill.ls-failed,.ls-pill.ls-crashed{color:var(--ls-danger)!important;border-color:currentColor}.ls-pill.ls-blocked,.ls-pill.ls-requested{color:var(--ls-warning)!important}.ls-pill.ls-updating{color:var(--ui-accent-lit,var(--ui-accent))!important}.ls-action{min-height:32px!important;border-radius:8px!important;padding:0 12px!important;font-size:13px!important}.ls-action[aria-disabled=true]{opacity:.55;cursor:not-allowed}.ls-danger{color:var(--ls-danger)!important;border:1px solid color-mix(in srgb,var(--ls-danger) 55%,var(--ls-line))!important}.ls-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px}.ls-footer{font-size:12px;color:var(--ui-text-secondary);margin-top:22px!important}.ls-empty{max-width:780px;margin:55px auto}.ls-empty-tiles{display:flex;gap:12px;justify-content:center}.ls-empty .ls-prompt{margin-top:12px}.ls-prompt{display:flex;align-items:flex-start;gap:10px;padding:12px;border:1px solid var(--ls-line);border-radius:8px;background:var(--ls-surface);font-size:13px}.ls-prompt q{flex:1;user-select:text;overflow-wrap:anywhere}.ls-prompt button{min-height:28px}.ls-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.ls-frame{height:100%;display:flex;flex-direction:column;padding:0 8px 8px;min-height:0}.ls-framebar{height:52px;flex:none;display:flex;align-items:center;gap:8px;padding:0 2px;background:transparent;position:relative;z-index:2}.ls-island{display:flex;align-items:center;gap:2px;height:38px;padding:0 3px;border-radius:12px;min-width:0;background:var(--ls-glass);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow)}.ls-island-identity{flex:0 1 auto;max-width:55%}.ls-frame-actions{margin-left:auto;flex:0 1 auto}.ls-island .ls-action{min-height:32px!important;height:32px;border:0!important;background:transparent!important;box-shadow:none!important;gap:6px}@media(hover:hover) and (pointer:fine){.ls-island .ls-action:hover{background:var(--ui-control-hover-background,color-mix(in srgb,var(--ui-text-primary) 7%,transparent))!important}}.ls-icon-button,.ls-island .ls-overflow{width:32px;min-width:32px;padding:0!important;justify-content:center}.ls-identity{display:flex;align-items:center;gap:8px;min-width:0;padding:0 10px 0 4px}.ls-identity .ls-tile-small{width:22px;height:22px;border-radius:6px}.ls-identity .ls-tile .codicon{font-size:13px}.ls-identity h1{font-size:14px!important;font-weight:600;letter-spacing:-.012em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.ls-frame-meta{display:inline-flex;align-items:center;gap:7px;height:32px;padding:0 10px;font-size:12.5px;color:var(--ui-text-secondary);white-space:nowrap;min-width:0;overflow:hidden}.ls-frame-meta-text{overflow:hidden;text-overflow:ellipsis}.ls-dot{flex:none;width:7px;height:7px;border-radius:50%;background:var(--ls-good);box-shadow:0 0 0 3px color-mix(in srgb,var(--ls-good) 18%,transparent)}.ls-dot[data-tone=danger]{background:var(--ls-danger);box-shadow:0 0 0 3px color-mix(in srgb,var(--ls-danger) 18%,transparent)}.ls-dot[data-tone=busy]{background:var(--ui-accent-lit,var(--ui-accent));box-shadow:none}.ls-dot[data-tone=idle]{background:var(--ui-text-tertiary,var(--ui-text-secondary));box-shadow:none}.ls-save{font-size:12px;display:inline-flex;gap:5px;align-items:center;max-width:220px;padding:0 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ls-save:empty{display:none}.ls-save[data-status=saved]{animation:ls-fade-out 400ms ease 2.6s forwards}@keyframes ls-fade-out{to{opacity:0}}.ls-content{position:relative;display:flex;flex:1;min-height:0;flex-direction:column}.ls-sandbox{flex:1;min-height:0;border-radius:14px;overflow:hidden;position:relative;background:var(--ui-bg-primary);box-shadow:0 0 0 1px var(--ui-stroke-secondary),0 2px 8px rgba(0,0,0,.12)}.ls-mount{height:100%;min-height:0}.ls-stale{filter:saturate(.7)}.ls-notices{position:absolute;right:12px;bottom:12px;z-index:3;width:min(400px,calc(100% - 24px));max-height:calc(100% - 24px);display:flex;flex-direction:column;align-items:flex-end;gap:6px;pointer-events:none}.ls-notices[data-empty]{display:none}.ls-notices>*{pointer-events:auto}.ls-notice-list{width:100%;display:flex;flex-direction:column;gap:6px;min-height:0;max-height:100%}.ls-notice-list[hidden]{display:none}.ls-notice-tools{display:flex;justify-content:flex-end}.ls-notice-minimise{display:inline-flex;align-items:center;gap:4px;height:24px;padding:0 9px;border:0;border-radius:999px;font:inherit;font-size:11.5px;color:var(--ui-text-secondary);cursor:pointer;background:var(--ls-glass);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow)}.ls-notice-stack{display:flex;flex-direction:column;gap:8px;overflow:auto;min-height:0;overscroll-behavior:contain;border-radius:14px}.ls-notice-pill{display:inline-flex;align-items:center;gap:8px;max-width:100%;height:34px;padding:0 12px;border:0;border-radius:999px;font:inherit;font-size:12.5px;font-weight:550;color:var(--ui-text-primary);cursor:pointer;background:var(--ls-glass-strong);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow)}.ls-notice-pill.ls-alert{color:var(--ls-danger)}.ls-notice-count{display:grid;place-items:center;min-width:18px;height:18px;padding:0 5px;border-radius:999px;font-size:11px;background:color-mix(in srgb,currentColor 14%,transparent)}.ls-banner{display:flex;gap:10px;flex:none;padding:12px 14px 12px 12px;border-radius:14px;font-size:13px;color:var(--ui-text-primary);background:var(--ls-glass-strong);-webkit-backdrop-filter:blur(20px) saturate(1.6);backdrop-filter:blur(20px) saturate(1.6);box-shadow:var(--ls-island-shadow);transition:transform 260ms var(--ls-ease-out),opacity 200ms ease}@starting-style{.ls-banner{transform:translateY(10px) scale(.98);opacity:0}}.ls-banner>.codicon{margin-top:2px;color:var(--ui-text-secondary)}.ls-banner .ls-actions{margin-top:10px;gap:6px}.ls-banner .ls-action{min-height:28px!important;height:28px;padding:0 10px!important;font-size:12.5px!important}.ls-banner.ls-failed,.ls-banner.ls-crashed,.ls-banner.ls-conflict{background:color-mix(in srgb,var(--ls-danger) 7%,var(--ls-glass-strong))}.ls-banner.ls-failed>.codicon,.ls-banner.ls-crashed>.codicon,.ls-banner.ls-conflict>.codicon,.ls-banner.ls-failed strong{color:var(--ls-danger)}.ls-banner.ls-blocked>.codicon,.ls-banner.ls-storage>.codicon{color:var(--ls-warning)}.ls-crash{max-width:620px;padding:40px 24px;margin:auto;overflow:auto;max-height:100%}.ls-diagnostic{max-height:180px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:var(--ui-bg-secondary);border:1px solid var(--ls-line);font:12px/1.5 var(--font-mono,monospace)}.ls-building{padding:40px;display:grid;gap:16px}
.ls-sheet{position:fixed!important;top:0!important;right:0!important;left:auto!important;bottom:0!important;transform:none!important;translate:none!important;width:min(460px,100vw)!important;max-width:460px!important;max-height:100dvh!important;height:100dvh!important;border-radius:0!important;background:var(--ui-bg-elevated,var(--ui-surface-background,Canvas))!important;animation:none!important}.ls-sheet-body{display:flex!important;flex-direction:column!important;height:100%;max-height:100dvh!important;padding:0!important;gap:0!important;overflow:hidden!important}.ls-sheet-header{display:flex!important;flex-direction:row!important;justify-content:space-between;align-items:center;padding:16px;border-bottom:1px solid var(--ls-line);flex:none}.ls-sheet-scroll{padding:18px 16px;overflow:auto;min-height:0;flex:1}.ls-disclosure{margin:8px 0!important;font-size:12px;line-height:1.55;max-width:60ch}.ls-internet .ls-row-top{min-height:56px}.ls-internet>.ls-secondary{font-size:12px;max-width:60ch}.ls-switch-value{display:flex;gap:8px;align-items:center}.ls-switch{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:40px;padding:0;border:0;background:none;cursor:pointer;flex:none}.ls-switch-track{display:block;width:40px;height:24px;border-radius:999px;border:1px solid var(--ui-stroke-secondary);background:var(--ui-stroke-secondary);position:relative}.ls-switch-thumb{position:absolute;left:2px;top:2px;width:18px;height:18px;border-radius:50%;background:var(--ui-text-primary);transition:transform 120ms ease-out}.ls-switch[aria-checked=true] .ls-switch-track{background:var(--ui-accent);border-color:var(--ui-accent)}.ls-switch[aria-checked=true] .ls-switch-thumb{transform:translateX(16px);background:var(--ui-text-on-accent,#fff)}.ls-switch[aria-disabled=true]{cursor:not-allowed}.ls-upkeep-prompt{margin:16px 0}.ls-upkeep-prompt h3,.ls-sheet h3{font-size:13px;font-weight:600;margin:0}.ls-upkeep-prompt p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.ls-clamp-six,.ls-clamp-three{display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}.ls-clamp-three{-webkit-line-clamp:3}.ls-upkeep-note{font-size:12px}.ls-upkeep-actions>.ls-danger{margin-left:auto}.ls-upkeep-feedback{font-size:12px;margin:12px 0;outline-offset:2px}.ls-section{margin:0 0 22px}.ls-section-title{font-size:12px!important;font-weight:600!important;letter-spacing:.025em;margin:4px 0 12px!important}.ls-grant,.ls-row{padding:12px;border:1px solid var(--ls-line);border-radius:8px;margin-bottom:12px}.ls-row-top{display:flex;align-items:center;gap:8px;justify-content:space-between}.ls-row-top>strong{display:flex;gap:8px;align-items:center}.ls-pending{background:color-mix(in srgb,var(--ls-warning) 6%,var(--ls-surface))}.ls-audit{padding-left:18px;font-size:12px}.ls-tabs{margin-bottom:16px}.ls-confirm{max-width:520px!important}.ls-compare{display:grid;gap:12px}.ls-directive{padding:14px;border:1px solid var(--ui-stroke-secondary);border-radius:12px;max-width:440px;background:var(--ui-bg-card,var(--ui-bg-secondary));display:grid;gap:10px}.ls-spin{animation:ls-spin 1s linear infinite}@keyframes ls-spin{to{transform:rotate(360deg)}}
.ls-frame[data-header-mode=compact] .ls-island-button .ls-label,.ls-frame[data-header-mode=narrow] .ls-island-button .ls-label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}.ls-frame[data-header-mode=compact] .ls-island-button,.ls-frame[data-header-mode=narrow] .ls-island-button{width:32px;min-width:32px;padding:0!important;justify-content:center}.ls-frame[data-header-mode=narrow] .ls-frame-meta{padding:0 8px}.ls-frame[data-header-mode=narrow] .ls-frame-meta-text{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}.ls-frame[data-header-mode=narrow] .ls-island-identity{max-width:none;flex:1}.ls-frame[data-header-mode=narrow] .ls-save{display:none}.ls-frame[data-header-mode=narrow]{padding:0 6px 6px}.ls-frame[data-header-mode=narrow] .ls-notices{right:8px;left:8px;bottom:8px;width:auto}
@media(max-width:899px){.ls-page{padding:20px 16px}.ls-page-heading{gap:8px}}@media(max-width:359px){.ls-internet .ls-row-top{flex-wrap:wrap}.ls-internet .ls-switch-value{width:100%}}@media(prefers-reduced-motion:reduce){.ls-spin{animation:none}.ls-root *,.ls-sheet *,.ls-confirm *{transition:none!important;animation:none!important}}@media(forced-colors:active){.ls-pill,.ls-card,.ls-tile,.ls-action{border:1px solid CanvasText!important}.ls-switch-track{border:1px solid ButtonText!important;background:Canvas!important}.ls-switch-thumb{background:ButtonText!important}.ls-switch[aria-checked=true] .ls-switch-track{background:Highlight!important}.ls-switch[aria-checked=true] .ls-switch-thumb{background:HighlightText!important}}
.ls-banner>div{min-width:0;flex:1}.ls-oneline{display:block;margin:4px 0 0!important;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ls-answer{margin-top:6px;max-height:min(42vh,360px);overflow:auto;overflow-wrap:anywhere;color:var(--ui-text-primary)}.ls-answer :is(p,ul,ol,pre,h5){margin:0 0 6px!important}.ls-answer h5{font-size:inherit}.ls-answer :is(ul,ol){padding-left:20px}.ls-answer pre{white-space:pre-wrap;padding:8px;background:var(--ui-bg-primary);border:1px solid var(--ls-line);font:12px/1.5 var(--font-mono,monospace)}.ls-answer code{font-family:var(--font-mono,monospace)}
.ls-collapse{display:grid;grid-template-rows:0fr;transition:grid-template-rows 240ms cubic-bezier(.23,1,.32,1)}.ls-collapse>div{min-height:0;overflow:hidden;opacity:0;transition:opacity 160ms ease}.ls-collapse[data-open=true]{grid-template-rows:1fr}.ls-collapse[data-open=true]>div{opacity:1;transition:opacity 200ms ease 60ms}
.ls-meter{height:4px;margin-top:6px;border-radius:4px;background:var(--ls-line);overflow:hidden}.ls-meter>i{display:block;height:100%;background:var(--ls-warning)}
@media(prefers-reduced-motion:reduce){.ls-root .ls-collapse{transition:none!important}.ls-root .ls-collapse>div{transition:opacity 160ms ease!important}}
:root.dark :is(.ls-root,.ls-sheet,.ls-confirm),.dark :is(.ls-root,.ls-sheet,.ls-confirm){--ls-island-shadow:0 0 0 1px rgba(255,255,255,.08),0 1px 0 rgba(255,255,255,.06) inset,0 10px 30px -8px rgba(0,0,0,.6)}.ls-sheet{top:8px!important;right:8px!important;bottom:8px!important;height:auto!important;max-height:calc(100dvh - 16px)!important;width:min(400px,calc(100vw - 16px))!important;max-width:400px!important;border-radius:16px!important;box-shadow:var(--ls-island-shadow),0 24px 60px -20px rgba(0,0,0,.45)!important;animation:ls-sheet-in 280ms var(--ls-ease-drawer) both!important}@keyframes ls-sheet-in{from{transform:translateX(24px);opacity:0}to{transform:none;opacity:1}}.ls-sheet-header{gap:10px;padding:14px 14px 12px 18px!important}.ls-sheet-header h2{flex:1}.ls-sheet-header .ls-tile-small{width:24px;height:24px;border-radius:7px}.ls-sheet-header .ls-tile .codicon{font-size:14px}.ls-detail{padding:14px 0;border-bottom:1px solid var(--ls-line)}.ls-detail:first-child{padding-top:0}.ls-detail:last-child{border-bottom:0}.ls-detail h3{font-size:11.5px!important;font-weight:600;letter-spacing:.02em;color:var(--ui-text-secondary);margin:0 0 6px!important}.ls-detail .ls-actions{margin-top:8px}.ls-note{font-size:12.5px}@media(prefers-reduced-motion:reduce){.ls-root .ls-thumb{transition:opacity 160ms ease!important}.ls-root .ls-card:hover .ls-thumb,.ls-root .ls-card:active .ls-thumb{transform:none}.ls-root .ls-banner{transition:opacity 200ms ease!important}@starting-style{.ls-root .ls-banner{transform:none;opacity:0}}.ls-sheet{animation:ls-fade-in 200ms ease both!important}@keyframes ls-fade-in{from{opacity:0}}}@media(max-width:699px){.ls-page{padding:16px}.ls-gallery h1{font-size:24px}.ls-sort{display:none}.ls-search{width:100%}}@media(prefers-reduced-transparency:reduce){.ls-island,.ls-banner,.ls-notice-pill,.ls-notice-minimise,.ls-search,.ls-pin,.ls-card-state .ls-pill{background:Canvas!important;-webkit-backdrop-filter:none!important;backdrop-filter:none!important}}@media(forced-colors:active){.ls-island,.ls-banner,.ls-notice-pill,.ls-thumb{border:1px solid CanvasText}}
`;

// src/desktop/ui/context.jsx
import { host as host3, useValue } from "@hermes/plugin-sdk";
import { useMemo as useMemo3 } from "react";
var currentScope = () => JSON.stringify([host3.state.connectionId.get(), host3.state.profile.get()]);
function useScopedContext(ctx) {
  const connectionId = useValue(host3.state.connectionId);
  const profile = useValue(host3.state.profile);
  const scopeKey = JSON.stringify([connectionId, profile]);
  return useMemo3(() => ({
    ctx: { ...ctx, rest: scopedRest((path, options) => ctx.rest(path, options), currentScope, scopeKey) },
    scopeKey,
    scope: { connectionId, profile },
    openingSessionRest: (path, options) => ctx.rest(path, options)
  }), [ctx, scopeKey]);
}

// src/desktop/plugin.src.js
function SpacesPage({ ctx }) {
  const scoped = useScopedContext(ctx);
  const [hash, setHash] = useState7(() => typeof location === "undefined" ? "" : location.hash);
  useEffect4(() => {
    const changed = () => setHash(location.hash);
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const sid = routeSpace(hash);
  return jsxs7("div", { className: "ls-root", children: [jsx7("style", { children: styles }), sid ? jsx7(SpaceView, { ...scoped, sid }, `${scoped.scopeKey}:${sid}`) : jsx7(SpacesIndex, { ctx: scoped.ctx, scopeKey: scoped.scopeKey }, scoped.scopeKey)] });
}
function OpenSpaceCard({ ctx, sid }) {
  const scoped = useScopedContext(ctx);
  const query = useQuery6({ queryKey: ["living-spaces", scoped.scopeKey, sid, "detail"], queryFn: () => scoped.ctx.rest(spacePath(sid)), refetchInterval: 2e3 });
  if (!query.data) return query.error ? jsx7(ErrorState6, { title: "This Space could not be loaded", description: query.error.message }) : jsx7("span", { role: "status", children: "Loading Space\u2026" });
  const space = query.data;
  return jsxs7("div", { className: "ls-root ls-directive", children: [jsx7("style", { children: styles }), jsxs7("div", { className: "ls-card-top", children: [jsx7(SpaceTile, { space }), jsxs7("div", { children: [jsx7("strong", { children: space.name }), jsx7(OwnerChip, { owner: space.owner })] })] }), jsxs7("div", { className: "ls-actions", children: [jsx7(StatusPill, { status: spaceStatus(space) }), jsx7("span", { children: `Revision ${space.head_rev}` }), jsx7(Action, { primary: true, onClick: () => host4.navigate(spaceRoute(sid)), children: "Open Space" })] })] });
}
function renderDirective(ctx, attrs) {
  return isSpaceId(attrs?.id) ? jsx7(OpenSpaceCard, { ctx, sid: attrs.id }) : null;
}
var plugin_src_default = {
  id: "living-spaces",
  name: "Spaces",
  register(ctx) {
    bindDesktopOs(ctx.os);
    ctx.registerMany([
      { id: "page", area: ROUTES_AREA, data: { path: "/spaces" }, render: () => jsx7(SpacesPage, { ctx }) },
      { id: "nav", area: SIDEBAR_NAV_AREA, order: 60, data: { path: "/spaces", label: "Spaces", codicon: "layers" } },
      { id: "open-space", area: TRANSCRIPT_DIRECTIVE_AREA, data: { name: "living-space", render: ({ attrs }) => renderDirective(ctx, attrs) } }
    ]);
  }
};
export {
  SpacesPage,
  plugin_src_default as default,
  renderDirective
};
