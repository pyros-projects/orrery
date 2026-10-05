// Galaxy tab: every logged output; ratings move the learned weights of its picks. On the left (#290): every
// output, its pictures, its videos, then the days (each with its images and videos) and the collections, which
// hold outputs without moving them (one output in as many as you like). What belongs together is one album's card
// (a sweep's runs, a reel's clips, and in a reel each scene's), opened with a click. A selection can be put into
// a collection by dragging, exported as training pairs or deleted into the home's trash.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { applyDials, exportRows, FACTORS, filterRows, folderDropPath, folderTree, markPicks, pictureSlots, rangeIds, templateHash, withDice } from "./model.js";
import { copyText, resizable } from "./parts.js";
import { openSave } from "./save.js";
import { openTakes } from "./takes.js";

const RATE_ICON = { love: "heart", like: "up", nope: "down", hate: "ban" };
const MEDIA = "application/x-orrery-media";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const parentOf = (path) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");
const inside = (path, folder) => path === folder || path.startsWith(`${folder}/`);

const TZ = () => -new Date().getTimezoneOffset();  // the days are the viewer's
const gfilt = (s) => (s.gFilt ??= { name: "", sub: "", since: 0, grep: "" });
const filtering = (s) => s.gScope !== "all" || !!s.gRating || !!s.gPick  // a filter shows the outputs themselves
  || !!(gfilt(s).name.trim() || gfilt(s).sub || gfilt(s).since || gfilt(s).grep.trim());
const SUBS = [["", "Every kind"], ["image", "Images"], ["video", "Videos"], ["reel", "Reels' clips"], ["sweep", "Sweeps' runs"]];
const SINCE = [[0, "Any time"], [1, "Today"], [7, "Last 7 days"], [30, "Last 30 days"]];
const TYPE = { shoot: ["Shoot", "image"], sweep: ["Sweep", "chart"], reel: ["Reel", "film"], scene: ["Scene", "play"] };

// What the place in the tree (gPlace: a view of every day or of one, or a collection) or the album open in it shows.
// The server groups and limits; the cards come newest first.
async function refresh(app) {
  const s = app.state, album = s.gAlbums.at(-1), p = s.gPlace;
  const query = { limit: 400, tz: TZ(), ...(filtering(s) ? { flat: 1 } : {}),
    ...(album ? { album: album.key } : { view: p.view, ...(p.day ? { day: p.day } : {}), ...(p.coll ? { collection: p.coll } : {}) }) };
  try {
    const d = await app.api.galaxyView(query);
    Object.assign(app.data, { gCards: d.cards, gRows: d.rows, gTree: d.tree, gTotal: d.tree.total, gTemplates: d.tree.templates });
    s.gDays ??= new Set(d.tree.days.slice(0, 1).map((x) => x.day));  // the newest day open
    app.data.weights = { ...app.data.weights, ...d.weights };
    const shown = new Set(d.rows.map((r) => r.id));
    s.gSel = new Set([...s.gSel].filter((id) => shown.has(id)));
  } catch (e) { app.data.gRows ??= []; app.data.gCards ??= []; app.fail(e); }
}

// Chrome blurs a focused input while innerHTML replaces it; the rename and new-folder fields must not
// take that for the user leaving them.
let painting = false;

