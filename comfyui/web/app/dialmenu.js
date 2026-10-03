// The dials' menu of choices, in place of the browser's datalist, which shows only the choices that
// match what the box holds: once a dial had a value, its list was one choice or none (#155).
import { esc } from "./highlight.js";

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

// The menu under (or, near the bottom, above) the dial's box, inside `host`. `choices` is null while a
// library's entries are still on their way. Returns the menu's state for keys and picks.
export function drawMenu(host, input, choices, at = -1) {
  host.querySelector(".dm")?.remove();
  const items = choices ? menuItems(choices, input.value) : [];
  const box = document.createElement("div");
  box.className = "dm";
  box.setAttribute("role", "listbox");
  const picked = new Set(choices ? chosen(choices, input.value) : []);
  const head = picked.size > 1 ? `<div class="dm-note">${picked.size} chosen · rolls among them</div>` : "";
  box.innerHTML = !choices ? '<div class="dm-note">Loading the choices…</div>'
    : items.length ? head + items.map((c, n) => `<div role="option" aria-selected="${picked.has(c)}" class="dm-item${n === at ? " on" : ""}${picked.has(c) ? " cur" : ""}" data-n="${n}">`
      + `<span class="dm-box" data-toggle="${n}" title="Add to the choices it rolls among (Space)">${picked.has(c) ? "✓" : ""}</span><span>${esc(c)}</span></div>`).join("")
      : `<div class="dm-note">${choices.length ? "Nothing matches: the dial takes what you type." : "No list here: type any value or expression."}</div>`;
  host.appendChild(box);
  // the host may be scaled (the node on ComfyUI's canvas): place it in the host's own pixels
  const h = host.getBoundingClientRect(), r = input.closest(".dial").getBoundingClientRect(), k = h.width / host.offsetWidth || 1;
  const left = (r.left - h.left) / k + host.scrollLeft, below = (r.bottom - h.top) / k + host.scrollTop, above = (r.top - h.top) / k + host.scrollTop;
  box.style.left = `${Math.max(4, Math.min(left, host.clientWidth - box.offsetWidth - 4))}px`;
  box.style.minWidth = `${r.width / k}px`;
  const roomBelow = host.clientHeight + host.scrollTop - below;
  box.style.top = `${roomBelow >= Math.min(box.offsetHeight, 160) ? below + 4 : Math.max(4, above - box.offsetHeight - 4)}px`;
  box.querySelector(".on")?.scrollIntoView({ block: "nearest" });
  return { box, items, at };
}

export function closeMenu(host) {
  host.querySelector(".dm")?.remove();
}
