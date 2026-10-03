// Small render pieces shared by several views.
import { esc } from "./highlight.js";
import { folderColor, glyph } from "./model.js";

export function thumbHTML(app, card) {
  return card.thumb
    ? `<img loading="lazy" src="${esc(app.api.thumbURL(card.thumb))}" alt="">`
    : glyph(card.name, folderColor(card.folder));
}

export function copyText(app, text, what) {
  const done = () => app.toast(`${what} copied`);
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(done, () => fallbackCopy(app, text, done));
  else fallbackCopy(app, text, done);
}

function fallbackCopy(app, text, done) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.cssText = "position:fixed;opacity:0";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  if (ok) done(); else app.toast("Copy was blocked by the browser");
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

// A side list as wide as you drag its edge (or press ← →); the node remembers the width in props[prop].
// box holds the width in the CSS variable cssVar; list is the column the grip sits on.
export function resizable(app, { box, grip, list, cssVar, prop, done = () => {} }) {
  if (!box || !grip) return;
  const set = (px) => {
    const w = Math.round(Math.min(Math.max(px, 140), box.clientWidth * 0.6));
    box.style.setProperty(cssVar, `${w}px`);
    app.bridge.props[prop] = w;
  };
  grip.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    grip.setPointerCapture(e.pointerId);
    const left = box.getBoundingClientRect().left;
    const move = (m) => set(m.clientX - left);
    const up = () => { grip.removeEventListener("pointermove", move); grip.removeEventListener("pointerup", up); done(); };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", up);
  });
  grip.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    set(list.offsetWidth + (e.key === "ArrowLeft" ? -16 : 16));
    done();
  });
}
