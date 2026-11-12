// src/desktop/plugin.src.js
import { ROUTES_AREA, SIDEBAR_NAV_AREA, TRANSCRIPT_DIRECTIVE_AREA, ErrorState as ErrorState6, host as host4, useQuery as useQuery6 } from "@hermes/plugin-sdk";
import { useEffect as useEffect3, useState as useState7 } from "react";
import { jsx as jsx7, jsxs as jsxs7 } from "react/jsx-runtime";

// src/desktop/ui/index.jsx
import { EmptyState, ErrorState, SearchField, SegmentedControl, Skeleton, host, useQuery } from "@hermes/plugin-sdk";
import { useState as useState2 } from "react";

// src/desktop/ui/components.jsx
import { Badge, Button, Codicon, CopyButton, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, fmtDateTime, relativeTime, Tip } from "@hermes/plugin-sdk";
import { useRef, useState } from "react";

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
  ready: { label: "Ready", icon: "check", border: "solid" },
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
function needsAttention(space) {
  return space.status !== "archived" && ["failed", "blocked", "crashed"].includes(spaceStatus(space, true));
}
function summaryCounts(spaces) {
  return { active: spaces.filter((s) => s.status !== "archived").length, attention: spaces.filter(needsAttention).length };
}
function visibleSpaces(spaces, search, filter) {
  const q = search.trim().toLocaleLowerCase();
  return spaces.filter((s) => filter === "archived" ? s.status === "archived" : s.status !== "archived" && (filter !== "attention" || needsAttention(s))).filter((s) => `${s.name} ${s.owner}`.toLocaleLowerCase().includes(q)).sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || (b.last_opened_at ?? 0) - (a.last_opened_at ?? 0) || b.updated_at - a.updated_at || a.id.localeCompare(b.id));
}
function headerFacts(space) {
  const f = space.freshness || {};
  if (space.status === "archived") return [{ key: "archive", label: "Archived", at: space.archived_at ?? space.updated_at }];
  if (space.status === "building" || !space.head_rev) return [{ key: "building", label: "Building the first version" }];
  if (f.last_success_at == null) return [{ key: "success", label: ["failed", "blocked"].includes(f.last_attempt_status) ? "No successful update yet" : "Not refreshed yet" }];
  const facts = [{ key: "success", label: "Updated", at: f.last_success_at }];
  if (f.source_as_of != null && Math.abs(f.source_as_of - f.last_success_at) >= 60) facts.push({ key: "source", label: "Source data from", at: f.source_as_of });
  return facts;
}
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
function restoreCopy(space, rev) {
  const kept = space.head_rev > rev + 1 ? `Revisions ${rev + 1}\u2013${space.head_rev} stay in history.` : `Revision ${space.head_rev} stays in history.`;
  return `Restore revision ${rev}? This brings back the Space's earlier code as a new revision ${space.head_rev + 1}. ${kept} Your records, notes and statuses stay as they are now.`;
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
function Freshness({ facts }) {
  return facts.map((fact, index) => /* @__PURE__ */ jsxs("span", { children: [
    index > 0 && " \xB7 ",
    fact.at == null ? fact.label : /* @__PURE__ */ jsxs(Fragment, { children: [
      fact.label,
      " ",
      /* @__PURE__ */ jsx(Time, { at: fact.at, relative: true })
    ] })
  ] }, fact.key));
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
function SpaceTile({ space, small = false }) {
  return /* @__PURE__ */ jsx("span", { className: `ls-tile${small ? " ls-tile-small" : ""}`, style: { "--ls-accent": accentColor(space.accent) }, children: /* @__PURE__ */ jsx(Icon, { name: iconName(space.icon) }) });
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
  return /* @__PURE__ */ jsxs("div", { className: `ls-banner ls-${kind}`, role: ["failed", "blocked", "crashed", "conflict"].includes(kind) ? "alert" : "status", children: [
    /* @__PURE__ */ jsx(Icon, { name: kind === "info" ? "info" : "warning" }),
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("strong", { children: title }),
      children && /* @__PURE__ */ jsx("div", { className: "ls-secondary", children }),
      actions && /* @__PURE__ */ jsx("div", { className: "ls-actions", children: actions })
    ] })
  ] });
}
function Drawer({ title, description, children, onClose, note, returnFocus }) {
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

// src/desktop/ui/index.jsx
import { Fragment as Fragment2, jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
function SpaceCard({ space }) {
  const status = spaceStatus(space);
  const lines = cardLines(space, relative);
  const facts = freshnessFacts(space, absolute);
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
      "aria-label": `${space.name}, ${status === "failed" ? "Failed" : status[0].toUpperCase() + status.slice(1)}, owner ${space.owner}. ${lines.join(". ")}. ${facts.map((f) => `${f.label} ${f.value}`).join(". ")}`,
      children: [
        /* @__PURE__ */ jsxs2("div", { className: "ls-card-top", children: [
          /* @__PURE__ */ jsx2(SpaceTile, { space }),
          /* @__PURE__ */ jsxs2("div", { children: [
            /* @__PURE__ */ jsx2("div", { className: "ls-card-name", children: space.name }),
            /* @__PURE__ */ jsx2(OwnerChip, { owner: space.owner })
          ] }),
          space.pinned ? /* @__PURE__ */ jsxs2("span", { className: "ls-pin", children: [
            /* @__PURE__ */ jsx2(Icon, { name: "pinned" }),
            /* @__PURE__ */ jsx2("span", { className: "ls-sr", children: "Pinned" })
          ] }) : null
        ] }),
        /* @__PURE__ */ jsx2("p", { className: "ls-card-description", children: space.description }),
        /* @__PURE__ */ jsx2("div", { children: /* @__PURE__ */ jsx2(StatusPill, { status }) }),
        /* @__PURE__ */ jsxs2("div", { className: "ls-card-freshness", children: [
          /* @__PURE__ */ jsx2("span", { children: lines[0] }),
          lines[1] && /* @__PURE__ */ jsx2("span", { className: "ls-secondary", children: lines[1] }),
          space.status !== "archived" && status !== "building" && /* @__PURE__ */ jsxs2(Fragment2, { children: [
            space.freshness?.last_attempt_at != null && /* @__PURE__ */ jsxs2("div", { className: "ls-secondary", children: [
              "Last attempt ",
              /* @__PURE__ */ jsx2(Time, { at: space.freshness.last_attempt_at, relative: true }),
              space.freshness.last_attempt_status && ` \xB7 ${space.freshness.last_attempt_status}`
            ] }),
            space.freshness?.source_as_of != null && /* @__PURE__ */ jsxs2("div", { className: "ls-secondary", children: [
              "Source data from ",
              /* @__PURE__ */ jsx2(Time, { at: space.freshness.source_as_of, relative: true })
            ] })
          ] })
        ] })
      ]
    }
  );
}
function FirstSpace({ ctx }) {
  const [notice, setNotice] = useState2("");
  const actions = ctx.listActions?.() || [];
  const action = actions.find((a) => a.id === "session.new") || actions.find((a) => /new.*chat|new.*session/i.test(`${a.id} ${a.label}`));
  function start() {
    const result = ctx.runAction?.(action.id);
    if (!result?.ok) setNotice("A new chat is unavailable. Copy an example prompt and paste it into a normal Hermes chat.");
  }
  return /* @__PURE__ */ jsxs2("div", { className: "ls-empty", children: [
    /* @__PURE__ */ jsxs2("div", { className: "ls-empty-tiles", "aria-hidden": "true", children: [
      /* @__PURE__ */ jsx2(SpaceTile, { space: { accent: "blue", icon: "book" } }),
      /* @__PURE__ */ jsx2(SpaceTile, { space: { accent: "green", icon: "calendar" } }),
      /* @__PURE__ */ jsx2(SpaceTile, { space: { accent: "purple", icon: "graph" } })
    ] }),
    /* @__PURE__ */ jsx2(EmptyState, { title: "Build your first Space in chat", description: "An open canvas for your bots that live in Hermes. Describe what you want in a normal Hermes chat, then open it here." }),
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
  return /* @__PURE__ */ jsxs2("div", { className: "ls-page", "data-testid": "spaces-index", children: [
    /* @__PURE__ */ jsxs2("div", { className: "ls-page-heading", children: [
      /* @__PURE__ */ jsx2("h1", { children: "Spaces" }),
      list.data && /* @__PURE__ */ jsxs2("span", { className: "ls-secondary ls-num", children: [
        counts.active,
        " active \xB7 ",
        counts.attention,
        " need attention"
      ] })
    ] }),
    list.error && /* @__PURE__ */ jsx2(ErrorState, { title: "Spaces could not be loaded", description: list.error.message, children: /* @__PURE__ */ jsx2(Action, { onClick: () => list.refetch(), children: "Try again" }) }),
    list.isLoading ? /* @__PURE__ */ jsx2("div", { className: "ls-grid", "aria-label": "Loading Spaces", children: [1, 2, 3].map((n) => /* @__PURE__ */ jsx2(Skeleton, { style: { height: 240 } }, n)) }) : list.data && !spaces.length ? /* @__PURE__ */ jsx2(FirstSpace, { ctx }) : list.data ? /* @__PURE__ */ jsxs2(Fragment2, { children: [
      /* @__PURE__ */ jsxs2("div", { className: "ls-toolbar", children: [
        /* @__PURE__ */ jsx2(SearchField, { value: search, onChange: setSearch, placeholder: "Search Spaces or owner", "aria-label": "Search Spaces or owner", variant: "box", containerClassName: "ls-search" }),
        /* @__PURE__ */ jsx2(SegmentedControl, { value: filter, onChange: setFilter, sizing: "content", options: [{ id: "all", label: "All" }, { id: "attention", label: `Needs attention \xB7 ${counts.attention}` }, { id: "archived", label: "Archived" }] }),
        /* @__PURE__ */ jsx2("span", { className: "ls-sort", children: "Sorted by recently used" })
      ] }),
      visible.length ? /* @__PURE__ */ jsx2("div", { className: "ls-grid", role: "list", "aria-label": "Spaces", children: visible.map((s) => /* @__PURE__ */ jsx2("div", { role: "listitem", children: /* @__PURE__ */ jsx2(SpaceCard, { space: s }) }, s.id)) }) : /* @__PURE__ */ jsx2("div", { role: "status", children: /* @__PURE__ */ jsx2(EmptyState, { title: search ? `No Spaces match \u201C${search}\u201D. Try another name or owner.` : filter === "attention" ? "Nothing needs attention." : "No archived Spaces." }) })
    ] }) : null,
    /* @__PURE__ */ jsx2("p", { className: "ls-footer", children: "Spaces are built and changed in a normal chat. Ask your agent to \u201Cbuild\u2026\u201D, \u201Cchange\u2026\u201D or \u201Ckeep \u2026 current\u201D." })
  ] });
}

// src/desktop/ui/space.jsx
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, ErrorState as ErrorState5, Skeleton as Skeleton5, host as host2, useQuery as useQuery5 } from "@hermes/plugin-sdk";
import { useEffect as useEffect2, useLayoutEffect, useRef as useRef4, useState as useState6 } from "react";

// src/desktop/ui/history.jsx
import { Badge as Badge2, EmptyState as EmptyState2, ErrorState as ErrorState2, Skeleton as Skeleton2, Tabs, TabsList, TabsTrigger, useQuery as useQuery2 } from "@hermes/plugin-sdk";
import { useState as useState3 } from "react";
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
  return /* @__PURE__ */ jsxs3("article", { className: "ls-row", children: [
    /* @__PURE__ */ jsxs3("div", { className: "ls-row-top", children: [
      /* @__PURE__ */ jsxs3("strong", { children: [
        "Revision ",
        revision.rev
      ] }),
      revision.rev === space.head_rev ? /* @__PURE__ */ jsx3(Badge2, { variant: "outline", children: "Current" }) : /* @__PURE__ */ jsx3(Action, { onClick: () => onRestore(revision.rev), children: "Restore\u2026" })
    ] }),
    /* @__PURE__ */ jsx3("p", { className: "ls-secondary", children: /* @__PURE__ */ jsx3(Time, { at: revision.created_at }) }),
    /* @__PURE__ */ jsxs3("p", { children: [
      revision.author,
      " \xB7 ",
      revision.summary
    ] })
  ] });
}
function HistorySheet({ ctx, scopeKey = null, space, onClose, onChanged, initialTab = "runs", returnFocus }) {
  const [tab, setTab] = useState3(initialTab);
  const [restore, setRestore] = useState3(null);
  const base = spacePath(space.id);
  const runs = useQuery2({ queryKey: ["living-spaces", scopeKey, space.id, "runs"], queryFn: () => ctx.rest(`${base}/runs`), refetchInterval: 2e3 });
  const revisions = useQuery2({ queryKey: ["living-spaces", scopeKey, space.id, "revisions"], queryFn: () => ctx.rest(`${base}/revisions`), refetchInterval: 2e3 });
  const query = tab === "runs" ? runs : revisions;
  return /* @__PURE__ */ jsxs3(Fragment3, { children: [
    /* @__PURE__ */ jsxs3(Drawer, { title: "History & revisions", description: `History and code revisions for ${space.name}`, onClose, returnFocus, children: [
      /* @__PURE__ */ jsx3(Tabs, { value: tab, onValueChange: setTab, className: "ls-tabs", children: /* @__PURE__ */ jsxs3(TabsList, { "aria-label": "History & revisions", children: [
        /* @__PURE__ */ jsx3(TabsTrigger, { id: "ls-runs-tab", "aria-controls": "ls-runs-panel", value: "runs", children: "Run history" }),
        /* @__PURE__ */ jsx3(TabsTrigger, { id: "ls-revisions-tab", "aria-controls": "ls-revisions-panel", value: "revisions", children: "Revisions" })
      ] }) }),
      /* @__PURE__ */ jsxs3("div", { role: "tabpanel", tabIndex: 0, id: `ls-${tab === "runs" ? "runs" : "revisions"}-panel`, "aria-labelledby": `ls-${tab === "runs" ? "runs" : "revisions"}-tab`, children: [
        tab === "revisions" && /* @__PURE__ */ jsx3("p", { className: "ls-secondary", children: "Restoring code does not rewind records. Your records, notes and statuses stay as they are now." }),
        query.error ? /* @__PURE__ */ jsx3(ErrorState2, { title: "History could not be loaded", description: errorText(query.error), children: /* @__PURE__ */ jsx3(Action, { onClick: () => query.refetch(), children: "Try again" }) }) : query.isLoading ? /* @__PURE__ */ jsx3(Skeleton2, { style: { height: 180 } }) : !query.data?.length ? /* @__PURE__ */ jsx3(EmptyState2, { title: tab === "runs" ? "No refresh runs yet." : "No revisions yet." }) : query.data.map((row) => tab === "runs" ? /* @__PURE__ */ jsx3(RunRow, { run: row }, row.id) : /* @__PURE__ */ jsx3(RevisionRow, { revision: row, space, onRestore: setRestore }, row.rev))
      ] })
    ] }),
    restore != null && /* @__PURE__ */ jsx3(DecisionDialog, { title: `Restore revision ${restore}?`, description: restoreCopy(space, restore), confirmLabel: "Restore as new revision", onClose: () => setRestore(null), onConfirm: async () => {
      await ctx.rest(`${base}/revisions/${restore}/restore`, { method: "POST" });
      await revisions.refetch();
      await onChanged();
    } })
  ] });
}

// src/desktop/ui/permissions.jsx
import { ErrorState as ErrorState3, Skeleton as Skeleton3, useQuery as useQuery3 } from "@hermes/plugin-sdk";
import { useRef as useRef2, useState as useState4 } from "react";
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
  const lock = useRef2(false);
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
import { useEffect, useRef as useRef3, useState as useState5 } from "react";
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
  const lock = useRef3(false);
  const feedbackNode = useRef3(null);
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
  const archived = space.status === "archived";
  const running = isRunning(data);
  const unavailable = !!data?.error || !!query.error || !!link && !job && !data?.missing;
  const blocked = archived || unavailable || !!busy;
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  useEffect(() => {
    if (data || query.error) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), 8e3);
    return () => clearTimeout(timer);
  }, [!!data, !!query.error]);
  useEffect(() => {
    if (!recentAction) return;
    const timer = setTimeout(() => setRecentAction(0), 6e4);
    return () => clearTimeout(timer);
  }, [recentAction]);
  useEffect(() => {
    if (!feedback || busy) return;
    const timer = setTimeout(() => setFeedback(""), 8e3);
    return () => clearTimeout(timer);
  }, [feedback, busy]);
  async function act(action) {
    if (lock.current) return;
    if (blocked || action === "run" && running) {
      if (action === "remove") throw new Error("Upkeep is unavailable. Reload the native state before removing it.");
      return;
    }
    lock.current = true;
    setBusy(action);
    setError("");
    setFeedback(action === "run" ? "Starting\u2026" : "Working\u2026");
    setRecentAction(Date.now());
    try {
      const response = await ctx.rest(`${base}/upkeep`, { method: "POST", body: { action } });
      if (action === "run" && response?.dispatch?.job?.execution_success === false) throw new Error(response.dispatch.job.execution_error || "Hermes reports that this execution failed.");
      const [current] = await Promise.all([query.refetch(), onChanged?.()]);
      if (current?.error || current?.data?.error) throw new Error(`The action was submitted, but the current native state couldn't be loaded. ${errorText(current.error || current.data.error)}`);
      if (current?.data && (action === "pause" && current.data.job?.enabled !== false || action === "resume" && current.data.job?.enabled !== true || action === "remove" && current.data.link)) throw new Error("Hermes has not confirmed the requested state.");
      const next = toSeconds(current?.data?.job?.next_run_at);
      setFeedback(action === "run" ? "Run requested. Execution and delivery are not confirmed by this request; review the last-result metadata below." : action === "pause" ? "Paused. Future runs stop until you resume. Already-running work may finish." : action === "resume" ? `Resumed.${next != null ? ` Next run ${absolute(next)}.` : ""}` : `Upkeep removed. ${space.name} is unchanged.`);
    } catch (e) {
      setFeedback("");
      setError(`${action === "run" ? "Couldn't start the run." : action === "pause" ? "Couldn't pause upkeep." : action === "resume" ? "Couldn't resume upkeep." : "Couldn't remove upkeep."} ${errorText(e)} Review the current native state before trying again.`);
      await query.refetch();
      if (action === "remove") throw e;
    } finally {
      lock.current = false;
      setBusy(null);
    }
  }
  const removeButton = /* @__PURE__ */ jsx5(Action, { danger: true, "aria-disabled": blocked, onClick: () => !blocked && setConfirm(true), children: data?.missing ? "Remove link" : "Remove" });
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
    archived && /* @__PURE__ */ jsx5("p", { children: "Archived Spaces don't run upkeep. Restore the Space to use it. Already-running work may finish." }),
    !link ? /* @__PURE__ */ jsxs5(Fragment5, { children: [
      /* @__PURE__ */ jsx5("h3", { children: "No upkeep yet" }),
      /* @__PURE__ */ jsxs5("p", { children: [
        "This Space isn't updated automatically. Ask ",
        space.owner,
        " in chat to set up upkeep as a Hermes cron job."
      ] }),
      ask
    ] }) : data.missing ? /* @__PURE__ */ jsxs5(Fragment5, { children: [
      /* @__PURE__ */ jsx5(StatusPill, { status: "blocked", label: "Job missing" }),
      /* @__PURE__ */ jsxs5(Banner, { kind: "blocked", title: "Hermes no longer has this job", actions: removeButton, children: [
        "Nothing will run. Ask ",
        space.owner,
        " in chat to schedule upkeep again."
      ] }),
      ask
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
        /* @__PURE__ */ jsx5(Action, { primary: !job.enabled, "aria-busy": busy === (job.enabled ? "pause" : "resume"), "aria-disabled": blocked, icon: job.enabled ? "debug-pause" : "play", onClick: () => act(job.enabled ? "pause" : "resume"), children: job.enabled ? "Pause" : "Resume" }),
        removeButton
      ] })
    ] }) : !data.error && /* @__PURE__ */ jsx5(Banner, { kind: "blocked", title: "Waiting for the native job state", actions: /* @__PURE__ */ jsx5(Action, { onClick: () => query.refetch(), children: "Try again" }), children: "Controls are unavailable until Hermes responds." })
  ] });
  return /* @__PURE__ */ jsxs5(Fragment5, { children: [
    /* @__PURE__ */ jsxs5(Drawer, { title: `Upkeep \xB7 ${space.name}`, description: "The Hermes cron job that keeps this Space current", onClose, returnFocus, children: [
      body,
      /* @__PURE__ */ jsx5("div", { ref: feedbackNode, tabIndex: -1, role: "status", "aria-live": "polite", className: "ls-upkeep-feedback", children: feedback }),
      error && /* @__PURE__ */ jsx5(Banner, { kind: "failed", title: error }),
      job?.uses_model === true && job.prompt && !data?.unavailable?.prompt && /* @__PURE__ */ jsx5("div", { className: "ls-section", children: /* @__PURE__ */ jsx5(Action, { "aria-expanded": fullPrompt, "aria-controls": "ls-upkeep-prompt", onClick: () => setFullPrompt(!fullPrompt), children: fullPrompt ? "Show less" : "Show full prompt" }) }),
      job?.last_error && ["failed", "error"].includes(job.last_status) && /* @__PURE__ */ jsxs5(Banner, { kind: "failed", title: `Last run failed${lastAt != null ? ` ${absolute(lastAt)}` : ""}`, actions: /* @__PURE__ */ jsxs5(Fragment5, { children: [
        /* @__PURE__ */ jsx5(Action, { "aria-disabled": blocked || running, onClick: () => act("run"), children: "Run now" }),
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
    confirm && /* @__PURE__ */ jsx5(DecisionDialog, { danger: true, successFocus: feedbackNode, title: `Remove upkeep for ${space.name}?`, description: "This deletes the Hermes cron job. Future runs stop, but already-running work may finish. The Space and its data are kept.", cancelLabel: "Keep upkeep", confirmLabel: "Remove", onClose: () => setConfirm(false), onConfirm: () => act("remove") })
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

// src/desktop/ui/session.mjs
var errorCode = (error) => [error?.error?.code, error?.body?.error?.code, error?.message, String(error)].filter(Boolean).join(" ");
function createSpaceSession({ rest, backend, sid, container, mount, onEvent, host: host5, onAction = () => {
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
  const failures = /* @__PURE__ */ new Map();
  const retries = /* @__PURE__ */ new Map();
  const publish = (event) => onWrite(failures.values().next().value || (pendingWrites ? { status: "saving" } : event));
  const actions = host5 ? createBotActions({
    host: host5,
    backend: scope,
    isActive: () => !closed && active(),
    post: (operation, body) => scopedRequest(`${base}/actions/${operation}`, { method: "POST", body: { ...body, session } }),
    onStatus: (status) => {
      if (closed) return;
      onAction(status);
      mounted?.postEvent?.("bot.status", status);
    }
  }) : null;
  const close = () => {
    if (!session) return Promise.resolve();
    closePromise ??= (async () => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          if (active()) return await rest(`${base}/sessions/${encodeURIComponent(session)}`, { method: "DELETE", timeoutMs: 5e3 });
          const route = await profileRoute(host5, scope);
          const result = await host5.requestProfile(route, "plugin.living-spaces.close_session", { space_id: sid, session }, 5e3);
          if (result?.closed !== true) throw new Error(result?.error?.message || "Space session cleanup was not confirmed");
          return result;
        } catch (error) {
          if (/session_invalid/.test(errorCode(error))) return { closed: true };
          onCloseError(error);
          if (attempt === 3) throw error;
          await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
        }
      }
    })().catch((error) => {
      closePromise = null;
      throw error;
    });
    return closePromise;
  };
  const call = async (op, args, retryToken) => {
    if (closed || !active()) return { ok: false, error: { code: "session_invalid", message: "This Space session is closed" } };
    if (op === "bot.request") {
      if (!actions) return { ok: false, error: { code: "blocked", message: "Native bot actions are unavailable" } };
      const result = await actions.request(args);
      if (closed || !active()) return { ok: false, error: { code: "session_invalid", message: "This Space session is closed" } };
      return { ok: true, result };
    }
    const writing = ["data.put", "data.delete", "data.batch"].includes(op);
    if (writing && retryToken == null) {
      args = structuredClone(args);
      const identify = (put) => {
        if (put.id == null) {
          put.id = "r_" + Array.from(crypto.getRandomValues(new Uint8Array(6)), (byte) => byte.toString(16).padStart(2, "0")).join("");
          put.base_rev = 0;
        }
      };
      if (op === "data.put") identify(args);
      if (op === "data.batch" && Array.isArray(args.ops)) args.ops.forEach((item) => {
        if (item?.op === "put") identify(item);
      });
    }
    const token = retryToken ?? ++nextWrite;
    if (writing) {
      pendingWrites++;
      publish({ status: "saving", op, args });
    }
    let reply;
    let unknown = false;
    try {
      reply = await scopedRequest(`${base}/bridge`, { method: "POST", body: { session, op, args } });
    } catch (error) {
      unknown = true;
      reply = { ok: false, error: { code: "unavailable", message: error.message || String(error) } };
    }
    if (closed || !active()) return { ok: false, error: { code: "session_invalid", message: "This Space session is closed" } };
    if (writing) {
      pendingWrites--;
      const retry = (next) => {
        if (retries.has(token)) return retries.get(token);
        const promise = call(op, next || args, token).finally(() => retries.delete(token));
        retries.set(token, promise);
        return promise;
      };
      unknown ||= failures.get(token)?.status === "unknown";
      const event = { status: reply.ok ? "saved" : reply.error?.code === "conflict" ? "conflict" : unknown ? "unknown" : "failed", token, op, args, reply, at: Date.now() / 1e3, retry };
      if (reply.ok) failures.delete(token);
      else failures.set(token, event);
      publish(event);
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
    checkAction() {
      return actions?.check();
    },
    retryAction() {
      return actions?.retry();
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
  "bot.request": null,
  refresh: null,
  "runs.list": null,
  log: "logs"
});
var MAX_REQUEST_SIZE = 1024 * 1024;
function requestError(message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) return { code: "invalid", message: "request must be an object" };
  if (message.v !== BRIDGE_VERSION) return { code: "invalid", message: "unsupported bridge version" };
  if (!Number.isSafeInteger(message.id)) return { code: "invalid", message: "id must be an integer" };
  if (typeof message.op !== "string") return { code: "invalid", message: "op must be a string" };
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
  const overflow = () => {
    if (overflowReported) return;
    overflowReported = true;
    onEvent({ kind: "log-overflow" });
  };
  const stop = () => {
    if (state === "closed") return;
    state = "closed";
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
      if (!Array.isArray(args.entries) || Array.from(args.entries).some((entry) => !entry || typeof entry.level !== "string" || typeof entry.msg !== "string")) {
        return reject({ code: "invalid", message: "Invalid log entries" });
      }
      if (args.entries.length > 50) return reject({ code: "limit", message: "Log batch exceeds 50 entries", limit: 50, actual: args.entries.length });
      const oversized = args.entries.find((entry) => entry.msg.length > 4e3);
      if (oversized) return reject({ code: "limit", message: "Log message exceeds 4000 characters", limit: 4e3, actual: oversized.msg.length });
      if (args.entries.some((entry) => entry.level === "warn" && entry.msg.startsWith("Space log overflow:"))) overflow();
      const now = performance.now();
      if (now - lastLog < 500) {
        overflow();
        reply({ ok: true, result: { stored: 0 } });
        return;
      }
      lastLog = now;
      args = { entries: args.entries };
    }
    try {
      const result = await call(m.op, args);
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

// src/desktop/ui/space.jsx
import { Fragment as Fragment6, jsx as jsx6, jsxs as jsxs6 } from "react/jsx-runtime";
function useHeaderMode(hasSpace) {
  const frame = useRef4(null);
  const [mode, setMode] = useState6("narrow");
  useLayoutEffect(() => {
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
function SaveStatus({ write, announcement }) {
  const labels = { saving: "Saving\u2026", saved: `Saved ${write?.at ? absolute(write.at) : ""}`, failed: "Not saved \u2014 this change was rejected", unknown: "Save outcome unknown \u2014 the change may have been stored", conflict: "Conflict \u2014 this record changed elsewhere" };
  return /* @__PURE__ */ jsxs6("span", { className: "ls-save", role: "status", "aria-live": "polite", "aria-atomic": "true", children: [
    write && /* @__PURE__ */ jsxs6(Fragment6, { children: [
      /* @__PURE__ */ jsx6(Icon, { name: write.status === "saving" ? "refresh" : ["failed", "unknown", "conflict"].includes(write.status) ? "warning" : "check", spin: write.status === "saving" }),
      labels[write.status]
    ] }),
    announcement && /* @__PURE__ */ jsx6("span", { children: announcement })
  ] });
}
function WriteBanner({ write, setWrite, onCompare, onUpdated, onDismiss }) {
  if (!write || !["failed", "unknown", "conflict"].includes(write.status)) return null;
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
function SpaceView({ ctx, scopeKey = null, scope, sessionRest, sid }) {
  const { connectionId, profile } = scope || { connectionId: host2.state.connectionId.get(), profile: host2.state.profile.get() };
  const base = spacePath(sid);
  const detail = useQuery5({ queryKey: ["living-spaces", scopeKey, sid, "detail"], queryFn: () => ctx.rest(base), refetchInterval: 2e3, notifyOnChangeProps: ["data", "error", "dataUpdatedAt"] });
  const space = detail.data;
  const [frame, headerMode] = useHeaderMode(!!space);
  const [sheet, setSheet] = useState6(null);
  const [confirmation, setConfirmation] = useState6(null);
  const [reload, setReload] = useState6(0);
  const [crash, setCrash] = useState6(null);
  const [ignoredCrashRev, setIgnoredCrashRev] = useState6(null);
  const [write, setWrite] = useState6(null);
  const [announcement, setAnnouncement] = useState6("");
  const [actionError, setActionError] = useState6("");
  const [botAction, setBotAction] = useState6(null);
  const [refreshPending, setRefreshPending] = useState6(false);
  const [ready, setReady] = useState6(false);
  const refreshLock = useRef4(false);
  const actionLock = useRef4(false);
  const content = useRef4(null);
  const overflow = useRef4(null);
  const confirmationTrigger = useRef4(null);
  const controller = useRef4(null);
  const cursor = useRef4(0);
  const seenRun = useRef4(null);
  const grantsKey = JSON.stringify(space?.grants || []);
  const hasData = space?.grants?.some((grant) => grant.capability === "data" && grant.status === "granted") === true;
  const building = !space || space.status === "building" || !space.head_rev;
  const archived = space?.status === "archived";
  const remoteCrash = space?.attention?.kind === "crashed" && ignoredCrashRev !== space?.head_rev;
  const status = crash || remoteCrash ? "crashed" : space ? spaceStatus(ignoredCrashRev === space.head_rev ? { ...space, attention: null } : space, true) : "building";
  const lastRun = space?.recent_runs?.[0];
  const runKey = JSON.stringify(lastRun || null);
  useEffect2(() => {
    let disposed = false;
    ctx.rest(`${base}/opened`, { method: "POST" }).catch((e) => {
      if (!disposed) setActionError(`Could not mark this Space as opened. ${errorText(e)}`);
    });
    return () => {
      disposed = true;
    };
  }, [ctx, base]);
  useEffect2(() => {
    if (building || archived || crash || remoteCrash || !content.current) return;
    let disposed = false;
    let errors = 0;
    cursor.current = 0;
    setReady(false);
    setBotAction(null);
    const backend = { connectionId, profile };
    const session = createSpaceSession({
      backend,
      host: host2,
      onAction: (event) => !disposed && setBotAction(event),
      rest: sessionRest || ((path, options) => ctx.rest(path, options)),
      sid,
      container: content.current,
      mount: mountSpace,
      onWrite: (event) => !disposed && setWrite(event),
      onEvent: (event) => {
        if (disposed) return;
        if (event.kind === "reloaded") setReload((n) => n + 1);
        if (event.kind === "booted") setReady(true);
        if (event.kind === "denied") setAnnouncement("A Space request was denied. Review Permissions for access details.");
        if (event.kind === "log-overflow") setAnnouncement("Some diagnostic entries were dropped because the log limit was reached.");
        if (event.kind === "error" && (event.fatal || event.phase === "load" || /load|entry|boot/i.test(event.message || "") || ++errors >= 3)) setCrash(diagnosticText(`${event.message || event.error || "Repeated runtime errors"}${event.location || event.filename ? `
Location: ${event.location || event.filename}` : ""}`));
      }
    });
    controller.current = session;
    session.ready.then(() => {
      if (!disposed) setReady(true);
    }).catch((e) => {
      if (!disposed) setCrash(diagnosticText(errorText(e)));
    });
    return () => {
      disposed = true;
      setReady(false);
      session.postEvent("session.closed", { reason: "Space view closed or reloaded" });
      session.destroy().catch((e) => host2.notifyError(e, "A Space session could not be closed after retries."));
      if (controller.current === session) controller.current = null;
    };
  }, [ctx, sessionRest, connectionId, profile, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload]);
  const changes = useQuery5({ queryKey: ["living-spaces", scopeKey, sid, "changes", space?.head_rev, grantsKey, reload], queryFn: () => ctx.rest(`${base}/changes?since=${cursor.current}`), enabled: hasData && ready && !building && !archived && !crash, refetchInterval: 1500 });
  useEffect2(() => {
    if (!hasData || !ready || !changes.data || !controller.current) return;
    const page = advanceCursor(cursor.current, changes.data);
    if (page.changes.length) {
      controller.current.postEvent("data.changed", page);
      cursor.current = page.seq;
    }
  }, [hasData, ready, changes.data, changes.dataUpdatedAt]);
  useEffect2(() => {
    if (!lastRun) return;
    if (ready) controller.current?.postEvent("run.updated", lastRun);
    if (seenRun.current && seenRun.current !== runKey && !inFlight(lastRun.status)) setAnnouncement(lastRun.status === "succeeded" ? `Refresh succeeded: ${runResult(lastRun)}` : `Refresh ${lastRun.status}: ${runResult(lastRun)}`);
    seenRun.current = runKey;
  }, [runKey, ready]);
  useEffect2(() => {
    if (crash && space?.head_rev) {
      setCrash(null);
    }
  }, [space?.head_rev]);
  async function refresh() {
    if (refreshLock.current || refreshPending || status === "updating" || inFlight(lastRun?.status) || refreshReason(space)) return;
    refreshLock.current = true;
    setRefreshPending(true);
    setActionError("");
    setAnnouncement("Refreshing\u2026");
    try {
      const run = await ctx.rest(`${base}/refresh`, { method: "POST" });
      if (run?.kind === "cron") setAnnouncement("Refresh started in Hermes");
      else {
        controller.current?.postEvent("run.updated", run);
        if (!inFlight(run.status)) setAnnouncement(`Refresh ${run.status}: ${runResult(run)}`);
      }
      await detail.refetch();
    } catch (e) {
      setActionError(errorText(e));
      setAnnouncement("Refresh failed");
    } finally {
      refreshLock.current = false;
      setRefreshPending(false);
    }
  }
  async function act(path, body) {
    if (actionLock.current) return;
    actionLock.current = true;
    setActionError("");
    try {
      await ctx.rest(`${base}/${path}`, { method: "POST", ...body ? { body } : {} });
      await detail.refetch();
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
  const openHistory = (tab) => openSheet("history", tab || "runs");
  const askConfirmation = (kind) => {
    confirmationTrigger.current = opener();
    setConfirmation(kind);
  };
  const crashMessage = diagnosticText(crash || space.attention?.message || "The Space hit repeated runtime errors.");
  return /* @__PURE__ */ jsxs6("div", { ref: frame, className: "ls-frame", "data-header-mode": headerMode, "data-testid": "space-view", children: [
    /* @__PURE__ */ jsxs6("header", { className: "ls-framebar", children: [
      /* @__PURE__ */ jsx6(Action, { icon: "chevron-left", onClick: () => host2.navigate("/spaces"), children: "Spaces" }),
      /* @__PURE__ */ jsxs6("div", { className: "ls-identity", children: [
        /* @__PURE__ */ jsx6(SpaceTile, { space, small: true }),
        /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsxs6("div", { className: "ls-name-row", children: [
            /* @__PURE__ */ jsx6("h1", { children: space.name }),
            /* @__PURE__ */ jsx6(StatusPill, { status })
          ] }),
          /* @__PURE__ */ jsxs6("div", { className: "ls-frame-meta", children: [
            /* @__PURE__ */ jsx6(OwnerChip, { owner: space.owner }),
            /* @__PURE__ */ jsxs6("span", { children: [
              " \xB7 ",
              /* @__PURE__ */ jsx6(Freshness, { facts: headerFacts(space) })
            ] })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxs6("div", { className: "ls-frame-actions", children: [
        /* @__PURE__ */ jsx6(SaveStatus, { write, announcement }),
        !building && /* @__PURE__ */ jsx6("div", { className: "ls-upkeep-action", children: /* @__PURE__ */ jsx6(Action, { icon: "watch", onClick: () => openSheet("upkeep"), children: !upkeep ? "Upkeep: none" : upkeep.missing ? "Upkeep: job missing" : upkeep.enabled === true ? "Upkeep: on" : upkeep.enabled === false ? "Upkeep: paused" : "Upkeep" }) }),
        /* @__PURE__ */ jsx6("span", { className: "ls-wide-only", children: /* @__PURE__ */ jsx6(Action, { onClick: () => openHistory(), children: "History" }) }),
        space.grants?.some((grant) => grant.capability === "net" && grant.status === "granted") && /* @__PURE__ */ jsx6(Action, { icon: "globe", onClick: () => openSheet("permissions"), children: "Internet on" }),
        !building && /* @__PURE__ */ jsxs6(Fragment6, { children: [
          /* @__PURE__ */ jsx6(Action, { onClick: () => openSheet("permissions"), children: "Permissions" }),
          /* @__PURE__ */ jsx6(DisabledReason, { reason, children: /* @__PURE__ */ jsx6(Action, { primary: true, icon: "refresh", "aria-busy": busy, "aria-disabled": !!reason || busy, title: reason || void 0, onClick: refresh, children: busy ? "Refreshing\u2026" : "Refresh now" }) })
        ] }),
        /* @__PURE__ */ jsxs6(DropdownMenu, { children: [
          /* @__PURE__ */ jsx6(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsx6(Action, { ref: overflow, className: "ls-action ls-overflow", "aria-label": "More Space actions", icon: "ellipsis" }) }),
          /* @__PURE__ */ jsxs6(DropdownMenuContent, { align: "end", children: [
            headerMode !== "wide" && /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openHistory(), children: "History" }),
            !building && /* @__PURE__ */ jsxs6(Fragment6, { children: [
              headerMode === "narrow" && /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openSheet("upkeep"), children: "Upkeep" }),
              /* @__PURE__ */ jsx6(DropdownMenuSeparator, {}),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => act("pin", { pinned: !space.pinned }), children: space.pinned ? "Unpin Space" : "Pin Space" }),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => archived ? act("unarchive") : askConfirmation("archive"), children: archived ? "Restore Space" : "Archive Space\u2026" }),
              archived && /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => askConfirmation("delete"), children: "Delete\u2026" })
            ] })
          ] })
        ] })
      ] })
    ] }),
    botAction && /* @__PURE__ */ jsxs6(Banner, { kind: ["failed", "offline", "unknown"].includes(botAction.status) ? "failed" : void 0, title: `Bot request: ${botAction.status}`, actions: /* @__PURE__ */ jsxs6(Fragment6, { children: [
      /* @__PURE__ */ jsx6(Action, { onClick: () => controller.current?.checkAction(), children: "Check bot status" }),
      botAction.activationId && ["unknown", "failed", "offline"].includes(botAction.status) && /* @__PURE__ */ jsx6(Action, { onClick: () => controller.current?.retryAction(), children: "Retry same request" })
    ] }), children: [
      /* @__PURE__ */ jsx6("span", { role: "status", "aria-live": "polite", children: botAction.message }),
      botAction.answer && /* @__PURE__ */ jsx6("p", { children: botAction.answer })
    ] }),
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
    ] }) : null,
    /* @__PURE__ */ jsx6("section", { className: "ls-content", "aria-label": "Space content", children: /* @__PURE__ */ jsx6("div", { className: `ls-sandbox${status === "failed" ? " ls-stale" : ""}`, children: building ? /* @__PURE__ */ jsxs6("div", { className: "ls-building", children: [
      /* @__PURE__ */ jsxs6("p", { role: "status", children: [
        space.owner,
        " is building the first version. This opens automatically when it's ready."
      ] }),
      /* @__PURE__ */ jsx6(Skeleton5, { style: { height: 100 } }),
      /* @__PURE__ */ jsx6(Skeleton5, { style: { height: 180 } })
    ] }) : status === "crashed" ? /* @__PURE__ */ jsxs6("div", { className: "ls-crash", children: [
      /* @__PURE__ */ jsx6(ErrorState5, { title: `${space.name} stopped working`, description: "The Space hit an error and was stopped. Your records are safe and weren't changed by the crash." }),
      /* @__PURE__ */ jsx6("pre", { className: "ls-diagnostic", children: `Revision ${space.head_rev}
${crashMessage}
Logged to this Space only. Common credential values redacted.` }),
      /* @__PURE__ */ jsxs6("div", { className: "ls-actions", children: [
        /* @__PURE__ */ jsx6(Action, { primary: true, onClick: () => {
          setCrash(null);
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
    ] }) : archived ? /* @__PURE__ */ jsx6("div", { className: "ls-building", children: /* @__PURE__ */ jsx6("p", { children: "Restore Space to open its content. Your records and revisions are kept." }) }) : /* @__PURE__ */ jsx6("div", { ref: content, className: "ls-mount", "data-testid": "space-host" }) }) }),
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
        host2.navigate("/spaces");
      } else {
        await ctx.rest(`${base}/archive`, { method: "POST" });
        await detail.refetch();
      }
    } })
  ] });
}

// src/desktop/ui/styles.js
var styles = `
.ls-root,.ls-sheet,.ls-confirm{font:14px/1.5 var(--font-sans,system-ui,sans-serif);color:var(--ui-text-primary);--ls-surface:var(--ui-bg-card,var(--ui-bg-secondary));--ls-line:var(--ui-stroke-secondary);--ls-danger:var(--ui-text-danger,var(--destructive));--ls-warning:var(--ui-text-warning,var(--ui-text-primary));--ls-good:var(--ui-text-success,var(--ui-text-primary))}
.ls-root{height:100%;min-height:0;overflow:auto;background:var(--ui-bg-primary)}
.ls-root *,.ls-sheet *,.ls-confirm *{box-sizing:border-box}
.ls-root :is(button,a,input):focus-visible,.ls-sheet :is(button,a,input):focus-visible,.ls-confirm button:focus-visible{outline:2px solid var(--ui-accent-lit,var(--ui-accent));outline-offset:2px}
.ls-root h1{font-size:20px;font-weight:600;margin:0;letter-spacing:-.01em}.ls-root h2,.ls-sheet h2{font-size:14px;font-weight:600;margin:0}.ls-root p,.ls-sheet p{margin:8px 0}
.ls-page{padding:20px 28px 40px;max-width:1240px}.ls-page-heading{display:flex;align-items:baseline;gap:16px}.ls-secondary{color:var(--ui-text-secondary)}.ls-num{font-variant-numeric:tabular-nums}.ls-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0 18px}.ls-search{flex:1;min-width:220px;max-width:380px;min-height:34px;box-shadow:inset 0 1px 2px var(--ui-stroke-tertiary)}.ls-sort{margin-left:auto;font-size:12px;color:var(--ui-text-secondary)}.ls-toolbar button{min-height:32px}
.ls-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr));gap:12px}.ls-card{display:flex;flex-direction:column;gap:12px;padding:14px;border:1px solid var(--ls-line);border-radius:12px;background:var(--ls-surface);color:inherit;text-decoration:none;transition:background .15s,border-color .15s}.ls-card:hover{background:color-mix(in srgb,var(--ls-accent) 5%,var(--ls-surface));border-color:color-mix(in srgb,var(--ls-accent) 55%,var(--ls-line))}.ls-card.ls-failed,.ls-card.ls-blocked{border-color:color-mix(in srgb,var(--ls-danger) 40%,var(--ls-line))}.ls-card.ls-archived{opacity:.9}.ls-card-top{display:flex;align-items:flex-start;gap:12px}.ls-card-name{font-weight:600;font-size:14px}.ls-card-description{margin:0!important;min-height:42px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:var(--ui-text-secondary)}.ls-card-freshness{border-top:1px solid var(--ls-line);padding-top:10px;font-size:12px;display:grid;gap:3px}.ls-facts{margin:10px 0;display:grid;gap:8px;font-size:12px}.ls-facts>div{display:grid;grid-template-columns:110px 1fr;gap:10px}.ls-facts dt{color:var(--ui-text-secondary)}.ls-facts dd{margin:0;overflow-wrap:anywhere}
.ls-tile{display:inline-flex;align-items:center;justify-content:center;flex:none;width:40px;height:40px;border-radius:10px;border:1px solid color-mix(in srgb,var(--ls-accent) 48%,transparent);background:color-mix(in srgb,var(--ls-accent) 22%,var(--ui-bg-primary));color:color-mix(in srgb,var(--ls-accent) 70%,var(--ui-text-primary))}.ls-tile .codicon{font-size:20px}.ls-tile-small{width:32px;height:32px;border-radius:8px}.ls-owner{display:inline-flex;gap:5px;align-items:center;font-size:12px;color:var(--ui-text-secondary)}.ls-avatar{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;font-size:10px;background:var(--ui-bg-quaternary);color:var(--ui-text-primary)}.ls-pin{margin-left:auto}
.ls-pill{display:inline-flex;gap:5px;align-items:center;min-height:22px;padding:2px 8px!important;border:1px solid var(--ls-line);border-radius:999px!important;background:transparent!important;color:var(--ui-text-primary)!important;font-size:12px!important;font-weight:500}.ls-pill.ls-ready,.ls-pill.ls-succeeded,.ls-pill.ls-granted{color:var(--ls-good)!important}.ls-pill.ls-failed,.ls-pill.ls-crashed{color:var(--ls-danger)!important;border-color:currentColor}.ls-pill.ls-blocked,.ls-pill.ls-requested{color:var(--ls-warning)!important}.ls-pill.ls-updating{color:var(--ui-accent-lit,var(--ui-accent))!important}.ls-action{min-height:32px!important;border-radius:8px!important;padding:0 12px!important;font-size:13px!important}.ls-action[aria-disabled=true]{opacity:.55;cursor:not-allowed}.ls-danger{color:var(--ls-danger)!important;border:1px solid color-mix(in srgb,var(--ls-danger) 55%,var(--ls-line))!important}.ls-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px}.ls-footer{font-size:12px;color:var(--ui-text-secondary);margin-top:22px!important}.ls-empty{max-width:780px;margin:55px auto}.ls-empty-tiles{display:flex;gap:12px;justify-content:center}.ls-empty .ls-prompt{margin-top:12px}.ls-prompt{display:flex;align-items:flex-start;gap:10px;padding:12px;border:1px solid var(--ls-line);border-radius:8px;background:var(--ls-surface);font-size:13px}.ls-prompt q{flex:1;user-select:text;overflow-wrap:anywhere}.ls-prompt button{min-height:28px}.ls-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.ls-frame{height:100%;display:flex;flex-direction:column}.ls-framebar{position:sticky;top:0;z-index:1;display:flex;align-items:center;gap:10px;padding:12px;border-bottom:1px solid var(--ls-line);background:var(--ui-bg-primary)}.ls-identity{display:flex;align-items:center;gap:10px;min-width:0;flex:1}.ls-identity>div{min-width:0}.ls-name-row{display:flex;align-items:center;gap:8px}.ls-name-row h1{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:16px}.ls-name-row .ls-pill{flex:none}.ls-frame-meta{font-size:12px;color:var(--ui-text-secondary);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.ls-frame-actions{display:flex;align-items:center;gap:6px;flex:none;flex-wrap:wrap}.ls-save{font-size:12px;display:inline-flex;gap:5px;align-items:center;max-width:220px}.ls-save:empty{width:0}.ls-content{display:flex;flex:1;min-height:420px;flex-direction:column;padding:12px;gap:8px}.ls-sandbox{flex:1;min-height:380px;border:1px solid var(--ls-line);border-radius:12px;overflow:hidden;position:relative}.ls-mount{height:100%;min-height:380px}.ls-stale{filter:saturate(.7)}.ls-banner{display:flex;gap:10px;padding:14px 22px;border-bottom:1px solid var(--ls-line);background:var(--ui-bg-secondary);font-size:13px}.ls-banner.ls-failed,.ls-banner.ls-crashed,.ls-banner.ls-conflict{border-color:color-mix(in srgb,var(--ls-danger) 45%,var(--ls-line));background:color-mix(in srgb,var(--ls-danger) 8%,var(--ui-bg-primary))}.ls-banner.ls-blocked{border-color:var(--ls-warning)}.ls-crash{max-width:620px;padding:40px 24px;margin:auto}.ls-diagnostic{max-height:180px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:var(--ui-bg-secondary);border:1px solid var(--ls-line);font:12px/1.5 var(--font-mono,monospace)}.ls-building{padding:40px;display:grid;gap:16px}
.ls-sheet{position:fixed!important;top:0!important;right:0!important;left:auto!important;bottom:0!important;transform:none!important;translate:none!important;width:min(460px,100vw)!important;max-width:460px!important;max-height:100dvh!important;height:100dvh!important;border-radius:0!important;background:var(--ui-bg-elevated,var(--ui-surface-background,Canvas))!important;animation:none!important}.ls-sheet-body{display:flex!important;flex-direction:column!important;height:100%;max-height:100dvh!important;padding:0!important;gap:0!important;overflow:hidden!important}.ls-sheet-header{display:flex!important;flex-direction:row!important;justify-content:space-between;align-items:center;padding:16px;border-bottom:1px solid var(--ls-line);flex:none}.ls-sheet-scroll{padding:18px 16px;overflow:auto;min-height:0;flex:1}.ls-disclosure{margin:8px 0!important;font-size:12px;line-height:1.55;max-width:60ch}.ls-internet .ls-row-top{min-height:56px}.ls-internet>.ls-secondary{font-size:12px;max-width:60ch}.ls-switch-value{display:flex;gap:8px;align-items:center}.ls-switch{display:inline-flex;align-items:center;justify-content:center;min-width:44px;min-height:40px;padding:0;border:0;background:none;cursor:pointer;flex:none}.ls-switch-track{display:block;width:40px;height:24px;border-radius:999px;border:1px solid var(--ui-stroke-secondary);background:var(--ui-stroke-secondary);position:relative}.ls-switch-thumb{position:absolute;left:2px;top:2px;width:18px;height:18px;border-radius:50%;background:var(--ui-text-primary);transition:transform 120ms ease-out}.ls-switch[aria-checked=true] .ls-switch-track{background:var(--ui-accent);border-color:var(--ui-accent)}.ls-switch[aria-checked=true] .ls-switch-thumb{transform:translateX(16px);background:var(--ui-text-on-accent,#fff)}.ls-switch[aria-disabled=true]{cursor:not-allowed}.ls-upkeep-prompt{margin:16px 0}.ls-upkeep-prompt h3,.ls-sheet h3{font-size:13px;font-weight:600;margin:0}.ls-upkeep-prompt p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.ls-clamp-six,.ls-clamp-three{display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:hidden}.ls-clamp-three{-webkit-line-clamp:3}.ls-upkeep-note{font-size:12px}.ls-upkeep-actions>.ls-danger{margin-left:auto}.ls-upkeep-feedback{font-size:12px;margin:12px 0;outline-offset:2px}.ls-section{margin:0 0 22px}.ls-section-title{font-size:12px!important;font-weight:600!important;letter-spacing:.025em;margin:4px 0 12px!important}.ls-grant,.ls-row{padding:12px;border:1px solid var(--ls-line);border-radius:8px;margin-bottom:12px}.ls-row-top{display:flex;align-items:center;gap:8px;justify-content:space-between}.ls-row-top>strong{display:flex;gap:8px;align-items:center}.ls-pending{background:color-mix(in srgb,var(--ls-warning) 6%,var(--ls-surface))}.ls-audit{padding-left:18px;font-size:12px}.ls-tabs{margin-bottom:16px}.ls-confirm{max-width:520px!important}.ls-compare{display:grid;gap:12px}.ls-directive{padding:14px;border:1px solid var(--ui-stroke-secondary);border-radius:12px;max-width:440px;background:var(--ui-bg-card,var(--ui-bg-secondary));display:grid;gap:10px}.ls-spin{animation:ls-spin 1s linear infinite}@keyframes ls-spin{to{transform:rotate(360deg)}}
.ls-frame:not([data-header-mode=wide]) .ls-wide-only{display:none!important}.ls-frame:not([data-header-mode=wide]) .ls-framebar{flex-wrap:wrap}.ls-frame:not([data-header-mode=wide]) .ls-frame-actions{width:100%;justify-content:flex-end}.ls-frame:not([data-header-mode=wide]) .ls-save{margin-right:auto}.ls-frame[data-header-mode=narrow] .ls-identity{flex-basis:100%}.ls-frame[data-header-mode=narrow] .ls-upkeep-action{display:none}.ls-frame[data-header-mode=narrow] .ls-frame-actions .ls-action:not(.ls-overflow){padding:0 8px!important}.ls-frame[data-header-mode=narrow] .ls-save{max-width:100%;flex-basis:100%}.ls-frame[data-header-mode=narrow] .ls-save:empty{display:none}.ls-frame-actions .ls-overflow{width:32px;height:32px;min-width:32px;padding:0!important;flex:none}
@media(max-width:899px){.ls-page{padding:20px 16px}.ls-content{padding:12px}.ls-page-heading{flex-wrap:wrap;gap:4px}.ls-sort{width:100%}.ls-sheet{width:min(460px,100vw)!important}}@media(max-width:359px){.ls-internet .ls-row-top{flex-wrap:wrap}.ls-internet .ls-switch-value{width:100%}}@media(prefers-reduced-motion:reduce){.ls-spin{animation:none}.ls-root *,.ls-sheet *,.ls-confirm *{transition:none!important;animation:none!important}}@media(forced-colors:active){.ls-pill,.ls-card,.ls-tile,.ls-action{border:1px solid CanvasText!important}.ls-switch-track{border:1px solid ButtonText!important;background:Canvas!important}.ls-switch-thumb{background:ButtonText!important}.ls-switch[aria-checked=true] .ls-switch-track{background:Highlight!important}.ls-switch[aria-checked=true] .ls-switch-thumb{background:HighlightText!important}}
`;

// src/desktop/ui/context.jsx
import { host as host3, useValue } from "@hermes/plugin-sdk";
import { useMemo } from "react";
var currentScope = () => JSON.stringify([host3.state.connectionId.get(), host3.state.profile.get()]);
function useScopedContext(ctx) {
  const connectionId = useValue(host3.state.connectionId);
  const profile = useValue(host3.state.profile);
  const scopeKey = JSON.stringify([connectionId, profile]);
  return useMemo(() => ({
    ctx: { ...ctx, rest: scopedRest((path, options) => ctx.rest(path, options), currentScope, scopeKey) },
    scopeKey,
    scope: { connectionId, profile },
    // Late-open tokens must survive a scope switch so cleanup can target their owner.
    sessionRest: (path, options) => ctx.rest(path, options)
  }), [ctx, scopeKey]);
}

// src/desktop/plugin.src.js
function SpacesPage({ ctx }) {
  const scoped = useScopedContext(ctx);
  const [hash, setHash] = useState7(() => typeof location === "undefined" ? "" : location.hash);
  useEffect3(() => {
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
