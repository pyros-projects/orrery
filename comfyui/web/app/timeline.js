// The film beside the editor: each CHUNK's clips as Orrery Film (or H3 Motion Context's Chain Video) keeps them, and
// the frames its SEND: lines handed on (Orrery Refs' anchors), level with the chunk's lines. The cells view
// (cells.js) shows the same under each chunk, in a section of its own.
import { icon } from "./icons.js";
import { plays, shape } from "./model.js";

const GAP = 3, MAX_H = 180, SEND_ROW = 26;

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
  const title = `Segment ${s}${clip ? ` · ${clip.frames ?? "?"} frames · hover to play, click to open` : " · not rendered yet"}${s === segment ? " · next" : ""}`;
  return `<button class="tl-clip${clip ? "" : " empty"}${s === segment ? " now" : ""}" data-seg="${s}" title="${title}" ${clip ? "" : "disabled"}>`
    + (clip ? `<img loading="lazy" alt="" src="${app.api.chainThumbURL(s, path, clip.version)}">` : "")
    + `<span class="n">${s}</span></button>`;
}

function sendHTML(app, n) {
  return `<div class="tl-send" title="Image ${n}: the frames Orrery Refs last sent to it"><img alt="" src="${app.api.anchorURL(n, app.data.anchorV)}"><span>→ image ${n}</span></div>`;
}

// The largest thumbs of the clips' aspect ratio (width / height) that fit n of them into the chunk,
// and the columns that make it: landscape stacks, portrait sits side by side. At most MAX_H tall.
export function fitThumbs(n, width, height, ratio) {
  let cols = 1, w = 0;
  for (let c = 1; c <= Math.max(1, n); c++) {
    const rows = Math.ceil(n / c);
    const cw = Math.min((width - (c - 1) * GAP) / c, ((height - (rows - 1) * GAP) / rows) * ratio);
    if (cw > w) [cols, w] = [c, cw];
  }
  w = Math.max(4, Math.min(w, MAX_H * ratio));
  return { cols, w: Math.floor(w), h: Math.floor(w / ratio) };
}

// The clips' width / height: a chain keeps one frame size; before it holds a clip, the size the template asks for.
export function clipRatio(app) {
  const { width, height } = app.data.chain?.width && app.data.chain?.height ? app.data.chain : shape(app.text);
  return width / height;
}

// A chunk's clips and sent frames for its section in the cells view; the section sizes them (--clip-h).
export function sectionHTML(app, c) {
  if (c.first === null) return '<span class="muted cm-none">never plays: a chunk before it repeats forever</span>';
  const clips = new Map((app.data.chain?.clips || []).map((x) => [x.segment, x]));
  const segment = Number(app.bridge.getSegment());
  return segmentsOf(c, clips).map((s) => clipHTML(app, s, clips.get(s), segment)).join("")
    + c.images.map((n) => sendHTML(app, n)).join("");
}

// Blocks level with the CHUNK lines the highlight drew; the track follows the textarea's scroll.
export function layoutTimeline(app, chunks) {
  const box = app.view.querySelector(".timeline");
  if (!box) return;
  box.hidden = !chunks;
  if (!chunks) return;
  const pre = app.view.querySelector(".editor pre.hl"), ed = app.view.querySelector(".editor textarea");
  const heads = [...pre.querySelectorAll(".chunkinfo")].map((el) => el.offsetTop);
  const end = pre.scrollHeight;
  const clips = new Map((app.data.chain?.clips || []).map((c) => [c.segment, c]));
  const segment = Number(app.bridge.getSegment());
  const ratio = clipRatio(app);
  const track = box.querySelector(".tl-track");
  track.style.height = `${end}px`;
  track.innerHTML = chunks.map((c, i) => {
    const top = heads[i] ?? 0, rowsH = (heads[i + 1] ?? end) - top;
    const segs = segmentsOf(c, clips);
    const now = plays(c, segment);
    const fit = fitThumbs(segs.length, box.clientWidth - 10, rowsH - 9 - c.images.length * SEND_ROW, ratio);
    return `<div class="tl-chunk${now ? " now" : ""}" style="top:${top}px;height:${rowsH}px">`
      + `<div class="tl-clips" style="--cols:${fit.cols};--clip-w:${fit.w}px;--clip-h:${fit.h}px">${segs.map((s) => clipHTML(app, s, clips.get(s), segment)).join("")}</div>`
      + c.images.map((n) => sendHTML(app, n)).join("") + "</div>";
  }).join("");
  track.style.transform = `translateY(${-ed.scrollTop}px)`;
}

