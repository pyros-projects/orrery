// The cells view of a reel: the editor cut into one cell per CHUNK (the world above them a cell of its own),
// and under every chunk a section with the clips it made and the frames its REMEMBER: lines take (the
// world's, from the input video, under the world). A cell is a textarea over its highlight, as tall as its
// text; the cells together scroll. Arrow keys cross from cell to cell, Backspace at a cell's start and Delete
// at its end join two, and a CHUNK line typed or removed cuts the text again, the caret where it was. A
// clip's shorter side is the settings' clip size, as far as the section is wide.
import { castNames } from "../orrery-complete.js";
import { highlight } from "./highlight.js";
import { splitCells } from "./model.js";
import { fillStrip, hintsFor, openPicker, rememberLines, stripHTML } from "./remember.js";
import { clipRatio, sectionHTML, sourceClip, wireClips } from "./timeline.js";

const box = (app) => app.view.querySelector(".editor.cells");
const areas = (app) => [...(box(app)?.querySelectorAll("textarea") || [])];
export const inCell = (ta) => !!ta?.closest(".cell");

// Where a cell's text starts in the whole text.
export function cellStart(app, ta) {
  let n = 0;
  for (const t of areas(app)) {
    if (t === ta) return n;
    n += t.value.length + 1;
  }
  return n;
}

// A clip's size: its shorter side `least` pixels, no wider than `width`, in the clips' aspect ratio.
export function clipSize(least, width, ratio) {
  let w = ratio >= 1 ? least * ratio : least;
  if (w > width) w = width;
  return { w: Math.max(16, Math.floor(w)), h: Math.max(16, Math.floor(w / ratio)) };
}

// The cells, the caret put back at `at` (an offset into the whole text) when given.
export function renderCells(app, at = null) {
  const host = box(app);
  if (!host) return;
  const cells = splitCells(app.text);
  host.innerHTML = cells.map((c, i) => `<div class="cell" data-cell="${i}" data-chunk="${c.chunk}">`
    + `<pre class="hl" aria-hidden="true"></pre><textarea spellcheck="false" aria-label="${c.chunk < 0 ? "Before the first SCENE" : `SCENE ${c.chunk + 1}`}"></textarea></div>`
    + `<div class="chunkmedia${c.chunk < 0 ? " head" : ""}" data-chunk="${c.chunk}"><div class="cm-body"></div></div>`).join("");
  areas(app).forEach((ta, i) => { ta.value = cells[i].text; ta.readOnly = !!app.state.sweepQueue; });
  app.cellsSig = null;
  paintCells(app);
  app.cellsResize?.disconnect();
  app.cellsResize = new ResizeObserver(() => sizeSections(app));  // a wider node, bigger clips
  app.cellsResize.observe(host);
  if (at !== null) placeCaret(app, at);
}

// Highlights with the chunk dividers, and the sections when what they show changed.
export function paintCells(app) {
  const host = box(app);
  if (!host) return;
  const cells = splitCells(app.text), chunks = app.chunks() || [], segment = Number(app.bridge.getSegment());
  const remembered = app.remembered();
  let before = 0;  // the REMEMBER: lines in the cells above: the hints count them through the whole text
  host.querySelectorAll(".cell").forEach((cell, i) => {
    const c = cells[i];
    if (!c) return;
    const local = c.chunk >= 0 && chunks[c.chunk] ? [{ ...chunks[c.chunk], line: 0 }] : null;
    const hints = hintsFor(c.text, remembered, before);
    before += rememberLines(c.text).length;
    cell.querySelector("pre").innerHTML = `${highlight(c.text, app.known(), { llm: app.llmActive(), chunks: local, segment, cast: castNames(app.text), hints })}​`;
  });
  const sig = JSON.stringify([chunks.map((c) => [c.first, c.last, c.segs]), (app.data.chain?.clips || []).map((c) => c.version),
    segment, clipRatio(app), app.data.clip_min, remembered?.key, remembered?.lines]);
  if (sig === app.cellsSig) return;
  app.cellsSig = sig;
  host.querySelectorAll(".chunkmedia").forEach((m) => {
    const scene = Number(m.dataset.chunk), c = chunks[scene];
    if (scene >= 0 && !c) return;
    const line = remembered?.lines.find((l) => l.scene === scene);
    const source = line ? sourceClip(app, line.source) : null;
    const body = m.querySelector(".cm-body");
    body.innerHTML = (scene >= 0 ? sectionHTML(app, c) : "") + stripHTML(app, scene, source?.url);
    fillStrip(body, source?.frames);
  });
  sizeSections(app);
}

// Every section's clips at the settings' clip size, as far as the section is wide.
function sizeSections(app) {
  const host = box(app);
  if (!host) return;
  const ratio = clipRatio(app), least = Number(app.data.clip_min) || 360;
  host.querySelectorAll(".chunkmedia").forEach((m) => {
    const { w, h } = clipSize(least, Math.max(64, m.clientWidth - 26), ratio);
    m.style.setProperty("--clip-w", `${w}px`);
    m.style.setProperty("--clip-h", `${h}px`);
  });
}

function placeCaret(app, at) {
  let n = 0;
  for (const ta of areas(app)) {
    if (at <= n + ta.value.length) return moveTo(app, ta, at - n);
    n += ta.value.length + 1;
  }
}

