// Galaxy tab: every logged output; ratings move the learned weights of its picks. Folders on the
// left sort outputs without moving their files; a selection can be exported as training pairs or
// deleted into the home's trash.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { applyDials, FACTORS, filterRows, folderDropPath, folderTree, markPicks, rangeIds, templateHash, withDice } from "./model.js";
import { copyText, resizable } from "./parts.js";
import { openSave } from "./save.js";

const RATE_ICON = { love: "heart", like: "up", nope: "down", hate: "ban" };
const MEDIA = "application/x-orrery-media";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const parentOf = (path) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");
const inside = (path, folder) => path === folder || path.startsWith(`${folder}/`);

function setFolders(app, d) {
  app.data.folders = d.folders;
  app.data.gTotal = d.total;
  app.data.gUnsorted = d.unsorted;
}

// The view shows one folder (gFolder: null for every output, "" for the unsorted ones); the server
// filters, so the row limit applies per folder.
async function refresh(app) {
  const s = app.state;
  try {
    const d = await app.api.galaxy({ limit: 400, ...(s.gFolder === null ? {} : { folder: s.gFolder }) });
    app.data.gRows = d.rows;
    if (s.gFolder === null) app.data.rows = d.rows;
    setFolders(app, d);
    app.data.weights = { ...app.data.weights, ...d.weights };
    const shown = new Set(d.rows.map((r) => r.id));
    s.gSel = new Set([...s.gSel].filter((id) => shown.has(id)));
  } catch (e) { app.data.gRows = app.data.gRows || []; app.fail(e); }
}

// Chrome blurs a focused input while innerHTML replaces it; the rename and new-folder fields must not
// take that for the user leaving them.
let painting = false;

export async function renderGalaxy(app) {
  if (!app.data.gRows || !app.state.gFetched) {
    app.state.gFetched = true;
    if (!app.data.gRows) app.view.innerHTML = '<div class="empty">Loading the gallery…</div>';
    await refresh(app);
    if (app.state.tab !== "galaxy") return;
    app.render();
    return;
  }
  const s = app.state;
  const old = app.view.querySelectorAll(".gal .scroll");  // re-rendering keeps the lists where they were
  if (old.length) s.gScroll = { folder: s.gFolder, tops: [...old].map((el) => el.scrollTop) };
  const rows = filterRows(app.data.gRows, { scope: s.gScope, hash: templateHash(app.text), preset: app.preset, rating: s.gRating, pick: s.gPick });
  const open = s.gOpen && app.data.gRows.find((r) => r.id === s.gOpen);
  const seg = (k, label) => `<button class="chip" aria-pressed="${s.gScope === k}" data-gs="${k}">${label}</button>`;
  const rch = (k, label) => `<button class="chip" aria-pressed="${s.gRating === k}" data-gr="${k}">${label}</button>`;
  const width = Number(app.bridge.props.galWidth) || 0;
  const empty = s.gFolder
    ? "Nothing in this folder yet. Drag outputs onto it in the list on the left."
    : `No outputs here yet.${s.gScope !== "all" ? " Queue this prompt, or switch to All outputs." : " Wire Orrery Log after your decoder and queue something."}`;
  painting = true;
  app.view.innerHTML = `<div class="gal${s.gSel.size ? " selecting" : ""}"${width ? ` style="--galw:${width}px"` : ""}>${treeHTML(app)}<div class="gmain">
    <div class="bar">${seg("all", "All outputs")}${seg("prompt", "This prompt")}${seg("preset", "This preset")}<span class="sep"></span>`
    + `${rch("love", `${icon("heart")}Loved`)}${rch("like", `${icon("up")}Liked`)}${rch("unrated", "Unrated")}`
    + `${s.gPick ? `<span class="chip mono" aria-pressed="true">${esc(s.gPick)}<button class="mini" data-gp="" aria-label="Clear pick filter">${icon("x")}</button></span>` : ""}
      <span class="grow"></span><button class="icon-btn" data-gact="reload" title="Reload the gallery">${icon("undo")}</button></div>
    ${s.gSel.size ? selBarHTML(s.gSel.size, rows.length) : ""}
    <div class="split ${open ? "has-detail" : ""}">
      <div class="scroll"><p class="rule">Ratings teach the dice: every pick in a <b class="love">loved</b> output weighs ×1.5, <b class="like">liked</b> ×1.2, <b class="nope">nope</b> ×0.8, <b class="hate">hate</b> ×0.5. Click an image for its picks; drag it onto a folder to sort it. Shift-click selects a range, Ctrl-click one more.</p>
      <div class="grid">${rows.map((r) => cardHTML(app, r)).join("") || `<div class="empty">${empty}</div>`}</div></div>
      ${open ? detailHTML(app, open) : ""}
    </div></div></div>`;
  painting = false;
  if (s.gScroll?.folder === s.gFolder) app.view.querySelectorAll(".gal .scroll").forEach((el, i) => { el.scrollTop = s.gScroll.tops[i] ?? 0; });
  const gal = app.view.querySelector(".gal");
  app.view.onclick = (e) => onClick(app, e, open, rows);
  app.view.ondblclick = (e) => {
    const path = e.target.closest(".gf.sub")?.dataset.gf;
    if (!path || e.target.closest("button, input")) return;
    s.gRen = path;
    s.gRenText = null;
    renderGalaxy(app);
  };
  hookMediaDrop();
  resizable(app, { box: gal, grip: gal.querySelector(".ggrip"), list: gal.querySelector(".gtree"), cssVar: "--galw", prop: "galWidth" });
  wireDrag(app, gal);
  wireInputs(app);
  hoverPlay(app.view);
}

