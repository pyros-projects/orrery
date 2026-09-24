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
