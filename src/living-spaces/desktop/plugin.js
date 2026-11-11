// src/desktop/plugin.src.js
import { ROUTES_AREA, SIDEBAR_NAV_AREA, TRANSCRIPT_DIRECTIVE_AREA, ErrorState as ErrorState5, host as host4, useQuery as useQuery5 } from "@hermes/plugin-sdk";
import { useEffect as useEffect2, useState as useState7 } from "react";
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
function freshnessFacts(space, format) {
  const f = space.freshness || {};
  const at = (value) => value == null ? "Never" : format(value);
  return [
    { key: "success", label: "Last successful update", value: at(f.last_success_at), at: f.last_success_at },
    { key: "attempt", label: "Last attempt", value: f.last_attempt_at == null ? "Never" : `${format(f.last_attempt_at)} \xB7 ${f.last_attempt_status || "Unknown"}`, at: f.last_attempt_at },
    { key: "source", label: "Source data from", value: f.source_as_of == null ? "Not reported" : format(f.source_as_of), at: f.source_as_of },
    { key: "next", label: "Next refresh", value: f.next_run_at == null ? "Not scheduled" : format(f.next_run_at), at: f.next_run_at }
  ];
}
function cardLines(space, format) {
  const f = space.freshness || {};
  const at = (value) => value == null ? "not yet available" : format(value);
  const state = spaceStatus(space);
  if (state === "building") return [`${space.owner} is building the first version`, `Started ${at(space.created_at ?? space.updated_at)}`];
  if (state === "archived") return [`Archived ${at(space.archived_at ?? space.updated_at)}`, "Schedules stopped"];
  if (space.attention?.kind === "crashed") return [`Stopped working ${at(f.last_attempt_at)}`, space.attention.message];
  if (state === "updating") return ["Refreshing now\u2026", `Last good update ${at(f.last_success_at)}`];
  if (state === "failed") return [`Refresh failed ${at(f.last_attempt_at)}`, `Showing last good data from ${at(f.last_success_at)}`];
  if (state === "blocked") return [`Refresh blocked ${at(f.last_attempt_at)}`, space.attention?.message || "Refresh needs your approval in Permissions"];
  return [f.last_success_at == null ? "No successful update yet" : `Updated ${at(f.last_success_at)}`, space.schedule?.status === "paused" ? "Upkeep paused" : `Next refresh ${f.next_run_at == null ? "not scheduled" : format(f.next_run_at)}`];
}
function advanceCursor(cursor, page) {
  const changes = (page?.changes || []).filter((c) => Number.isSafeInteger(c.seq) && c.seq > cursor).sort((a, b) => a.seq - b.seq);
  const seq = changes.length ? changes.at(-1).seq : cursor;
  return { seq, changes };
}
function refreshReason(space) {
  if (space.status === "archived") return "This Space is archived. Restore it to refresh.";
  if (!space.manifest?.upkeep) return "No refresh handler is declared. Ask the owner in chat to add one.";
  if (!space.grants?.some((g) => g.capability === "refresh" && g.status === "granted")) return "Refresh needs your approval in Permissions";
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
var CATCH_UP = "Runs one current refresh when Hermes wakes. Missed intervals aren't replayed.";
var PROMPTS = [
  "Build Research Desk: an overview, a searchable library and a reading queue. Keep my notes and reading status.",
  "Build a weekly fitness planner with a progress chart. Refresh it every Monday."
];
function restoreCopy(space, rev) {
  const kept = space.head_rev > rev + 1 ? `Revisions ${rev + 1}\u2013${space.head_rev} stay in history.` : `Revision ${space.head_rev} stays in history.`;
  return `Restore revision ${rev}? This brings back the Space's earlier code as a new revision ${space.head_rev + 1}. ${kept} Your records, notes and statuses stay as they are now.`;
}
function errorText(error) {
  const detail = error?.error || error?.body?.error || error;
  const message = detail?.message || String(error);
  return detail?.code === "incompatible" || /incompatible/.test(message) ? `Incompatible revision: ${message}. Your current code and records are unchanged.` : message;
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
import { jsx, jsxs } from "react/jsx-runtime";
var relative = (seconds) => relativeTime(seconds * 1e3);
function absolute(seconds) {
  if (seconds == null) return "Not reported";
  const date = new Date(seconds * 1e3);
  const zone = new Intl.DateTimeFormat(void 0, { timeZoneName: "short" }).formatToParts(date).find((p) => p.type === "timeZoneName")?.value || "";
  return `${fmtDateTime.format(date)} ${zone}`.trim();
}
function Time({ at, children }) {
  return /* @__PURE__ */ jsx("span", { title: at == null ? void 0 : absolute(at), children: children ?? (at == null ? "Not reported" : absolute(at)) });
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
function DecisionDialog({ title, description, confirmLabel, cancelLabel = "Cancel", danger = false, onClose, onConfirm, returnFocus }) {
  const cancel = useRef(null);
  const trigger = useRef(returnFocus || (typeof document === "undefined" ? null : document.activeElement));
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState("");
  async function confirm() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await onConfirm();
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
        trigger.current?.focus();
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
import { Fragment, jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
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
          /* @__PURE__ */ jsx2(Time, { at: space.freshness?.last_attempt_at, children: lines[0] }),
          /* @__PURE__ */ jsx2("span", { className: "ls-secondary", children: lines[1] }),
          space.status !== "archived" && status !== "building" && /* @__PURE__ */ jsxs2(Fragment, { children: [
            /* @__PURE__ */ jsx2("div", { className: "ls-secondary", children: /* @__PURE__ */ jsxs2(Time, { at: space.freshness?.last_attempt_at, children: [
              "Last attempt ",
              space.freshness?.last_attempt_at == null ? "never" : `${relative(space.freshness.last_attempt_at)} \xB7 ${space.freshness.last_attempt_status}`
            ] }) }),
            /* @__PURE__ */ jsx2("div", { className: "ls-secondary", children: /* @__PURE__ */ jsxs2(Time, { at: space.freshness?.source_as_of, children: [
              "Source data from ",
              space.freshness?.source_as_of == null ? "not reported" : relative(space.freshness.source_as_of)
            ] }) })
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
    /* @__PURE__ */ jsx2(EmptyState, { title: "Build your first Space in chat", description: "A Space is a dashboard, planner, game or small app your agent builds and keeps current. Describe it in any Hermes chat, then open it here." }),
    PROMPTS.map((text) => /* @__PURE__ */ jsx2(CopyPrompt, { text }, text)),
    /* @__PURE__ */ jsxs2("div", { className: "ls-actions", children: [
      action ? /* @__PURE__ */ jsx2(Action, { primary: true, icon: "add", onClick: start, children: "Start a new chat" }) : /* @__PURE__ */ jsx2(CopyPrompt, { text: PROMPTS[0], label: "Start a new chat" }),
      /* @__PURE__ */ jsx2("span", { className: "ls-secondary", children: "New Spaces appear here, labelled Building until ready." })
    ] }),
    !action && /* @__PURE__ */ jsx2("p", { role: "status", children: "This host cannot start a new chat here. The action copies the example prompt to paste into a normal Hermes chat." }),
    notice && /* @__PURE__ */ jsx2("p", { role: "status", children: notice })
  ] });
}
function SpacesIndex({ ctx }) {
  const [search, setSearch] = useState2("");
  const [filter, setFilter] = useState2("all");
  const list = useQuery({ queryKey: ["living-spaces", ctx.queryScope || null, "spaces"], queryFn: () => ctx.rest("/spaces"), refetchInterval: 2e3 });
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
    list.isLoading ? /* @__PURE__ */ jsx2("div", { className: "ls-grid", "aria-label": "Loading Spaces", children: [1, 2, 3].map((n) => /* @__PURE__ */ jsx2(Skeleton, { style: { height: 240 } }, n)) }) : list.data && !spaces.length ? /* @__PURE__ */ jsx2(FirstSpace, { ctx }) : list.data ? /* @__PURE__ */ jsxs2(Fragment, { children: [
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
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, ErrorState as ErrorState4, Skeleton as Skeleton4, host as host2, useQuery as useQuery4 } from "@hermes/plugin-sdk";
import { useEffect, useRef as useRef4, useState as useState6 } from "react";

// src/desktop/ui/history.jsx
import { Badge as Badge2, EmptyState as EmptyState2, ErrorState as ErrorState2, Skeleton as Skeleton2, Tabs, TabsList, TabsTrigger, useQuery as useQuery2 } from "@hermes/plugin-sdk";
import { useState as useState3 } from "react";
import { Fragment as Fragment2, jsx as jsx3, jsxs as jsxs3 } from "react/jsx-runtime";
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
    /* @__PURE__ */ jsx3("p", { children: runResult(run) })
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
function HistorySheet({ ctx, space, onClose, onChanged, initialTab = "runs", returnFocus }) {
  const [tab, setTab] = useState3(initialTab);
  const [restore, setRestore] = useState3(null);
  const base = spacePath(space.id);
  const runs = useQuery2({ queryKey: ["living-spaces", ctx.queryScope || null, space.id, "runs"], queryFn: () => ctx.rest(`${base}/runs`), refetchInterval: 2e3 });
  const revisions = useQuery2({ queryKey: ["living-spaces", ctx.queryScope || null, space.id, "revisions"], queryFn: () => ctx.rest(`${base}/revisions`), refetchInterval: 2e3 });
  const query = tab === "runs" ? runs : revisions;
  return /* @__PURE__ */ jsxs3(Fragment2, { children: [
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
import { Badge as Badge3, ErrorState as ErrorState3, Skeleton as Skeleton3, useQuery as useQuery3 } from "@hermes/plugin-sdk";
import { useRef as useRef2, useState as useState4 } from "react";

// src/desktop/sandbox/index.js
var BRIDGE_VERSION = 1;
var WEBRTC_NOTE = "Spaces block ordinary internet connections unless you approve a site or capability. This is not a complete block: a browser feature called WebRTC can still send data that this Space can read. It does not give the Space access to Hermes, credentials, your unapproved files or other Spaces. Only put data in a Space that you trust it to handle.";
var OP_GRANT = Object.freeze({
  meta: null,
  "data.query": "data",
  "data.get": "data",
  "data.put": "data",
  "data.delete": "data",
  "data.batch": "data",
  refresh: "refresh",
  "runs.list": null,
  log: "logs"
});
var MAX_REQUEST_SIZE = 1024 * 1024;
function validateRequest(message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) return "request must be an object";
  if (message.v !== BRIDGE_VERSION) return "unsupported bridge version";
  if (!Number.isSafeInteger(message.id)) return "id must be an integer";
  if (typeof message.op !== "string") return "op must be a string";
  if (!message.args || typeof message.args !== "object" || Array.isArray(message.args)) return "args must be an object";
  try {
    if (JSON.stringify(message).length > MAX_REQUEST_SIZE) return "request exceeds 1 MB";
  } catch {
    return "request is not JSON serializable";
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
    const reason = validateRequest(m);
    if (reason) {
      onEvent({ kind: "denied", op: typeof m?.op === "string" ? m.op : null, reason });
      if (m?.v === BRIDGE_VERSION && Number.isSafeInteger(m.id)) {
        port.postMessage({ v: 1, id: m.id, ok: false, error: { code: reason === "request exceeds 1 MB" ? "limit" : "invalid", message: reason } });
      }
      return;
    }
    const reply = (body) => {
      if (state === "booted") port.postMessage({ v: 1, id: m.id, ...body });
    };
    const denied = checkGrant(m.op, grants);
    if (denied) {
      onEvent({ kind: "denied", op: m.op, reason: denied.message });
      reply({ ok: false, error: denied });
      return;
    }
    let args = m.args;
    if (m.op === "log") {
      if (!Array.isArray(args.entries) || args.entries.length > 50 || args.entries.some((entry) => !entry || typeof entry.level !== "string" || typeof entry.msg !== "string" || entry.msg.length > 4e3)) {
        onEvent({ kind: "denied", op: "log", reason: "invalid log entries" });
        reply({ ok: false, error: { code: "invalid", message: "Invalid log entries" } });
        return;
      }
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
      if (revoked && result.ok) {
        onEvent({ kind: "denied", op: m.op, reason: revoked.message });
        reply({ ok: false, error: revoked });
      } else reply(result);
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
      port.postMessage({ v: 1, type: "event", event, payload });
      if (event === "session.closed") stop();
    },
    destroy() {
      stop();
      frame.remove();
    }
  };
}

// src/desktop/ui/permissions.jsx
import { Fragment as Fragment3, jsx as jsx4, jsxs as jsxs4 } from "react/jsx-runtime";
var CAPABILITIES = {
  data: { name: "Own data", icon: "folder", scope: "This Space's records only. Cannot see other Spaces.", purpose: "Store your records, notes and statuses.", leaves: "No ordinary network access. Space-readable data is subject to the WebRTC limit above." },
  refresh: { name: "Refresh", icon: "refresh", purpose: "Keep public-source records current.", leaves: "Yes \xB7 requests the approved public sources through Hermes." },
  logs: { name: "Diagnostics", icon: "info", scope: "Error logs from this Space, secrets redacted.", purpose: "Let the owner see crashes and repair them.", leaves: "No ordinary network access. The owner can read these logs in chat." }
};
var FUTURE = ["Approved sites", "Camera", "Microphone", "Location", "Hermes tools (per tool)", "Files and folders", "Cross-Space access", "Agent requests"];
function WebRTCNote() {
  return /* @__PURE__ */ jsxs4("div", { className: "ls-disclosure", "data-testid": "webrtc-note", children: [
    /* @__PURE__ */ jsxs4("strong", { children: [
      /* @__PURE__ */ jsx4(Icon, { name: "info" }),
      " Before you approve anything"
    ] }),
    /* @__PURE__ */ jsx4("p", { children: WEBRTC_NOTE })
  ] });
}
function GrantCard({ grant, onDecide, busy }) {
  const model = CAPABILITIES[grant.capability];
  if (!model) return null;
  const scope = grant.requested_scope || grant.scope || {};
  const scopeText = grant.capability === "refresh" ? `Host-owned public-source handler. Approved hosts: ${(scope.hosts || []).join(", ") || "No hosts requested"}.` : model.scope;
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
    /* @__PURE__ */ jsx4("div", { className: "ls-actions", children: grant.status === "granted" ? /* @__PURE__ */ jsx4(Action, { danger: true, disabled: busy, onClick: () => onDecide(grant, "revoke"), children: "Revoke" }) : grant.status === "requested" ? /* @__PURE__ */ jsxs4(Fragment3, { children: [
      /* @__PURE__ */ jsx4(Action, { primary: true, disabled: busy, onClick: () => onDecide(grant, "grant"), children: "Approve" }),
      /* @__PURE__ */ jsx4(Action, { disabled: busy, onClick: () => onDecide(grant, "deny"), children: "Deny" })
    ] }) : /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: grant.status === "denied" ? `Denied. The Space shows \u201C${model.name} isn't available\u201D instead of prompting again.` : `${model.name} was revoked. Ask in chat to request access again.` }) })
  ] });
}
function PermissionsContent({ space, grants, audit = [], schedule, onDecide, onSchedule, busy = false }) {
  const pending = grants.filter((g) => g.status === "requested");
  const settled = grants.filter((g) => g.status !== "requested");
  return /* @__PURE__ */ jsxs4(Fragment3, { children: [
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
      schedule?.status === "requested" && /* @__PURE__ */ jsxs4("article", { className: "ls-grant ls-pending", children: [
        /* @__PURE__ */ jsxs4("div", { className: "ls-row-top", children: [
          /* @__PURE__ */ jsxs4("strong", { children: [
            /* @__PURE__ */ jsx4(Icon, { name: "watch" }),
            "Scheduled upkeep"
          ] }),
          /* @__PURE__ */ jsx4(StatusPill, { status: "requested" })
        ] }),
        /* @__PURE__ */ jsxs4("dl", { className: "ls-facts", children: [
          /* @__PURE__ */ jsxs4("div", { children: [
            /* @__PURE__ */ jsx4("dt", { children: "Cadence" }),
            /* @__PURE__ */ jsx4("dd", { children: schedule.cadence })
          ] }),
          /* @__PURE__ */ jsxs4("div", { children: [
            /* @__PURE__ */ jsx4("dt", { children: "Timezone" }),
            /* @__PURE__ */ jsx4("dd", { children: schedule.timezone })
          ] }),
          /* @__PURE__ */ jsxs4("div", { children: [
            /* @__PURE__ */ jsx4("dt", { children: "Purpose" }),
            /* @__PURE__ */ jsx4("dd", { children: schedule.purpose })
          ] }),
          /* @__PURE__ */ jsxs4("div", { children: [
            /* @__PURE__ */ jsx4("dt", { children: "Owner" }),
            /* @__PURE__ */ jsx4("dd", { children: space.owner })
          ] }),
          /* @__PURE__ */ jsxs4("div", { children: [
            /* @__PURE__ */ jsx4("dt", { children: "Cost" }),
            /* @__PURE__ */ jsx4("dd", { children: "No model calls" })
          ] })
        ] }),
        /* @__PURE__ */ jsx4("p", { children: CATCH_UP }),
        /* @__PURE__ */ jsxs4("div", { className: "ls-actions", children: [
          /* @__PURE__ */ jsx4(Action, { primary: true, disabled: busy, onClick: () => onSchedule("approve"), children: "Approve" }),
          /* @__PURE__ */ jsx4(Action, { disabled: busy, onClick: () => onSchedule("deny"), children: "Deny" })
        ] })
      ] }),
      !pending.length && schedule?.status !== "requested" && /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: "Nothing waiting for your decision." })
    ] }),
    /* @__PURE__ */ jsxs4("section", { className: "ls-section", "data-testid": "release-two", children: [
      /* @__PURE__ */ jsx4("h2", { className: "ls-section-title", children: "Coming in release 2 \u2014 not available yet" }),
      FUTURE.map((name) => /* @__PURE__ */ jsx4("div", { className: "ls-grant ls-future", children: /* @__PURE__ */ jsxs4("div", { className: "ls-row-top", children: [
        /* @__PURE__ */ jsx4("strong", { children: name }),
        /* @__PURE__ */ jsx4(Badge3, { variant: "outline", children: "Not available yet" })
      ] }) }, name)),
      /* @__PURE__ */ jsx4("p", { className: "ls-secondary", children: "Camera, microphone and location will start off and also follow Hermes and macOS permission prompts. Release 2 will revisit what Spaces can read before tool and file access is offered." })
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
function PermissionsSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const base = spacePath(space.id);
  const query = useQuery3({ queryKey: ["living-spaces", ctx.queryScope || null, space.id, "grants"], queryFn: () => ctx.rest(`${base}/grants`), refetchInterval: 2e3 });
  const schedule = useQuery3({ queryKey: ["living-spaces", ctx.queryScope || null, space.id, "schedule"], queryFn: () => ctx.rest(`${base}/schedule`), refetchInterval: 2e3 });
  const [revoke, setRevoke] = useState4(null);
  const [busy, setBusy] = useState4(false);
  const [error, setError] = useState4("");
  const lock = useRef2(false);
  async function decide(grant, decision) {
    if (decision === "revoke") {
      setRevoke(grant);
      return;
    }
    await change(`${base}/grants/${grant.capability}`, { decision, ...decision === "grant" ? { requested_scope: grant.requested_scope ?? grant.scope ?? {} } : {} });
  }
  async function change(path, body) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await ctx.rest(path, { method: "POST", body });
      await Promise.all([query.refetch(), schedule.refetch(), onChanged()]);
    } catch (e) {
      if ((e?.error || e?.body?.error || e)?.code === "conflict") {
        setError("Permission request changed. Review the new request before approving.");
      } else setError(`${errorText(e)} Review the current request before trying again.`);
      await Promise.all([query.refetch(), schedule.refetch()]);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return /* @__PURE__ */ jsxs4(Fragment3, { children: [
    /* @__PURE__ */ jsxs4(Drawer, { title: `Permissions \xB7 ${space.name}`, description: "Review this Space's access and schedule requests.", onClose, note: /* @__PURE__ */ jsx4(WebRTCNote, {}), returnFocus, children: [
      error && /* @__PURE__ */ jsx4(Banner, { kind: "failed", title: error }),
      query.error || schedule.error ? /* @__PURE__ */ jsx4(ErrorState3, { title: "Permissions could not be loaded", description: errorText(query.error || schedule.error), children: /* @__PURE__ */ jsx4(Action, { onClick: () => {
        query.refetch();
        schedule.refetch();
      }, children: "Try again" }) }) : query.isLoading ? /* @__PURE__ */ jsx4(Skeleton3, { style: { height: 180 } }) : /* @__PURE__ */ jsx4(PermissionsContent, { space, grants: query.data?.grants || [], audit: query.data?.audit || [], schedule: schedule.data, onDecide: decide, onSchedule: (decision) => change(`${base}/schedule`, { decision }), busy })
    ] }),
    revoke && /* @__PURE__ */ jsx4(DecisionDialog, { danger: true, title: `Revoke ${CAPABILITIES[revoke.capability].name} for ${space.name}?`, description: revoke.capability === "refresh" ? "Scheduled and manual refreshes stop and show Blocked. Data already delivered to the Space can't be recalled, and completed requests can't be undone." : `The Space loses ${CAPABILITIES[revoke.capability].name.toLowerCase()} access. Data already delivered to the Space can't be recalled, and completed requests can't be undone.`, cancelLabel: "Keep access", confirmLabel: "Revoke", onClose: () => setRevoke(null), onConfirm: async () => {
      await ctx.rest(`${base}/grants/${revoke.capability}`, { method: "POST", body: { decision: "revoke" } });
      await query.refetch();
      await onChanged();
    } })
  ] });
}

// src/desktop/ui/schedule.jsx
import { useRef as useRef3, useState as useState5 } from "react";
import { Fragment as Fragment4, jsx as jsx5, jsxs as jsxs5 } from "react/jsx-runtime";
function ScheduleSheet({ ctx, space, onClose, onChanged, returnFocus }) {
  const [error, setError] = useState5("");
  const [busy, setBusy] = useState5(false);
  const lock = useRef3(false);
  const schedule = space.schedule;
  async function pause() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    try {
      await ctx.rest(`${spacePath(space.id)}/schedule`, { method: "POST", body: { paused: schedule.status !== "paused" } });
      await onChanged();
    } catch (e) {
      setError(errorText(e));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return /* @__PURE__ */ jsxs5(Drawer, { title: `Schedule \xB7 ${space.name}`, description: "Schedule, cost and missed-run policy", onClose, returnFocus, children: [
    error && /* @__PURE__ */ jsx5(Banner, { kind: "failed", title: error }),
    schedule ? /* @__PURE__ */ jsxs5(Fragment4, { children: [
      /* @__PURE__ */ jsx5(StatusPill, { status: schedule.status === "active" ? "ready" : schedule.status === "paused" ? "paused" : schedule.status, label: schedule.status === "active" ? "Active" : schedule.status === "disabled" ? "Disabled" : void 0 }),
      /* @__PURE__ */ jsxs5("dl", { className: "ls-facts", children: [
        /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Cadence" }),
          /* @__PURE__ */ jsx5("dd", { children: schedule.cadence })
        ] }),
        /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Timezone" }),
          /* @__PURE__ */ jsx5("dd", { children: schedule.timezone })
        ] }),
        /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Purpose" }),
          /* @__PURE__ */ jsx5("dd", { children: schedule.purpose })
        ] }),
        /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Next run" }),
          /* @__PURE__ */ jsx5("dd", { children: schedule.status === "active" ? /* @__PURE__ */ jsx5(Time, { at: schedule.next_run_at ?? space.freshness?.next_run_at }) : "Not scheduled while upkeep is inactive" })
        ] }),
        /* @__PURE__ */ jsxs5("div", { children: [
          /* @__PURE__ */ jsx5("dt", { children: "Last attempt" }),
          /* @__PURE__ */ jsxs5("dd", { children: [
            /* @__PURE__ */ jsx5(Time, { at: space.freshness?.last_attempt_at }),
            " \xB7 ",
            space.freshness?.last_attempt_status || "No attempts"
          ] })
        ] })
      ] })
    ] }) : /* @__PURE__ */ jsx5("p", { children: "No schedule approved." }),
    /* @__PURE__ */ jsxs5("section", { className: "ls-section", children: [
      /* @__PURE__ */ jsx5("h2", { className: "ls-section-title", children: "Cost" }),
      /* @__PURE__ */ jsx5("p", { children: "No model calls. Refreshes use the declared public-source handler and approved hosts." }),
      /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: "Feed limit 3 MB \xB7 200 entries per source \xB7 20 s request timeout." })
    ] }),
    /* @__PURE__ */ jsxs5("section", { className: "ls-section", children: [
      /* @__PURE__ */ jsx5("h2", { className: "ls-section-title", children: "If Hermes is asleep" }),
      /* @__PURE__ */ jsx5("p", { children: CATCH_UP }),
      /* @__PURE__ */ jsx5("p", { className: "ls-secondary", children: "Background execution depends on Hermes being available." })
    ] }),
    schedule && ["active", "paused"].includes(schedule.status) && /* @__PURE__ */ jsx5(Action, { disabled: busy || space.status === "archived", icon: schedule.status === "paused" ? "play" : "debug-pause", onClick: pause, children: schedule.status === "paused" ? "Resume upkeep" : "Pause upkeep" }),
    /* @__PURE__ */ jsx5("div", { className: "ls-section", children: /* @__PURE__ */ jsx5(CopyPrompt, { text: `${space.owner}, change the upkeep schedule for ${space.name}. Please confirm the cadence, timezone and purpose before requesting approval.`, label: "Change schedule in chat" }) })
  ] });
}

