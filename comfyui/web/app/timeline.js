// The film beside the editor: each CHUNK's clips as H3 Motion Context's Chain Video keeps them, and
// the frames its SEND: lines handed on (Orrery Refs' anchors), level with the chunk's lines.
import { icon } from "./icons.js";

// The clips the chain holds, fetched again after every run.
export async function loadChain(app) {
  try { app.data.chain = await app.api.chain(app.bridge.latentPath()); } catch { app.data.chain = null; }
  app.data.anchorV = Date.now();  // anchors change in place: a new run, a new URL
}

// The segments a chunk shows: all it plays, or for one that repeats forever, the clips made so far
// and the next one.
function segmentsOf(c, clips) {
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

// The fewest columns whose 16:9 thumbs fit the chunk's height, and their height (cropped when tighter).
function fit(n, width, height) {
  const most = Math.max(1, Math.min(6, n));
  let cols = 1, h = 0;
  for (; cols <= most; cols++) {
    const rows = Math.ceil(n / cols), natural = ((width - (cols - 1) * 3) / cols) * 9 / 16;
    h = Math.min(natural, (height - (rows - 1) * 3) / rows);
    if (h >= natural - 0.5 || cols === most) break;
  }
  return [cols, Math.round(Math.max(16, Math.min(h, 90)))];
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
  const track = box.querySelector(".tl-track");
  track.style.height = `${end}px`;
  track.innerHTML = chunks.map((c, i) => {
    const top = heads[i] ?? 0, height = (heads[i + 1] ?? end) - top;
    const segs = segmentsOf(c, clips);
    const now = c.first !== null && segment >= c.first && segment <= c.last;
    const [cols, clipH] = fit(segs.length, box.clientWidth - 10, height - 9 - c.images.length * 26);
    return `<div class="tl-chunk${now ? " now" : ""}" style="top:${top}px;height:${height}px">`
      + `<div class="tl-clips" style="--cols:${cols};--clip-h:${clipH}px">${segs.map((s) => clipHTML(app, s, clips.get(s), segment)).join("")}</div>`
      + c.images.map((n) => sendHTML(app, n)).join("") + "</div>";
  }).join("");
  track.style.transform = `translateY(${-ed.scrollTop}px)`;
}

export function scrollTimeline(app) {
  const track = app.view.querySelector(".timeline .tl-track"), ed = app.view.querySelector(".editor textarea");
  if (track && ed) track.style.transform = `translateY(${-ed.scrollTop}px)`;
}

// Hover plays a clip in place; a click opens it large.
export function wireTimeline(app) {
  const box = app.view.querySelector(".timeline");
  if (!box) return;
  box.addEventListener("wheel", (e) => {
    const ed = app.view.querySelector(".editor textarea");
    ed.scrollTop += e.deltaY;
    e.preventDefault();
  }, { passive: false });
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
      + `<p class="muted flush">${made?.frames ?? "?"} frames, as Chain Video keeps them (without the pinned context)</p></div>`);
    sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  });
}
