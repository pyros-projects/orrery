// Results under the prompt in every mode (#211): a template without scenes shows, under its one cell, the live
// preview while it samples, then what it made; its takes (each run's pictures, clips or sound, as its Save or
// Preview nodes wrote them) line up under the result, and a click shows one. Generate ×N and 📌 work as in a
// reel's scenes (#206): the takes' seeds numbered on, or as the node's control after generate says; with 📌 the
// rolled prompt stays and only the sampler's noise changes. The takes are kept on the node, per preset (saved
// with the workflow); taking one off the list leaves its files where they are.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";

export const TAKES = [1, 2, 4, 8];
export const takesOf = (app) => (TAKES.includes(Number(app.bridge.props?.orrery_takes)) ? Number(app.bridge.props.orrery_takes) : 1);
export const kept = (app, n) => !!app.bridge.props?.orrery_keep?.[n];
const MOST = 64;  // the takes a preset keeps on the node; the oldest go first
const HEAD = -1;  // the cell before the first SCENE: a whole template without scenes

const key = (app) => app.preset || "";
export const resultsOf = (app) => (app.bridge.props?.orrery_results?.[key(app)] || []);
const keepResults = (app, list) => {
  app.bridge.props.orrery_results = { ...app.bridge.props.orrery_results, [key(app)]: list.slice(-MOST) };
};
export const shownResult = (app) => {
  const list = resultsOf(app);
  return list.find((t) => t.prompt === app.bridge.props?.orrery_shown?.[key(app)]) || list[list.length - 1] || null;
};
const show = (app, prompt) => { app.bridge.props.orrery_shown = { ...app.bridge.props.orrery_shown, [key(app)]: prompt }; };

// What changes the section, for the cells to tell when to draw it again.
export const resultsSig = (app) => [key(app), resultsOf(app).map((t) => `${t.prompt}:${t.media.length}`), shownResult(app)?.prompt,
  takesOf(app), kept(app, HEAD)];

// A run of this node begins (orrery.segment, segment -1): its take waits for what the run writes.
export function resultBegins(app, d) {
  if (!d.prompt_id) return;
  (app.state.pendingResults ??= {})[d.prompt_id] = { prompt: d.prompt_id, seed: d.seed ?? null, take: d.take || 0,
    created: new Date().toISOString(), preset: key(app), media: [] };
}

const KIND = (m) => (/\.(mp4|webm|mov|mkv|m4v)$/i.test(m.filename) || /^video\//.test(m.format || "") ? "video"
  : /\.(wav|mp3|flac|ogg|m4a|opus)$/i.test(m.filename) || m.kind === "audio" ? "audio" : "image");

// What a node of the run wrote (ComfyUI's executed): its media join the run's take, which is shown now. True when
// it was this node's run.
export function resultMedia(app, detail) {
  const pending = app.state.pendingResults?.[detail.prompt_id];
  if (!pending) return false;
  const out = detail.output || {};
  const media = ["images", "gifs", "videos", "audio"].flatMap((k) => (out[k] || []).map((m) => ({ ...m, kind: k })))
    .filter((m) => m?.filename).map((m) => ({ filename: m.filename, subfolder: m.subfolder || "", type: m.type || "output", kind: KIND(m) }));
  if (!media.length || pending.preset !== key(app)) return false;
  const list = resultsOf(app), had = list.find((t) => t.prompt === pending.prompt);
  const take = { ...pending, ...had, media: [...(had?.media || []), ...media] };
  delete take.preset;
  keepResults(app, [...list.filter((t) => t.prompt !== take.prompt), take]);
  show(app, take.prompt);
  return true;
}

// A run that ends without writing anything leaves no take.
export function resultEnds(app, prompt) { if (prompt && app.state.pendingResults) delete app.state.pendingResults[prompt]; }

// A take's media to show: a saved file before a preview's.
const main = (t) => t.media.find((m) => m.type === "output") || t.media[0];

function mediaHTML(app, m, big = false) {
  const src = app.api.viewURL(m);
  if (m.kind === "video") return `<video muted loop playsinline preload="metadata" src="${esc(src)}#t=0.05"></video>`;
  if (m.kind === "audio") return big ? `<audio controls preload="metadata" src="${esc(src)}"></audio>` : `<span class="r-audio">${icon("play")}</span>`;
  return `<img ${big ? "" : 'loading="lazy" '}alt="" src="${esc(src)}">`;
}

