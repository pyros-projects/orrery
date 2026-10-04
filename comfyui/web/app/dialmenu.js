// The dials' menu of choices, in place of the browser's datalist, which shows only the choices that
// match what the box holds: once a dial had a value, its list was one choice or none (#155).
import { esc } from "./highlight.js";

export const MENU_MAX = 500;  // a menu lists this many choices; the filter reaches the rest, and any can be typed

// The choices the box holds: one of them, or several as `{a|b}` (a narrower roll that still varies, #156).
export function chosen(choices, value) {
  const v = (value || "").trim();
  const exact = choices.find((c) => c.toLowerCase() === v.toLowerCase());
  if (exact !== undefined) return [exact];
  if (!(v.startsWith("{") && v.endsWith("}"))) return [];
  const parts = [];
  let depth = 0, start = 1;
  for (let i = 1; i < v.length - 1; i++) {  // the top level only: a choice may hold its own {…|…}
    const ch = v[i];
    if (ch === "{" || ch === "[") depth++;
    else if ((ch === "}" || ch === "]") && depth > 0) depth--;
    else if (ch === "|" && depth === 0) { parts.push(v.slice(start, i)); start = i + 1; }
  }
  parts.push(v.slice(start, -1));
  const found = parts.map((p) => choices.find((c) => c === p.trim().replace(/:\d+(\.\d+)?$/, "")));
  return found.every((c) => c !== undefined) ? [...new Set(found)] : [];
}

// The box's text for these choices: none, the one, or `{a|b}`.
export function joinChoices(list) {
  return list.length === 0 ? "" : list.length === 1 ? list[0] : `{${list.join("|")}}`;
}

// What the menu lists: every choice while the box is empty or holds some of them, else the ones that
// contain what is typed.
export function menuItems(choices, value) {
  const v = (value || "").trim().toLowerCase();
  if (!v || chosen(choices, value).length) return choices;
  return choices.filter((c) => c.toLowerCase().includes(v));
}

// The filter (#186): a regex, case-insensitive, over a choice's text, its properties (`genre: noir` and `genre=noir`)
// and its tags; a pattern that is no regex matches as plain text. `info(choice)` → { props, tags } for an entry.
export function filterPattern(query) {
  const q = (query || "").trim();
  if (!q) return null;
  try { return new RegExp(q, "i"); } catch { const low = q.toLowerCase(); return { test: (text) => text.toLowerCase().includes(low) }; }
}

// Why a choice matches: "" for its text, else the property or tag that does; null when nothing does.
export function matchedBy(choice, rx, info = null) {
  if (!rx || rx.test(choice)) return "";
  const more = info?.(choice) || {};
  const prop = Object.entries(more.props || {}).find(([k, v]) => rx.test(`${k}: ${v}`) || rx.test(`${k}=${v}`));
  if (prop) return `${prop[0]}: ${prop[1]}`;
  const tag = (more.tags || []).find((t) => rx.test(t));
  return tag ? `#${tag}` : null;
}

export function filterChoices(choices, query, info = null) {
  const rx = filterPattern(query);
  return rx ? choices.filter((c) => matchedBy(c, rx, info) !== null) : choices;
}

// The menu under (or, near the bottom, above) the dial's box, inside `host`. `choices` is null while a
// library's entries are still on their way. Returns the menu's state for keys and picks.
// `describe(choice)` → { sub, thumb } shows more than a choice's text (a gallery character: who it is, its picture).
// `filter` and `info` (#186): the filter's text, and a choice's properties and tags. The head (filter, All, None)
// shows for a list of more than one; fillMenu redraws only the list, so the filter keeps its focus while typing.
export function drawMenu(host, input, choices, at = -1, describe = null, { filter = "", info = null } = {}) {
  host.querySelector(".dm")?.remove();
  const box = document.createElement("div");
  box.className = "dm";
  box.setAttribute("role", "listbox");
  const head = choices?.length > 1 ? `<div class="dm-head"><input class="dm-filter" value="${esc(filter)}" placeholder="Filter · a regex, properties too" spellcheck="false" autocomplete="off" aria-label="Filter the choices">`
    + '<button type="button" class="dm-act" data-all title="Roll among every choice shown">All</button><button type="button" class="dm-act" data-none title="No choice: the default roll">None</button></div>' : "";
  box.innerHTML = `${head}<div class="dm-list"></div>`;
  const items = fillMenu(box, input, choices, at, describe, { filter, info });
  host.appendChild(box);
  // the host may be scaled (the node on ComfyUI's canvas): place it in the host's own pixels
  const h = host.getBoundingClientRect(), r = input.closest(".dial").getBoundingClientRect(), k = h.width / host.offsetWidth || 1;
  const left = (r.left - h.left) / k + host.scrollLeft, below = (r.bottom - h.top) / k + host.scrollTop, above = (r.top - h.top) / k + host.scrollTop;
  box.style.left = `${Math.max(4, Math.min(left, host.clientWidth - box.offsetWidth - 4))}px`;
  box.style.minWidth = `${r.width / k}px`;
  const roomBelow = host.clientHeight + host.scrollTop - below;
  box.style.top = `${roomBelow >= Math.min(box.offsetHeight, 160) ? below + 4 : Math.max(4, above - box.offsetHeight - 4)}px`;
  reveal(box, box.querySelector(".on"));
  return { box, items, at };
}