function treeHTML(app) {
  const s = app.state, d = app.data;
  const top = (key, label, count) => `<li><div class="gf top${s.gFolder === key ? " on" : ""}" tabindex="0" data-gf="${key === null ? "*" : ""}" data-drop="">`
    + `${icon(key === null ? "star" : "image")}<span class="ln">${label}</span><span class="lc">${count}</span></div></li>`;
  const node = (n, depth) => {
    const kids = n.children.length > 0, shut = s.gFold.has(n.path), editing = s.gRen === n.path;
    const name = editing
      ? `<input class="input mono gren" value="${esc(s.gRenText ?? n.name)}" aria-label="New name for ${esc(n.path)}" spellcheck="false" autocomplete="off">`
      : `<span class="ln">${esc(n.name)}</span>`;
    return `<li><div class="gf sub${s.gFolder === n.path ? " on" : ""}" tabindex="0" draggable="${!editing}" data-gf="${esc(n.path)}" data-drop="${esc(n.path)}" style="padding-left:${4 + depth * 14}px" title="${esc(n.path)} · double-click to rename">`
      + `<button class="mini tw${kids ? "" : " leaf"}" data-gfold="${esc(n.path)}" tabindex="-1" aria-label="${shut ? "Open" : "Close"} ${esc(n.name)}">${icon("chev", shut ? "rot" : "")}</button>`
      + `${icon("folder")}${name}<span class="lc">${n.count || ""}</span>`
      + `<button class="mini gfx" data-gfdel="${esc(n.path)}" aria-label="Delete folder ${esc(n.path)}" title="Delete the folder; what is in it moves up">${icon("trash")}</button></div>`
      + `${kids && !shut ? `<ul>${n.children.map((c) => node(c, depth + 1)).join("")}</ul>` : ""}</li>`;
  };
  const add = s.gNew
    ? `<input class="input mono" id="oa-gnew" value="${esc(s.gNewText ?? "")}" placeholder="${s.gFolder ? `in ${esc(s.gFolder)}/…` : "name, or parent/name"}" aria-label="New folder" spellcheck="false" autocomplete="off">`
    : `<button class="btn wide" data-gact="newf">${icon("plus")}New folder</button>`;
  return `<div class="gtree"><div class="libgrip ggrip" role="separator" aria-orientation="vertical" aria-label="Folder list width" tabindex="0" title="Drag to resize (or ← →)"></div>
    <div class="scroll"><ul>${top(null, "All outputs", d.gTotal ?? 0)}${top("", "Unsorted", d.gUnsorted ?? 0)}</ul>
    <ul class="gfolders">${folderTree(d.folders || []).map((n) => node(n, 0)).join("")}</ul></div>
    <div class="addrow">${add}</div></div>`;
}

