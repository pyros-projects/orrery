// The Orrery Prompt node becomes one app: prompt, presets, libraries, galaxy, help.
import { api } from "../../scripts/api.js";
import { app } from "../../scripts/app.js";
import { downstream } from "./app/model.js";
import { OrreryApp } from "./app/shell.js";

const NO_PRESET = "(none)";
const MIN = { width: 620, height: 560 };

function loadStyles() {
  if (document.getElementById("orrery-css")) return;
  const link = document.createElement("link");
  link.id = "orrery-css";
  link.rel = "stylesheet";
  link.href = new URL("./orrery.css", import.meta.url).href;
  document.head.appendChild(link);
}

// widget.hidden is the official switch since frontend 1.53.5; computeSize covers older canvases.
// Never change widget.type: that breaks serialization.
function hide(widget) {
  if (!widget) return;
  widget.hidden = true;
  widget.options = { ...widget.options, hidden: true };
  widget.computeSize = () => [0, -4];
  const el = widget.element || widget.inputEl;
  if (el) el.style.display = "none";
}

// The graph as the Generate button sees it: which node feeds which, and which ones are outputs.
function graphOf(node) {
  const g = node.graph || app.graph;
  const linkOf = (id) => (g.links?.get ? g.links.get(id) : g.links?.[id]);
  return (g._nodes || g.nodes || []).map((n) => ({
    id: n.id,
    type: n.comfyClass || n.type,
    output: !!n.constructor?.nodeData?.output_node,
    targets: (n.outputs || []).flatMap((o) => (o.links || []).map((l) => linkOf(l)?.target_id)).filter((t) => t != null),
  }));
}

function mount(node) {
  loadStyles();
  const find = (name) => node.widgets?.find((w) => w.name === name);
  const template = find("template"), preset = find("preset"), home = find("home"), params = find("params");
  [template, preset, home, params].forEach(hide);
  node.properties = node.properties || {};

  // the control_after_generate combo that belongs to an INT widget (seed and segment each have one)
  const controlOf = (name) => {
    const i = node.widgets?.findIndex((w) => w.name === name) ?? -1;
    const w = node.widgets?.[i];
    return w?.linkedWidgets?.find((l) => l.name === "control_after_generate")
      ?? (node.widgets?.[i + 1]?.name === "control_after_generate" ? node.widgets[i + 1] : null);
  };
  // A new node plays a reel clip after clip; configure() restores a saved workflow's choice later.
  const segmentControl = controlOf("segment");
  if (segmentControl) segmentControl.value = "increment";

  const set = (name, value) => {
    const w = find(name);
    if (!w) return;
    w.value = value;
    w.callback?.(value);
    node.setDirtyCanvas?.(true, true);
  };
  const batch = { id: 0, done: null };  // the Generate loop that is queueing right now
  const bridge = {
    props: node.properties,
    getText: () => template?.value ?? "",
    setText: (text) => set("template", text),
    getSeed: () => find("seed")?.value ?? 0,
    setSeed: (seed) => set("seed", seed),
    setControl: (mode) => { const c = controlOf("seed"); if (c) { c.value = mode; node.setDirtyCanvas?.(true, true); } },
    getControl: () => controlOf("seed")?.value ?? "",
    getTarget: () => find("target")?.value || "text",
    setTarget: (target) => set("target", target),
    getParams: () => { try { return JSON.parse(params?.value || "{}") || {}; } catch { return {}; } },
    setParams: (values) => set("params", Object.keys(values).length ? JSON.stringify(values) : ""),
    home: () => home?.value || "",
    nodeId: () => String(node.id),
    downstream: () => downstream(graphOf(node), node.id),
    // Queue only the outputs this node feeds (ComfyUI's partial execution): its branch, not the whole canvas.
    // One queue item per run, so control after generate steps seed and segment between them, and a newer
    // Generate or Restart stops the loop between two runs (ComfyUI's batch count cannot be stopped).
    generate: async (runs = 1) => {
      const { outputs } = downstream(graphOf(node), node.id);
      if (!outputs.length) return 0;
      const id = ++batch.id;
      batch.done = (async () => {
        let queued = 0;
        for (; queued < runs && id === batch.id; queued++) await app.queuePrompt(0, 1, { queueNodeIds: outputs.map(String) });
        return queued;
      })();
      return batch.done;  // how many runs went into the queue
    },
    stopGenerate: async () => { batch.id++; await batch.done?.catch(() => {}); },
    getSegment: () => find("segment")?.value ?? 0,
    setSegment: (value) => set("segment", value),
    // Restart: dequeue this node's pending runs and interrupt its running one; other jobs stay queued.
    cancelRuns: async () => {
      const q = await (await api.fetchApi("/queue")).json();
      const wf = (node.graph?.rootGraph || app.rootGraph || app.graph)?.id;
      const ours = (item) => (!wf || item[3]?.extra_pnginfo?.workflow?.id === wf)
        && Object.entries(item[2] || {}).some(([k, n]) => n?.class_type === "OrreryPrompt" && (k === String(node.id) || k.endsWith(`:${node.id}`)));
      const post = (path, body) => api.fetchApi(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const pending = (q.queue_pending || []).filter(ours).map((i) => i[1]);
      const running = (q.queue_running || []).filter(ours).map((i) => i[1]);
      if (pending.length) await post("/queue", { delete: pending });
      for (const id of running) await post("/interrupt", { prompt_id: id });
      return pending.length + running.length;
    },
    forwardWheel: (e) => app.canvas?.processMouseWheel?.(e),
    takeLegacyPreset: () => {
      const name = preset?.value;
      if (!name || name === NO_PRESET) return null;
      preset.value = NO_PRESET;
      return name;
    },
  };

  const orrery = new OrreryApp(bridge);
  const widget = node.addDOMWidget("orrery_app", "orrery", orrery.root, {
    serialize: false,
    hideOnZoom: true,
    getMinHeight: () => MIN.height,
  });
  widget.serialize = false;
  widget.computeLayoutSize = () => ({ minHeight: MIN.height, minWidth: MIN.width, maxHeight: 1e6, maxWidth: 1e6 });
  if (node.size[0] < 700 || node.size[1] < 900) node.setSize([Math.max(node.size[0], 700), Math.max(node.size[1], 960)]);

  // configure() (a loaded workflow's values and properties) runs after nodeCreated.
  setTimeout(() => orrery.start(), 0);

  // Which reel segment runs: the node announces it; a finished, failed or stopped prompt ends it.
  const mine = (id) => id != null && (String(id) === String(node.id) || String(id).endsWith(`:${node.id}`));
  const onSegment = ({ detail }) => { if (mine(detail?.node)) orrery.showRun(detail); };
  const onDone = ({ detail }) => orrery.runDone(detail?.prompt_id);
  const ENDS = ["execution_success", "execution_error", "execution_interrupted"];
  api.addEventListener("orrery.segment", onSegment);
  ENDS.forEach((e) => api.addEventListener(e, onDone));
  const segment = find("segment"), segmentChanged = segment?.callback;
  if (segment) segment.callback = function (...args) { const r = segmentChanged?.apply(this, args); orrery.refreshRun(); return r; };

  const onRemoved = node.onRemoved;
  node.onRemoved = function (...args) {
    api.removeEventListener("orrery.segment", onSegment);
    ENDS.forEach((e) => api.removeEventListener(e, onDone));
    orrery.destroy();
    return onRemoved?.apply(this, args);
  };
}

app.registerExtension({
  name: "orrery.app",
  setup: loadStyles,
  nodeCreated(node) {
    if (node.comfyClass === "OrreryPrompt") mount(node);
  },
});
