// Presets tab: a tree on the left like the Gallery's (#307): every preset, the image presets, the video presets, the
// favorites and the recent ones, then the collections (the folders, "mine" the presets at the top), each with its
// images and its videos. Above the cards the filters (#308): a name, a kind (still, scene, reel), how recent, and a
// regex over the template text. A card opens its detail.
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";
import { filterCards, folderColor, folderTree, glyph, markPicks, presetFolders, presetsAt } from "./model.js";
import { copyText, resizable, thumbHTML } from "./parts.js";
import { openSave } from "./save.js";

const SUBS = [["", "Every kind"], ["still", "Stills"], ["scene", "Scenes"], ["reel", "Reels"]];
const SINCE = [[0, "Any time"], [1, "Today"], [7, "Last 7 days"], [30, "Last 30 days"]];

function presetState(s) {
  s.pPlace ??= { view: "all", folder: null, kind: null };
  s.pFilt ??= { name: s.pSearch || "", sub: "", since: 0, grep: "" };
  s.pFold ??= new Set();
  return s;
}

export function renderPresets(app) {
  const s = presetState(app.state), f = s.pFilt, d = app.data;
  const grep = f.grep.trim() && s.pGrep?.pattern === f.grep.trim() ? s.pGrep.names : null;
  const list = filterCards(presetsAt(d.presets, s.pPlace, { favorites: d.favorites, recent: d.recent }), { ...f, grep });
  const width = Number(app.bridge.props.presWidth) || 0;
  const select = (id, options, value, label) => `<select class="input" id="${id}" aria-label="${label}">${options.map(([v, l]) =>
    `<option value="${v}" ${String(v) === String(value) ? "selected" : ""}>${l}</option>`).join("")}</select>`;
  app.view.innerHTML = `<div class="gal pres"${width ? ` style="--galw:${width}px"` : ""}>${treeHTML(app)}<div class="gmain">
    <div class="bar pfilters"><label class="search">${icon("search")}<input class="input" id="oa-ps" placeholder="Name, title, tag or note" value="${esc(f.name)}"></label>`
    + `${select("oa-psub", SUBS, f.sub, "Kind")}${select("oa-psince", SINCE, f.since, "Changed")}`
    + `<label class="search">${icon("search")}<input class="input mono" id="oa-pgrep" placeholder="Prompt text · a regex" value="${esc(f.grep)}" spellcheck="false"></label>`
    + `<button class="icon-btn" data-pact="reload" title="Reload the presets">${icon("reload")}</button></div>
    <div class="split ${s.pOpen ? "has-detail" : ""}">
      <div class="scroll"><div class="grid">${list.map((c) => cardHTML(app, c)).join("") || '<div class="empty">Nothing matches. Clear a filter or pick another place on the left.</div>'}</div></div>
      ${s.pOpen ? detailHTML(app) : ""}
    </div></div></div>`;
  const keep = (id, set) => {  // a field keeps its focus and caret through the redraw it causes
    const el = app.$(id);
    el.addEventListener("input", () => {
      const pos = el.selectionEnd;
      set(el.value);
      renderPresets(app);
      const again = app.$(id);
      again.focus();
      again.setSelectionRange(pos, pos);
    });
  };
  keep("#oa-ps", (v) => { f.name = v; s.pSearch = v; });
  keep("#oa-pgrep", (v) => { f.grep = v; grepSoon(app); });
  app.$("#oa-psub").onchange = (e) => { f.sub = e.target.value; renderPresets(app); };
  app.$("#oa-psince").onchange = (e) => { f.since = Number(e.target.value); renderPresets(app); };
  const gal = app.view.querySelector(".gal");
  resizable(app, { box: gal, grip: gal.querySelector(".ggrip"), list: gal.querySelector(".gtree"), cssVar: "--galw", prop: "presWidth" });
  app.view.onclick = (e) => onClick(app, e);
  app.view.onkeydown = (e) => {
    const card = e.target.closest("[data-open], .gf");
    if (card && (e.key === "Enter" || e.key === " ") && e.target === card) { e.preventDefault(); card.click(); }
  };
}

// The prompt regex asks the server, which reads every template, a moment after typing stops.
let grepTimer = null;
function grepSoon(app) {
  clearTimeout(grepTimer);
  const pattern = app.state.pFilt.grep.trim();
  if (!pattern) return;
  grepTimer = setTimeout(async () => {
    try {
      const got = await app.api.presetsGrep(pattern);
      if (app.state.pFilt.grep.trim() !== pattern) return;
      app.state.pGrep = { pattern, names: new Set(got.names) };
    } catch (e) { return app.fail(e); }
    if (app.state.tab === "presets") renderPresets(app);
  }, 300);
}