function selBarHTML(n, visible) {
  return `<div class="bar selbar"><b>${n} selected</b><button class="btn slim ghost" data-gact="selall">Select all ${visible}</button>`
    + `<button class="btn slim ghost" data-gact="selnone">Clear</button><span class="grow"></span>`
    + `<button class="btn slim" data-gact="export" title="Copy the files with their prompts as .txt into export/ in your orrery home">${icon("save")}Export pairs</button>`
    + `<button class="btn slim ghost danger" data-gact="delete">${icon("trash")}Delete</button></div>`;
}

// Videos play muted while the pointer rests on their card.
function hoverPlay(view) {
  view.querySelectorAll(".vthumb").forEach((box) => {
    box.addEventListener("mouseenter", () => {
      if (box.querySelector("video")) return;
      const v = document.createElement("video");
      Object.assign(v, { src: box.dataset.video, muted: true, loop: true, playsInline: true, autoplay: true });
      v.dataset.gopen = box.querySelector("img")?.dataset.gopen || "";
      box.appendChild(v);
    });
    box.addEventListener("mouseleave", () => box.querySelector("video")?.remove());
  });
}

function media(app, r, big) {
  if (r.kind === "none") {
    return big
      ? `<div class="nofile">${icon("film")}<span>No file was logged for this run. For videos, wire Create Video into Orrery Log's <b>video</b> input.</span></div>`
      : `<div class="textcard" data-gopen="${r.id}">${esc((r.text || "").replace(/^[\s\S]*?\[Shot 1\]\s*/, "").slice(0, 220))}</div>`;
  }
  if (big) {
    return r.kind === "video"
      ? `<video class="big" src="${esc(app.api.mediaURL(r.id))}" poster="${esc(app.api.thumbURL(r.id))}" controls loop playsinline></video>`
      : `<img class="big" src="${esc(app.api.mediaURL(r.id))}" alt="" data-gmedia="${r.id}" title="Drag onto the canvas like the file itself">`;
  }
  const img = `<img loading="lazy" draggable="false" src="${esc(app.api.thumbURL(r.id))}" alt="${esc(r.text || "")}" data-gopen="${r.id}">`;
  return r.kind === "video"
    ? `<div class="vthumb" data-video="${esc(app.api.mediaURL(r.id))}">${img}<span class="play">${icon("play", "fill")}</span></div>`
    : img;
}

function rateButtons(r, pad = "") {
  return Object.keys(FACTORS).map((k) => `<button class="rbtn ${k} ${r.rating === k ? "on" : ""}" data-rate="${r.id}" data-k="${k}" title="${k}" aria-label="${k}" ${pad}>`
    + `${icon(RATE_ICON[k], k === "love" && r.rating === "love" ? "fill" : "")}</button>`).join("");
}

function cardHTML(app, r) {
  const name = r.preset ? r.preset.split("/").pop() : `#${r.template.slice(0, 6)}`;
  const on = app.state.gSel.has(r.id);
  return `<div class="gcard ${r.rating ? `rated r-${r.rating}` : ""}${on ? " picked" : ""}" draggable="true" data-gcard="${r.id}">${media(app, r, false)}
    <button class="gsel${on ? " on" : ""}" data-gsel="${r.id}" aria-pressed="${on}" aria-label="Select" title="Select · Shift: a range">${icon("check")}</button>
    <div class="rate">${rateButtons(r)}</div>
    <div class="gfoot"><span>${esc(name)}</span><span>${r.seed}</span></div></div>`;
}

