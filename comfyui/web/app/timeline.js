// A reel's clips as Orrery Film (or H3 Motion Context's Chain Video) keeps them, under each scene in the cells
// view (cells.js), each scene's in a section of its own. The column beside the editor went in #185: the dials
// have that place now.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { shape } from "./model.js";
import { fetchTemplates, useVersion, versionOf, versionText } from "./versions.js";

// The clips the chain holds, fetched again after every run, and the templates its takes were made with (#242).
export async function loadChain(app) {
  try { app.data.chain = await app.api.chain(app.bridge.chain()); } catch { app.data.chain = null; }
  await fetchTemplates(app, Object.values(app.data.chain?.takes || {}).flat());
  app.data.anchorV = Date.now();  // anchors change in place: a new run, a new URL
}

// The segments a chunk shows: all it plays, or for one that repeats forever, the clips made so far
// and the next one.
function segmentsOf(c, clips) {
  if (c.segs) {  // GOTO: the segments on the walked path; an endless one, those made and the next
    if (!c.endless) return c.segs;
    const next = c.segs.find((s) => !clips.has(s));
    return [...c.segs.filter((s) => clips.has(s)), ...(next === undefined ? [] : [next])];
  }
  if (c.first === null) return [];
  if (c.repeat !== Infinity) return Array.from({ length: c.repeat }, (_, i) => c.first + i);
  const made = [...clips.keys()].filter((s) => s >= c.first);
  return [...made, made.length ? Math.max(...made) + 1 : c.first];
}

function clipHTML(app, s, clip, segment) {
  const path = app.bridge.chain();
  const title = `Clip ${s + 1}${clip ? ` · ${clip.frames ?? "?"} frames · hover to play, click to open` : " · not rendered yet"}${s === segment ? " · next" : ""}`;  // clips count from 1
  return `<button class="tl-clip${clip ? "" : " empty"}${s === segment ? " now" : ""}" data-seg="${s}" title="${title}" ${clip ? "" : "disabled"}>`
    + (clip ? `<img loading="lazy" alt="" src="${app.api.chainThumbURL(s, path, clip.version)}">` : "")
    + `<span class="n">${s + 1}</span></button>`;
}

// The clips' width / height: a chain keeps one frame size; before it holds a clip, the size the template asks for.
export function clipRatio(app) {
  const { width, height } = app.data.chain?.width && app.data.chain?.height ? app.data.chain : shape(app.text);
  return width / height;
}

// A clip in the cells view: the video itself (its first frame until hovered), at the section's size (--clip-w,
// --clip-h); one not rendered yet is a small placeholder.
function bigClipHTML(app, s, clip, segment) {
  if (!clip) return clipHTML(app, s, clip, segment).replace('class="tl-clip empty', 'class="tl-clip empty small');
  const path = app.bridge.chain(), src = app.api.chainVideoURL(s, path, clip.version);
  return `<button class="tl-clip big${s === segment ? " now" : ""}" data-seg="${s}" title="Clip ${s + 1} · ${clip.frames ?? "?"} frames · hover to play, click to open${s === segment ? " · next" : ""}">`
    + `<video muted loop playsinline preload="metadata" poster="${app.api.chainThumbURL(s, path, clip.version)}" src="${src}#t=0.05"></video>`
    + `<span class="n">${s + 1}</span>${TAKE.test(clip.version || "") ? delHTML(clip.version) : ""}</button>`;
}

// A chunk's clips for its section in the cells view; the section sizes them (--clip-w, --clip-h). The frames
// its REMEMBER: lines take come under them (remember.js stripHTML).
export function sectionHTML(app, c) {
  if (c.first === null) {
    return `<span class="muted cm-none">${!c.segs ? "never plays: a scene before it repeats forever"
      : app.reelPath() ? "never plays at this seed: the walk does not reach it" : "walking the reel at this seed…"}</span>`;
  }
  const clips = new Map((app.data.chain?.clips || []).map((x) => [x.segment, x]));
  const segment = Number(app.bridge.getSegment()), segs = segmentsOf(c, clips);
  return `<div class="cm-clips">${segs.map((s) => bigClipHTML(app, s, clips.get(s), segment)).join("")}</div>${segs.map((s) => takesHTML(app, s)).join("")}`;
}

const TAKE = /^seg_\d{4}_[0-9a-f]{8}$/;  // an Orrery Film take's folder

// The × that deletes a take (#214), on hover; a click asks in place.
function delHTML(folder) {
  return `<span class="del" role="button" data-del="${esc(folder)}" title="Delete this take" aria-label="Delete this take">${icon("x")}</span>`;
}

