// Takes at the line (#173): a 🎲 at the end of a slot's line, of a library still to be written and of a `> enhance`
// line opens a sheet with takes for that place (three, or as many as the settings say, #274), written at the node's
// seed. More asks for as many more, new against those there are; a steering line goes with them. A click selects a
// take (#276), and Use selected puts it in place of the slot as an unsaved edit; Keep the direction writes the steer
// into the slot's (the line's) directions; both with Undo. A `> enhance` take is kept for its roll instead: the run
// that rolls the same prompt uses it. A library's sheet selects several: one still to be written is written in it and
// kept as the library (#272), one that exists offers its rolls and new entries to add (#273); its directions stay
// with the library, never in the template (#275). With an API endpoint the server asks it directly, outside
// ComfyUI's queue. A gallery picture's slot from `image output` (#175) opens the same sheet: its takes are written
// from the picture, Use selected writes one into its exports.
import { esc, LIBRARY } from "./highlight.js";
import { icon } from "./icons.js";
import { llmLocal } from "./miniruns.js";
import { splitCells } from "./model.js";

const LIB = (name) => new RegExp(`__${name.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")}(?:\\[[^\\]\\n]*\\])?(?:#[\\w-]+:\\$?[\\w.-]+)*(?::\\d+)?__(?:\\(([^()]*)\\))?`);
const SAID = { slot: "the slot", library: "the library still to be written", entries: "the library", enhance: "what the line rewrites",
  picture: "the picture's slot" };

// After a library was written from a sheet: the editor knows it now, its 🎲 goes, its rolls show.
async function librariesChanged(app) {
  try { app.data.libraries = (await app.api.libraries()).libraries; } catch { /* the next run reads them */ }
  app.data.libFull = {};
  app.dialLibs = {};
  await app.refreshCompletion().catch(() => {});
  app.data.annotations = null;  // the line's annotation rolls it now: ask again for the same template and seed
  app.state.annotateKey = null;
  app.cellsSig = null;
  if (app.state.tab === "prompt") app.render();
}

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
  if (place.kind === "library" || place.kind === "entries") return onLine(text, place, (l) => (LIB(place.what).test(l) ? l.replace(LIB(place.what), take) : null));
  return text;
}

// The steer into the place's directions: a slot's (`--a, steer--`), the instruction of a `>` line. A library keeps
// its own, never `(…)` in the template (#275).
export function keepDirection(text, place, steer) {
  const s = steer.trim();
  if (!s) return text;
  if (place.kind === "slot") return onLine(text, place, (l) => (l.includes(`--${place.what}--`) ? l.replace(`--${place.what}--`, `--${place.what}, ${s}--`) : null));
  if (place.kind === "enhance") return onLine(text, place, (l) => (/^\s*>/.test(l) ? `${l.replace(/\s+$/, "")}, ${s}` : null));
  return text;
}

// The place a 🎲 stands for, its line counted in the whole template (a cell's key counts in its cell).
export function placeOf(app, key) {
  const local = Number(key.dataset.line) || 0, cell = key.closest(".cell");
  const start = cell ? splitCells(app.text)[Number(cell.dataset.cell)]?.line ?? 0 : 0;
  return { kind: key.dataset.llm, what: key.dataset.what || "", directions: key.dataset.dirs || "", line: start + local };
}

// The `n`-th library of a line, as the server counts them for its rolls (#202).
export function nthLibrary(line, n) {
  return [...line.matchAll(LIBRARY)][n]?.[1] ?? null;
}

const SLOT = /--(?=[^\s-])([^\n]*?[^\s-])--/g;
const inHome = (app, name) => (app.data.completion?.libraries || []).some((l) => l.name === name);  // not a template's @lib

// The library a roll at a line's end stands for (#273): the k-th `__…__` of its line.
export function placeOfRoll(app, el) {
  const local = Number(el.dataset.line) || 0, cell = el.closest(".cell");
  const start = cell ? splitCells(app.text)[Number(cell.dataset.cell)]?.line ?? 0 : 0;
  const name = nthLibrary(app.text.split("\n")[start + local] || "", Number(el.dataset.lroll));
  return name && inHome(app, name) ? { kind: "entries", what: name, roll: el.textContent, directions: "", line: start + local } : null;
}