function detailHTML(app, r) {
  const w = (k) => app.data.weights[k] ?? 1;
  return `<aside class="detail gdetail">
    <div class="head"><button class="icon-btn" data-gact="close" aria-label="Close">${icon(app.state.big ? "x" : "back")}</button><b>${esc(r.preset ? app.card(r.preset)?.title || r.preset : "Output")}</b><span class="pname">seed ${r.seed}</span></div>
    <div class="scroll"><div class="body">
      ${media(app, r, true)}
      <div class="row center">${rateButtons(r, 'style="padding:8px"')}</div>
      <p class="flush prose">${markPicks(r.text || "", r.picks)}</p>
      <div class="row"><button class="btn primary" data-gact="use">Use template + seed</button><button class="btn" data-gact="save">${icon("save")}Save as preset</button>`
    + `<button class="btn ghost" data-gact="copyp">${icon("copy")}Prompt</button><button class="btn ghost" data-gact="copys">${icon("copy")}Seed</button></div>
      <div><span class="label">Picks · click one to see every output that shares it</span><div class="picklist">
        ${r.picks.map((p) => p.keys.map((k) => `<button class="pick" data-gpick="${esc(k)}"><span>${esc(k.split("=").slice(1).join("="))}<small>${esc(p.label)}</small></span>`
          + `<span class="wv ${w(k) > 1.001 ? "up" : w(k) < 0.999 ? "dn" : ""}">×${w(k).toFixed(2)}</span></button>`).join("")).join("")}</div></div>
      <div class="stat">template #${esc(r.template)}${r.preset ? ` · @${esc(r.preset)}` : ""}${r.folder ? ` · in ${esc(r.folder)}` : ""}${Object.entries(r.params || {}).map(([k, v]) => ` · $${esc(k)} = ${esc(v)}`).join("")} · ${esc((r.ts || "").replace("T", " ").slice(0, 16))} · ${esc(r.target || "")}</div>
    </div></div></aside>`;
}

async function rate(app, id, rating) {
  const row = app.data.gRows.find((r) => r.id === id), old = row.rating, next = old === rating ? null : rating;
  try {
    const d = await app.api.rate(id, next);
    Object.assign(row, d.row);
    app.data.weights = { ...app.data.weights, ...d.weights };
  } catch (e) { return app.fail(e); }
  renderGalaxy(app);
  const keys = row.picks.flatMap((p) => p.keys).length;
  app.toast(next ? `${next[0].toUpperCase()}${next.slice(1)}d · ${keys} pick${keys === 1 ? "" : "s"} now weigh ×${FACTORS[next]}` : "Rating cleared · weights restored",
    { label: "Undo", run: () => rate(app, id, old ?? next) });
}

async function templateOf(app, r) {
  return (await app.api.template(r.template)).text;
}

// --- selection ---------------------------------------------------------------------------------

function select(app, id, e, rows) {
  const s = app.state;
  if (e.shiftKey && s.gAnchor) rangeIds(rows.map((r) => r.id), s.gAnchor, id).forEach((x) => s.gSel.add(x));
  else if (s.gSel.has(id)) s.gSel.delete(id);
  else s.gSel.add(id);
  s.gAnchor = id;
  renderGalaxy(app);
}

function confirmDelete(app) {
  const s = app.state, ids = [...s.gSel], n = ids.length;
  const sheet = app.openSheet(`<form class="panel"><div class="row spread"><h4>Delete ${plural(n, "output")}?</h4></div>
    <p class="muted flush">They leave the gallery, and their files move to the <code>trash</code> folder in your orrery home, where you can still fetch them back. What their ratings taught the dice stays.</p>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn danger">${icon("trash")}Delete ${n}</button></div></form>`);
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  sheet.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    let d;
    try { d = await app.api.deleteOutputs(ids); } catch (err) { app.closeSheet(); return app.fail(err); }
    app.closeSheet();
    setFolders(app, d);
    s.gSel.clear();
    s.gAnchor = null;
    if (ids.includes(s.gOpen)) s.gOpen = null;
    await refresh(app);
    app.render();
    app.toast(`Deleted ${plural(d.deleted, "output")} · the files are in the trash`);
  };
  sheet.querySelector("button.danger").focus();
}

function openExport(app) {
  const s = app.state, ids = [...s.gSel], n = ids.length;
  const name = (s.gFolder ? s.gFolder.split("/").pop() : `selection-${new Date().toISOString().slice(0, 10)}`).replace(/[^\w .-]/g, "_");
  const sheet = app.openSheet(`<form class="panel"><div class="row spread"><h4>Export ${plural(n, "pair")}</h4></div>
    <div class="field"><label class="label" for="oa-exp">Folder in export/ · an existing one is added to</label>
      <input class="input mono" id="oa-exp" value="${esc(name)}" spellcheck="false" autocomplete="off"><span class="warn bad" hidden></span></div>
    <p class="muted flush">Each picture or video is copied next to a <code>.txt</code> with the prompt that made it: the pairs trainers read.</p>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("save")}Export</button></div></form>`);
  const input = sheet.querySelector("#oa-exp"), warn = sheet.querySelector(".warn");
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  sheet.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    let d;
    try { d = await app.api.exportPairs(ids, input.value); } catch (err) {
      warn.hidden = false;
      warn.textContent = err.message;
      return;
    }
    app.closeSheet();
    app.toast(`Exported ${plural(d.exported, "pair")} to <b>${esc(d.path)}</b>${d.skipped ? ` · ${d.skipped} without a file skipped` : ""}`);
  };
  input.focus();
  input.select();
}

