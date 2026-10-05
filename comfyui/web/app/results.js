// Results under the prompt in every mode (#211): a template without scenes shows, in the preview (stage.js, #305),
// the live preview while it samples, then what it made; its takes (each run's pictures, clips or sound, as its
// Save, Preview or Orrery Log nodes wrote them) line up under the result, and a click shows one. The take that counts,
// the circled one, is chosen apart from the one shown (Circle this take): browsing never changes it, nor the node's seed.
// Generate ×N and 📌 work as in a reel's scenes (#206): the takes' seeds numbered on, or as the node's control after
// generate says; with 📌 the rolled prompt stays and only the sampler's noise changes. The takes are kept on the node, per preset (saved
// with the workflow); taking one off the list leaves its files where they are. They belong to a shoot (#320): Finish
// shoot folds them into the earlier shoots, each shown by its circled take, and a click opens one again. A grid's or
// a sweep's runs at one seed are one take.
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

// The shoots (#320): the one the takes go to now (its takes are the results above, its id names it in the gallery)
// and the finished ones, newest last; the node keeps the last SHOOTS, the gallery every one.
const SHOOTS = 12;
export const shootsOf = (app) => app.bridge.props?.orrery_shoots?.[key(app)] || [];
const keepShoots = (app, list) => { app.bridge.props.orrery_shoots = { ...app.bridge.props.orrery_shoots, [key(app)]: list.slice(-SHOOTS) }; };
const setFor = (app, prop, value) => { app.bridge.props[prop] = { ...app.bridge.props[prop], [key(app)]: value }; };
export function shootId(app) {
  const id = app.bridge.props?.orrery_shoot?.[key(app)];
  if (id) return id;
  const ids = shootsOf(app).map((x) => x.id);
  let made = new Date().toISOString();
  while (ids.includes(made)) made += "+";  // begun in the same millisecond as one before: still after it
  setFor(app, "orrery_shoot", made);
  return made;
}

// The take circled in a shoot leads the shoot's album in the gallery (#321), by the files its Save nodes wrote.
export function markCircled(app, shoot, t) {
  const files = (t?.media || []).filter((m) => m.type === "output").map((m) => m.filename);
  if (shoot && files.length) app.api.circle?.(shoot, files)?.catch(() => {});  // nothing logged: nothing to lead
}

// Finish shoot: the takes fold into the earlier shoots with the circled one, and the next Roll starts a new shoot.
export function finishShoot(app) {
  const list = resultsOf(app);
  if (!list.length) return false;
  const id = shootId(app), circled = chosenResult(app);
  keepShoots(app, [...shootsOf(app), { id, takes: list, circled: circled?.prompt ?? null, finished: new Date().toISOString() }]);
  markCircled(app, id, circled);
  keepResults(app, []);
  setFor(app, "orrery_chosen", null);
  setFor(app, "orrery_shown", null);
  setFor(app, "orrery_shoot", null);
  app.bridge.setShoot?.("");  // a run from ComfyUI's own Queue goes to no shoot until a Roll begins the next
  return true;
}

// An earlier shoot opened again: its takes are the results, the next Roll adds to it; the shoot open till now, if
// it has takes, goes among the earlier ones.
export function openShoot(app, id) {
  const shoots = shootsOf(app), at = shoots.find((x) => x.id === id);
  if (!at) return false;
  finishShoot(app);
  keepShoots(app, shootsOf(app).filter((x) => x.id !== id));
  keepResults(app, at.takes);
  setFor(app, "orrery_chosen", at.circled);
  setFor(app, "orrery_shown", at.circled);
  setFor(app, "orrery_shoot", at.id);
  app.bridge.setShoot?.(at.id);
  return true;
}

// The take that counts: the one chosen, else the newest (a fresh run's is chosen as it comes).
export const chosenResult = (app) => {
  const list = resultsOf(app);
  return list.find((t) => t.prompt === app.bridge.props?.orrery_chosen?.[key(app)]) || list[list.length - 1] || null;
};

// A take circled; one that rolled anew gives the node its seed, so the next roll is its world (#206).
export function chooseResult(app, t) {
  if (!t) return;
  app.bridge.props.orrery_chosen = { ...app.bridge.props.orrery_chosen, [key(app)]: t.prompt };
  markCircled(app, app.bridge.props.orrery_shoot?.[key(app)], t);
  if (!t.take && t.seed != null && Number(t.seed) !== Number(app.bridge.getSeed())) app.bridge.setSeed(Number(t.seed));
}

// What changes the section, for the cells to tell when to draw it again.
export const resultsSig = (app) => [key(app), resultsOf(app).map((t) => `${t.prompt}:${t.media.length}`), shownResult(app)?.prompt,
  chosenResult(app)?.prompt, takesOf(app), kept(app, HEAD), shootsOf(app).map((x) => `${x.id}:${x.takes.length}:${x.circled}`)];