// src/desktop/ui/session.mjs
function createSpaceSession({ rest, backend, sid, container, mount, onEvent, onWrite = () => {
}, onCloseError = (error) => console.warn("Space session cleanup failed", error) }) {
  const base = spacePath(sid);
  const { api, connectionId, profile } = backend || {};
  const lifecycleRest = api ? (path, options = {}) => api({ ...options, path: `/api/plugins/living-spaces${path}`, connectionId, profile, timeoutMs: options.method === "DELETE" ? 5e3 : void 0 }) : rest;
  let closed = false;
  let session = null;
  let mounted = null;
  let closePromise = null;
  let nextWrite = 0;
  let pendingWrites = 0;
  const failures = /* @__PURE__ */ new Map();
  const retries = /* @__PURE__ */ new Map();
  const publish = (event) => onWrite(failures.values().next().value || (pendingWrites ? { status: "saving" } : event));
  const close = () => {
    if (!session) return Promise.resolve();
    closePromise ??= (async () => {
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          return await lifecycleRest(`${base}/sessions/${encodeURIComponent(session)}`, { method: "DELETE" });
        } catch (error) {
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
    if (closed) return { ok: false, error: { code: "session_invalid", message: "This Space session is closed" } };
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
      reply = await rest(`${base}/bridge`, { method: "POST", body: { session, op, args } });
    } catch (error) {
      unknown = true;
      reply = { ok: false, error: { code: "unavailable", message: error.message || String(error) } };
    }
    if (closed) return { ok: false, error: { code: "session_invalid", message: "This Space session is closed" } };
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
    const opened = await lifecycleRest(`${base}/sessions`, { method: "POST" });
    session = opened.session;
    if (closed) return close();
    try {
      const bundle = await lifecycleRest(`${base}/bundle`);
      if (closed) return close();
      if (bundle.rev !== opened.head_rev) throw new Error("The Space changed while opening. Reload Space to open the current revision.");
      mounted = mount(container, { bundle, grants: opened.grants, call, onEvent: (event) => !closed && onEvent(event) });
    } catch (error) {
      closed = true;
      await close().catch(() => {
      });
      throw error;
    }
  })();
  return {
    ready,
    dismissWrite(token) {
      failures.delete(token);
      publish(null);
    },
    postEvent(event, payload) {
      if (!closed) mounted?.postEvent?.(event, payload);
    },
    destroy() {
      closed = true;
      mounted?.destroy();
      mounted = null;
      return close();
    }
  };
}

