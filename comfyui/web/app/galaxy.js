// Galaxy tab: every logged output; ratings move the learned weights of its picks.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { applyDials, FACTORS, filterRows, markPicks, templateHash } from "./model.js";
import { copyText } from "./parts.js";
import { openSave } from "./save.js";

const RATE_ICON = { love: "heart", like: "up", nope: "down", hate: "ban" };

async function refresh(app) {
  try {
    const d = await app.api.galaxy({ limit: 400 });
    app.data.rows = d.rows;
    app.data.weights = { ...app.data.weights, ...d.weights };
  } catch (e) { app.data.rows = app.data.rows || []; app.fail(e); }
}

export async function renderGalaxy(app) {
  if (!app.data.rows || !app.state.gFetched) {
    app.state.gFetched = true;
    if (!app.data.rows) app.view.innerHTML = '<div class="empty">Loading the galaxy…</div>';
    await refresh(app);
    if (app.state.tab !== "galaxy") return;
    app.render();
    return;
  }
  const s = app.state;
  const rows = filterRows(app.data.rows, { scope: s.gScope, hash: templateHash(app.text), preset: app.preset, rating: s.gRating, pick: s.gPick });
  const open = s.gOpen && app.data.rows.find((r) => r.id === s.gOpen);
  const seg = (k, label) => `<button class="chip" aria-pressed="${s.gScope === k}" data-gs="${k}">${label}</button>`;
  const rch = (k, label) => `<button class="chip" aria-pressed="${s.gRating === k}" data-gr="${k}">${label}</button>`;
  app.view.innerHTML = `
    <div class="bar">${seg("all", "All outputs")}${seg("prompt", "This prompt")}${seg("preset", "This preset")}<span class="sep"></span>`
    + `${rch("love", `${icon("heart")}Loved`)}${rch("like", `${icon("up")}Liked`)}${rch("unrated", "Unrated")}`
    + `${s.gPick ? `<span class="chip mono" aria-pressed="true">${esc(s.gPick)}<button class="mini" data-gp="" aria-label="Clear pick filter">${icon("x")}</button></span>` : ""}
      <span class="grow"></span><button class="icon-btn" data-gact="reload" title="Reload the galaxy">${icon("undo")}</button></div>
    <div class="split ${open ? "has-detail" : ""}">
      <div class="scroll"><p class="rule">Ratings teach the dice: every pick in a <b class="love">loved</b> output weighs ×1.5, <b class="like">liked</b> ×1.2, <b class="nope">nope</b> ×0.8, <b class="hate">hate</b> ×0.5. Click an image for its picks.</p>
      <div class="grid">${rows.map((r) => cardHTML(app, r)).join("") || `<div class="empty">No outputs here yet.${s.gScope !== "all" ? " Queue this prompt, or switch to All outputs." : " Wire Orrery Log after your decoder and queue something."}</div>`}</div></div>
      ${open ? detailHTML(app, open) : ""}
    </div>`;
  app.view.onclick = (e) => onClick(app, e, open);
  hoverPlay(app.view);
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
      : `<img class="big" src="${esc(app.api.mediaURL(r.id))}" alt="">`;
  }
  const img = `<img loading="lazy" src="${esc(app.api.thumbURL(r.id))}" alt="${esc(r.text || "")}" data-gopen="${r.id}">`;
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
  return `<div class="gcard ${r.rating ? `rated r-${r.rating}` : ""}">${media(app, r, false)}
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
      <div class="stat">template #${esc(r.template)}${r.preset ? ` · @${esc(r.preset)}` : ""}${Object.entries(r.params || {}).map(([k, v]) => ` · $${esc(k)} = ${esc(v)}`).join("")} · ${esc((r.ts || "").replace("T", " ").slice(0, 16))} · ${esc(r.target || "")}</div>
    </div></div></aside>`;
}

async function rate(app, id, rating) {
  const row = app.data.rows.find((r) => r.id === id), old = row.rating, next = old === rating ? null : rating;
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

async function onClick(app, e, open) {
  const s = app.state;
  const rt = e.target.closest("[data-rate]");
  if (rt) return rate(app, rt.dataset.rate, rt.dataset.k);
  const gs = e.target.closest("[data-gs]");
  if (gs) { s.gScope = gs.dataset.gs; return renderGalaxy(app); }
  const gr = e.target.closest("[data-gr]");
  if (gr) { s.gRating = s.gRating === gr.dataset.gr ? null : gr.dataset.gr; return renderGalaxy(app); }
  const gp = e.target.closest("[data-gp]");
  if (gp) { s.gPick = null; return renderGalaxy(app); }
  const pick = e.target.closest("[data-gpick]");
  if (pick) { s.gPick = pick.dataset.gpick; s.gOpen = null; return renderGalaxy(app); }
  const go = e.target.closest("[data-gopen]");
  if (go) { s.gOpen = go.dataset.gopen; return renderGalaxy(app); }
  const act = e.target.closest("[data-gact]")?.dataset.gact;
  if (act === "reload") { await refresh(app); return app.render(); }
  if (act === "close") { s.gOpen = null; return renderGalaxy(app); }
  if (!open) return;
  if (act === "use") {
    try {
      const text = await templateOf(app, open);
      app.text = text;
      app.preset = open.preset;
      app.base = open.preset ? text : null;
      app.bridge.setSeed(open.seed);
      app.bridge.setControl("fixed");
      app.bridge.setParams(open.params || {});
    } catch (err) { return app.fail(err); }
    app.go("prompt");
    app.toast(`Template and seed ${open.seed} restored · control after generate set to <b>fixed</b>, so the next run reproduces it`);
  }
  if (act === "save") {
    try { openSave(app, { text: applyDials(await templateOf(app, open), open.params), from: open.preset }); } catch (err) { app.fail(err); }
  }
  if (act === "copyp") copyText(app, open.text || "", "Prompt");
  if (act === "copys") copyText(app, String(open.seed), "Seed");
}
