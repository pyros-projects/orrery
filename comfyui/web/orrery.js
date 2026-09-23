// Autocomplete for the Orrery Prompt template: __libraries__, [tags], $bindings, H3 words.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { missingLibraries, suggest } from "./orrery-complete.js";

const STYLE = `
.orrery-complete { position: fixed; z-index: 10000; min-width: 220px; max-width: 420px;
  background: var(--comfy-menu-bg, #202020); color: var(--input-text, #ddd);
  border: 1px solid var(--border-color, #444); border-radius: 6px; font: 12px monospace;
  box-shadow: 0 4px 16px rgba(0,0,0,.4); overflow: hidden; }
.orrery-complete ul { list-style: none; margin: 0; padding: 2px 0; max-height: 240px; overflow-y: auto; }
.orrery-complete li { display: flex; justify-content: space-between; gap: 16px; padding: 3px 8px; cursor: pointer; }
.orrery-complete li.active { background: var(--comfy-input-bg, #333); }
.orrery-complete li span:last-child { opacity: .55; }
.orrery-complete .preview { padding: 4px 8px; border-top: 1px solid var(--border-color, #444);
  opacity: .7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
`;

const MIRRORED = ["boxSizing", "width", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
  "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth", "fontFamily",
  "fontSize", "fontWeight", "lineHeight", "letterSpacing", "wordSpacing", "tabSize"];

// Screen position just below the caret; the canvas zooms textareas with a CSS transform.
function caretPoint(ta) {
  const mirror = document.createElement("div");
  const css = getComputedStyle(ta);
  for (const p of MIRRORED) mirror.style[p] = css[p];
  Object.assign(mirror.style, { position: "absolute", visibility: "hidden", top: "0", left: "-9999px",
    whiteSpace: "pre-wrap", overflowWrap: "break-word" });
  mirror.textContent = ta.value.slice(0, ta.selectionEnd);
  const mark = document.createElement("span");
  mark.textContent = "​";
  mirror.appendChild(mark);
  document.body.appendChild(mirror);
  const box = ta.getBoundingClientRect();
  const scale = box.width / (ta.offsetWidth || 1);
  const point = {
    x: box.left + (mark.offsetLeft - ta.scrollLeft) * scale,
    y: box.top + (mark.offsetTop - ta.scrollTop + mark.offsetHeight) * scale,
  };
  mirror.remove();
  return point;
}

class Completer {
  constructor(node, ta) {
    this.node = node;
    this.ta = ta;
    this.data = null;
    this.items = [];
    this.active = 0;
    this.box = document.createElement("div");
    this.box.className = "orrery-complete";
    this.box.style.display = "none";
    document.body.appendChild(this.box);
    ta.addEventListener("focus", () => this.refresh());
    ta.addEventListener("input", () => { this.update(); this.check(); });
    ta.addEventListener("keydown", (e) => this.key(e), true);
    ta.addEventListener("blur", () => this.close());
  }

  async refresh() {
    const home = this.node.widgets?.find((w) => w.name === "home")?.value ?? "";
    try {
      const res = await api.fetchApi(`/orrery/completions?home=${encodeURIComponent(home)}`);
      if (res.ok) this.data = await res.json();
    } catch (err) {
      console.warn("[orrery] completions unavailable", err);
    }
    this.check();
  }

  check() {
    if (!this.data) return;
    const missing = missingLibraries(this.ta.value, this.data);
    this.ta.style.outline = missing.length ? "1px solid #d05050" : "";
    this.ta.title = missing.length
      ? missing.map((n) => `unknown library __${n}__ (create it: orrery lib gen ${n})`).join("\n")
      : "";
  }

  update() {
    const found = suggest(this.ta.value, this.ta.selectionEnd, this.data);
    this.items = found.items;
    this.from = found.replaceFrom;
    this.active = 0;
    if (this.items.length) this.render(); else this.close();
  }

  render() {
    const item = this.items[this.active];
    this.box.innerHTML = "";
    const list = document.createElement("ul");
    this.items.forEach((it, i) => {
      const li = document.createElement("li");
      li.className = i === this.active ? "active" : "";
      li.innerHTML = "<span></span><span></span>";
      li.firstChild.textContent = it.insert.trim();
      li.lastChild.textContent = it.detail;
      li.addEventListener("mousedown", (e) => { e.preventDefault(); this.active = i; this.accept(); });
      list.appendChild(li);
    });
    this.box.appendChild(list);
    if (item.preview) {
      const preview = document.createElement("div");
      preview.className = "preview";
      preview.textContent = item.preview;
      this.box.appendChild(preview);
    }
    const { x, y } = caretPoint(this.ta);
    Object.assign(this.box.style, { display: "block", left: `${x}px`, top: `${y + 2}px` });
    list.children[this.active]?.scrollIntoView({ block: "nearest" });
  }

  key(e) {
    if (!this.items.length) return;
    const moves = { ArrowDown: 1, ArrowUp: -1 };
    if (e.key in moves) {
      this.active = (this.active + moves[e.key] + this.items.length) % this.items.length;
      this.render();
    } else if (e.key === "Enter" || e.key === "Tab") {
      this.accept();
    } else if (e.key === "Escape") {
      this.close();
    } else {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
  }

  accept() {
    const { insert } = this.items[this.active];
    const ta = this.ta;
    const caret = ta.selectionEnd;
    ta.value = ta.value.slice(0, this.from) + insert + ta.value.slice(caret);
    ta.selectionStart = ta.selectionEnd = this.from + insert.length;
    this.close();
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }

  close() {
    this.items = [];
    this.box.style.display = "none";
  }
}

app.registerExtension({
  name: "orrery.autocomplete",
  setup() {
    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);
  },
  nodeCreated(node) {
    if (node.comfyClass !== "OrreryPrompt") return;
    const widget = node.widgets?.find((w) => w.name === "template");
    const ta = widget?.inputEl ?? widget?.element;
    if (!(ta instanceof HTMLTextAreaElement)) {
      console.warn("[orrery] template textarea not found; autocomplete off for this node");
      return;
    }
    const completer = new Completer(node, ta);
    const onRemoved = node.onRemoved;
    node.onRemoved = function () {
      completer.box.remove();
      return onRemoved?.apply(this, arguments);
    };
  },
});