// What a Ctrl+click in the editor landed on: a library, its takes (#273) or, still to be written, its sheet (#272);
// else a slot, its takes (#280; one from `image output` is the Gallery's).
export function placeAt(app, ta) {
  const at = ta.selectionStart, cell = ta.closest(".cell");
  const under = (rx) => [...ta.value.matchAll(rx)].find((x) => x.index <= at && at <= x.index + x[0].length);
  const m = under(LIBRARY), s = !m && under(SLOT);
  if (!m && !s) return null;
  const start = cell ? splitCells(app.text)[Number(cell.dataset.cell)]?.line ?? 0 : 0;
  const line = start + ta.value.slice(0, (m || s).index).split("\n").length - 1;
  if (s) return /\bimage\s+output\b/.test(s[1]) ? null : { kind: "slot", what: s[1], directions: "", line };
  if (app.known().has(m[1]) && !inHome(app, m[1])) return null;
  return { kind: app.known().has(m[1]) ? "entries" : "library", what: m[1], roll: "", directions: m[2] || "", line };
}

// The top-level nodes of line `i` in a highlighted <pre>: between its i-th newline and the next.
function lineNodes(pre, i) {
  const out = [];
  let at = 0;
  for (const n of pre.childNodes) {
    if (n.nodeType === Node.TEXT_NODE) at += (n.textContent.match(/\n/g) || []).length;
    else if (at === i) out.push(n);
    if (at > i) break;
  }
  return out;
}

// While the pointer is on a 🎲, the place it stands for is outlined in its line (#280): two slots on one line, two
// dice at its end, each showing its own.
export function markPlace(key, on) {
  const pre = key.closest("pre");
  if (!pre) return;
  pre.querySelectorAll(".t-hl").forEach((el) => el.classList.remove("t-hl"));
  if (!on) return;
  const { llm: kind, what } = key.dataset;
  const sel = kind === "slot" ? ".t-slot" : kind === "enhance" ? ".t-enh" : ".t-lib";
  const lib = new RegExp(`^__${what.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")}(?![\\w/])`);
  const fits = (el) => (kind === "slot" ? el.textContent === `--${what}--` : kind === "enhance" || lib.test(el.textContent));
  lineNodes(pre, Number(key.dataset.line)).flatMap((el) => [...(el.matches(sel) ? [el] : []), ...el.querySelectorAll(sel)])
    .filter(fits).forEach((el) => el.classList.add("t-hl"));
}