export function fillMenu(box, input, choices, at = -1, describe = null, { filter = "", info = null } = {}) {
  const rx = filterPattern(filter);
  const found = choices ? filterChoices(menuItems(choices, input.value), filter, info) : [];
  const items = found.slice(0, MENU_MAX);
  const picked = new Set(choices ? chosen(choices, input.value) : []);
  const note = (picked.size > 1 ? `<div class="dm-note">${picked.size} chosen · rolls among them</div>` : "")
    + (found.length > MENU_MAX ? `<div class="dm-note">The first ${MENU_MAX} of ${found.length}: filter for the rest.</div>` : "");
  box.querySelector(".dm-list").innerHTML = !choices ? '<div class="dm-note">Loading the choices…</div>'
    : items.length ? note + items.map((c, n) => `<div role="option" aria-selected="${picked.has(c)}" class="dm-item${n === at ? " on" : ""}${picked.has(c) ? " cur" : ""}" data-n="${n}">`
      + `<span class="dm-box" data-toggle="${n}" title="Add to the choices it rolls among (Space)">${picked.has(c) ? "✓" : ""}</span>${itemHTML(c, describe?.(c) || why(c, rx, info))}</div>`).join("")
      : `<div class="dm-note">${!choices.length ? "No list here: type any value or expression." : filter.trim() ? "Nothing matches the filter."
        : "Nothing matches: the dial takes what you type."}</div>`;
  return items;
}

// The property or tag a choice was found by, under its text.
function why(choice, rx, info) {
  const by = rx && matchedBy(choice, rx, info);
  return by ? { sub: choice, note: by } : null;
}

function itemHTML(choice, more) {
  if (more?.note) return `<span class="dm-text"><span>${esc(choice)}</span><small>${esc(more.note)}</small></span>`;
  if (!more) return `<span>${esc(choice)}</span>`;
  return `${more.thumb ? `<img class="dm-pic" src="${esc(more.thumb)}" alt="" loading="lazy">` : ""}`
    + `<span class="dm-text"><span>${esc(more.sub || choice)}</span>${more.sub ? `<small>${esc(choice)}</small>` : ""}</span>`;
}

// Where a redrawn menu scrolls (#300): a tick redraws it, and the choice ticked stays where it was on screen
// (the "N chosen" note above the list may come or go); without that choice in the new list, the old position.
// `before`: { top, anchor } (the box's scrollTop, the ticked item's offsetTop then, or null); `anchor`: its offsetTop now.
export function keptScroll(before, anchor) {
  if (before.anchor == null || anchor == null) return before.top;
  return Math.max(0, before.top + anchor - before.anchor);
}

// Scrolls `list` so `item` shows, and nothing else: scrollIntoView scrolls every scrolling box around it too, the
// editor (which jumped up while typing at its end, #303) and ComfyUI's canvas.
export function reveal(list, item) {
  if (!list || !item) return;
  const top = item.offsetTop - (item.offsetParent === list ? 0 : list.offsetTop), bottom = top + item.offsetHeight;
  if (top < list.scrollTop) list.scrollTop = top;
  else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight;
}

export function closeMenu(host) {
  host.querySelector(".dm")?.remove();
}
