// A reel's clips as Orrery Film (or H3 Motion Context's Chain Video) keeps them, under each scene in the cells
// view (cells.js), each scene's in a section of its own. The column beside the editor went in #185: the dials
// have that place now.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { shape } from "./model.js";

// The clips the chain holds, fetched again after every run.
export async function loadChain(app) {
  try { app.data.chain = await app.api.chain(app.bridge.chain()); } catch { app.data.chain = null; }
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
    + `<span class="n">${s + 1}</span></button>`;
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

// A clip's takes (#206), where it has more than one: hover plays one, a click puts it in the film.
function takesHTML(app, s) {
  const takes = app.data.chain?.takes?.[s] || [];
  if (takes.length < 2) return "";
  return `<div class="cm-takes" data-seg="${s}"><span class="muted">clip ${s + 1} · ${takes.length} takes</span>${takes.map((t, i) =>
    `<button type="button" class="take${t.active ? " on" : ""}" data-take="${esc(t.folder)}" data-seg="${s}" title="Take ${i + 1} · seed ${t.seed ?? "?"}`
    + `${t.take ? ` + ${t.take}` : ""}${t.active ? " · in the film" : " · click to put it in the film"}">`
    + `<img loading="lazy" alt="" src="${app.api.takeThumbURL(app.bridge.chain(), t.folder)}"><span class="n">${i + 1}</span></button>`).join("")}</div>`;
}

// Sample surfing (#206): the take picked is the one the film, REMEMBER: and the next clip use. A take that rolled
// anew sets the node's seed to its own, so the clips after it roll the same world.
async function pickTake(app, segment, folder) {
  try {
    const got = await app.api.pickTake(app.bridge.chain(), segment, folder, app.data.keep_takes === false);
    if (!got.take && got.seed != null && Number(got.seed) !== Number(app.bridge.getSeed())) app.bridge.setSeed(Number(got.seed));
    await loadChain(app);
    app.refreshRun?.();
    app.toast(`This take of clip ${segment + 1} is in the film${app.data.keep_takes === false ? "; the others are deleted" : ""}`);
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

// Hover plays a clip in place; a click opens it large.
export function wireClips(app, box) {
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
    if (take && !take.contains(e.relatedTarget)) take.querySelector("video")?.remove();
    const clip = e.target.closest(".tl-clip");
    if (!clip || clip.contains(e.relatedTarget)) return;
    if (clip.classList.contains("big")) clip.querySelector("video")?.pause();
    else clip.querySelector("video")?.remove();
  });
  box.addEventListener("click", (e) => {
    const take = e.target.closest(".take");
    if (take) { if (!take.classList.contains("on")) pickTake(app, Number(take.dataset.seg), take.dataset.take); return; }
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (!clip) return;
    const s = clip.dataset.seg, made = app.data.chain?.clips.find((c) => String(c.segment) === s);
    const sheet = app.openSheet(`<div class="panel"><div class="row spread"><h4>Clip ${Number(s) + 1}</h4>`
      + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
      + `<video class="tl-video" controls autoplay loop src="${app.api.chainVideoURL(s, app.bridge.chain(), made?.version)}"></video>`
      + `<p class="muted flush">${made?.frames ?? "?"} frames, as the reel keeps them (without the pinned frames)</p></div>`);
    sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  });
}