// A run of this node begins (orrery.segment, segment -1): its take waits for what the run writes.
export function resultBegins(app, d) {
  if (!d.prompt_id) return;
  (app.state.pendingResults ??= {})[d.prompt_id] = { prompt: d.prompt_id, seed: d.seed ?? null, take: d.take || 0,
    ...(d.roll ? { roll: d.roll } : {}), created: new Date().toISOString(), preset: key(app), media: [] };
}

const KIND = (m) => (/\.(mp4|webm|mov|mkv|m4v)$/i.test(m.filename) || /^video\//.test(m.format || "") ? "video"
  : /\.(wav|mp3|flac|ogg|m4a|opus)$/i.test(m.filename) || m.kind === "audio" ? "audio" : "image");

// What an output node this one feeds wrote (ComfyUI's executed): its media, and whether the app logs them to the
// gallery itself, which it does only without Orrery Log (that logs its own). null: another node's, or nothing written.
// The results take the media either way (#302): with Orrery Log they never showed the picture.
export function capturedMedia(detail, { outputs, log }) {
  if (!outputs.map(String).includes(String(detail.display_node ?? detail.node))) return null;
  const out = detail.output || {};
  const media = ["images", "gifs", "videos", "audio"].flatMap((k) => out[k] || []).filter((m) => m && m.filename);
  return media.length && detail.prompt_id ? { media, log: !log } : null;
}

// What a node of the run wrote (ComfyUI's executed): its media join the run's take, which is shown now. True when
// it was this node's run.
export function resultMedia(app, detail) {
  const pending = app.state.pendingResults?.[detail.prompt_id];
  if (!pending) return false;
  const out = detail.output || {};
  const media = ["images", "gifs", "videos", "audio"].flatMap((k) => (out[k] || []).map((m) => ({ ...m, kind: k })))
    .filter((m) => m?.filename).map((m) => ({ filename: m.filename, subfolder: m.subfolder || "", type: m.type || "output", kind: KIND(m) }));
  if (!media.length || pending.preset !== key(app)) return false;
  // a grid's or a sweep's runs at one seed (and take) are one take: its views together (#320)
  const same = (t) => (pending.roll ? t.roll === pending.roll && t.seed === pending.seed && (t.take || 0) === pending.take : t.prompt === pending.prompt);
  const list = resultsOf(app), had = list.find(same);
  const take = { ...pending, ...had, media: [...(had?.media || []), ...media] };
  delete take.preset;
  keepResults(app, [...list.filter((t) => t.prompt !== take.prompt), take]);
  shootId(app);  // the shoot begins with its first take
  show(app, take.prompt);
  app.bridge.props.orrery_chosen = { ...app.bridge.props.orrery_chosen, [key(app)]: take.prompt };  // made at the node's seed
  return true;
}

// A run that ends without writing anything leaves no take.
export function resultEnds(app, prompt) { if (prompt && app.state.pendingResults) delete app.state.pendingResults[prompt]; }

// A take's media to show: a saved file before a preview's; a take of a grid or a sweep has several (#320).
export const mainMedia = (t) => t.media.find((m) => m.type === "output") || t.media[0];
const main = mainMedia;
export const takeMedia = (t) => (t.media.some((m) => m.type === "output") ? t.media.filter((m) => m.type === "output") : t.media);

// A take's tile: its picture, or up to four of a grid's in a mosaic.
export function thumbHTML(app, t) {
  const all = takeMedia(t);
  if (all.length < 2) return mediaHTML(app, main(t));
  return `<span class="mosaic m${Math.min(all.length, 4)}">${all.slice(0, 4).map((m) => mediaHTML(app, m)).join("")}</span>`;
}

