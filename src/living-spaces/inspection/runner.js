(() => {
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

  // src/inspection/runner.mjs
  var MAX_QUEUE = 1e3;
  function createInspector() {
    const queue = [];
    const pending = /* @__PURE__ */ new Map();
    const events = [];
    let seq = 0;
    let mounted = null;
    let wake = null;
    let refused = 0;
    const notify = () => {
      if (wake) {
        const w = wake;
        wake = null;
        w();
      }
    };
    const call = (op, args, _transfer, requestId) => new Promise((resolve) => {
      if (queue.length >= MAX_QUEUE) {
        refused++;
        resolve({ ok: false, error: { code: "limit", message: "Inspection bridge queue is full" } });
        return;
      }
      const id = ++seq;
      pending.set(id, resolve);
      const rid = op === "editor.save" ? requestId : ["data.put", "data.delete", "data.batch"].includes(op) ? `inspect_write_${id}` : void 0;
      queue.push({ id, op, args, ...rid ? { request_id: rid } : {} });
      notify();
    });
    return {
      mount(bundle, grants) {
        const container = document.createElement("div");
        container.id = "space";
        container.style.cssText = "position:fixed;inset:0";
        document.body.style.margin = "0";
        document.body.append(container);
        mounted = mountSpace(container, { bundle, grants, call, onEvent: (event) => {
          events.push(event);
          notify();
        } });
        return true;
      },
      // Resolves with everything queued, or after `ms` with nothing.
      next(ms) {
        const drain = () => ({ requests: queue.splice(0), events: events.splice(0), refused, viewport: [innerWidth, innerHeight, devicePixelRatio] });
        if (queue.length || events.length) return Promise.resolve(drain());
        return new Promise((resolve) => {
          const timer = setTimeout(() => {
            wake = null;
            resolve(drain());
          }, ms);
          wake = () => {
            clearTimeout(timer);
            resolve(drain());
          };
        });
      },
      reply(id, body) {
        const resolve = pending.get(id);
        if (!resolve) return false;
        pending.delete(id);
        resolve(body);
        return true;
      },
      destroy() {
        for (const resolve of pending.values()) resolve({ ok: false, error: { code: "session_invalid", message: "Inspection ended" } });
        pending.clear();
        mounted?.destroy();
        mounted = null;
        return true;
      }
    };
  }
  Object.defineProperty(globalThis, "__lsInspect", { value: createInspector() });
})();