// ✎ on a take made with another prompt (#242): its title says what changed, a click puts that prompt in the editor.
function verHTML(app, t) {
  const v = versionOf(app, t);
  return v ? `<span class="ver" role="button" data-ver="${esc(t.folder)}" title="${esc(`Made with another prompt · click: use this prompt\n${versionText(v)}`)}">✎</span>` : "";
}

// The takes made with another prompt, for the cells to tell when their marks change.
export function olderTakes(app) {
  return Object.values(app.data.chain?.takes || {}).flat().filter((t) => versionOf(app, t)).map((t) => t.folder);
}

// A take's size in the clip's shape (#215): `least`, the shorter side, as the grip at the strip's end sets it.
function takeVars(app, least = Number(app.data.take_min) || 54) {
  const ratio = clipRatio(app), w = ratio >= 1 ? least * ratio : least, h = ratio >= 1 ? least : least / ratio;
  return `--take-w:${Math.round(w)}px;--take-h:${Math.round(h)}px`;
}

// A clip's takes (#206), where it has more than one: hover plays one, a click puts it in the film.
function takesHTML(app, s) {
  const takes = app.data.chain?.takes?.[s] || [];
  if (takes.length < 2) return "";
  return `<div class="cm-takes" data-seg="${s}" style="${takeVars(app)}"><span class="cm-takes-head"><span class="muted">clip ${s + 1} · ${takes.length} takes</span>`
    + `<span class="btn ghost" role="button" data-clear="others" title="Delete every take of clip ${s + 1} but the one in the film">${icon("trash")}the others</span>`
    + `<span class="btn ghost danger" role="button" data-clear="all" title="Delete every take of clip ${s + 1}, the one in the film too: the film then ends before it">${icon("trash")}all</span>`
    + `<span class="btn ghost" role="button" data-playall title="Play every take of clip ${s + 1} at once, from the start, to compare them">${icon("play")}play all</span></span>${takes.map((t, i) =>
    `<button type="button" class="take${t.active ? " on" : ""}" data-take="${esc(t.folder)}" data-seg="${s}" title="Take ${i + 1} · seed ${t.seed ?? "?"}`
    + `${t.take ? ` + ${t.take}` : ""}${t.active ? " · in the film" : " · click to put it in the film"}">`
    + `<img loading="lazy" alt="" src="${app.api.takeThumbURL(app.bridge.chain(), t.folder)}"><span class="n">${i + 1}</span>${verHTML(app, t)}${delHTML(t.folder)}</button>`).join("")}`
    + `<span class="grip" data-grip title="Drag to size the takes"></span></div>`;
}

// Sample surfing (#206): the take picked is the one the film, REMEMBER: and the next clip use. A take that rolled
// anew sets the node's seed to its own, so the clips after it roll the same world.
async function pickTake(app, segment, folder) {
  try {
    const got = await app.api.pickTake(app.bridge.chain(), segment, folder);
    followSeed(app, got);
    await loadChain(app);
    app.refreshRun?.();
    app.toast(`This take of clip ${segment + 1} is in the film`);
  } catch (err) { app.fail(err); }
}

function followSeed(app, got) {
  if (!got.take && got.seed != null && Number(got.seed) !== Number(app.bridge.getSeed())) app.bridge.setSeed(Number(got.seed));
}

// Every take of a clip at once (#238): from the start and in step, muted and looping, to compare their motion;
// again, and the stills are back.
function playAll(app, strip, button) {
  const on = !strip.classList.contains("playing");
  strip.classList.toggle("playing", on);
  button.innerHTML = on ? `${icon("stop")}stop all` : `${icon("play")}play all`;
  const takes = [...strip.querySelectorAll(".take")];
  if (!on) return takes.forEach((t) => t.querySelector("video")?.remove());
  const videos = takes.map((t) => {
    let v = t.querySelector("video");
    if (!v) {
      v = Object.assign(document.createElement("video"), { muted: true, loop: true, playsInline: true, preload: "auto" });
      v.src = app.api.takeVideoURL(app.bridge.chain(), t.dataset.take);
      t.prepend(v);
    }
    v.pause();
    return v;
  });
  Promise.all(videos.map((v) => (v.readyState >= 3 ? null : new Promise((ok) => v.addEventListener("canplay", ok, { once: true }))))).then(() => {
    if (!strip.classList.contains("playing")) return;
    videos.forEach((v) => { v.currentTime = 0; v.play().catch(() => {}); });
  });
}

// A clip's takes deleted at once (#234), asked in place: all but the one in the film, or that one too, and then
// the film ends before the clip, and the next clip is that one.
async function clearTakes(app, segment, keep) {
  try {
    const got = await app.api.clearTakes(app.bridge.chain(), segment, keep);
    const ended = !keep && Number(app.bridge.getSegment()) > segment;
    if (ended) app.bridge.setSegment(segment);
    await loadChain(app);
    app.refreshRun?.();
    app.toast(keep ? `${got.deleted} takes of clip ${segment + 1} deleted; the one in the film stays`
      : `Clip ${segment + 1} deleted with its ${got.deleted} takes: the film ends before it${ended ? `, and the next clip is ${segment + 1}` : ""}`);
  } catch (err) { app.fail(err); }
}

// What deleting a take does, asked in place (#214): the clip plays another take, or the film ends before it.
export function deleteQuestion(app, host) {
  const s = Number(host.dataset.seg), folder = host.querySelector("[data-del]").dataset.del;
  const takes = app.data.chain?.takes?.[s] || [], at = takes.findIndex((t) => t.folder === folder);
  if (at >= 0 && !takes[at].active) return `Delete take ${at + 1}?`;
  const others = takes.filter((t) => t.folder !== folder);  // the clip in its box is the take in the film
  return others.length ? `Delete this take? Clip ${s + 1} then plays take ${takes.indexOf(others[others.length - 1]) + 1}.`
    : `Delete clip ${s + 1}? The film ends before it.`;
}

// A take deleted (#214): the film keeps the clip's newest other take, or ends before the clip, and then the next
// clip is that one.
async function deleteTake(app, segment, folder) {
  try {
    const got = await app.api.deleteTake(app.bridge.chain(), segment, folder);
    const ended = !got.folder && Number(app.bridge.getSegment()) > segment;
    if (got.folder) followSeed(app, got);
    else if (ended) app.bridge.setSegment(segment);
    await loadChain(app);
    app.refreshRun?.();
    app.toast(got.folder ? `Take deleted; clip ${segment + 1} plays another take`
      : `Clip ${segment + 1} deleted: the film ends before it${ended ? `, and the next clip is ${segment + 1}` : ""}`);
  } catch (err) { app.fail(err); }
}

// The clip a scene's REMEMBER: lines cut their frames from (its first), when the chain holds it; -1 the input video.
export function sourceClip(app, source) {
  if (source === null || source === undefined) return null;
  if (source < 0) return { url: app.api.chainVideoURL(-1, app.bridge.chain()), frames: null };
  const clip = (app.data.chain?.clips || []).find((x) => x.segment === source);
  return clip ? { url: app.api.chainVideoURL(source, app.bridge.chain(), clip.version), frames: clip.frames ?? null } : null;
}

// The clip rendering now (#205): its tile under the scene shows the sampler's preview (a picture, or KJNodes'
// whole clip as a video) and the step it is at. The tile is drawn again when the sections change, so this paints
// over whatever is there; without a live clip it takes the overlay off.
export function paintLive(app) {
  const host = app.view?.querySelector(".editor.cells");
  if (!host) return;
  const live = app.live;
  host.querySelectorAll(".tl-clip.live").forEach((tile) => {
    if (!live || tile.dataset.seg !== String(live.segment)) {
      tile.classList.remove("live");
      tile.querySelectorAll(".tl-live, .tl-step").forEach((el) => el.remove());
    }
  });
  if (!live) return;
  const tile = host.querySelector(`.tl-clip[data-seg="${live.segment}"]`);
  if (!tile) return;
  tile.classList.add("live");
  let view = tile.querySelector(".tl-live");
  if (live.url && (!view || (view.tagName === "VIDEO") !== live.video)) {
    view?.remove();
    view = document.createElement(live.video ? "video" : "img");
    view.className = "tl-live";
    if (live.video) Object.assign(view, { muted: true, loop: true, autoplay: true, playsInline: true });
    tile.prepend(view);
  }
  if (view && live.url && view.src !== live.url) view.src = live.url;
  let step = tile.querySelector(".tl-step");
  if (!step) {
    step = Object.assign(document.createElement("span"), { className: "tl-step" });
    tile.append(step);
  }
  const p = live.total ? live.step / live.total : 0;
  step.textContent = live.total ? `step ${live.step} / ${live.total}` : "starting…";
  step.style.setProperty("--p", `${Math.round(p * 100)}%`);
}

// Hover plays a clip in place; a click opens it large. The grip at a takes strip's end sizes every take (#215).
export function wireClips(app, box) {
  box.addEventListener("pointerdown", (e) => {
    const grip = e.target.closest("[data-grip]");
    if (!grip) return;
    e.preventDefault();
    e.stopPropagation();  // not a drag of the node
    const ratio = clipRatio(app), start = Number(app.data.take_min) || 54, x0 = e.clientX, y0 = e.clientY;
    let least = start;
    // the window's events, not the grip's: the grip moves away under the pointer as the takes resize and wrap
    const move = (m) => {  // along the take's longer move: its shorter side follows the pointer
      const dx = (m.clientX - x0) / Math.max(ratio, 1), dy = (m.clientY - y0) / Math.max(1 / ratio, 1);
      least = Math.min(480, Math.max(32, Math.round(start + (Math.abs(dx) > Math.abs(dy) ? dx : dy))));
      box.querySelectorAll(".cm-takes").forEach((strip) => { strip.style.cssText = takeVars(app, least); });
    };
    const up = async () => {
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("pointerup", up, true);
      if (least === start) return;
      app.data.take_min = least;
      try { Object.assign(app.data, await app.api.saveUi({ take_min: least })); } catch (err) { app.fail(err); }
    };
    window.addEventListener("pointermove", move, true);
    window.addEventListener("pointerup", up, true);
  });
  box.addEventListener("pointerover", (e) => {
    const take = e.target.closest(".take");
    if (take && !take.querySelector("video")) {
      const v = Object.assign(document.createElement("video"), { muted: true, loop: true, autoplay: true, playsInline: true });
      v.src = app.api.takeVideoURL(app.bridge.chain(), take.dataset.take);
      take.prepend(v);
      return;
    }
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (clip?.classList.contains("big")) { clip.querySelector("video")?.play().catch(() => {}); return; }
    if (!clip || clip.querySelector("video")) return;
    const v = document.createElement("video");
    Object.assign(v, { muted: true, loop: true, autoplay: true, playsInline: true });
    v.src = app.api.chainVideoURL(clip.dataset.seg, app.bridge.chain(), app.data.chain?.clips.find((c) => String(c.segment) === clip.dataset.seg)?.version);
    clip.prepend(v);
  });
  box.addEventListener("pointerout", (e) => {
    const take = e.target.closest(".take");
    if (take && !take.contains(e.relatedTarget) && !take.closest(".cm-takes.playing")) take.querySelector("video")?.remove();
    const clip = e.target.closest(".tl-clip");
    if (!clip || clip.contains(e.relatedTarget)) return;
    if (clip.classList.contains("big")) clip.querySelector("video")?.pause();
    else clip.querySelector("video")?.remove();
  });
  box.addEventListener("click", (e) => {
    const head = e.target.closest(".cm-takes-head");
    if (head) {
      const strip = head.closest(".cm-takes"), s = Number(strip.dataset.seg), count = strip.querySelectorAll(".take").length;
      const play = e.target.closest("[data-playall]");
      if (play) return playAll(app, strip, play);
      if (e.target.closest("[data-clearno]")) return head.querySelector(".ask")?.remove();
      const yes = e.target.closest("[data-clearyes]");
      if (yes) return clearTakes(app, s, yes.dataset.clearyes === "others");
      const ask = e.target.closest("[data-clear]");
      if (!ask) return;
      head.querySelector(".ask")?.remove();
      const others = ask.dataset.clear === "others";
      return head.insertAdjacentHTML("beforeend", `<span class="ask">${others ? `Delete ${count - 1} takes? The one in the film stays.`
        : `Delete all ${count} takes? The film ends before clip ${s + 1}.`}<span class="btn danger" role="button" data-clearyes="${ask.dataset.clear}">Delete</span>`
        + `<span class="btn ghost" role="button" data-clearno>Keep</span></span>`);
    }
    const ver = e.target.closest("[data-ver]");
    if (ver) {
      const v = versionOf(app, Object.values(app.data.chain?.takes || {}).flat().find((t) => t.folder === ver.dataset.ver));
      return v && useVersion(app, v);
    }
    const host = e.target.closest(".take, .tl-clip");
    if (e.target.closest("[data-delno]")) return host.querySelector(".ask")?.remove();
    if (e.target.closest("[data-delyes]")) return deleteTake(app, Number(host.dataset.seg), host.querySelector("[data-del]").dataset.del);
    if (e.target.closest(".ask")) return;
    if (e.target.closest("[data-del]")) {
      return host.insertAdjacentHTML("beforeend", `<span class="ask">${deleteQuestion(app, host)}`
        + `<span class="btn danger" role="button" data-delyes>Delete</span><span class="btn ghost" role="button" data-delno>Keep</span></span>`);
    }
    const take = e.target.closest(".take");
    if (take) { if (!take.classList.contains("on")) pickTake(app, Number(take.dataset.seg), take.dataset.take); return; }
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (!clip) return;
    const s = clip.dataset.seg, made = app.data.chain?.clips.find((c) => String(c.segment) === s);
    const sheet = app.openSheet(`<div class="panel"><div class="row spread"><h4>Clip ${Number(s) + 1}</h4>`
      + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
      + `<video class="tl-video" controls autoplay loop src="${app.api.chainVideoURL(s, app.bridge.chain(), made?.version)}"></video>`
      + `<p class="muted flush">${made?.frames ?? "?"} frames, as the reel keeps them (without the pinned frames)</p></div>`, clip, { over: true });
    sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  });
}