// --- folders -----------------------------------------------------------------------------------

async function showFolder(app, folder) {
  const s = app.state;
  if (s.gFolder === folder) return;
  s.gFolder = folder;
  s.gSel.clear();
  s.gAnchor = null;
  s.gOpen = null;
  await refresh(app);
  renderGalaxy(app);
}

async function moveOutputs(app, ids, folder) {
  let d;
  try { d = await app.api.moveOutputs(ids, folder); } catch (e) { return app.fail(e); }
  setFolders(app, d);
  await refresh(app);
  renderGalaxy(app);
  app.toast(`Moved ${plural(ids.length, "output")} to <b>${esc(folder || "Unsorted")}</b>`);
}

async function moveFolder(app, path, to) {
  const s = app.state;
  const moved = (f) => (inside(f, path) ? to + f.slice(path.length) : f);
  try { setFolders(app, await app.api.renameFolder(path, to)); } catch (e) { app.fail(e); return renderGalaxy(app); }
  if (s.gFolder) s.gFolder = moved(s.gFolder);
  s.gFold = new Set([...s.gFold].map(moved));
  await refresh(app);
  renderGalaxy(app);
  app.toast(`Folder <b>${esc(path)}</b> is now <b>${esc(to)}</b>`);
}

async function addFolder(app, value) {
  const s = app.state;
  const name = value.trim().replace(/^\/+|\/+$/g, "");
  s.gNew = false;
  s.gNewText = null;
  if (!name) return renderGalaxy(app);
  try { setFolders(app, await app.api.addFolder(s.gFolder ? `${s.gFolder}/${name}` : name)); } catch (e) { app.fail(e); }
  if (s.gFolder) s.gFold.delete(s.gFolder);
  renderGalaxy(app);
}

function renameFolder(app, path, value) {
  const s = app.state;
  s.gRen = null;
  s.gRenText = null;
  const name = value.trim().replace(/^\/+|\/+$/g, "");
  const to = name ? [parentOf(path), name].filter(Boolean).join("/") : path;
  return to === path ? renderGalaxy(app) : moveFolder(app, path, to);
}

// Removing a folder deletes nothing: what is in it moves up a level. With something inside, ask first.
function deleteFolder(app, path) {
  const s = app.state, parent = parentOf(path);
  const within = (app.data.folders || []).filter((f) => inside(f.path, path));
  const n = within.reduce((a, f) => a + f.count, 0), subs = within.length - 1;
  const where = parent ? `<b>${esc(parent)}</b>` : "the top level";
  const run = async () => {
    let d;
    try { d = await app.api.deleteFolder(path); } catch (e) { app.closeSheet(); return app.fail(e); }
    app.closeSheet();
    setFolders(app, d);
    if (s.gFolder && inside(s.gFolder, path)) s.gFolder = [parent, s.gFolder.slice(path.length + 1)].filter(Boolean).join("/");
    await refresh(app);
    renderGalaxy(app);
    app.toast(`Folder <b>${esc(path)}</b> removed${n || subs ? ` · what was in it moved up to ${where}` : ""}`);
  };
  if (!n && !subs) return run();
  const what = [n ? plural(n, "output") : "", subs ? plural(subs, "subfolder") : ""].filter(Boolean).join(" and ");
  const sheet = app.openSheet(`<form class="panel"><div class="row spread"><h4>Remove the folder ${esc(path)}?</h4></div>
    <p class="muted flush">Its ${what} move up to ${where}. Nothing is deleted.</p>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("trash")}Remove folder</button></div></form>`);
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  sheet.querySelector("form").onsubmit = (e) => { e.preventDefault(); run(); };
  sheet.querySelector("button.primary").focus();
}

