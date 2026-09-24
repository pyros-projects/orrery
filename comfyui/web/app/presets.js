// Presets tab: gallery with galaxy thumbnails, filters, and a detail pane.
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";
import { filterPresets, folderColor, glyph, markPicks } from "./model.js";
import { copyText, thumbHTML } from "./parts.js";
import { openSave } from "./save.js";

export function renderPresets(app) {
  const s = app.state;
  const folders = [...new Set(app.data.presets.map((p) => p.folder || "mine"))];
  const list = filterPresets(app.data.presets, { filter: s.pFilter, search: s.pSearch, favorites: app.data.favorites, recent: app.data.recent });
  const chip = (k, label, pre = "") => `<button class="chip" aria-pressed="${s.pFilter === k}" data-pf="${k}">${pre}${esc(label)}</button>`;
  app.view.innerHTML = `
    <div class="bar"><label class="search">${icon("search")}<input class="input" id="oa-ps" placeholder="Search titles, notes, tags and template text…" value="${esc(s.pSearch)}"></label></div>
    <div class="bar flat">${chip("all", "All")}${chip("fav", "Favorites", icon("star"))}${chip("recent", "Recent", icon("clock"))}<span class="sep"></span>`
    + `${folders.map((f) => chip(`f:${f}`, f, `<span class="sw" style="background:${folderColor(f === "mine" ? "" : f)}"></span>`)).join("")}</div>
    <div class="split ${s.pOpen ? "has-detail" : ""}">
      <div class="scroll"><div class="grid">${list.map((c) => cardHTML(app, c)).join("") || '<div class="empty">Nothing matches. Clear the search or pick another folder.</div>'}</div></div>
      ${s.pOpen ? detailHTML(app) : ""}
    </div>`;
  const ps = app.$("#oa-ps");
  ps.addEventListener("input", () => {
    const pos = ps.selectionEnd;
    s.pSearch = ps.value;
    renderPresets(app);
    const n = app.$("#oa-ps");
    n.focus();
    n.setSelectionRange(pos, pos);
  });
  app.view.onclick = (e) => onClick(app, e);
  app.view.onkeydown = (e) => {
    const card = e.target.closest("[data-open]");
    if (card && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); card.click(); }
  };
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
      ${s.pConfirm ? `<div class="confirm">Delete @${esc(c.name)}? Its outputs stay in the galaxy. <button class="btn danger" data-pact="delyes">Delete</button><button class="btn ghost" data-pact="delno">Keep</button></div>` : ""}
      ${s.pRoll ? `<div class="roll"><span class="seed">seed ${s.pRoll.seed}</span>${markPicks(s.pRoll.text, s.pRoll.picks)}</div>` : ""}
      <div><span class="label">Template</span><pre class="codebox">${highlight(d.text, app.known())}</pre></div>
    </div></div></aside>`;
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
  const pf = e.target.closest("[data-pf]");
  if (pf) { s.pFilter = pf.dataset.pf; return renderPresets(app); }
  const card = e.target.closest("[data-open]");
  if (card) return open(app, card.dataset.open);
  const act = e.target.closest("[data-pact]")?.dataset.pact;
  const d = s.pDetail;
  if (!act) return;
  if (act === "close") { s.pOpen = null; return renderPresets(app); }
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