export async function renderGalaxy(app) {
  if (!app.data.gCards || !app.state.gFetched) {
    app.state.gFetched = true;
    if (!app.data.gRows) app.view.innerHTML = '<div class="empty">Loading the gallery…</div>';
    await refresh(app);
    if (app.state.tab !== "galaxy") return;
    app.render();
    return;
  }
  const s = app.state;
  const here = placeKey(s);
  const old = app.view.querySelectorAll(".gal .scroll");  // re-rendering keeps the lists where they were
  if (old.length) s.gScroll = { here, tops: [...old].map((el) => el.scrollTop) };
  const byId = new Map(app.data.gRows.map((r) => [r.id, r]));
  const cards = filtering(s)
    ? filterRows(app.data.gRows, { scope: s.gScope, hash: templateHash(app.text), preset: app.preset, rating: s.gRating, pick: s.gPick,
      ...gfilt(s), title: (n) => app.card(n)?.title }).map((r) => ({ kind: "row", id: r.id }))
    : app.data.gCards.filter((c) => c.kind === "album" || byId.has(c.id));
  const rows = cards.filter((c) => c.kind === "row").map((c) => byId.get(c.id));  // the outputs shown, in order
  const open = s.gOpen && app.data.gRows.find((r) => r.id === s.gOpen);
  const seg = (k, label) => `<button class="chip" aria-pressed="${s.gScope === k}" data-gs="${k}">${label}</button>`;
  const rch = (k, label) => `<button class="chip" aria-pressed="${s.gRating === k}" data-gr="${k}">${label}</button>`;
  const width = Number(app.bridge.props.galWidth) || 0;
  const empty = s.gPlace.coll && !s.gAlbums.length
    ? "Nothing in this collection yet. Drag outputs or albums onto it in the list on the left."
    : `No outputs here yet.${s.gScope !== "all" ? " Queue this prompt, or switch to All outputs." : " Wire Orrery Log after your decoder and queue something."}`;
  painting = true;
  app.view.innerHTML = `<div class="gal${s.gSel.size ? " selecting" : ""}"${width ? ` style="--galw:${width}px"` : ""}>${treeHTML(app)}<div class="gmain">
    <div class="bar">${seg("all", "All outputs")}${seg("prompt", "This prompt")}${seg("preset", "This preset")}<span class="sep"></span>`
    + `${rch("love", `${icon("heart")}Loved`)}${rch("like", `${icon("up")}Liked`)}${rch("unrated", "Unrated")}`
    + `${s.gPick ? `<span class="chip mono" aria-pressed="true">${esc(s.gPick)}<button class="mini" data-gp="" aria-label="Clear pick filter">${icon("x")}</button></span>` : ""}
      <span class="grow"></span><button class="icon-btn" data-gact="reload" title="Reload the gallery">${icon("reload")}</button></div>
    ${filtersHTML(s)}
    ${crumbsHTML(app)}${s.gSel.size ? selBarHTML(s.gSel.size, rows.length, s.gPlace.coll && !s.gAlbums.length ? s.gPlace.coll : null) : ""}
    <div class="split ${open ? "has-detail" : ""}">
      <div class="scroll"><p class="rule">Ratings teach the dice: every pick in a <b class="love">loved</b> output weighs ×1.5, <b class="like">liked</b> ×1.2, <b class="nope">nope</b> ×0.8, <b class="hate">hate</b> ×0.5. Click an image for its picks, an album to open it; drag either onto a collection to keep it there too. Shift-click selects a range, Ctrl-click one more.</p>
      <div class="grid">${cards.map((c) => (c.kind === "album" ? albumHTML(app, c) : cardHTML(app, byId.get(c.id)))).join("") || `<div class="empty">${empty}</div>`}</div></div>
      ${open ? detailHTML(app, open) : ""}
    </div></div></div>`;
  painting = false;
  if (s.gScroll?.here === here) app.view.querySelectorAll(".gal .scroll").forEach((el, i) => { el.scrollTop = s.gScroll.tops[i] ?? 0; });
  const gal = app.view.querySelector(".gal");
  app.view.onclick = (e) => onClick(app, e, open, rows);
  app.view.ondblclick = (e) => {
    const path = e.target.closest(".gf.coll")?.dataset.gc;
    if (!path || e.target.closest("button, input")) return;
    s.gRen = path;
    s.gRenText = null;
    renderGalaxy(app);
  };
  wireFilters(app);
  hookMediaDrop();
  resizable(app, { box: gal, grip: gal.querySelector(".ggrip"), list: gal.querySelector(".gtree"), cssVar: "--galw", prop: "galWidth" });
  wireDrag(app, gal);
  wireInputs(app);
  hoverPlay(app.view);
}