export function openTakes(app, place, near = null) {
  const s = { takes: [], pick: null, picked: new Set(), keep: null, busy: false, error: "", note: "" };
  const picture = place.kind === "picture", enhance = place.kind === "enhance";
  const known = place.kind === "entries";  // a library that exists: its rolls and new entries (#273)
  const multi = place.kind === "library" || known;  // a library's entries: several at once (#272)
  const from = [];  // known: where each take came from, "rolled", "new" or "added"
  const token = place.kind === "slot" || picture ? `--${place.what}--` : enhance ? `> ${place.what}` : `__${place.what}__`;
  const useTitle = picture ? "Write the selected take into the picture's exports"
    : enhance ? "Keep the selected rewrite for this roll: a run that rolls this prompt uses it instead of asking the model"
      : `Put the selected take in place of ${esc(token)}: an unsaved edit`;
  const sheet = app.openSheet(`<div class="panel takes-panel"><div class="row spread"><h4>${icon("dice")} Takes</h4>`
    + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
    + `<p class="muted flush">For ${SAID[place.kind]} <code>${esc(token)}</code>, ${picture ? "written from the picture, the prompt that made it beside it."
      : `at seed ${esc(String(app.bridge.getSeed()))}.`}`
    + `${enhance ? " A rewrite happens at every run: Use selected keeps the one you pick for this roll, and the run uses it." : ""}`
    + `${known ? " Its rolls (the one at this seed first) and new entries the language model writes, none it has. Select the new ones worth keeping: Add to the library writes them in."
      : multi ? " As many entries as a new library starts with, written as a run would. Select the ones worth keeping: Keep as the library writes them as the library, straight in." : " Click a take to select it."}</p>`
    + (multi ? `<div class="row take-sel"><button class="btn ghost slim" data-tall>All</button><button class="btn ghost slim" data-tnone>None</button><span class="muted" data-tcount></span></div>` : "")
    + `<ol class="take-list${multi ? " multi" : ""}" role="listbox" aria-label="Takes"${multi ? ' aria-multiselectable="true"' : ""}></ol><p class="muted flush take-state" role="status"></p>`
    + `<div class="row take-steer"><input class="input grow" data-steer placeholder="Steer them: darker, older, as an anime character …" aria-label="Steer the takes">`
    + `<button class="btn" data-tmore>${icon("dice")}More takes</button>`
    + (picture ? "" : `<button class="btn ghost" data-tkeep title="Write the steer into ${esc(SAID[place.kind])}'s directions, so it keeps rolling that way">${icon("pin")}Keep the direction</button>`) + "</div>"
    + `<div class="row take-use"><span class="grow"></span><button class="btn${multi ? " ghost" : " primary"}" data-tuse title="${useTitle}">${icon("check")}Use selected</button>`
    + (known ? `<button class="btn primary" data-tlib title="Write the selected new entries into __${esc(place.what)}__, straight in">${icon("save")}Add to the library</button>`
      : multi ? `<button class="btn primary" data-tlib title="Write the selected entries as __${esc(place.what)}__, straight into your libraries">${icon("save")}Keep as the library</button>` : "")
    + "</div></div>", near);
  const list = sheet.querySelector(".take-list"), state = sheet.querySelector(".take-state"), steer = sheet.querySelector("[data-steer]");
  const use = sheet.querySelector("[data-tuse]"), lib = sheet.querySelector("[data-tlib]");
  const on = (i) => (multi ? s.picked.has(i) : s.pick === i);
  const chosen = () => (multi ? (s.picked.size === 1 ? [...s.picked][0] : null) : s.pick);
  const draw = () => {
    const tag = (i) => (known ? `<small class="tk ${from[i]}">${from[i] === "new" ? "new" : from[i] === "added" ? "added" : "rolled"}</small>` : "");
    list.innerHTML = s.takes.map((t, i) => `<li class="${on(i) ? "on" : ""}" data-tpick="${i}" tabindex="0" role="option" aria-selected="${on(i)}">${esc(t)}${tag(i)}</li>`).join("");
    state.textContent = s.busy ? "Writing…" : s.error || s.note;
    state.classList.toggle("warn", !!s.error && !s.busy);
    sheet.querySelector("[data-tmore]").disabled = s.busy;
    use.disabled = s.busy || chosen() === null || (enhance && !s.keep);
    if (lib) lib.disabled = s.busy || !(known ? [...s.picked].some((i) => from[i] === "new") : s.picked.size);
    if (multi) sheet.querySelector("[data-tcount]").textContent = `${s.picked.size} of ${s.takes.length} selected`;
    if (enhance && !s.keep && s.takes.length) use.title = "This > rewrites several passages of the screenplay, each on its own at the run: there is no one rewrite to keep";
  };
  const add = (got) => {  // what a request answered: the rolls of a library first, then the model's takes
    for (const [list, kind] of [[got.rolled || [], "rolled"], [got.takes || [], "new"]]) {
      for (const t of list.filter((x) => !s.takes.includes(x))) { s.takes.push(t); from.push(kind); }
    }
    if (known && !place.directions) place.directions = got.directions || "";
    if (enhance && got.keep !== undefined) s.keep = got.keep || null;
  };
  const ask = async () => {
    s.busy = true;
    s.error = "";
    draw();
    try {
      if (picture) {
        const got = await app.api.galaxyTakes({ id: place.id, what: place.what, steer: steer.value, have: s.takes });
        s.takes.push(...got.takes.filter((t) => !s.takes.includes(t)));
        return;
      }
      const take = { kind: place.kind, what: place.what, directions: place.directions, steer: steer.value,
        roll: s.takes.length ? "" : place.roll || "" };
      if (!app.llmApi() && llmLocal(app)) {  // a text encoder: in runs of their own at the queue's front (#178)
        const one = place.kind === "slot" || enhance;  // one take a run, each sampled anew; a library's in one run
        const runs = one ? Number(app.data.llm?.takes?.[enhance ? "enhance" : "slot"]) || 3 : 1;
        for (let i = 0; i < runs; i++) {
          const got = await app.bridge.ask("takes", "", JSON.stringify({ ...take, have: s.takes, ...(one ? { n: 1 } : {}) }), { front: true });
          if (got.error) throw new Error(got.error);
          add(got);
          draw();
        }
        return;
      }
      // a slot naming the node's first or last frame (#174): the files of the Load Image nodes behind them
      const frames = /\bimage\s+(first|last)_frame\b/.test(place.what) ? (await app.bridge.frameFiles?.())?.names || {} : {};
      add(await app.api.takes({ ...take, template: app.text, target: app.bridge.getTarget(), params: app.bridge.getParams(),
        seed: app.bridge.getSeed(), segment: app.bridge.getSegment?.() ?? 0, chain: app.bridge.chain?.() || "",
        have: s.takes, frames }));  // as many as the settings say (#274)
    } catch (err) { s.error = err.message; } finally {
      s.busy = false;
      draw();
    }
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
  if (!picture) sheet.querySelector("[data-tkeep]").onclick = () => {
    if (!steer.value.trim()) return steer.focus();
    if (multi) {  // a library keeps its directions itself, not (…) in the template (#272, #275)
      place.directions = place.directions ? `${place.directions}, ${steer.value.trim()}` : steer.value.trim();
      steer.value = "";
      if (!known) {
        s.note = `Kept: __${place.what}__ gets the directions “${place.directions}” when you keep it, and More asks with them.`;
        return draw();
      }
      return app.api.addToLibrary({ name: place.what, entries: [], directions: place.directions })
        .then(() => { s.note = `__${place.what}__ keeps the directions “${place.directions}”: its top-ups and More ask with them.`; draw(); })
        .catch((err) => { s.error = err.message; draw(); });
    }
    const text = keepDirection(app.text, place, steer.value), moved = text !== app.text;
    changed(text, `Your steer is in ${esc(SAID[place.kind])}'s directions · an unsaved edit`);
    if (!moved) return;
    if (place.kind === "slot" || enhance) place.what = `${place.what}, ${steer.value.trim()}`;  // the next takes ask with it
    else place.directions = place.directions ? `${place.directions}, ${steer.value.trim()}` : steer.value.trim();
    if (enhance) s.keep = null;  // another instruction: its takes come with More
    steer.value = "";
    draw();
  };
  const select = (li) => {
    if (!li) return;
    const i = Number(li.dataset.tpick);
    if (!multi) s.pick = i;
    else if (s.picked.has(i)) s.picked.delete(i);
    else s.picked.add(i);
    draw();
    list.querySelector(`[data-tpick="${s.pick}"]`)?.focus();
  };
  list.addEventListener("click", (e) => select(e.target.closest("[data-tpick]")));
  list.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(e.target.closest("[data-tpick]")); } });
  if (multi) {
    sheet.querySelector("[data-tall]").onclick = () => { s.takes.forEach((_, i) => s.picked.add(i)); draw(); };
    sheet.querySelector("[data-tnone]").onclick = () => { s.picked.clear(); draw(); };
    lib.onclick = async () => {
      const picked = [...s.picked].sort((a, b) => a - b).filter((i) => !known || from[i] === "new");
      const entries = picked.map((i) => s.takes[i]);
      try {
        if (known) {  // the sheet stays: More, then add more
          const d = await app.api.addToLibrary({ name: place.what, entries });
          picked.forEach((i) => { from[i] = "added"; s.picked.delete(i); });
          s.note = `Added ${d.added} to __${place.what}__.`;
          draw();
          return librariesChanged(app);
        }
        const d = await app.api.addToLibrary({ name: place.what, entries, directions: place.directions || "" });
        app.closeSheet();
        app.toast(`<b>__${esc(place.what)}__</b> is written: ${d.added} entries, in your libraries`,
          { label: "Open", run: () => { app.state.lib = place.what; app.go("libraries"); } });
        await librariesChanged(app);
      } catch (err) { s.error = err.message; draw(); }
    };
  }
  use.onclick = async () => {
    const take = s.takes[chosen()];
    if (take === undefined) return;
    try {
      if (picture) {
        const d = await app.api.galaxyWrite({ id: place.id, what: place.what, text: take });
        app.closeSheet();
        place.written?.(d.row);
        return app.toast("The take is in the picture's exports");
      }
      if (enhance) {
        await app.api.keepRewrite({ key: s.keep, instruction: place.what, text: take });
        app.closeSheet();
        return app.toast(`Kept for this roll: a run at seed ${esc(String(app.bridge.getSeed()))} that rolls this prompt uses it instead of asking the model`);
      }
    } catch (err) { s.error = err.message; return draw(); }
    app.closeSheet();
    changed(insertTake(app.text, place, take), "The take is in the editor · an unsaved edit");
  };
  draw();
  ask();
}