function treeHTML(app) {
  const s = app.state, d = app.data, p = s.pPlace, cards = d.presets;
  const at = (view, folder, kind) => (p.view === view && p.folder === folder && p.kind === kind ? " on" : "");
  const count = (view) => presetsAt(cards, { view, folder: null, kind: null }, { favorites: d.favorites, recent: d.recent }).length;
  const top = (view, label, ico) => `<li><div class="gf top${at(view, null, null)}" tabindex="0" data-pv="${view}">${icon(ico)}<span class="ln">${label}</span><span class="lc">${count(view)}</span></div></li>`;
  const folders = new Map(presetFolders(cards).map((f) => [f.path, f]));
  const node = (n, depth) => {
    const f = folders.get(n.path), shut = !s.pFold.has(n.path), pad = 4 + depth * 14;
    const kind = (k, label, ico) => (f[k] ? `<li><div class="gf sub${at("all", n.path, k)}" tabindex="0" data-pc="${esc(n.path)}" data-pk="${k}" style="padding-left:${pad + 20}px">`
      + `${icon(ico)}<span class="ln">${label}</span><span class="lc">${f[k]}</span></div></li>` : "");
    return `<li><div class="gf sub${at("all", n.path, null)}" tabindex="0" data-pc="${esc(n.path)}" style="padding-left:${pad}px" title="${esc(n.path)}">`
      + `<button class="mini tw" data-pfold="${esc(n.path)}" tabindex="-1" aria-label="${shut ? "Open" : "Close"} ${esc(n.name)}">${icon("chev", shut ? "rot" : "")}</button>`
      + `<span class="sw" style="background:${folderColor(n.path === "mine" ? "" : n.path.split("/")[0])}"></span><span class="ln">${esc(n.name)}</span><span class="lc">${f.count}</span></div>`
      + `${shut ? "" : `<ul>${kind("image", "image", "image")}${kind("video", "video", "film")}${n.children.map((c) => node(c, depth + 1)).join("")}</ul>`}</li>`;
  };
  return `<div class="gtree"><div class="libgrip ggrip" role="separator" aria-orientation="vertical" aria-label="Presets list width" tabindex="0" title="Drag to resize (or ← →)"></div>
    <div class="scroll"><ul>${top("all", "All presets", "star")}${top("image", "All image presets", "image")}${top("video", "All video presets", "film")}`
    + `${top("fav", "Favorites", "heart")}${top("recent", "Recent", "clock")}</ul>
    <div class="glabel">Collections</div><ul class="gfolders">${folderTree([...folders.values()]).map((n) => node(n, 0)).join("")}</ul></div></div>`;
}

function cardHTML(app, c) {
  const fav = app.data.favorites.has(c.name);
  return `<div class="card ${app.state.pOpen === c.name ? "sel" : ""}" data-open="${esc(c.name)}" tabindex="0" role="button" aria-label="${esc(c.title)}">
    <div class="thumb">${thumbHTML(app, c)}${c.builtin ? `<span class="lock" title="Built-in">${icon("lock")}</span>` : ""}`
    + `${c.outputs ? `<span class="badge">${icon("image")}${c.outputs}</span>` : ""}`
    + `<button class="star ${fav ? "on" : ""}" data-fav="${esc(c.name)}" aria-label="Favorite">${icon("star", fav ? "fill" : "")}</button></div>
    <div class="cap"><b>${esc(c.title)}</b><span>${esc(c.folder || "mine")} · ${esc((c.tags || []).filter((t) => t !== c.folder).slice(0, 2).join(", ") || "no tags")}</span></div></div>`;
}

function detailHTML(app) {
  const s = app.state, d = s.pDetail;
  if (!d || d.name !== s.pOpen) return `<aside class="detail"><div class="head"><button class="icon-btn" data-pact="close" aria-label="Close">${icon("back")}</button><b>Loading…</b></div></aside>`;
  const c = d.card;
  const strip = d.rows.length
    ? d.rows.map((r) => `<span class="sthumb ${r.kind}"><img loading="lazy" src="${esc(app.api.thumbURL(r.id))}" alt="">${r.kind === "video" ? `<span class="play">${icon("play", "fill")}</span>` : ""}</span>`).join("")
    : `${glyph(c.name, folderColor(c.folder))}<span class="muted hint">No outputs yet. Your first render becomes this preset's preview.</span>`;
  return `<aside class="detail">
    <div class="head"><button class="icon-btn" data-pact="close" aria-label="Close">${icon(s.big ? "x" : "back")}</button><b>${esc(c.title)}</b><span class="pname">@${esc(c.name)}</span></div>
    <div class="scroll"><div class="body">
      <div class="strip">${strip}</div>
      ${c.note ? `<p class="muted flush">${esc(c.note)}</p>` : ""}
      <div class="row">${(c.tags || []).map((t) => `<span class="tagchip">${esc(t)}</span>`).join("")}${c.builtin ? `<span class="chip">${icon("lock")}built-in · read-only</span>` : ""}</div>
      <div class="row"><button class="btn primary" data-pact="load">Load into editor</button><button class="btn" data-pact="roll">${icon("dice")}Sample roll</button>`
    + `<button class="btn ghost" data-pact="copy">${icon("copy")}Copy</button><button class="btn ghost" data-pact="dup">Duplicate</button>`
    + `${c.builtin ? "" : `<button class="btn ghost danger" data-pact="del">${icon("trash")}Delete</button>`}</div>
      ${s.pConfirm ? `<div class="confirm">Delete @${esc(c.name)}? Its outputs stay in the gallery. <button class="btn danger" data-pact="delyes">Delete</button><button class="btn ghost" data-pact="delno">Keep</button></div>` : ""}
      ${s.pRoll ? `<div class="roll"><span class="seed">seed ${s.pRoll.seed}</span>${markPicks(s.pRoll.text, s.pRoll.picks)}</div>` : ""}
      <div><span class="label">Template</span><pre class="codebox">${highlight(d.text, app.known())}</pre></div>
    </div></div></aside>`;
}

