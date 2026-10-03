// The dials' menu of choices, in place of the browser's datalist, which shows only the choices that
// match what the box holds: once a dial had a value, its list was one choice or none (#155).
import { esc } from "./highlight.js";

// What the menu lists: every choice while the box is empty or holds one of them, else the ones that
// contain what is typed.
export function menuItems(choices, value) {
  const v = (value || "").trim().toLowerCase();
  if (!v || choices.some((c) => c.toLowerCase() === v)) return choices;
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
  const current = input.value.trim().toLowerCase();
  box.innerHTML = !choices ? '<div class="dm-note">Loading the choices…</div>'
    : items.length ? items.map((c, n) => `<div role="option" class="dm-item${n === at ? " on" : ""}${c.toLowerCase() === current ? " cur" : ""}" data-n="${n}">${esc(c)}</div>`).join("")
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
