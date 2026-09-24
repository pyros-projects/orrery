// The Orrery Prompt node becomes one app: prompt, presets, libraries, galaxy, help.
import { app } from "../../scripts/app.js";
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

function mount(node) {
  loadStyles();
  const find = (name) => node.widgets?.find((w) => w.name === name);
  const template = find("template"), preset = find("preset"), home = find("home");
  [template, preset, home].forEach(hide);
  node.properties = node.properties || {};

  const set = (name, value) => {
    const w = find(name);
    if (!w) return;
    w.value = value;
    w.callback?.(value);
    node.setDirtyCanvas?.(true, true);
  };
  const bridge = {
    props: node.properties,
    getText: () => template?.value ?? "",
    setText: (text) => set("template", text),
    getSeed: () => find("seed")?.value ?? 0,
    setSeed: (seed) => set("seed", seed),
    setControl: (mode) => set("control_after_generate", mode),
    getTarget: () => find("target")?.value || "text",
    home: () => home?.value || "",
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

  const onRemoved = node.onRemoved;
  node.onRemoved = function (...args) {
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
