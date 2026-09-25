// The orrery app: one element that lives in the node or, in the big view, over the canvas.
import { client } from "./api.js";
import { renderGalaxy } from "./galaxy.js";
import { renderHelp } from "./help.js";
import { esc } from "./highlight.js";
import { icon, LOGO } from "./icons.js";
import { renderLibraries } from "./libraries.js";
import { renderPresets } from "./presets.js";
import { refreshFoot, renderPrompt } from "./prompt.js";
import { openSettings } from "./settings.js";
import { renderTest } from "./test.js";

const TABS = [
  ["prompt", "Prompt", renderPrompt],
  ["test", "Test", renderTest],
  ["presets", "Presets", renderPresets],
  ["libraries", "Libraries", renderLibraries],
  ["galaxy", "Galaxy", renderGalaxy],
  ["help", "Help", renderHelp],
];

function canScroll(el, dy) {
  if (!/(auto|scroll)/.test(getComputedStyle(el).overflowY) || el.scrollHeight <= el.clientHeight) return false;
  return dy < 0 ? el.scrollTop > 0 : el.scrollTop + el.clientHeight < el.scrollHeight - 1;
}

export class OrreryApp {
  constructor(bridge) {
    this.bridge = bridge;
    this.api = client(() => bridge.home());
    this.state = {
      tab: bridge.props.orrery_tab || "prompt", big: false,
      pick: false, pickQ: "", pickI: 0,
      pFilter: "all", pSearch: "", pOpen: null, pDetail: null, pConfirm: false, pRoll: null,
      lib: null, libSearch: "", libTag: null, libNew: null,
      gScope: "all", gRating: null, gPick: null, gOpen: null,
    };
    this.data = { presets: [], favorites: new Set(), recent: [], completion: null, libraries: null, rows: null, weights: {}, llm: null };
    this.base = null;
    this.run = null;  // {segment, prompt}: the reel segment this node is generating right now
    this.uid = Math.random().toString(36).slice(2, 8);  // keeps element ids unique across nodes
    this.root = document.createElement("div");
    this.root.className = "orrery-app";
    this.root.innerHTML = `<div class="app-head"><div class="brand">${LOGO}orrery</div><nav class="tabs" role="tablist"></nav>`
      + `<button class="icon-btn gear-btn" title="Settings: home folder, language model">${icon("gear")}</button><button class="icon-btn big-btn"></button></div><section class="view"></section><div class="sheet-host"></div><div class="toast-host"></div>`;
    this.view = this.$(".view");
    this.$(".tabs").addEventListener("click", (e) => { const t = e.target.closest("[data-tab]"); if (t) this.go(t.dataset.tab); });
    this.$(".big-btn").addEventListener("click", () => this.setBig(!this.state.big));
    this.$(".gear-btn").addEventListener("click", () => openSettings(this));
    this.isolate();
    // A preview that fails to load (file moved, video without frames) becomes a quiet placeholder.
    this.root.addEventListener("error", (e) => {
      if (e.target.tagName !== "IMG" || e.target.dataset.failed) return;
      const ph = document.createElement("div");
      ph.className = "missing";
      ph.innerHTML = icon("image");
      if (e.target.dataset.gopen) ph.dataset.gopen = e.target.dataset.gopen;
      e.target.dataset.failed = "1";
      e.target.replaceWith(ph);
    }, true);
  }

  $(sel) { return this.root.querySelector(sel); }
  get text() { return this.bridge.getText(); }
  set text(t) { this.bridge.setText(t); }
  get preset() { return this.bridge.props.orrery_preset || null; }
  set preset(name) {
    if (name) this.bridge.props.orrery_preset = name;
    else delete this.bridge.props.orrery_preset;
  }
  card(name) { return this.data.presets.find((p) => p.name === name); }
  known() { return new Set((this.data.completion?.libraries || []).map((l) => l.name)); }
  llmActive() { return !!this.data.llm?.file; }
  dirty() { return this.preset ? this.base !== null && this.text !== this.base : this.text.trim() !== ""; }