function wireInputs(app) {
  const s = app.state;
  const ren = app.view.querySelector(".gren");
  if (ren) {
    const path = s.gRen;
    ren.addEventListener("input", () => { s.gRenText = ren.value; });
    ren.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); renameFolder(app, path, ren.value); }
      if (e.key === "Escape") { e.preventDefault(); s.gRen = null; renderGalaxy(app); }
    });
    ren.addEventListener("blur", () => { if (!painting && s.gRen === path) { s.gRen = null; renderGalaxy(app); } });
    if (document.activeElement !== ren) { ren.focus(); ren.select(); }
  }
  const add = app.$("#oa-gnew");
  if (add) {
    add.addEventListener("input", () => { s.gNewText = add.value; });
    add.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addFolder(app, add.value); }
      if (e.key === "Escape") { e.preventDefault(); s.gNew = false; renderGalaxy(app); }
    });
    add.addEventListener("blur", () => { if (!painting && s.gNew && !add.value.trim()) { s.gNew = false; renderGalaxy(app); } });
    if (document.activeElement !== add) add.focus();
  }
  app.view.querySelectorAll(".gf").forEach((el) => el.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target === el) { e.preventDefault(); el.click(); }
  }));
}

// Cards (with the selection, when the card is part of it) and folders drag onto folders. Every
// drag event is kept inside the app, so ComfyUI never takes a drop for a workflow to load.
function wireDrag(app, gal) {
  const s = app.state;
  const clear = () => gal.querySelectorAll(".dropping").forEach((el) => el.classList.remove("dropping"));
  const target = (e) => {
    const el = e.target.closest?.("[data-drop]");
    if (!el || !s.gDrag) return null;
    return s.gDrag.folder !== undefined && folderDropPath(s.gDrag.folder, el.dataset.drop) === null ? null : el;
  };
  gal.addEventListener("dragstart", (e) => {
    const card = e.target.closest?.("[data-gcard]"), folder = e.target.closest?.(".gf.sub"), big = e.target.closest?.("[data-gmedia]");
    if (big) {
      const row = app.data.gRows.find((r) => r.id === big.dataset.gmedia);
      if (row?.media_name) e.dataTransfer.setData(MEDIA, JSON.stringify({ url: app.api.mediaURL(row.id), name: row.media_name }));
      return;
    }
    if (card) {
      const id = card.dataset.gcard;
      s.gDrag = { ids: s.gSel.has(id) ? [...s.gSel] : [id] };
    } else if (folder && folder.getAttribute("draggable") === "true") {
      s.gDrag = { folder: folder.dataset.gf };
    } else return;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("application/x-orrery-galaxy", s.gDrag.folder ?? s.gDrag.ids.join(","));
    gal.classList.add("dragging");
  });
  gal.addEventListener("dragend", () => { s.gDrag = null; clear(); gal.classList.remove("dragging"); });
  gal.addEventListener("dragover", (e) => {
    if (!s.gDrag) return;
    e.preventDefault();
    e.stopPropagation();
    const el = target(e);
    e.dataTransfer.dropEffect = el ? "move" : "none";
    clear();
    el?.classList.add("dropping");
  });
  gal.addEventListener("dragleave", (e) => { if (!gal.contains(e.relatedTarget)) clear(); });
  gal.addEventListener("drop", (e) => {
    if (!s.gDrag) return;
    e.preventDefault();
    e.stopPropagation();
    const el = target(e), drag = s.gDrag;
    s.gDrag = null;
    clear();
    gal.classList.remove("dragging");
    if (!el) return;
    const to = el.dataset.drop;
    if (drag.ids) moveOutputs(app, drag.ids, to);
    else moveFolder(app, drag.folder, folderDropPath(drag.folder, to));
  });
}

// The detail picture dragged out of the app arrives as the file itself. Left alone, ComfyUI fetches
// the picture's URL and names the upload after it, which fails; so the drop is caught first, the file
// is fetched under its own name, and the drop is handed to ComfyUI again, now carrying that file (a
// new Load Image node, a Load Image node's new picture, or the workflow the picture carries).
let dropHooked = false;

function hookMediaDrop() {
  if (dropHooked) return;
  dropHooked = true;
  document.addEventListener("drop", (e) => {
    const raw = e.dataTransfer?.types?.includes(MEDIA) ? e.dataTransfer.getData(MEDIA) : "";
    if (!raw) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (!e.target.closest?.(".orrery-app")) dropAsFile(e, JSON.parse(raw));
  }, true);
}

