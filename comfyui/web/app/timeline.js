// A reel's clips as Orrery Film (or H3 Motion Context's Chain Video) keeps them, under each scene in the cells
// view (cells.js), each scene's in a section of its own. The column beside the editor went in #185: the dials
// have that place now.
import { icon } from "./icons.js";
import { shape } from "./model.js";

// The clips the chain holds, fetched again after every run.
export async function loadChain(app) {
  try { app.data.chain = await app.api.chain(app.bridge.latentPath()); } catch { app.data.chain = null; }
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
  const path = app.bridge.latentPath();
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
  const path = app.bridge.latentPath(), src = app.api.chainVideoURL(s, path, clip.version);
  return `<button class="tl-clip big${s === segment ? " now" : ""}" data-seg="${s}" title="Clip ${s + 1} · ${clip.frames ?? "?"} frames · hover to play, click to open${s === segment ? " · next" : ""}">`
    + `<video muted loop playsinline preload="metadata" poster="${app.api.chainThumbURL(s, path, clip.version)}" src="${src}#t=0.05"></video>`
    + `<span class="n">${s + 1}</span></button>`;
}

// A chunk's clips for its section in the cells view; the section sizes them (--clip-w, --clip-h). The frames
// its REMEMBER: lines take come under them (remember.js stripHTML).
export function sectionHTML(app, c) {
  if (c.first === null) return '<span class="muted cm-none">never plays: a scene before it repeats forever</span>';
  const clips = new Map((app.data.chain?.clips || []).map((x) => [x.segment, x]));
  const segment = Number(app.bridge.getSegment());
  return `<div class="cm-clips">${segmentsOf(c, clips).map((s) => bigClipHTML(app, s, clips.get(s), segment)).join("")}</div>`;
}

// The clip a scene's REMEMBER: lines cut their frames from (its first), when the chain holds it; -1 the input video.
export function sourceClip(app, source) {
  if (source === null || source === undefined) return null;
  if (source < 0) return { url: app.api.chainVideoURL(-1, app.bridge.latentPath()), frames: null };
  const clip = (app.data.chain?.clips || []).find((x) => x.segment === source);
  return clip ? { url: app.api.chainVideoURL(source, app.bridge.latentPath(), clip.version), frames: clip.frames ?? null } : null;
}

// Hover plays a clip in place; a click opens it large.
export function wireClips(app, box) {
  box.addEventListener("pointerover", (e) => {
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (clip?.classList.contains("big")) { clip.querySelector("video")?.play().catch(() => {}); return; }
    if (!clip || clip.querySelector("video")) return;
    const v = document.createElement("video");
    Object.assign(v, { muted: true, loop: true, autoplay: true, playsInline: true });
    v.src = app.api.chainVideoURL(clip.dataset.seg, app.bridge.latentPath(), app.data.chain?.clips.find((c) => String(c.segment) === clip.dataset.seg)?.version);
    clip.prepend(v);
  });
  box.addEventListener("pointerout", (e) => {
    const clip = e.target.closest(".tl-clip");
    if (!clip || clip.contains(e.relatedTarget)) return;
    if (clip.classList.contains("big")) clip.querySelector("video")?.pause();
    else clip.querySelector("video")?.remove();
  });
  box.addEventListener("click", (e) => {
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (!clip) return;
    const s = clip.dataset.seg, made = app.data.chain?.clips.find((c) => String(c.segment) === s);
    const sheet = app.openSheet(`<div class="panel"><div class="row spread"><h4>Clip ${Number(s) + 1}</h4>`
      + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
      + `<video class="tl-video" controls autoplay loop src="${app.api.chainVideoURL(s, app.bridge.latentPath(), made?.version)}"></video>`
      + `<p class="muted flush">${made?.frames ?? "?"} frames, as the reel keeps them (without the pinned frames)</p></div>`);
    sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  });
}