// src/desktop/ui/space.jsx
import { Fragment as Fragment5, jsx as jsx6, jsxs as jsxs6 } from "react/jsx-runtime";
function SaveStatus({ write, announcement }) {
  const labels = { saving: "Saving\u2026", saved: `Saved ${write?.at ? absolute(write.at) : ""}`, failed: "Not saved \u2014 this change was rejected", unknown: "Save outcome unknown \u2014 the change may have been stored", conflict: "Conflict \u2014 this record changed elsewhere" };
  return /* @__PURE__ */ jsxs6("span", { className: "ls-save", role: "status", "aria-live": "polite", "aria-atomic": "true", children: [
    /* @__PURE__ */ jsx6(Icon, { name: write?.status === "saving" ? "refresh" : ["failed", "unknown", "conflict"].includes(write?.status) ? "warning" : "check", spin: write?.status === "saving" }),
    write ? labels[write.status] : "No unsaved changes",
    announcement && /* @__PURE__ */ jsx6("span", { children: announcement })
  ] });
}
function WriteBanner({ write, setWrite, onCompare, onUpdated }) {
  if (!write || !["failed", "unknown", "conflict"].includes(write.status)) return null;
  const current = write.reply?.error?.current;
  const canKeep = write.op === "data.put" && current?.rev != null;
  return /* @__PURE__ */ jsx6(
    Banner,
    {
      kind: write.status === "conflict" ? "conflict" : "failed",
      title: write.status === "conflict" ? "Conflict \u2014 this record changed elsewhere" : write.status === "unknown" ? "Save outcome unknown \u2014 the change may have been stored" : "Not saved \u2014 this change was rejected",
      actions: write.status === "conflict" ? /* @__PURE__ */ jsxs6(Fragment5, { children: [
        canKeep && /* @__PURE__ */ jsx6(Action, { onClick: () => write.retry({ ...write.args, base_rev: current.rev }), children: "Keep my note" }),
        /* @__PURE__ */ jsx6(Action, { onClick: () => {
          setWrite(null);
          onUpdated(current);
        }, children: "Use updated record" }),
        /* @__PURE__ */ jsx6(Action, { onClick: onCompare, children: "Compare" })
      ] }) : /* @__PURE__ */ jsx6(Action, { onClick: () => write.retry(), children: "Retry save" }),
      children: write.reply?.error?.message || "Your change is kept in this view until you choose how to continue."
    }
  );
}
function SpaceView({ ctx, sid }) {
  const base = spacePath(sid);
  const detail = useQuery4({ queryKey: ["living-spaces", ctx.queryScope || null, sid, "detail"], queryFn: () => ctx.rest(base), refetchInterval: 2e3 });
  const space = detail.data;
  const [sheet, setSheet] = useState6(null);
  const [confirmation, setConfirmation] = useState6(null);
  const [reload, setReload] = useState6(0);
  const [crash, setCrash] = useState6(null);
  const [ignoredCrashRev, setIgnoredCrashRev] = useState6(null);
  const [write, setWrite] = useState6(null);
  const [announcement, setAnnouncement] = useState6("");
  const [actionError, setActionError] = useState6("");
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
  useEffect(() => {
    let disposed = false;
    ctx.rest(`${base}/opened`, { method: "POST" }).catch((e) => {
      if (!disposed) setActionError(`Could not mark this Space as opened. ${errorText(e)}`);
    });
    return () => {
      disposed = true;
    };
  }, [ctx, base]);
  useEffect(() => {
    if (building || archived || crash || remoteCrash || !content.current) return;
    let disposed = false;
    let errors = 0;
    cursor.current = 0;
    setReady(false);
    const [connectionId, profile] = ctx.queryScope ? JSON.parse(ctx.queryScope) : [host2.state.connectionId.get(), host2.state.profile.get()];
    const backend = { api: window.hermesDesktop?.api, connectionId, profile };
    const session = createSpaceSession({
      backend,
      rest: (path, options) => ctx.rest(path, options),
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
        if (event.kind === "error" && (event.fatal || event.phase === "load" || /load|entry|boot/i.test(event.message || "") || ++errors >= 3)) setCrash(diagnosticText(`${event.message || event.error || "Repeated runtime errors"}
Location: ${event.location || event.filename || "Not reported by runtime"}`));
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
  }, [ctx, sid, space?.head_rev, grantsKey, building, archived, crash, remoteCrash, reload]);
  const changes = useQuery4({ queryKey: ["living-spaces", ctx.queryScope || null, sid, "changes", space?.head_rev, grantsKey, reload], queryFn: () => ctx.rest(`${base}/changes?since=${cursor.current}`), enabled: hasData && ready && !building && !archived && !crash, refetchInterval: 1500 });
  useEffect(() => {
    if (!hasData || !ready || !changes.data || !controller.current) return;
    const page = advanceCursor(cursor.current, changes.data);
    if (page.changes.length) {
      controller.current.postEvent("data.changed", page);
      cursor.current = page.seq;
    }
  }, [hasData, ready, changes.data, changes.dataUpdatedAt]);
  useEffect(() => {
    if (!lastRun) return;
    if (ready) controller.current?.postEvent("run.updated", lastRun);
    if (seenRun.current && seenRun.current !== runKey && !inFlight(lastRun.status)) setAnnouncement(lastRun.status === "succeeded" ? `Refresh succeeded: ${runResult(lastRun)}` : `Refresh ${lastRun.status}: ${runResult(lastRun)}`);
    seenRun.current = runKey;
  }, [runKey, ready]);
  useEffect(() => {
    if (crash && space?.head_rev) {
      setCrash(null);
    }
  }, [space?.head_rev]);
  async function refresh() {
    if (refreshLock.current || refreshPending || inFlight(lastRun?.status) || refreshReason(space)) return;
    refreshLock.current = true;
    setRefreshPending(true);
    setActionError("");
    setAnnouncement("Refreshing\u2026");
    try {
      const run = await ctx.rest(`${base}/refresh`, { method: "POST" });
      controller.current?.postEvent("run.updated", run);
      if (!inFlight(run.status)) setAnnouncement(`Refresh ${run.status}: ${runResult(run)}`);
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
  if (!space) return /* @__PURE__ */ jsx6("div", { className: "ls-page", children: detail.error ? /* @__PURE__ */ jsxs6(ErrorState4, { title: "This Space could not be opened", description: errorText(detail.error), children: [
    /* @__PURE__ */ jsx6(Action, { onClick: () => detail.refetch(), children: "Try again" }),
    /* @__PURE__ */ jsx6(Action, { onClick: () => host2.navigate("/spaces"), children: "Spaces" })
  ] }) : /* @__PURE__ */ jsx6(Skeleton4, { style: { height: 400 } }) });
  const schedule = space.schedule;
  const busy = refreshPending || inFlight(lastRun?.status) || status === "updating";
  const reason = refreshReason(space);
  const pause = () => act("schedule", { paused: schedule.status !== "paused" });
  const pauseAction = schedule && ["active", "paused"].includes(schedule.status) && !archived ? /* @__PURE__ */ jsx6(Action, { icon: schedule.status === "paused" ? "play" : "debug-pause", onClick: pause, children: schedule.status === "paused" ? "Resume upkeep" : "Pause upkeep" }) : null;
  const opener = () => document.activeElement?.getAttribute("role") === "menuitem" ? overflow.current : document.activeElement;
  const openSheet = (kind, tab) => setSheet({ kind, tab, returnFocus: opener() });
  const openHistory = (tab) => openSheet("history", tab || "runs");
  const askConfirmation = (kind) => {
    confirmationTrigger.current = opener();
    setConfirmation(kind);
  };
  const crashMessage = diagnosticText(crash || space.attention?.message || "The Space hit repeated runtime errors.");
  return /* @__PURE__ */ jsxs6("div", { className: "ls-frame", "data-testid": "space-view", children: [
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
              "Last successful update ",
              /* @__PURE__ */ jsx6(Time, { at: space.freshness?.last_success_at }),
              " \xB7 source data from ",
              /* @__PURE__ */ jsx6(Time, { at: space.freshness?.source_as_of })
            ] })
          ] })
        ] })
      ] }),
      /* @__PURE__ */ jsxs6("div", { className: "ls-frame-actions", children: [
        /* @__PURE__ */ jsx6(SaveStatus, { write, announcement }),
        !building && /* @__PURE__ */ jsxs6(Fragment5, { children: [
          /* @__PURE__ */ jsx6("div", { className: "ls-wide-only", children: /* @__PURE__ */ jsx6(Action, { icon: "watch", onClick: () => openSheet("schedule"), children: schedule ? `${schedule.status === "paused" ? "Paused \xB7 " : ""}${schedule.cadence} ${schedule.timezone}` : "No schedule" }) }),
          /* @__PURE__ */ jsx6("div", { className: "ls-wide-only", children: pauseAction })
        ] }),
        /* @__PURE__ */ jsx6("span", { className: "ls-wide-only", children: /* @__PURE__ */ jsx6(Action, { onClick: () => openHistory(), children: "History" }) }),
        !building && /* @__PURE__ */ jsxs6(Fragment5, { children: [
          /* @__PURE__ */ jsx6(Action, { onClick: () => openSheet("permissions"), children: "Permissions" }),
          /* @__PURE__ */ jsx6(DisabledReason, { reason, children: /* @__PURE__ */ jsx6(Action, { primary: true, icon: "refresh", "aria-busy": busy, "aria-disabled": !!reason, title: reason || void 0, onClick: refresh, children: busy ? "Refreshing\u2026" : "Refresh now" }) })
        ] }),
        /* @__PURE__ */ jsxs6(DropdownMenu, { children: [
          /* @__PURE__ */ jsx6(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsx6(Action, { ref: overflow, "aria-label": "More Space actions", icon: "ellipsis" }) }),
          /* @__PURE__ */ jsxs6(DropdownMenuContent, { align: "end", children: [
            /* @__PURE__ */ jsx6("div", { className: "ls-compact-only", children: /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openHistory(), children: "History" }) }),
            !building && /* @__PURE__ */ jsxs6(Fragment5, { children: [
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => openSheet("schedule"), children: "Schedule" }),
              pauseAction && /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: pause, children: schedule.status === "paused" ? "Resume upkeep" : "Pause upkeep" }),
              /* @__PURE__ */ jsx6(DropdownMenuSeparator, {}),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => act("pin", { pinned: !space.pinned }), children: space.pinned ? "Unpin Space" : "Pin Space" }),
              /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => archived ? act("unarchive") : askConfirmation("archive"), children: archived ? "Restore Space" : "Archive Space\u2026" }),
              archived && /* @__PURE__ */ jsx6(DropdownMenuItem, { onSelect: () => askConfirmation("delete"), children: "Delete\u2026" })
            ] })
          ] })
        ] })
      ] })
    ] }),
    actionError && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: actionError }),
    detail.error && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: "Space status could not be refreshed. You're seeing the last loaded state.", actions: /* @__PURE__ */ jsx6(Action, { onClick: () => detail.refetch(), children: "Try again" }), children: errorText(detail.error) }),
    changes.error && /* @__PURE__ */ jsx6(Banner, { kind: "failed", title: "Live record updates are delayed. Your displayed data may be out of date.", actions: /* @__PURE__ */ jsx6(Action, { onClick: () => changes.refetch(), children: "Retry live updates" }), children: errorText(changes.error) }),
    /* @__PURE__ */ jsx6(WriteBanner, { write, setWrite, onCompare: () => openSheet("compare"), onUpdated: () => {
      controller.current?.dismissWrite(write.token);
      setReload((n) => n + 1);
    } }),
    archived ? /* @__PURE__ */ jsx6(Banner, { title: "This Space is archived. Refreshes and schedules are off.", actions: /* @__PURE__ */ jsxs6(Fragment5, { children: [
      /* @__PURE__ */ jsx6(Action, { onClick: () => act("unarchive"), children: "Restore Space" }),
      /* @__PURE__ */ jsx6(Action, { danger: true, onClick: () => askConfirmation("delete"), children: "Delete\u2026" })
    ] }), children: "Restore it to resume upkeep. Delete removes it and its data permanently." }) : status === "failed" ? /* @__PURE__ */ jsxs6(Banner, { kind: "failed", title: `Refresh failed at ${absolute(space.freshness?.last_attempt_at)}. You're seeing data from ${absolute(space.freshness?.last_success_at)}.`, actions: /* @__PURE__ */ jsxs6(Fragment5, { children: [
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
    /* @__PURE__ */ jsxs6("section", { className: "ls-content", "aria-label": "Space content", children: [
      /* @__PURE__ */ jsx6("div", { className: "ls-caption", children: "Content below the bar is generated by this Space and runs sandboxed" }),
      /* @__PURE__ */ jsx6("div", { className: `ls-sandbox${status === "failed" ? " ls-stale" : ""}`, children: building ? /* @__PURE__ */ jsxs6("div", { className: "ls-building", children: [
        /* @__PURE__ */ jsxs6("p", { role: "status", children: [
          space.owner,
          " is building the first version. This opens automatically when it's ready."
        ] }),
        /* @__PURE__ */ jsx6(Skeleton4, { style: { height: 100 } }),
        /* @__PURE__ */ jsx6(Skeleton4, { style: { height: 180 } })
      ] }) : status === "crashed" ? /* @__PURE__ */ jsxs6("div", { className: "ls-crash", children: [
        /* @__PURE__ */ jsx6(ErrorState4, { title: `${space.name} stopped working`, description: "The Space hit an error and was stopped. Your records are safe and weren't changed by the crash." }),
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
      ] }) : archived ? /* @__PURE__ */ jsx6("div", { className: "ls-building", children: /* @__PURE__ */ jsx6("p", { children: "Restore Space to open its content. Your records and revisions are kept." }) }) : /* @__PURE__ */ jsx6("div", { ref: content, className: "ls-mount", "data-testid": "space-host" }) })
    ] }),
    sheet?.kind === "permissions" && /* @__PURE__ */ jsx6(PermissionsSheet, { returnFocus: sheet.returnFocus, ctx, space, onClose: () => setSheet(null), onChanged: () => detail.refetch() }),
    sheet?.kind === "history" && /* @__PURE__ */ jsx6(HistorySheet, { returnFocus: sheet.returnFocus, ctx, space, initialTab: sheet.tab, onClose: () => setSheet(null), onChanged: () => detail.refetch() }),
    sheet?.kind === "schedule" && /* @__PURE__ */ jsx6(ScheduleSheet, { returnFocus: sheet.returnFocus, ctx, space, onClose: () => setSheet(null), onChanged: () => detail.refetch() }),
    sheet?.kind === "compare" && write && /* @__PURE__ */ jsx6(Drawer, { returnFocus: sheet.returnFocus, title: "Compare record changes", description: "Your submitted change and the latest stored record", onClose: () => setSheet(null), children: /* @__PURE__ */ jsxs6("div", { className: "ls-compare", children: [
      /* @__PURE__ */ jsx6("h2", { children: "Your change" }),
      /* @__PURE__ */ jsx6("pre", { className: "ls-diagnostic", children: JSON.stringify(write.args, null, 2) }),
      /* @__PURE__ */ jsx6("h2", { children: "Updated record" }),
      /* @__PURE__ */ jsx6("pre", { className: "ls-diagnostic", children: JSON.stringify(write.reply?.error?.current, null, 2) })
    ] }) }),
    confirmation && /* @__PURE__ */ jsx6(DecisionDialog, { returnFocus: confirmationTrigger.current, danger: true, title: confirmation === "delete" ? `Delete ${space.name}?` : `Archive ${space.name}?`, description: confirmation === "delete" ? "Delete removes this Space, all its records and revisions permanently and stops future upkeep. Exported copies aren't recalled." : "Archiving stops refreshes and schedules. Your records and revisions are kept. You can restore this Space later.", confirmLabel: confirmation === "delete" ? "Delete Space" : "Archive Space", onClose: () => setConfirmation(null), onConfirm: async () => {
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
.ls-frame{height:100%;display:flex;flex-direction:column}.ls-framebar{position:sticky;top:0;z-index:1;display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:16px 22px;border-bottom:1px solid var(--ls-line);background:var(--ui-bg-primary)}.ls-identity{display:flex;align-items:center;gap:10px;min-width:0;flex:1}.ls-name-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.ls-frame-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px}.ls-frame-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.ls-save{font-size:12px;display:inline-flex;gap:5px;align-items:center;min-width:100px}.ls-content{display:flex;flex:1;min-height:420px;flex-direction:column;padding:16px 20px 20px;gap:8px}.ls-caption{font-size:12px;color:var(--ui-text-secondary)}.ls-sandbox{flex:1;min-height:380px;border:1px solid var(--ls-line);border-radius:12px;overflow:hidden;position:relative}.ls-mount{height:100%;min-height:380px}.ls-stale{filter:saturate(.7)}.ls-banner{display:flex;gap:10px;padding:14px 22px;border-bottom:1px solid var(--ls-line);background:var(--ui-bg-secondary);font-size:13px}.ls-banner.ls-failed,.ls-banner.ls-crashed,.ls-banner.ls-conflict{border-color:color-mix(in srgb,var(--ls-danger) 45%,var(--ls-line));background:color-mix(in srgb,var(--ls-danger) 8%,var(--ui-bg-primary))}.ls-banner.ls-blocked{border-color:var(--ls-warning)}.ls-crash{max-width:620px;padding:40px 24px;margin:auto}.ls-diagnostic{max-height:180px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:var(--ui-bg-secondary);border:1px solid var(--ls-line);font:12px/1.5 var(--font-mono,monospace)}.ls-building{padding:40px;display:grid;gap:16px}.ls-compact-only{display:none}
.ls-sheet{position:fixed!important;top:0!important;right:0!important;left:auto!important;bottom:0!important;transform:none!important;translate:none!important;width:min(460px,100vw)!important;max-width:460px!important;max-height:100dvh!important;height:100dvh!important;border-radius:0!important;background:var(--ls-surface)!important;animation:none!important}.ls-sheet-body{display:flex!important;flex-direction:column!important;height:100%;max-height:100dvh!important;padding:0!important;gap:0!important;overflow:hidden!important}.ls-sheet-header{display:flex!important;flex-direction:row!important;justify-content:space-between;align-items:center;padding:16px;border-bottom:1px solid var(--ls-line);flex:none}.ls-sheet-scroll{padding:18px 16px;overflow:auto;min-height:0;flex:1}.ls-disclosure{margin:16px 16px 0;padding:12px;border:1px solid var(--ls-line);border-radius:10px;font-size:12px;flex:none;line-height:1.55}.ls-disclosure p{margin:6px 0 0}.ls-section{margin:0 0 22px}.ls-section-title{font-size:12px!important;font-weight:600!important;letter-spacing:.025em;margin:4px 0 12px!important}.ls-grant,.ls-row{padding:12px;border:1px solid var(--ls-line);border-radius:8px;margin-bottom:12px}.ls-row-top{display:flex;align-items:center;gap:8px;justify-content:space-between}.ls-row-top>strong{display:flex;gap:8px;align-items:center}.ls-pending{background:color-mix(in srgb,var(--ls-warning) 6%,var(--ls-surface))}.ls-future{border-style:dashed}.ls-future p{font-size:12px;color:var(--ui-text-secondary)}.ls-audit{padding-left:18px;font-size:12px}.ls-tabs{margin-bottom:16px}.ls-confirm{max-width:520px!important}.ls-compare{display:grid;gap:12px}.ls-directive{padding:14px;border:1px solid var(--ui-stroke-secondary);border-radius:12px;max-width:440px;background:var(--ui-bg-card,var(--ui-bg-secondary));display:grid;gap:10px}.ls-spin{animation:ls-spin 1s linear infinite}@keyframes ls-spin{to{transform:rotate(360deg)}}
@media(max-width:1200px){.ls-frame-actions{width:100%;justify-content:flex-end}}@media(max-width:899px){.ls-wide-only{display:none!important}.ls-compact-only{display:inline-flex}.ls-page{padding:20px 16px}.ls-framebar{padding:12px}.ls-frame-meta{gap:4px}.ls-frame-actions{justify-content:flex-start}.ls-content{padding:12px}.ls-page-heading{flex-wrap:wrap;gap:4px}.ls-sort{width:100%}.ls-sheet{width:min(460px,100vw)!important}}@media(prefers-reduced-motion:reduce){.ls-spin{animation:none}.ls-root *,.ls-sheet *,.ls-confirm *{transition:none!important;animation:none!important}}@media(forced-colors:active){.ls-pill,.ls-card,.ls-tile,.ls-action{border:1px solid CanvasText!important}}
`;

// src/desktop/ui/context.jsx
import { host as host3, useValue } from "@hermes/plugin-sdk";
import { useMemo } from "react";
var currentScope = () => JSON.stringify([host3.state.connectionId.get(), host3.state.profile.get()]);
function useScopedContext(ctx) {
  const connection = useValue(host3.state.connectionId);
  const profile = useValue(host3.state.profile);
  const queryScope = JSON.stringify([connection, profile]);
  return useMemo(() => ({ ...ctx, queryScope, rest: scopedRest((path, options) => ctx.rest(path, options), currentScope, queryScope) }), [ctx, queryScope]);
}

// src/desktop/plugin.src.js
function SpacesPage({ ctx }) {
  const scoped = useScopedContext(ctx);
  const [hash, setHash] = useState7(() => typeof location === "undefined" ? "" : location.hash);
  useEffect2(() => {
    const changed = () => setHash(location.hash);
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const sid = routeSpace(hash);
  return jsxs7("div", { className: "ls-root", children: [jsx7("style", { children: styles }), sid ? jsx7(SpaceView, { ctx: scoped, sid }, `${scoped.queryScope}:${sid}`) : jsx7(SpacesIndex, { ctx: scoped }, scoped.queryScope)] });
}
function OpenSpaceCard({ ctx, sid }) {
  const scoped = useScopedContext(ctx);
  const query = useQuery5({ queryKey: ["living-spaces", scoped.queryScope, sid, "detail"], queryFn: () => scoped.rest(spacePath(sid)), refetchInterval: 2e3 });
  if (!query.data) return query.error ? jsx7(ErrorState5, { title: "This Space could not be loaded", description: query.error.message }) : jsx7("span", { role: "status", children: "Loading Space\u2026" });
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