  async start() {
    if (this.started) return;
    this.started = true;
    await Promise.all([this.refreshPresets(), this.refreshCompletion(),
      this.api.llm().then((l) => { this.data.llm = l; }).catch(() => {})]).catch((e) => this.fail(e));
    const legacy = this.bridge.takeLegacyPreset();
    if (legacy) await this.loadPreset(legacy, { quiet: true });
    else if (this.preset) await this.fetchBase();
    this.stopListening = this.api.onRunDone(() => this.afterRun());
    this.stopCapture = this.api.onExecuted((e) => this.capture(e.detail || {}));
    this.render();
  }

  // A run may have let the language model write libraries: refresh, and point at anything to review.
  async afterRun() {
    const before = new Set((this.data.libraries || []).filter((l) => l.pending || (l.pending_entries || []).length).map((l) => l.name));
    let libs;
    try { libs = (await this.api.libraries()).libraries; } catch { return; }
    this.data.libraries = libs;
    this.data.libStale = false;
    this.refreshCompletion().catch(() => {});
    const fresh = libs.filter((l) => (l.pending || (l.pending_entries || []).length) && !before.has(l.name));
    if (this.state.tab === "libraries") this.render();
    if (fresh.length) {
      this.toast(`The language model wrote ${fresh.map((l) => `<b>__${esc(l.name)}__</b>`).join(", ")}`, {
        label: "Review", run: () => { this.state.lib = fresh[0].name; this.go("libraries"); },
      });
    }
  }
  async fetchBase() {
    try { this.base = (await this.api.preset(this.preset)).text; } catch { this.base = null; }
  }
  async refreshPresets() {
    const d = await this.api.presets();
    this.data.presets = d.presets;
    this.data.favorites = new Set(d.favorites);
    this.data.recent = d.recent;
    this.data.quickstart = d.quickstart !== false;
  }
  async refreshCompletion() { this.data.completion = await this.api.completions(); }

  render() {
    const n = { presets: this.data.presets.length, libraries: this.data.completion?.libraries.length, galaxy: this.data.rows?.length };
    this.$(".tabs").innerHTML = TABS.map(([k, label]) => `<button class="tab" role="tab" aria-selected="${this.state.tab === k}" data-tab="${k}">`
      + `${label}${n[k] ? `<span class="n">${n[k]}</span>` : ""}</button>`).join("");
    const big = this.$(".big-btn");
    big.innerHTML = icon(this.state.big ? "shrink" : "expand");
    big.title = this.state.big ? "Back into the node (Esc)" : "Big view";
    TABS.find(([k]) => k === this.state.tab)[2](this);
  }
  go(tab) {
    // Opening Libraries reads the folder again: files added outside the node show up without a reload.
    if (tab === "libraries" && this.state.tab !== "libraries") {
      this.data.libStale = true;
      this.refreshCompletion().catch(() => {});
    }
    this.state.tab = tab;
    this.state.pick = false;
    this.bridge.props.orrery_tab = tab;
    this.render();
  }

  async loadPreset(name, { quiet = false, tab = true } = {}) {
    const prev = { preset: this.preset, base: this.base, text: this.text, params: this.bridge.getParams() };
    const wasDirty = this.dirty();
    try {
      const p = await this.api.preset(name);
      this.preset = p.name;
      this.base = p.text;
      this.text = p.text;
      this.bridge.setParams({});
    } catch (e) { return this.fail(e); }
    if (this.state.test) Object.assign(this.state.test, { rolls: null, freq: null, offset: 0, start: 0 });
    this.state.pick = false;
    this.api.recent(name).then((r) => { this.data.recent = r.recent; }).catch(() => {});
    if (tab) this.state.tab = "prompt";
    this.render();
    if (!quiet) {
      this.toast(`Loaded <b>@${esc(name)}</b>`, wasDirty ? {
        label: "Undo", run: () => {
          this.preset = prev.preset; this.base = prev.base; this.text = prev.text; this.bridge.setParams(prev.params); this.render();
        },
      } : null);
    }
  }

