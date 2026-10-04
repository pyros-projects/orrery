// Takes at the line (#173): a 🎲 at the end of a slot's line, of a library still to be written and of a `> enhance`
// line opens a sheet with three takes for that place, written at the node's seed. More asks for three more, new
// against those there are; a steering line goes with them. Insert puts a take in place of the slot (or the library)
// as an unsaved edit, Keep the direction writes the steer into the slot's (the library's, the line's) directions;
// both with Undo. With an API endpoint the server asks it directly, outside ComfyUI's queue.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { splitCells } from "./model.js";

const LIB = (name) => new RegExp(`__${name.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")}(?:\\[[^\\]\\n]*\\])?(?:#[\\w-]+:\\$?[\\w.-]+)*(?::\\d+)?__(?:\\(([^()]*)\\))?`);
const SAID = { slot: "the slot", library: "the library still to be written", enhance: "what the line rewrites" };

// The template's line `place.line` changed by `edit(line)`; the text as it was when the line is not there.
function onLine(text, place, edit) {
  const lines = text.split("\n");
  if (place.line < 0 || place.line >= lines.length) return text;
  const next = edit(lines[place.line]);
  if (next === null || next === lines[place.line]) return text;
  lines[place.line] = next;
  return lines.join("\n");
}

// A take in place of the slot, or of the library (its directions go with it); `> enhance` has nothing to put in.
export function insertTake(text, place, take) {
  if (place.kind === "slot") return onLine(text, place, (l) => (l.includes(`--${place.what}--`) ? l.replace(`--${place.what}--`, take) : null));
  if (place.kind === "library") return onLine(text, place, (l) => (LIB(place.what).test(l) ? l.replace(LIB(place.what), take) : null));
  return text;
}

// The steer into the place's directions: a slot's (`--a, steer--`), a library's (`__name__(a, steer)`), the
// instruction of a `>` line.
export function keepDirection(text, place, steer) {
  const s = steer.trim();
  if (!s) return text;
  if (place.kind === "slot") return onLine(text, place, (l) => (l.includes(`--${place.what}--`) ? l.replace(`--${place.what}--`, `--${place.what}, ${s}--`) : null));
  if (place.kind === "library") {
    return onLine(text, place, (l) => {
      const m = LIB(place.what).exec(l);
      if (!m) return null;
      const token = m[1] !== undefined ? m[0].replace(/\(([^()]*)\)$/, `(${m[1]}, ${s})`) : `${m[0]}(${s})`;
      return l.slice(0, m.index) + token + l.slice(m.index + m[0].length);
    });
  }
  return onLine(text, place, (l) => (/^\s*>/.test(l) ? `${l.replace(/\s+$/, "")}, ${s}` : null));
}

// The place a 🎲 stands for, its line counted in the whole template (a cell's key counts in its cell).
export function placeOf(app, key) {
  const local = Number(key.dataset.line) || 0, cell = key.closest(".cell");
  const start = cell ? splitCells(app.text)[Number(cell.dataset.cell)]?.line ?? 0 : 0;
  return { kind: key.dataset.llm, what: key.dataset.what || "", directions: key.dataset.dirs || "", line: start + local };
}

export function openTakes(app, place, near = null) {
  const s = { takes: [], busy: false, error: "" };
  const token = place.kind === "slot" ? `--${place.what}--` : place.kind === "library" ? `__${place.what}__` : `> ${place.what}`;
  const sheet = app.openSheet(`<div class="panel takes-panel"><div class="row spread"><h4>${icon("dice")} Takes</h4>`
    + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
    + `<p class="muted flush">For ${SAID[place.kind]} <code>${esc(token)}</code>, at seed ${esc(String(app.bridge.getSeed()))}.`
    + `${place.kind === "enhance" ? " A rewrite happens at every run: these show what it does, and Keep the direction puts your steer into it." : ""}</p>`
    + `<ol class="take-list"></ol><p class="muted flush take-state" role="status"></p>`
    + `<div class="row take-steer"><input class="input grow" data-steer placeholder="Steer them: darker, older, as an anime character …" aria-label="Steer the takes">`
    + `<button class="btn" data-tmore>${icon("dice")}More takes</button>`
    + `<button class="btn ghost" data-tkeep title="Write the steer into ${esc(SAID[place.kind])}'s directions, so it keeps rolling that way">${icon("pin")}Keep the direction</button></div></div>`, near);
  const list = sheet.querySelector(".take-list"), state = sheet.querySelector(".take-state"), steer = sheet.querySelector("[data-steer]");
  const draw = () => {
    list.innerHTML = s.takes.map((t, i) => `<li><span>${esc(t)}</span>${place.kind === "enhance" ? ""
      : `<button class="btn primary" data-tins="${i}" title="Put it in place of ${esc(token)}: an unsaved edit">Insert</button>`}</li>`).join("");
    state.textContent = s.busy ? "Writing…" : s.error;
    state.classList.toggle("warn", !!s.error && !s.busy);
    sheet.querySelector("[data-tmore]").disabled = s.busy;
  };
  const ask = async () => {
    s.busy = true;
    s.error = "";
    draw();
    try {
      const got = await app.api.takes({ kind: place.kind, what: place.what, directions: place.directions, template: app.text,
        target: app.bridge.getTarget(), params: app.bridge.getParams(), seed: app.bridge.getSeed(), segment: app.bridge.getSegment?.() ?? 0,
        chain: app.bridge.chain?.() || "", steer: steer.value, have: s.takes, n: 3 });
      s.takes.push(...got.takes.filter((t) => !s.takes.includes(t)));
    } catch (err) { s.error = err.message; }
    s.busy = false;
    draw();
  };
  const changed = (text, said) => {
    const before = app.text;
    if (text === before) return app.toast(`${esc(token)} is not on its line any more: the editor changed since.`);
    app.text = text;
    app.cellsSig = null;
    if (app.state.tab === "prompt") app.render();
    app.toast(said, { label: "Undo", run: () => { app.text = before; app.cellsSig = null; if (app.state.tab === "prompt") app.render(); } });
  };
  sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  sheet.querySelector("[data-tmore]").onclick = () => ask();
  steer.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); ask(); } });
  sheet.querySelector("[data-tkeep]").onclick = () => {
    if (!steer.value.trim()) return steer.focus();
    const text = keepDirection(app.text, place, steer.value), moved = text !== app.text;
    changed(text, `Your steer is in ${esc(SAID[place.kind])}'s directions · an unsaved edit`);
    if (!moved) return;
    if (place.kind === "slot") place.what = `${place.what}, ${steer.value.trim()}`;  // the next takes ask with it
    else if (place.kind === "enhance") place.what = `${place.what}, ${steer.value.trim()}`;
    else place.directions = place.directions ? `${place.directions}, ${steer.value.trim()}` : steer.value.trim();
    steer.value = "";
  };
  list.addEventListener("click", (e) => {
    const ins = e.target.closest("[data-tins]");
    if (!ins) return;
    app.closeSheet();
    changed(insertTake(app.text, place, s.takes[Number(ins.dataset.tins)]), "The take is in the editor · an unsaved edit");
  });
  draw();
  ask();
}
