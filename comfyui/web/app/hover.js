// Hover in the editor (#136, #147): a keyword says what it does and its forms, a directive what it sets, a
// CAST member who it is in this clip (its description, its pictures with their strengths, its RefMods), a
// library how big it is and what it holds, a binding what it rolled at the node's seed. With the annotations on
// hover (#203), a marked word says first what it rolled.
import { DIRECTIVES, KEYWORDS } from "../orrery-complete.js";
import { esc } from "./highlight.js";

// The keyword a line head starts with (`SHOT 5s:` → SHOT, `REMEMBER:`), or null.
export function keywordHelp(text) {
  const t = text.trim().toLowerCase();
  const k = KEYWORDS.find((k) => {
    const word = k.word.trim().replace(/\s*\$$/, "").toLowerCase();
    return t === word || t.startsWith(`${word} `) || t.startsWith(word.endsWith(":") ? word : `${word}:`) || (word === "cast" && t === "cast");
  });
  return k ? { word: k.word.trim().replace(/\s*\$$/, ""), says: k.says, forms: k.forms } : null;
}

export function directiveHelp(text) {
  const d = DIRECTIVES.find(([insert]) => text.trim() === insert.trim().split(" ")[0]);
  return d ? { word: d[0].trim(), says: d[1] } : null;
}

const pct = (v) => `${Math.round(v * 100)}%`;

// One picture's or RefMod's dials as they read in a line: at 0.6 from 35% to 80%.
export function dialText(d) {
  const parts = [];
  if (d.strength !== undefined && d.strength !== 1) parts.push(`at ${d.strength}`);
  const from = d.from ?? d.start, to = d.to ?? d.end;
  if (from) parts.push(`from ${pct(from)}`);
  if (to !== undefined && to < 1) parts.push(`to ${pct(to)}`);
  return parts.join(" ");
}

// What a marked word rolled (#203: annotations on hover), above its own card.
function card(app, span) {
  const roll = span.dataset.roll ? `<div class="hv-roll">${esc(span.dataset.roll)}</div>` : "";
  const own = help(app, span);
  return own && span.classList.contains("t-var") ? own : roll + own;  // a binding's card says its roll already
}