  toast(html, action) {
    clearTimeout(this.toastTimer);
    const host = this.$(".toast-host");
    host.innerHTML = `<div class="toast" role="status"><span>${html}</span>${action ? `<button class="btn act">${esc(action.label)}</button>` : ""}`
      + `<button class="mini close" aria-label="Dismiss">${icon("x")}</button></div>`;
    if (action) host.querySelector(".act").onclick = () => { host.innerHTML = ""; action.run(); };
    host.querySelector(".close").onclick = () => { host.innerHTML = ""; };
    this.toastTimer = setTimeout(() => { host.innerHTML = ""; }, 5200);
  }
  fail(err) {
    console.warn("[orrery]", err);
    this.toast(esc(err?.message || String(err)));
  }

  openSheet(html) {
    const host = this.$(".sheet-host");
    host.innerHTML = `<div class="sheet">${html}</div>`;
    host.firstChild.addEventListener("mousedown", (e) => { if (e.target === host.firstChild) this.closeSheet(); });
    return host.firstChild;
  }
  closeSheet() { this.$(".sheet-host").innerHTML = ""; }
  sheetOpen() { return !!this.$(".sheet"); }

  setBig(on) {
    if (on === this.state.big) return;
    this.state.big = on;
    if (on) {
      this.home = this.root.parentElement;
      this.parked = document.createElement("div");
      this.parked.className = "orrery-parked";
      this.parked.innerHTML = `Open in the big view · Esc or ${icon("shrink")} brings it back`;
      this.home.appendChild(this.parked);
      this.overlay = document.createElement("div");
      this.overlay.className = "orrery-overlay";
      this.overlay.innerHTML = '<div class="frame"></div>';
      this.overlay.addEventListener("mousedown", (e) => { if (e.target === this.overlay) this.setBig(false); });
      this.overlay.firstChild.appendChild(this.root);
      document.body.appendChild(this.overlay);
      this.root.classList.add("big");
    } else {
      this.parked?.remove();
      this.home?.appendChild(this.root);
      this.overlay?.remove();
      this.root.classList.remove("big");
    }
    this.render();
  }

  // Keep ComfyUI's shortcuts and canvas gestures out of the app, but let the wheel zoom the
  // canvas wherever nothing inside can scroll, and let Ctrl+Enter still queue.
  isolate() {
    this.root.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") return;
      if (e.key === "Escape" && this.state.big && !e.defaultPrevented && !this.sheetOpen() && !this.state.pick) this.setBig(false);
      e.stopPropagation();
    });
    this.root.addEventListener("wheel", (e) => {
      if (this.state.big) return;
      for (let el = e.target; el && el !== this.root; el = el.parentElement) if (canScroll(el, e.deltaY)) return;
      e.preventDefault();
      this.bridge.forwardWheel(e);
    }, { passive: false });
  }

  // Generate without Orrery Log: when a Save node downstream of this node writes files, they go to the
  // galaxy with this run's picks (the node remembered them under the prompt id).
  async capture(detail) {
    const { outputs, log } = this.bridge.downstream?.() || { outputs: [], log: true };
    if (log || !outputs.map(String).includes(String(detail.display_node ?? detail.node))) return;
    const out = detail.output || {};
    const media = ["images", "gifs", "videos", "audio"].flatMap((k) => out[k] || []).filter((m) => m && m.filename);
    if (!media.length || !detail.prompt_id) return;
    try {
      const res = await this.api.captureOutputs({ prompt_id: detail.prompt_id, node: this.bridge.nodeId(), media });
      if (res.logged) { this.data.rows = null; if (this.state.tab === "galaxy") this.render(); }
    } catch { /* an older run or a restarted ComfyUI: nothing to log */ }
  }

  showRun(d) {
    this.run = d.end ? null : { segment: d.segment, prompt: d.prompt_id };
    if (d.end) this.toast(`Segment <b>${d.segment}</b> is past the end of the reel, so nothing ran. Restart plays it from the beginning.`);
    this.refreshRun();
  }
  runDone(prompt) {
    if (!this.run || (prompt && this.run.prompt && prompt !== this.run.prompt)) return;
    this.run = null;
    this.refreshRun();
  }
  refreshRun() { if (this.state.tab === "prompt") refreshFoot(this); }

  destroy() {
    this.stopListening?.();
    this.stopCapture?.();
    clearTimeout(this.toastTimer);
    this.overlay?.remove();
    this.parked?.remove();
  }
}