// The caret into a cell, and the cells scrolled so its line shows (never scrollIntoView: it scrolls the canvas too).
function moveTo(app, ta, pos) {
  ta.focus({ preventScroll: true });
  ta.setSelectionRange(pos, pos);
  const host = box(app), cell = ta.closest(".cell");
  const line = parseFloat(getComputedStyle(ta).lineHeight) || 20;
  const y = cell.offsetTop + caretPoint(ta).y;
  if (y - line < host.scrollTop) host.scrollTop = Math.max(0, y - line * 2);
  else if (y > host.scrollTop + host.clientHeight) host.scrollTop = y - host.clientHeight + line;
}

// Where the caret sits in a textarea (below its line), measured with a hidden copy of it.
export function caretPoint(ta) {
  const mirror = document.createElement("div"), css = getComputedStyle(ta);
  for (const k of ["boxSizing", "width", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "fontFamily",
    "fontSize", "fontWeight", "lineHeight", "letterSpacing", "overflowWrap", "tabSize", "scrollbarGutter"]) mirror.style[k] = css[k];
  Object.assign(mirror.style, { position: "absolute", visibility: "hidden", top: "0", left: "-9999px", whiteSpace: "pre-wrap",
    overflowY: css.overflowY === "hidden" ? "hidden" : "scroll" });
  mirror.textContent = ta.value.slice(0, ta.selectionEnd);
  const mark = document.createElement("span");
  mark.textContent = "​";
  mirror.appendChild(mark);
  document.body.appendChild(mirror);
  const p = { x: mark.offsetLeft - ta.scrollLeft, y: mark.offsetTop - ta.scrollTop + mark.offsetHeight };
  mirror.remove();
  return p;
}

// One text again from the cells; cut anew (caret kept) when a CHUNK line came or went.
function edited(app, ta, onEdit) {
  const at = cellStart(app, ta) + ta.selectionEnd;
  app.text = areas(app).map((t) => t.value).join("\n");
  const fresh = splitCells(app.text), tas = areas(app);
  if (fresh.length !== tas.length || fresh.some((c, i) => c.text !== tas[i].value)) {
    renderCells(app, at);
    return onEdit(null);
  }
  paintCells(app);
  onEdit(ta);
}

// Join two cells: remove the newline at `at` in the whole text.
function join(app, at, caret, onEdit) {
  app.text = app.text.slice(0, at) + app.text.slice(at + 1);
  renderCells(app, caret);
  onEdit(null);
}

// `onEdit(textarea | null)`: what the editor does after every change (stats, dials, completion);
// `onKey(event)`: true when the completion took the key.
export function wireCells(app, { onEdit, onKey, onFocus, onBlur }) {
  const host = box(app);
  host.addEventListener("input", (e) => { if (e.target.tagName === "TEXTAREA") edited(app, e.target, onEdit); });
  host.addEventListener("focusin", (e) => { if (e.target.tagName === "TEXTAREA") onFocus(); });
  host.addEventListener("focusout", (e) => { if (e.target.tagName === "TEXTAREA") onBlur(e.target); });
  host.addEventListener("keydown", (e) => {
    const ta = e.target;
    if (ta.tagName !== "TEXTAREA" || onKey(e)) return;
    const tas = areas(app), i = tas.indexOf(ta), v = ta.value, s = ta.selectionStart;
    if (s !== ta.selectionEnd || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (e.key === "ArrowUp" && i > 0 && v.lastIndexOf("\n", s - 1) === -1) {
      e.preventDefault();
      const prev = tas[i - 1], start = prev.value.lastIndexOf("\n") + 1;
      moveTo(app, prev, Math.min(start + s, prev.value.length));
    } else if (e.key === "ArrowDown" && i < tas.length - 1 && v.indexOf("\n", s) === -1) {
      e.preventDefault();
      const next = tas[i + 1], col = s - (v.lastIndexOf("\n", s - 1) + 1), end = next.value.indexOf("\n");
      moveTo(app, next, Math.min(col, end < 0 ? next.value.length : end));
    } else if (e.key === "Backspace" && i > 0 && s === 0 && !ta.readOnly) {
      e.preventDefault();
      join(app, cellStart(app, ta) - 1, cellStart(app, ta) - 1, onEdit);
    } else if (e.key === "Delete" && i < tas.length - 1 && s === v.length && !ta.readOnly) {
      e.preventDefault();
      join(app, cellStart(app, ta) + v.length, cellStart(app, ta) + v.length, onEdit);
    }
  });
  wireClips(app, host);
  host.addEventListener("click", (e) => {  // a remembered frame clicked: pick another by eye
    const img = e.target.closest(".rm-item img.pick");
    if (!img) return;
    const item = img.closest(".rm-item"), line = Number(img.closest(".rm-line").dataset.line);
    openPicker(app, { line, item: Number(item.dataset.item), url: item.dataset.url, frame: Number(img.dataset.frame) },
      () => { renderCells(app); onEdit(null); });
  });
}

// Jump: the cells scrolled to a chunk's cell, the caret at its start.
export function jumpCell(app, chunk) {
  const cell = box(app)?.querySelector(`.cell[data-chunk="${chunk}"]`);
  if (!cell) return false;
  box(app).scrollTop = Math.max(0, cell.offsetTop - 8);
  const ta = cell.querySelector("textarea");
  ta.focus({ preventScroll: true });
  ta.setSelectionRange(0, 0);
  return true;
}