// The presets as the home holds them now (#301): opening the tab and its reload button read them again, and an
// open preset's detail with them.
export async function reloadPresets(app) {
  try { await app.refreshPresets(); } catch (e) { return app.fail(e); }
  if (app.state.pOpen && app.card(app.state.pOpen)) return open(app, app.state.pOpen);
  app.state.pOpen = null;
  if (app.state.tab === "presets") app.render();
}

async function open(app, name) {
  const s = app.state;
  s.pOpen = name;
  s.pConfirm = false;
  s.pRoll = null;
  renderPresets(app);
  try {
    const card = app.card(name);
    const [full, galaxy] = await Promise.all([app.api.preset(name), app.api.galaxy({ preset: name })]);
    if (s.pOpen !== name) return;
    s.pDetail = { name, card, text: full.text, rows: galaxy.rows.filter((r) => r.kind !== "none") };
  } catch (e) { s.pOpen = null; app.fail(e); }
  if (app.state.tab === "presets") renderPresets(app);
}

async function onClick(app, e) {
  const s = app.state;
  const fav = e.target.closest("[data-fav]");
  if (fav) {
    e.stopPropagation();
    const name = fav.dataset.fav, on = !app.data.favorites.has(name);
    try { app.data.favorites = new Set((await app.api.favorite(name, on)).favorites); } catch (err) { return app.fail(err); }
    return renderPresets(app);
  }
  const fold = e.target.closest("[data-pfold]");
  if (fold) {
    const path = fold.dataset.pfold;
    if (s.pFold.has(path)) s.pFold.delete(path); else s.pFold.add(path);
    return renderPresets(app);
  }
  const pv = e.target.closest("[data-pv]");
  if (pv) { s.pPlace = { view: pv.dataset.pv, folder: null, kind: null }; return renderPresets(app); }
  const pc = e.target.closest("[data-pc]");
  if (pc) { s.pPlace = { view: "all", folder: pc.dataset.pc, kind: pc.dataset.pk || null }; return renderPresets(app); }
  const card = e.target.closest("[data-open]");
  if (card) return open(app, card.dataset.open);
  const act = e.target.closest("[data-pact]")?.dataset.pact;
  const d = s.pDetail;
  if (!act) return;
  if (act === "close") { s.pOpen = null; return renderPresets(app); }
  if (act === "reload") return reloadPresets(app);
  if (!d) return;
  if (act === "load") return app.loadPreset(d.name);
  if (act === "roll") {
    const seed = Math.floor(Math.random() * 1e9);
    try { s.pRoll = (await app.api.roll({ template: d.text, seed, n: 1, target: "text" })).rolls[0]; } catch (err) { return app.fail(err); }
    return renderPresets(app);
  }
  if (act === "copy") return copyText(app, d.text, "Template");
  if (act === "dup") return openSave(app, { text: d.text, from: d.name });
  if (act === "del") { s.pConfirm = true; return renderPresets(app); }
  if (act === "delno") { s.pConfirm = false; return renderPresets(app); }
  if (act === "delyes") {
    const gone = { ...d.card, text: d.text };
    try { await app.api.deletePreset(gone.name); await app.refreshPresets(); } catch (err) { return app.fail(err); }
    s.pOpen = null;
    s.pConfirm = false;
    app.render();
    app.toast(`Deleted <b>@${esc(gone.name)}</b>`, {
      label: "Undo",
      run: async () => {
        try {
          await app.api.savePreset({ name: gone.name, text: gone.text, title: gone.title, tags: gone.tags, note: gone.note });
          await app.refreshPresets();
          app.render();
        } catch (err) { app.fail(err); }
      },
    });
  }
}