// The seeds of N more takes: numbered on from the takes there are (seed+1, seed+2 …), or as the node's control
// says; with 📌 they are take numbers (the noise: seed + take), without, the node's seed for each.
export function resultSeeds(app, n, keep) {
  const base = Number(app.bridge.getSeed()) || 0, control = app.bridge.getControl();
  const had = resultsOf(app).map((t) => (keep ? t.take : (t.seed ?? base) - base)).filter((v) => v >= 0);
  const start = had.length ? Math.max(...had) + 1 : 0;
  return Array.from({ length: n }, (_, k) => (app.data.surf_numbered !== false || control === "increment" ? start + k
    : control === "randomize" ? Math.floor(Math.random() * 2 ** 31) : control === "decrement" ? -(start + k) : 0));
}

// Under a template without scenes: the result (the live preview while it samples), the takes beside their column.
export function resultsHTML(app, takeVars) {
  const list = resultsOf(app), shown = shownResult(app), n = list.indexOf(shown) + 1, takes = takesOf(app), keep = kept(app, HEAD);
  const tile = shown
    ? `<button type="button" class="tl-clip big result" data-seg="-1" title="Take ${n} · seed ${shown.seed ?? "?"}${shown.take ? ` + ${shown.take}` : ""} · click to open">`
      + `${mediaHTML(app, main(shown), true)}<span class="n">${n}</span></button>`
    : `<div class="tl-clip big result empty" data-seg="-1"><span class="muted">What a run makes comes in here: the live preview while it samples, then the picture or the clip.</span></div>`;
  const button = (act, inner, title, extra = "") => `<span class="btn ghost" role="button" data-ract="${act}" title="${esc(title)}" ${extra}>${inner}</span>`;
  const head = `<span class="cm-takes-head"><span class="th-top">`
    + button("gen", `${icon("plus")}${takes > 1 ? `${takes} takes` : "take"}`, `Add ${takes > 1 ? `${takes} takes` : "a take"}: Generate, as ×N and 📌 say`)
    + button("takes", `×${takes}`, `Takes per Generate: ${takes}. Click for ${TAKES[(TAKES.indexOf(takes) + 1) % TAKES.length]}. Takes differ only if their seeds do (the gear: Clips, Sample surfing)`)
    + button("keep", icon("pin"), keep ? "Keeps the rolled prompt: the takes change only the sampler's noise. Click to roll each take anew"
      : "Each take rolls anew. Click to keep the rolled prompt and change only the sampler's noise", `aria-pressed="${keep}"`)
    + `</span><span class="th-mid"><span class="th-clip">results</span><span class="th-stats">`
    + `<span><i>takes</i><b>${list.length}</b></span>${shown ? `<span><i>shown</i><b>#${n}</b></span><span><i>seed</i><b>${shown.seed ?? "?"}${shown.take ? ` + ${shown.take}` : ""}</b></span>` : ""}</span></span>`
    + (list.length > 1 ? `<span class="th-low">${button("others", `${icon("trash")}the others`, "Take every take off the list but the one shown (the files stay)")}`
      + `${button("all", `${icon("trash")}all`, "Take every take off the list (the files stay)", 'data-danger="1"')}</span>` : "") + "</span>";
  const strip = list.length ? `<div class="cm-takes results" data-seg="-1" style="${takeVars}">${head}<div class="cm-takes-list">${list.map((t, i) =>
    `<button type="button" class="take${t === shown ? " on" : ""}" data-result="${esc(t.prompt)}" title="Take ${i + 1} · seed ${t.seed ?? "?"}${t.take ? ` + ${t.take}` : ""}${t === shown ? " · shown" : " · click to show it"}">`
    + `${mediaHTML(app, main(t))}<span class="n">${i + 1}</span><span class="del" role="button" data-rdel="${esc(t.prompt)}" title="Take it off the list (the file stays)">${icon("x")}</span></button>`).join("")}</div></div>`
    : `<div class="cm-takes results" data-seg="-1">${head}</div>`;
  return `<div class="cm-clips">${tile}</div>${strip}`;
}