// `controls`: the preview's, a clip playing with its controls.
export function mediaHTML(app, m, big = false, controls = false) {
  const src = app.api.viewURL(m);
  if (m.kind === "video" && controls) return `<video class="st-video" controls autoplay loop playsinline src="${esc(src)}"></video>`;
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

// A strip's buttons, its numbers.
export const ghostHTML = (attrs, inner, title, extra = "") => `<span class="btn ghost" role="button" ${attrs} title="${esc(title)}" ${extra}>${inner}</span>`;
export const statHTML = (label, value, cls = "") => `<span class="${cls}"><i>${label}</i><b>${value}</b></span>`;

// The head every take strip shares (#319), the results' and each reel clip's: on top what makes takes (+ take, ×N,
// 📌) and, for videos, plays them all at once; in the middle the strip in numbers; at the bottom what clears it.
// `attr(act)` gives a button its data attributes, so each strip wires its own.
// `off`: why + take can't add one now (it shows, greyed).
export function stripHeadHTML(app, { attr, keep, off = "", play = false, title, sub = "", stats, low = "" }) {
  const takes = takesOf(app);
  return `<span class="cm-takes-head"><span class="th-top">`
    + ghostHTML(off ? 'aria-disabled="true"' : attr("gen"), `${icon("plus")}${takes > 1 ? `${takes} takes` : "take"}`,
      off || `Add ${takes > 1 ? `${takes} takes` : "a take"}, as ×N and 📌 say`)
    + ghostHTML(attr("takes"), `×${takes}`, `Takes per click: ${takes}. Click for ${TAKES[(TAKES.indexOf(takes) + 1) % TAKES.length]}. Takes differ only if their seeds do (the gear: Clips, Sample surfing)`)
    + ghostHTML(attr("keep"), icon("pin"), keep ? "Keeps the rolled prompt: the takes change only the sampler's noise. Click to roll each take anew"
      : "Each take rolls anew. Click to keep the rolled prompt and change only the sampler's noise", `aria-pressed="${keep}"`)
    + (play ? ghostHTML(attr("play"), `${icon("play")}all`, "Play every take at once, from the start, to compare them") : "")
    + `</span><span class="th-mid"><span class="th-clip">${esc(title)}</span>${sub ? `<span class="th-scene" title="${esc(sub)}">${esc(sub)}</span>` : ""}`
    + `<span class="th-stats">${stats}</span></span>${low ? `<span class="th-low">${low}</span>` : ""}</span>`;
}

// Every take of a strip at once (#238, #319): its videos from the start and in step, muted and looping, to compare
// their motion; again, and they stop. `load(take)` gives a take's video; one it made (data-made) for a strip of
// stills goes again at the stop.
export function playAll(strip, button, load = (t) => t.querySelector("video")) {
  const on = !strip.classList.contains("playing");
  strip.classList.toggle("playing", on);
  button.innerHTML = on ? `${icon("stop")}stop` : `${icon("play")}all`;
  const videos = [...strip.querySelectorAll(".take:not(.live)")].map(load).filter(Boolean);
  if (!on) return videos.forEach((v) => { if (v.dataset.made) return v.remove(); v.pause(); v.currentTime = 0.05; });  // a made one: the still again
  videos.forEach((v) => v.pause());
  Promise.all(videos.map((v) => (v.readyState >= 3 ? null : new Promise((ok) => v.addEventListener("canplay", ok, { once: true }))))).then(() => {
    if (!strip.classList.contains("playing")) return;
    videos.forEach((v) => { v.currentTime = 0; v.play().catch(() => {}); });
  });
}

// Under a template without scenes: the result (the live preview while it samples), the takes beside their column.
// The takes under the preview, like a photo viewer: the one shown outlined, the circled one golden.
export function resultsHTML(app, takeVars) {
  const list = resultsOf(app), shown = shownResult(app), chosen = chosenResult(app), n = list.indexOf(shown) + 1;
  const attr = (act) => `data-ract="${act}"`;
  const earlier = shootsOf(app), number = shootNumbers(app);
  const head = stripHeadHTML(app, { attr, keep: kept(app, HEAD), play: list.filter((t) => main(t).kind === "video").length > 1, title: `shoot ${number(null)}`,
    stats: statHTML("takes", list.length) + (chosen ? statHTML("circled", `#${list.indexOf(chosen) + 1}`) : "")
      + (shown ? statHTML("shown", `#${n}`) + statHTML("seed", `${shown.seed ?? "?"}${shown.take ? ` + ${shown.take}` : ""}`) : ""),
    low: (list.length ? ghostHTML(attr("finish"), `${icon("check")}finish shoot`, "Finish this shoot: its takes fold into the earlier shoots, shown by the circled one, and the next Roll starts a new shoot") : "")
      + (list.length > 1 ? ghostHTML(attr("others"), `${icon("trash")}the others`, "Take every take off the list but the circled one (the files stay)")
      + ghostHTML(attr("all"), `${icon("trash")}all`, "Take every take off the list (the files stay)", 'data-danger="1"') : "") });
  const strip = list.length ? `<div class="cm-takes results" data-seg="-1" style="${takeVars}">${head}<div class="cm-takes-list">${list.map((t, i) =>
    `<button type="button" class="take${t === chosen ? " on" : ""}${t === shown ? " shown" : ""}" data-result="${esc(t.prompt)}" title="Take ${i + 1} · seed ${t.seed ?? "?"}${t.take ? ` + ${t.take}` : ""}${t === chosen ? " · circled" : ""}${t === shown ? " · shown" : " · click to show it"}">`
    + `${thumbHTML(app, t)}<span class="n">${i + 1}</span><span class="del" role="button" data-rdel="${esc(t.prompt)}" title="Take it off the list (the file stays)">${icon("x")}</span></button>`).join("")}`
    + `<span class="grip" data-grip title="Drag to size the takes"></span></div></div>`
    : `<div class="cm-takes results" data-seg="-1">${head}</div>`;
  return strip + shootsHTML(app, earlier, number, takeVars);
}

// The shoots numbered in the order they began (their ids are when), so opening an old one keeps every number;
// number(null) is the shoot open now, which begins with its first take.
export function shootNumbers(app) {
  const now = app.bridge.props?.orrery_shoot?.[key(app)];
  const order = [...shootsOf(app).map((x) => x.id), ...(now ? [now] : [])].sort();
  return (id) => (id === null && !now ? order.length + 1 : order.indexOf(id ?? now) + 1);
}

// The earlier shoots under the strip (#320), the newest first, each shown by its circled take; a click opens one again.
function shootsHTML(app, earlier, number, takeVars) {
  if (!earlier.length) return "";
  const day = (iso) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return `<div class="shoots" style="${takeVars}"><span class="sh-label">earlier shoots</span>${earlier.slice().sort((a, b) => b.id.localeCompare(a.id)).map((x) => {
    const t = x.takes.find((y) => y.prompt === x.circled) || x.takes[x.takes.length - 1], n = number(x.id);
    return `<button type="button" class="shoot" data-shoot="${esc(x.id)}" title="Shoot ${n} · ${x.takes.length} take${x.takes.length === 1 ? "" : "s"} · finished ${esc(day(x.finished))} · click to open it again: the next Roll adds to it">`
      + `<span class="take on">${t ? thumbHTML(app, t) : ""}</span><span class="sh-n">shoot ${n}</span><span class="sh-c">${x.takes.length} · ${esc(day(x.finished))}</span></button>`;
  }).join("")}</div>`;
}

// Clicks in the results: show a take, take one or more off the list (Undo brings them back), ×N, 📌, Generate.
export function wireResults(app, box, repaint) {
  box.addEventListener("click", (e) => {
    const act = e.target.closest("[data-ract]")?.dataset.ract, del = e.target.closest("[data-rdel]"), pick = e.target.closest("[data-result]");
    const shoot = e.target.closest("[data-shoot]");
    if (!act && !del && !pick && !shoot) return;
    e.stopPropagation();
    const list = resultsOf(app), before = list.slice(), chosen = chosenResult(app);
    const undo = (said) => app.toast(said, { label: "Undo", run: () => { keepResults(app, before); repaint(); } });
    const props = ["orrery_results", "orrery_shoots", "orrery_chosen", "orrery_shown", "orrery_shoot"];
    const was = Object.fromEntries(props.map((p) => [p, app.bridge.props[p]]));
    const undoShoot = (said) => app.toast(said, { label: "Undo", run: () => { Object.assign(app.bridge.props, was); repaint(); } });
    if (shoot) {
      if (openShoot(app, shoot.dataset.shoot)) undoShoot(`Shoot opened again: the next Roll adds to it${list.length ? "; the one before is among the earlier shoots" : ""}`);
      return repaint();
    }
    if (act === "finish") {
      if (finishShoot(app)) undoShoot(`Shoot finished with ${list.length} take${list.length === 1 ? "" : "s"}: the next Roll starts a new one`);
      return repaint();
    }
    if (act === "takes") app.bridge.props.orrery_takes = TAKES[(TAKES.indexOf(takesOf(app)) + 1) % TAKES.length];
    else if (act === "keep") app.bridge.props.orrery_keep = { ...app.bridge.props.orrery_keep, [HEAD]: !kept(app, HEAD) };
    else if (act === "gen") return generate(app);
    else if (act === "play") return playAll(box.querySelector(".cm-takes.results"), e.target.closest("[data-ract]"));
    else if (act === "others") { keepResults(app, chosen ? [chosen] : []); undo(`${list.length - 1} takes off the list; the files stay`); }
    else if (act === "all") { keepResults(app, []); undo(`${list.length} takes off the list; the files stay`); }
    else if (del) { keepResults(app, list.filter((t) => t.prompt !== del.dataset.rdel)); undo("A take off the list; its file stays"); }
    else if (pick) {  // shown only: Circle this take in the preview chooses it
      const t = list.find((x) => x.prompt === pick.dataset.result);
      if (!t) return;
      show(app, t.prompt);
    }
    repaint();
  });
  box.addEventListener("pointerover", (e) => {
    if (!e.target.closest(".cm-takes.playing")) e.target.closest(".take[data-result]")?.querySelector("video")?.play().catch(() => {});
  });
  box.addEventListener("pointerout", (e) => {
    const t = e.target.closest(".take[data-result]");
    if (t && !t.contains(e.relatedTarget) && !t.closest(".cm-takes.playing")) t.querySelector("video")?.pause();
  });
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