export function scrollTimeline(app) {
  const track = app.view.querySelector(".timeline .tl-track"), ed = app.view.querySelector(".editor textarea");
  if (track && ed) track.style.transform = `translateY(${-ed.scrollTop}px)`;
}

// The column: the wheel scrolls the editor, and the grip before it sets its width (kept in the node).
export function wireTimeline(app) {
  const box = app.view.querySelector(".timeline");
  if (!box) return;
  box.addEventListener("wheel", (e) => {
    const ed = app.view.querySelector(".editor textarea");
    ed.scrollTop += e.deltaY;
    e.preventDefault();
  }, { passive: false });
  wireClips(app, box);
  const row = app.view.querySelector(".edrow"), grip = row.querySelector(".tl-grip");
  const set = (w) => {
    const px = Math.round(Math.min(Math.max(w, 90), row.clientWidth * 0.6));
    row.style.setProperty("--tl-w", `${px}px`);
    app.bridge.props.orrery_tl_w = px;
  };
  drag(grip, (dx, start) => set(start - dx), () => box.offsetWidth, () => layoutTimeline(app, app.chunks()));
  grip.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    set(box.offsetWidth + (e.key === "ArrowLeft" ? 16 : -16));
    layoutTimeline(app, app.chunks());
  });
}

// A pointer drag in the node's CSS pixels: the canvas zoom scales the screen pixels the pointer moves.
export function drag(grip, move, start, done) {
  grip.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation();
    grip.setPointerCapture(e.pointerId);
    const scale = grip.getBoundingClientRect().width / (grip.offsetWidth || 1) || 1;
    const x0 = e.clientX, y0 = e.clientY, from = start();
    const onMove = (m) => move((m.clientX - x0) / scale, from, (m.clientY - y0) / scale);
    const up = () => { grip.removeEventListener("pointermove", onMove); grip.removeEventListener("pointerup", up); done(); };
    grip.addEventListener("pointermove", onMove);
    grip.addEventListener("pointerup", up);
  });
}

// Hover plays a clip in place; a click opens it large.
export function wireClips(app, box) {
  box.addEventListener("pointerover", (e) => {
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (!clip || clip.querySelector("video")) return;
    const v = document.createElement("video");
    Object.assign(v, { muted: true, loop: true, autoplay: true, playsInline: true });
    v.src = app.api.chainVideoURL(clip.dataset.seg, app.bridge.latentPath(), app.data.chain?.clips.find((c) => String(c.segment) === clip.dataset.seg)?.version);
    clip.prepend(v);
  });
  box.addEventListener("pointerout", (e) => {
    const clip = e.target.closest(".tl-clip");
    if (clip && !clip.contains(e.relatedTarget)) clip.querySelector("video")?.remove();
  });
  box.addEventListener("click", (e) => {
    const clip = e.target.closest(".tl-clip:not(.empty)");
    if (!clip) return;
    const s = clip.dataset.seg, made = app.data.chain?.clips.find((c) => String(c.segment) === s);
    const sheet = app.openSheet(`<div class="panel"><div class="row spread"><h4>Segment ${s}</h4>`
      + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
      + `<video class="tl-video" controls autoplay loop src="${app.api.chainVideoURL(s, app.bridge.latentPath(), made?.version)}"></video>`
      + `<p class="muted flush">${made?.frames ?? "?"} frames, as the reel keeps them (without the pinned frames)</p></div>`);
    sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  });
}