function help(app, span) {
  const text = span.textContent;
  if (span.classList.contains("t-cast")) {
    const name = text.replace(/^@/, "").replace(/[(:].*$/, "").trim(), m = app.annotations?.()?.members?.[name];
    if (!m) return `<div class="hv-t"><b>@${esc(name)}</b> <span class="muted">· rolling the clip…</span></div>`;
    const pics = m.pictures.map((p) => `<figure>${p.id ? `<img src="${esc(app.api.thumbURL(p.id))}" alt="">` : '<span class="hv-none">wired</span>'}`
      + `<figcaption>image ${p.image}${dialText(p) ? ` ${esc(dialText(p))}` : ""}</figcaption></figure>`).join("");
    const named = [...new Set(m.pictures.map((p) => p.name).filter(Boolean))];
    return `<div class="hv-t"><b>@${esc(name)}</b> in this clip</div><div class="hv-who">${esc(m.who)}</div>`
      + (pics ? `<div class="hv-pics">${pics}</div>` : '<div class="muted">no picture in this clip</div>')
      + (named.length ? `<div class="muted">${named.map(esc).join(" · ")}</div>` : "")
      + m.refmods.map((r) => `<div>refmod <b>${esc(r.name)}</b> ${esc(dialText(r))}</div>`).join("")
      + (m.voice ? `<div>voice: ${esc(m.voice)}</div>` : "");
  }
  if (span.classList.contains("t-kw")) {
    const k = keywordHelp(text);
    if (!k) return "";
    return `<div class="hv-t"><b>${esc(k.word)}</b> ${esc(k.says)}</div><ul>${k.forms.slice(0, 7).map(([f, d]) =>
      `<li><code>${esc(f.replace(/\n/g, " ⏎ "))}</code> <span class="muted">${esc(d)}</span></li>`).join("")}</ul>`
      + '<div class="hv-f">Type its start for every form · Ctrl+Space</div>';
  }
  if (span.classList.contains("t-param")) {
    const d = directiveHelp(text);
    const grid = /^@grid$|^grid$/.test(text.trim()) && app.annotations?.()?.grid;
    return d ? `<div class="hv-t"><b>${esc(d.word)}</b> ${esc(d.says)}</div>${grid ? `<div class="muted">${esc(grid)}</div>` : ""}` : "";
  }
  if (span.classList.contains("t-lib")) {
    const name = text.replace(/^__/, "").replace(/(\[.*|#.*|:\d+)?__.*$/, ""), lib = app.data.completion?.libraries.find((l) => l.name === name);
    if (!lib) return "";
    const kind = lib.name.startsWith("pictures/") ? "the gallery's pictures, a character each" : { builtin: "built-in", user: "yours", llm: "written by the language model" }[lib.source] || lib.source;
    return `<div class="hv-t"><b>__${esc(lib.name)}__</b> · ${lib.count} entries · ${esc(kind)}</div>`
      + (lib.fields?.length ? `<div class="muted">fields: ${lib.fields.filter((f) => !["ids", "pictures", "prompt"].includes(f)).map(esc).join(", ")}</div>` : "")
      + `<ul>${(lib.sample || []).slice(0, 4).map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`;
  }
  if (span.classList.contains("t-var")) {
    const [, name, field] = /^\$([A-Za-z_]\w*)(?:\.([\w-]+))?/.exec(text) || [], ann = app.annotations?.();
    const value = name && (field ? ann?.fields?.[name]?.[field]
      : ann?.bindings?.[name] ?? (ann?.exports?.[name] && `kept: ${ann.exports[name]}`));
    return value ? `<div class="hv-t"><b>$${esc(name)}${field ? `.${esc(field)}` : ""}</b> at this seed</div><div class="hv-who">${esc(value)}</div>` : "";
  }
  return "";
}

// The editor (or the cells' editor) shows a card for what is under the pointer, below it or above when the
// app has no room; it goes on a key, a scroll, the pointer leaving, or the completion opening.
export function wireHover(app, editor) {
  if (!editor || editor.dataset.hover) return;
  editor.dataset.hover = "1";
  let frame = 0, last = null;
  const hide = () => { editor.querySelector(".hv")?.remove(); last = null; };
  const show = (x, y) => {
    if (app.ac) return hide();
    const spans = [...editor.querySelectorAll("pre .t-cast, pre .t-kw, pre .t-param, pre .t-lib, pre .t-var")].reverse();
    const span = spans.find((s) => [...s.getClientRects()].some((r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom));
    if (!span) return hide();
    if (span === last) return;
    const html = card(app, span);
    if (!html) return hide();
    last = span;
    editor.querySelector(".hv")?.remove();
    const box = Object.assign(document.createElement("div"), { className: "hv", innerHTML: html });
    editor.appendChild(box);
    const er = editor.getBoundingClientRect(), sr = span.getClientRects()[0], k = er.width / editor.offsetWidth || 1;
    const root = (editor.closest(".orrery-app") || editor).getBoundingClientRect();
    const left = (sr.left - er.left) / k, below = (sr.bottom - er.top) / k + 4, above = (sr.top - er.top) / k - box.offsetHeight - 4;
    box.style.left = `${Math.max(4, Math.min(left, editor.clientWidth - box.offsetWidth - 4))}px`;
    box.style.top = `${(root.bottom - er.top) / k - below >= box.offsetHeight || above < -(er.top - root.top) / k ? below : above}px`;
  };
  editor.addEventListener("mousemove", (e) => {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; show(e.clientX, e.clientY); });
  });
  editor.addEventListener("mouseleave", hide);
  editor.addEventListener("keydown", hide);
  editor.addEventListener("scroll", hide, true);
}