// Clicks in the results: show a take, take one or more off the list (Undo brings them back), ×N, 📌, Generate.
export function wireResults(app, box, repaint) {
  box.addEventListener("click", (e) => {
    const act = e.target.closest("[data-ract]")?.dataset.ract, del = e.target.closest("[data-rdel]"), pick = e.target.closest("[data-result]");
    const tile = e.target.closest(".tl-clip.result:not(.empty)");
    if (!act && !del && !pick && !tile) return;
    e.stopPropagation();
    const list = resultsOf(app), before = list.slice(), shown = shownResult(app);
    const undo = (said) => app.toast(said, { label: "Undo", run: () => { keepResults(app, before); repaint(); } });
    if (act === "takes") app.bridge.props.orrery_takes = TAKES[(TAKES.indexOf(takesOf(app)) + 1) % TAKES.length];
    else if (act === "keep") app.bridge.props.orrery_keep = { ...app.bridge.props.orrery_keep, [HEAD]: !kept(app, HEAD) };
    else if (act === "gen") return generate(app);
    else if (act === "others") { keepResults(app, shown ? [shown] : []); undo(`${list.length - 1} takes off the list; the files stay`); }
    else if (act === "all") { keepResults(app, []); undo(`${list.length} takes off the list; the files stay`); }
    else if (del) { keepResults(app, list.filter((t) => t.prompt !== del.dataset.rdel)); undo("A take off the list; its file stays"); }
    else if (pick) {
      const t = list.find((x) => x.prompt === pick.dataset.result);
      if (!t) return;
      show(app, t.prompt);  // a take that rolled anew gives the node its seed, so the next roll is its world (#206)
      if (!t.take && t.seed != null && Number(t.seed) !== Number(app.bridge.getSeed())) app.bridge.setSeed(Number(t.seed));
    } else if (tile && shown) return open(app, shown, tile);
    repaint();
  });
  box.addEventListener("pointerover", (e) => e.target.closest(".take[data-result], .tl-clip.result")?.querySelector("video")?.play().catch(() => {}));
  box.addEventListener("pointerout", (e) => {
    const t = e.target.closest(".take[data-result], .tl-clip.result");
    if (t && !t.contains(e.relatedTarget)) t.querySelector("video")?.pause();
  });
}

function open(app, t, near) {
  const m = main(t), n = resultsOf(app).indexOf(t) + 1, src = app.api.viewURL(m);
  const body = m.kind === "video" ? `<video class="tl-video" controls autoplay loop src="${esc(src)}"></video>`
    : m.kind === "audio" ? `<audio controls autoplay src="${esc(src)}"></audio>` : `<img class="tl-video" alt="" src="${esc(src)}">`;
  const sheet = app.openSheet(`<div class="panel"><div class="row spread"><h4>Take ${n}</h4><button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
    + `${body}<p class="muted flush">seed ${t.seed ?? "?"}${t.take ? ` + ${t.take}` : ""} · ${esc(m.filename)}${t.media.length > 1 ? ` · and ${t.media.length - 1} more` : ""}</p></div>`, near, { over: true });
  sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
}

// Generate ×N: each take queued with its seed (or take number, with 📌), the node's seed and take back after.
async function generate(app) {
  if (app.state.sweepQueue) return;
  const keep = kept(app, HEAD), base = Number(app.bridge.getSeed()) || 0, offsets = resultSeeds(app, takesOf(app), keep);
  let queued = 0;
  try {
    for (const offset of offsets) {
      app.bridge.setTake(keep ? Math.max(0, offset) : 0);
      app.bridge.setSeed(keep ? base : Math.max(0, base + offset) % 2 ** 32);
      queued += await app.bridge.generate(1);
    }
    if (!queued) app.toast("Nothing to generate: connect this node's outputs toward a Save or Preview node.");
    else if (offsets.length > 1) app.toast(`Queued <b>${queued}</b> takes: they line up under the result as they come in`);
  } catch (err) { app.fail(err); }
  app.bridge.setTake(0);
  app.bridge.setSeed(base);
}