async function dropAsFile(e, { url, name }) {
  const { target, clientX, clientY, screenX, screenY } = e;
  let file;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`the gallery answered ${res.status}`);
    const blob = await res.blob();
    file = new File([blob], name, { type: blob.type });
  } catch (err) { console.warn("[orrery] the output could not be fetched for the drop", err); return; }
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  target.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, composed: true, clientX, clientY, screenX, screenY, dataTransfer }));
}

// --- clicks ------------------------------------------------------------------------------------

async function onClick(app, e, open, rows) {
  const s = app.state;
  const sel = e.target.closest("[data-gsel]");
  if (sel) return select(app, sel.dataset.gsel, e, rows);
  const rt = e.target.closest("[data-rate]");
  if (rt) return rate(app, rt.dataset.rate, rt.dataset.k);
  const fold = e.target.closest("[data-gfold]");
  if (fold) {
    const p = fold.dataset.gfold;
    if (s.gFold.has(p)) s.gFold.delete(p); else s.gFold.add(p);
    return renderGalaxy(app);
  }
  const fdel = e.target.closest("[data-gfdel]");
  if (fdel) return deleteFolder(app, fdel.dataset.gfdel);
  const gf = e.target.closest("[data-gf]");
  if (gf) return e.target.closest("input") ? undefined : showFolder(app, gf.dataset.gf === "*" ? null : gf.dataset.gf);
  const gs = e.target.closest("[data-gs]");
  if (gs) { s.gScope = gs.dataset.gs; return renderGalaxy(app); }
  const gr = e.target.closest("[data-gr]");
  if (gr) { s.gRating = s.gRating === gr.dataset.gr ? null : gr.dataset.gr; return renderGalaxy(app); }
  const gp = e.target.closest("[data-gp]");
  if (gp) { s.gPick = null; return renderGalaxy(app); }
  const pick = e.target.closest("[data-gpick]");
  if (pick) { s.gPick = pick.dataset.gpick; s.gOpen = null; return renderGalaxy(app); }
  const go = e.target.closest("[data-gopen]");
  // While something is selected, and with Ctrl, Cmd or Shift, a click on a card selects it.
  if (go && (s.gSel.size || e.ctrlKey || e.metaKey || e.shiftKey)) return select(app, go.dataset.gopen, e, rows);
  if (go) { s.gOpen = go.dataset.gopen; return renderGalaxy(app); }
  const act = e.target.closest("[data-gact]")?.dataset.gact;
  if (act === "reload") { await refresh(app); return app.render(); }
  if (act === "close") { s.gOpen = null; return renderGalaxy(app); }
  if (act === "newf") { s.gNew = true; s.gNewText = null; return renderGalaxy(app); }
  if (act === "selall") { rows.forEach((r) => s.gSel.add(r.id)); return renderGalaxy(app); }
  if (act === "selnone") { s.gSel.clear(); s.gAnchor = null; return renderGalaxy(app); }
  if (act === "delete") return confirmDelete(app);
  if (act === "export") return openExport(app);
  if (!open) return;
  if (act === "use" && !app.busy()) {
    let kept = false;
    try {
      const text = await templateOf(app, open);
      app.text = withDice(text, open);
      kept = app.text !== text;
      app.preset = open.preset;
      app.base = open.preset ? text : null;
      app.bridge.setSeed(open.seed);
      app.bridge.setControl("fixed");
      app.bridge.setParams(open.params || {});
    } catch (err) { return app.fail(err); }
    app.go("prompt");
    app.toast(`Template and seed ${open.seed} restored · control after generate set to <b>fixed</b>, so the next run reproduces it`
      + (kept ? " · replayed as it was made: <b>@rng 1</b> or <b>full</b> added (the dice and the format of back then)" : ""));
  }
  if (act === "save") {
    try { openSave(app, { text: applyDials(await templateOf(app, open), open.params), from: open.preset }); } catch (err) { app.fail(err); }
  }
  if (act === "copyp") copyText(app, open.text || "", "Prompt");
  if (act === "copys") copyText(app, String(open.seed), "Seed");
}