// The filters (#308): a preset's name or title, a kind, how recent, a regex over the prompt.
function filtersHTML(s) {
  const f = gfilt(s), select = (id, options, value, label) => `<select class="input" id="${id}" aria-label="${label}">${options.map(([v, l]) =>
    `<option value="${v}" ${String(v) === String(value) ? "selected" : ""}>${l}</option>`).join("")}</select>`;
  return `<div class="bar flat gfilters"><label class="search">${icon("search")}<input class="input" id="oa-gname" placeholder="Preset name or title" value="${esc(f.name)}"></label>`
    + `${select("oa-gsub", SUBS, f.sub, "Kind")}${select("oa-gsince", SINCE, f.since, "Made")}`
    + `<label class="search">${icon("search")}<input class="input mono" id="oa-ggrep" placeholder="Prompt text · a regex" value="${esc(f.grep)}" spellcheck="false"></label></div>`;
}

// A filter changed: the outputs themselves come when the first is set and the albums when the last goes; else the
// rows there are are filtered again. A text field keeps its focus and caret.
function wireFilters(app) {
  const s = app.state, f = gfilt(s);
  const changed = async (set, id) => {
    const was = filtering(s);
    set();
    if (filtering(s) !== was) await refresh(app);
    const pos = id && app.$(id)?.selectionEnd;
    renderGalaxy(app);
    if (id) { const again = app.$(id); again?.focus(); again?.setSelectionRange(pos, pos); }
  };
  app.$("#oa-gname").oninput = (e) => changed(() => { f.name = e.target.value; }, "#oa-gname");
  app.$("#oa-ggrep").oninput = (e) => changed(() => { f.grep = e.target.value; }, "#oa-ggrep");
  app.$("#oa-gsub").onchange = (e) => changed(() => { f.sub = e.target.value; });
  app.$("#oa-gsince").onchange = (e) => changed(() => { f.since = Number(e.target.value); });
}

// Where the view is: the place in the tree, and the albums opened in it.
const placeKey = (s) => JSON.stringify([s.gPlace, s.gAlbums.map((a) => a.key)]);

function placeLabel(s) {
  const p = s.gPlace;
  if (p.coll) return p.coll;
  const view = { all: "All outputs", images: "All images", videos: "All videos" }[p.view];
  return p.day ? `${p.day}${p.view === "all" ? "" : ` · ${p.view}`}` : view;
}

function treeHTML(app) {
  const s = app.state, t = app.data.gTree || { total: 0, images: 0, videos: 0, days: [], collections: [] }, p = s.gPlace;
  const at = (view, day, coll) => !s.gAlbums.length && p.view === view && p.day === day && p.coll === coll ? " on" : "";
  const top = (view, label, n, ico) => `<li><div class="gf top${at(view, null, null)}" tabindex="0" data-gv="${view}">`
    + `${icon(ico)}<span class="ln">${label}</span><span class="lc">${n}</span></div></li>`;
  const kind = (d, k, n) => (n ? `<li><div class="gf sub${at(k, d.day, null)}" tabindex="0" data-gday="${d.day}" data-gk="${k}" style="padding-left:24px">`
    + `${icon(k === "images" ? "image" : "film")}<span class="ln">${k}</span><span class="lc">${n}</span></div></li>` : "");
  const day = (d) => {
    const open = s.gDays?.has(d.day);
    return `<li><div class="gf sub${at("all", d.day, null)}" tabindex="0" data-gday="${d.day}" title="${d.day}: everything made that day">`
      + `<button class="mini tw" data-gdfold="${d.day}" tabindex="-1" aria-label="${open ? "Close" : "Open"} ${d.day}">${icon("chev", open ? "" : "rot")}</button>`
      + `${icon("clock")}<span class="ln">${d.day}</span><span class="lc">${d.total}</span></div>`
      + `${open ? `<ul>${kind(d, "images", d.images)}${kind(d, "videos", d.videos)}</ul>` : ""}</li>`;
  };
  const node = (n, depth) => {
    const kids = n.children.length > 0, shut = s.gFold.has(n.path), editing = s.gRen === n.path;
    const name = editing
      ? `<input class="input mono gren" value="${esc(s.gRenText ?? n.name)}" aria-label="New name for ${esc(n.path)}" spellcheck="false" autocomplete="off">`
      : `<span class="ln">${esc(n.name)}</span>`;
    return `<li><div class="gf sub coll${at("all", null, n.path)}" tabindex="0" draggable="${!editing}" data-gc="${esc(n.path)}" data-drop="${esc(n.path)}" style="padding-left:${4 + depth * 14}px" title="${esc(n.path)} · double-click to rename">`
      + `<button class="mini tw${kids ? "" : " leaf"}" data-gfold="${esc(n.path)}" tabindex="-1" aria-label="${shut ? "Open" : "Close"} ${esc(n.name)}">${icon("chev", shut ? "rot" : "")}</button>`
      + `${icon("folder")}${name}<span class="lc">${n.count || ""}</span>`
      + `<button class="mini gfx" data-gfdel="${esc(n.path)}" aria-label="Delete collection ${esc(n.path)}" title="Remove the collection: what is in it stays in the gallery, the collections in it move up">${icon("trash")}</button></div>`
      + `${kids && !shut ? `<ul>${n.children.map((c) => node(c, depth + 1)).join("")}</ul>` : ""}</li>`;
  };
  const add = s.gNew
    ? `<input class="input mono" id="oa-gnew" value="${esc(s.gNewText ?? "")}" placeholder="${p.coll ? `in ${esc(p.coll)}/…` : "name, or parent/name"}" aria-label="New collection" spellcheck="false" autocomplete="off">`
    : `<button class="btn wide" data-gact="newf">${icon("plus")}New collection</button>`;
  return `<div class="gtree"><div class="libgrip ggrip" role="separator" aria-orientation="vertical" aria-label="Gallery list width" tabindex="0" title="Drag to resize (or ← →)"></div>
    <div class="scroll"><ul>${top("all", "All outputs", t.total, "star")}${top("images", "All images", t.images, "image")}${top("videos", "All videos", t.videos, "film")}</ul>
    ${t.days.length ? `<div class="glabel">Days</div><ul class="gdays">${t.days.map(day).join("")}</ul>` : ""}
    <div class="glabel" data-drop="" title="Drop a collection here to move it to the top">Collections</div>
    <ul class="gfolders">${folderTree(t.collections || []).map((n) => node(n, 0)).join("")}</ul></div>
    <div class="addrow">${add}</div></div>`;
}

// Inside an album: the way back, place by place.
function crumbsHTML(app) {
  const s = app.state;
  if (!s.gAlbums.length) return "";
  return `<div class="bar crumbs"><button class="btn slim ghost" data-gcrumb="-1">${icon("back")}${esc(placeLabel(s))}</button>`
    + s.gAlbums.map((a, i) => `<span class="muted">›</span>${i === s.gAlbums.length - 1 ? `<b>${esc(a.title)}</b>`
      : `<button class="btn slim ghost" data-gcrumb="${i}">${esc(a.title)}</button>`}`).join("") + "</div>";
}

// An album's name: its preset's title and what it is (a sweep's dial and time, a reel, a scene's title).
function albumNames(app, c) {
  const preset = c.preset ? app.card(c.preset)?.title || c.preset : "";
  if (c.type === "scene") return { title: c.title, sub: `scene ${c.chunk + 1}` };
  if (c.type === "reel") return { title: preset || c.title, sub: preset ? c.title : "reel" };
  if (c.type === "shoot") {  // its title is when it began (#321)
    const at = new Date(c.title), when = Number.isNaN(at.getTime()) ? "" : at.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    return { title: preset || "Shoot", sub: `shoot${when ? ` · ${when}` : ""}` };
  }
  return { title: preset || "Sweep", sub: c.title };
}

// An album's card: up to eight of its pictures in a grid, what it is, how many it holds.
function albumHTML(app, c) {
  const { title, sub } = albumNames(app, c), [label, ico] = TYPE[c.type];
  const n = c.previews.length, cols = n <= 1 ? 1 : n <= 4 ? 2 : 3;  // the pictures fill the card, row by row
  const pics = c.previews.map((id) => `<img loading="lazy" draggable="false" src="${esc(app.api.thumbURL(id))}" alt="">`).join("");
  const what = c.type === "sweep" ? `${c.count} runs` : c.type === "reel" ? `${c.count} clips`
    : c.type === "shoot" ? `${c.count} ${c.videos === c.count ? "videos" : "pictures"}` : `${c.count} takes`;
  return `<div class="gcard album" draggable="true" data-galbum="${esc(c.key)}" tabindex="0" role="button" title="${esc(`${title} · ${sub} · ${what} · click to open`)}">`
    + `<div class="agrid" style="--cols:${cols}">${pics || `<span class="aempty">${icon(ico)}</span>`}</div>`
    + `<span class="abadge">${icon(ico)}${label} · ${c.count}</span>`
    + `<div class="gfoot"><span>${esc(title)}</span><span>${esc(sub)}</span></div></div>`;
}

function selBarHTML(n, visible, coll) {
  return `<div class="bar selbar"><b>${n} selected</b><button class="btn slim ghost" data-gact="selall">Select all ${visible}</button>`
    + `<button class="btn slim ghost" data-gact="selnone">Clear</button><span class="grow"></span>`
    + (coll ? `<button class="btn slim ghost" data-gact="uncollect" title="They leave ${esc(coll)}; they stay in the gallery">${icon("x")}Out of the collection</button>` : "")
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
      ${sheetHTML(r)}
      <div><span class="label">Picks · click one to see every output that shares it</span><div class="picklist">
        ${r.picks.map((p) => p.keys.map((k) => `<button class="pick" data-gpick="${esc(k)}"><span>${esc(k.split("=").slice(1).join("="))}<small>${esc(p.label)}</small></span>`
          + `<span class="wv ${w(k) > 1.001 ? "up" : w(k) < 0.999 ? "dn" : ""}">×${w(k).toFixed(2)}</span></button>`).join("")).join("")}</div></div>
      <div class="stat">template #${esc(r.template)}${r.preset ? ` · @${esc(r.preset)}` : ""}${r.collections?.length ? ` · in ${r.collections.map(esc).join(", ")}` : ""}${Object.entries(r.params || {}).map(([k, v]) => ` · $${esc(k)} = ${esc(v)}`).join("")} · ${esc((r.ts || "").replace("T", " ").slice(0, 16))} · ${esc(r.target || "")}</div>
    </div></div></aside>`;
}

// An export's text; a slot still to be written from the picture gets a 🎲 that opens its takes (#175).
const slotted = (v) => pictureSlots(v).map((p) => (p.slot === undefined ? esc(p.text) : `<code>--${esc(p.slot)}--</code>`
  + `<button class="llm-key" data-gwrite="${esc(p.slot)}" title="Takes for this slot, written from the picture: then more, steered; pick one and Use selected writes it in">${icon("dice")}</button>`)).join("");

// What the picture carries beyond its prompt (EXPORT:): a reel reads it as $hero.mood, other systems from the gallery.
function sheetHTML(r) {
  const rows = exportRows(r.exports);
  if (!rows.length) return "";
  return `<div class="exports"><div class="row spread"><span class="label">What it carries · EXPORT:</span>`
    + `<button class="btn ghost" data-gact="copyx">${icon("copy")}JSON</button></div><dl>`
    + rows.map((x) => `<dt>${esc(x.name)}</dt><dd>${x.items.length ? x.items.map((i) => `<span class="tagchip">${slotted(i)}</span>`).join(" ") : slotted(x.value)}`
      + x.fields.map(([k, v]) => `<small><b>${esc(k)}</b> ${slotted(v)}</small>`).join("") + "</dd>").join("")
    + "</dl></div>";
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
  const where = s.gAlbums.at(-1)?.title || s.gPlace.coll?.split("/").pop() || s.gPlace.day;  // the album, the collection, the day
  const name = (where || `selection-${new Date().toISOString().slice(0, 10)}`).replace(/[^\w .-]/g, "_").slice(0, 80);
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

// --- places and collections --------------------------------------------------------------------

// A place in the tree: a view (all, images, videos) of every day or of one, or a collection. Albums close.
async function showPlace(app, place) {
  const s = app.state;
  s.gPlace = { view: "all", day: null, coll: null, ...place };
  s.gAlbums = [];
  s.gSel.clear();
  s.gAnchor = null;
  s.gOpen = null;
  await refresh(app);
  renderGalaxy(app);
}

// An album opened (it stacks: a reel, then one of its scenes), or back to one of them (-1: the place itself).
async function showAlbum(app, album, back = null) {
  const s = app.state;
  s.gAlbums = back === null ? [...s.gAlbums, album] : s.gAlbums.slice(0, back + 1);
  s.gSel.clear();
  s.gAnchor = null;
  s.gOpen = null;
  await refresh(app);
  renderGalaxy(app);
}

function setCollections(app, d) {
  if (app.data.gTree) app.data.gTree.collections = d.collections;
}

async function collectOutputs(app, ids, path) {
  let d;
  try { d = await app.api.collect(ids, path); } catch (e) { return app.fail(e); }
  setCollections(app, d);
  if (app.state.gPlace.coll) await refresh(app);
  renderGalaxy(app);
  app.toast(`${plural(ids.length, "output")} in <b>${esc(path)}</b> now, and still where they were`);
}

async function uncollectOutputs(app, ids, path) {
  let d;
  try { d = await app.api.uncollect(ids, path); } catch (e) { return app.fail(e); }
  setCollections(app, d);
  app.state.gSel.clear();
  await refresh(app);
  renderGalaxy(app);
  app.toast(`${plural(ids.length, "output")} out of <b>${esc(path)}</b>; they stay in the gallery`,
    { label: "Undo", run: () => collectOutputs(app, ids, path) });
}

async function moveCollection(app, path, to) {
  const s = app.state;
  const moved = (f) => (inside(f, path) ? to + f.slice(path.length) : f);
  try { setCollections(app, await app.api.renameCollection(path, to)); } catch (e) { app.fail(e); return renderGalaxy(app); }
  if (s.gPlace.coll) s.gPlace = { ...s.gPlace, coll: moved(s.gPlace.coll) };
  s.gFold = new Set([...s.gFold].map(moved));
  await refresh(app);
  renderGalaxy(app);
  app.toast(`Collection <b>${esc(path)}</b> is now <b>${esc(to)}</b>`);
}

async function addCollection(app, value) {
  const s = app.state;
  const name = value.trim().replace(/^\/+|\/+$/g, "");
  s.gNew = false;
  s.gNewText = null;
  if (!name) return renderGalaxy(app);
  try { setCollections(app, await app.api.addCollection(s.gPlace.coll ? `${s.gPlace.coll}/${name}` : name)); } catch (e) { app.fail(e); }
  if (s.gPlace.coll) s.gFold.delete(s.gPlace.coll);
  renderGalaxy(app);
}

function renameCollection(app, path, value) {
  const s = app.state;
  s.gRen = null;
  s.gRenText = null;
  const name = value.trim().replace(/^\/+|\/+$/g, "");
  const to = name ? [parentOf(path), name].filter(Boolean).join("/") : path;
  return to === path ? renderGalaxy(app) : moveCollection(app, path, to);
}

// Removing a collection deletes nothing: its outputs leave it and stay in the gallery, the collections in it
// move up a level. With something inside, ask first.
function deleteCollection(app, path) {
  const s = app.state, parent = parentOf(path);
  const within = (app.data.gTree?.collections || []).filter((f) => inside(f.path, path));
  const n = within.find((f) => f.path === path)?.count || 0, subs = within.length - 1;
  const run = async () => {
    let d;
    try { d = await app.api.deleteCollection(path); } catch (e) { app.closeSheet(); return app.fail(e); }
    app.closeSheet();
    setCollections(app, d);
    if (s.gPlace.coll && inside(s.gPlace.coll, path)) s.gPlace = { view: "all", day: null, coll: null };
    await refresh(app);
    renderGalaxy(app);
    app.toast(`Collection <b>${esc(path)}</b> removed${n ? " · its outputs stay in the gallery" : ""}${subs ? ` · ${plural(subs, "collection")} moved up` : ""}`);
  };
  if (!n && !subs) return run();
  const what = [n ? `its ${plural(n, "output")} leave it and stay in the gallery` : "", subs ? `its ${plural(subs, "collection")} move up to ${parent ? `<b>${esc(parent)}</b>` : "the top"}` : ""].filter(Boolean).join("; ");
  const sheet = app.openSheet(`<form class="panel"><div class="row spread"><h4>Remove the collection ${esc(path)}?</h4></div>
    <p class="muted flush">${what}. Nothing is deleted.</p>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("trash")}Remove collection</button></div></form>`);
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
      if (e.key === "Enter") { e.preventDefault(); renameCollection(app, path, ren.value); }
      if (e.key === "Escape") { e.preventDefault(); s.gRen = null; renderGalaxy(app); }
    });
    ren.addEventListener("blur", () => { if (!painting && s.gRen === path) { s.gRen = null; renderGalaxy(app); } });
    if (document.activeElement !== ren) { ren.focus(); ren.select(); }
  }
  const add = app.$("#oa-gnew");
  if (add) {
    add.addEventListener("input", () => { s.gNewText = add.value; });
    add.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addCollection(app, add.value); }
      if (e.key === "Escape") { e.preventDefault(); s.gNew = false; renderGalaxy(app); }
    });
    add.addEventListener("blur", () => { if (!painting && s.gNew && !add.value.trim()) { s.gNew = false; renderGalaxy(app); } });
    if (document.activeElement !== add) add.focus();
  }
  app.view.querySelectorAll(".gf, .gcard.album").forEach((el) => el.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target === el) { e.preventDefault(); el.click(); }
  }));
}

// Cards (with the selection, when the card is part of it) and albums drag onto collections, which take them in as
// well; collections drag onto collections, or onto the header to the top. Every drag event is kept inside the app,
// so ComfyUI never takes a drop for a workflow to load.
function wireDrag(app, gal) {
  const s = app.state;
  const clear = () => gal.querySelectorAll(".dropping").forEach((el) => el.classList.remove("dropping"));
  const target = (e) => {
    const el = e.target.closest?.("[data-drop]");
    if (!el || !s.gDrag) return null;
    if (s.gDrag.ids) return el.dataset.drop ? el : null;  // outputs go into a collection, never onto the header
    return folderDropPath(s.gDrag.folder, el.dataset.drop) === null ? null : el;
  };
  gal.addEventListener("dragstart", (e) => {
    const card = e.target.closest?.("[data-gcard]"), album = e.target.closest?.("[data-galbum]"), folder = e.target.closest?.(".gf.coll");
    const big = e.target.closest?.("[data-gmedia]");
    if (big) {
      const row = app.data.gRows.find((r) => r.id === big.dataset.gmedia);
      if (row?.media_name) e.dataTransfer.setData(MEDIA, JSON.stringify({ url: app.api.mediaURL(row.id), name: row.media_name }));
      return;
    }
    if (card) {
      const id = card.dataset.gcard;
      s.gDrag = { ids: s.gSel.has(id) ? [...s.gSel] : [id] };
    } else if (album) {
      s.gDrag = { ids: app.data.gCards.find((c) => c.key === album.dataset.galbum)?.ids || [] };
    } else if (folder && folder.getAttribute("draggable") === "true") {
      s.gDrag = { folder: folder.dataset.gc };
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
    if (drag.ids) collectOutputs(app, drag.ids, to);
    else moveCollection(app, drag.folder, folderDropPath(drag.folder, to));
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
  if (fdel) return deleteCollection(app, fdel.dataset.gfdel);
  const dfold = e.target.closest("[data-gdfold]");
  if (dfold) {
    const d = dfold.dataset.gdfold;
    if (s.gDays.has(d)) s.gDays.delete(d); else s.gDays.add(d);
    return renderGalaxy(app);
  }
  const gv = e.target.closest("[data-gv]");
  if (gv) return showPlace(app, { view: gv.dataset.gv });
  const gday = e.target.closest("[data-gday]");
  if (gday) return showPlace(app, { view: gday.dataset.gk || "all", day: gday.dataset.gday });
  const gc = e.target.closest("[data-gc]");
  if (gc) return e.target.closest("input") ? undefined : showPlace(app, { coll: gc.dataset.gc });
  const crumb = e.target.closest("[data-gcrumb]");
  if (crumb) return showAlbum(app, null, Number(crumb.dataset.gcrumb));
  const alb = e.target.closest("[data-galbum]");
  if (alb) {
    const c = app.data.gCards.find((x) => x.key === alb.dataset.galbum);
    return c && showAlbum(app, { key: c.key, title: albumNames(app, c).title + (c.type === "sweep" ? ` · ${c.title}` : c.type === "shoot" ? ` · ${albumNames(app, c).sub}` : "") });
  }
  const gs = e.target.closest("[data-gs]");
  // a filter shows the outputs themselves, every album opened: the cards come again
  const refilter = async () => { await refresh(app); renderGalaxy(app); };
  if (gs) { s.gScope = gs.dataset.gs; return refilter(); }
  const gr = e.target.closest("[data-gr]");
  if (gr) { s.gRating = s.gRating === gr.dataset.gr ? null : gr.dataset.gr; return refilter(); }
  const gp = e.target.closest("[data-gp]");
  if (gp) { s.gPick = null; return refilter(); }
  const pick = e.target.closest("[data-gpick]");
  if (pick) { s.gPick = pick.dataset.gpick; s.gOpen = null; return refilter(); }
  const go = e.target.closest("[data-gopen]");
  // While something is selected, and with Ctrl, Cmd or Shift, a click on a card selects it.
  if (go && (s.gSel.size || e.ctrlKey || e.metaKey || e.shiftKey)) return select(app, go.dataset.gopen, e, rows);
  if (go) { s.gOpen = go.dataset.gopen; return renderGalaxy(app); }
  const act = e.target.closest("[data-gact]")?.dataset.gact;
  if (act === "reload") { await refresh(app); return app.render(); }
  if (act === "close") { s.gOpen = null; return renderGalaxy(app); }
  if (act === "newf") { s.gNew = true; s.gNewText = null; return renderGalaxy(app); }
  if (act === "selall") { rows.forEach((r) => s.gSel.add(r.id)); return renderGalaxy(app); }
  if (act === "uncollect" && s.gPlace.coll) return uncollectOutputs(app, [...s.gSel], s.gPlace.coll);
  if (act === "selnone") { s.gSel.clear(); s.gAnchor = null; return renderGalaxy(app); }
  if (act === "delete") return confirmDelete(app);
  if (act === "export") return openExport(app);
  if (!open) return;
  const gw = e.target.closest("[data-gwrite]");
  if (gw) {
    return openTakes(app, { kind: "picture", id: open.id, what: gw.dataset.gwrite,
      written: (row) => { Object.assign(open, row); if (app.state.tab === "galaxy") renderGalaxy(app); } }, gw);
  }
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
    app.toast(`Template and seed ${open.seed} restored · control after generate set to <b>fixed</b>: the next run rolls it again with today's libraries and learned weights (they may have changed since; the prompt it made is a copy away)`
      + (kept ? " · replayed as it was made: <b>@rng 1</b> or <b>full</b> added (the dice and the format of back then)" : ""));
  }
  if (act === "save") {
    try { openSave(app, { text: applyDials(await templateOf(app, open), open.params), from: open.preset }); } catch (err) { app.fail(err); }
  }
  if (act === "copyp") copyText(app, open.text || "", "Prompt");
  if (act === "copys") copyText(app, String(open.seed), "Seed");
  if (act === "copyx") copyText(app, JSON.stringify(open.exports || {}, null, 2), "Exports");
}
