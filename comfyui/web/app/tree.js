// The take tree (#241): every take of the reel's run as a graph with videos, like a git graph. A column per clip,
// a node per take in the clip's shape (hover plays it), curves from each take to the takes made on it, and the
// film's path lit in brass along the top. A click makes the film the path through a take (to it from clip 1,
// then on as it was last walked); ✂ ends the film after it. Hovering a take shows the way the film would go. A take
// made with another version of its scene carries ✎ (#242): hovering it shows what changed, ✎ brings that prompt back.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { clipRatio, loadChain } from "./timeline.js";
import { fetchTemplates, useVersion, versionHTML, versionOf } from "./versions.js";

// The takes' rows, as a tidy tree: a take sits on the row of its first child, so a path runs straight; the film's
// path comes first, so it is the top line, the rest in the order they were made. A take whose parent is not
// known starts a row of its own.
export function layoutTree(takes, path = []) {
  const by = new Map(takes.map((t) => [t.folder, t])), kids = new Map(), film = new Set(path);
  for (const t of takes) if (t.parent && by.has(t.parent)) (kids.get(t.parent) ?? kids.set(t.parent, []).get(t.parent)).push(t);
  const order = (list) => [...list].sort((a, b) => (film.has(b.folder) - film.has(a.folder)) || a.segment - b.segment
    || String(a.created || "").localeCompare(String(b.created || "")));
  const rows = new Map();
  let next = 0;
  const place = (t) => {
    const ks = order(kids.get(t.folder) || []);
    ks.forEach(place);
    rows.set(t.folder, ks.length ? rows.get(ks[0].folder) : next++);
  };
  order(takes.filter((t) => !t.parent || !by.has(t.parent))).forEach(place);
  return rows;
}

// The way the film would go through a take: the takes it came after, it, and on as last walked from it.
export function wayThrough(tree, folder) {
  const by = new Map(tree.takes.map((t) => [t.folder, t])), way = [folder];
  for (let t = by.get(folder); t?.parent && by.has(t.parent); t = by.get(t.parent)) way.unshift(t.parent);
  for (let at = folder; tree.last?.[at] && by.has(tree.last[at]); at = tree.last[at]) way.push(tree.last[at]);
  return way;
}

const SIZE = 96;  // a node's shorter side unless the slider says otherwise

export function treeHTML(app, tree, size = SIZE) {
  const takes = tree.takes || [];
  if (!takes.length) return `<p class="muted tree-none">No takes yet: render a clip, and the tree starts growing.</p>`;
  const rows = layoutTree(takes, tree.path), by = new Map(takes.map((t) => [t.folder, t])), film = new Set(tree.path);
  const ratio = clipRatio(app), w = Math.round(ratio >= 1 ? size * ratio : size), h = Math.round(ratio >= 1 ? size : size / ratio);
  const colW = w + Math.max(48, w * 0.45), rowH = h + 34, left = 18, top = 44;
  const x = (s) => left + s * colW, y = (r) => top + r * rowH;
  const segs = Math.max(...takes.map((t) => t.segment)) + 1, height = top + Math.max(...rows.values(), 0) * rowH + h + 30;
  const chunks = app.chunks?.() || [];
  const nth = new Map();  // a take's number in its clip, in the order they were made
  for (let s = 0; s < segs; s++) {
    takes.filter((t) => t.segment === s).sort((a, b) => String(a.created || "").localeCompare(String(b.created || "")))
      .forEach((t, i) => nth.set(t.folder, i + 1));
  }
  const heads = Array.from({ length: segs }, (_, s) => {
    const scenes = [...new Set(takes.filter((t) => t.segment === s && t.scene != null).map((t) => chunks[t.scene]?.title).filter(Boolean))];
    return `<div class="thead" style="left:${x(s)}px;width:${w}px"><b>clip ${s + 1}</b>${scenes.length ? `<span>${esc(scenes.join(" · "))}</span>` : ""}</div>`;
  }).join("");
  const edges = takes.filter((t) => t.parent && by.has(t.parent)).map((t) => {
    const p = by.get(t.parent), x1 = x(p.segment) + w, y1 = y(rows.get(p.folder)) + h / 2, x2 = x(t.segment), y2 = y(rows.get(t.folder)) + h / 2;
    const mid = (x1 + x2) / 2, on = film.has(t.folder) && film.has(p.folder);
    return `<path class="tedge${on ? " on" : ""}" data-edge="${esc(t.folder)}" d="M${x1} ${y1} C${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}"/>`;
  }).join("");
  const nodes = takes.map((t) => {
    const r = rows.get(t.folder), on = film.has(t.folder), older = !!versionOf(app, t);
    const title = `Clip ${t.segment + 1}, take ${nth.get(t.folder)} · seed ${t.seed ?? "?"}${t.take ? ` + ${t.take}` : ""}${on ? " · in the film" : ""}`
      + `${older ? " · made with another prompt" : ""} · click: the film goes through it`;
    return `<button type="button" class="tnode${on ? " on" : ""}${t.test ? " test" : ""}${older ? " older" : ""}" data-tree="${esc(t.folder)}" style="left:${x(t.segment)}px;top:${y(r)}px;width:${w}px;height:${h}px" title="${esc(title)}">`
      + `<img loading="lazy" alt="" src="${app.api.takeThumbURL(app.bridge.chain(), t.folder)}"><span class="n">${nth.get(t.folder)}</span>`
      + (older ? `<span class="ver" role="button" data-ver="${esc(t.folder)}" title="Use this prompt: the scene as this take was made with it, into the editor">✎</span>` : "")
      + (on ? `<span class="tend" role="button" data-tend="${t.segment}" title="End the film after this take">✂</span>` : "") + "</button>";
  }).join("");
  return `<div class="tree-canvas" style="width:${x(segs - 1) + w + left}px;height:${height}px">`
    + `<svg class="tree-lines" width="${x(segs - 1) + w + left}" height="${height}">${edges}</svg>${heads}${nodes}<div class="tree-diff" hidden></div></div>`;
}

export function openTree(app) {
  const size = () => Number(app.bridge.props.orrery_tree_size) || SIZE;
  const sheet = app.openSheet(`<div class="panel tree-panel"><div class="row spread"><h4>${icon("tree")} The take tree</h4>`
    + `<span class="muted" data-tstat></span><span class="grow"></span>`
    + `<input type="range" min="48" max="240" step="8" value="${size()}" data-tsize title="The takes' size" aria-label="The takes' size">`
    + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
    + `<div class="tree-scroll"><p class="muted tree-none">Growing the tree…</p></div>`
    + `<p class="muted flush tree-hint">A click on a take: the film goes the path through it, to it from clip 1 and on as it was last walked. `
    + `✂ ends the film after a take of it. Hover plays a take and shows the way. ✎ marks a take made with another prompt: `
    + `hover shows what changed, ✎ puts that prompt in the editor. Switching takes never changes the editor.</p></div>`);
  const scroll = sheet.querySelector(".tree-scroll");
  let tree = null;
  const draw = () => {
    scroll.innerHTML = treeHTML(app, tree, size());
    const paths = (tree.takes || []).filter((t) => !(tree.takes || []).some((k) => k.parent === t.folder)).length;
    sheet.querySelector("[data-tstat]").textContent = `${tree.takes.length} takes · ${paths} path${paths === 1 ? "" : "s"} · the film ${tree.path.length} clips`;
  };
  const grow = async () => {
    try {
      tree = await app.api.chainTree(app.bridge.chain());
      await fetchTemplates(app, tree.takes || []);
      draw();
    } catch (err) { app.fail(err); }
  };
  const change = async (call, said) => {
    try {
      const got = await call();
      if (got?.seed != null && !got.take && Number(got.seed) !== Number(app.bridge.getSeed())) app.bridge.setSeed(Number(got.seed));
      await loadChain(app);
      app.refreshRun?.();
      app.toast(said(got));
      await grow();
    } catch (err) { app.fail(err); }
  };
  sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  sheet.querySelector("[data-tsize]").oninput = (e) => { app.bridge.props.orrery_tree_size = Number(e.target.value); if (tree) draw(); };
  scroll.addEventListener("click", (e) => {
    const ver = e.target.closest("[data-ver]"), v = ver && versionOf(app, tree.takes.find((t) => t.folder === ver.dataset.ver));
    if (ver) {
      e.stopPropagation();
      if (v) useVersion(app, v);
      return draw();
    }
    const end = e.target.closest("[data-tend]");
    if (end) {
      e.stopPropagation();
      const s = Number(end.dataset.tend);
      return change(() => app.api.endFilm(app.bridge.chain(), s), () => `The film ends after clip ${s + 1}`);
    }
    const node = e.target.closest("[data-tree]");
    if (node) change(() => app.api.walkTo(app.bridge.chain(), node.dataset.tree), (got) => `The film goes through this take: ${got.clips} clips`);
  });
  scroll.addEventListener("pointerover", (e) => {
    const node = e.target.closest("[data-tree]");
    if (!node || !tree) return;
    if (!node.querySelector("video")) {
      const v = Object.assign(document.createElement("video"), { muted: true, loop: true, autoplay: true, playsInline: true });
      v.src = app.api.takeVideoURL(app.bridge.chain(), node.dataset.tree);
      node.prepend(v);
    }
    const way = new Set(wayThrough(tree, node.dataset.tree));
    scroll.querySelectorAll("[data-tree]").forEach((n) => n.classList.toggle("way", way.has(n.dataset.tree)));
    scroll.querySelectorAll("[data-edge]").forEach((p) => p.classList.toggle("way", way.has(p.dataset.edge)));
    const v = versionOf(app, tree.takes.find((t) => t.folder === node.dataset.tree)), card = scroll.querySelector(".tree-diff");
    if (!v || !card) return;
    card.innerHTML = versionHTML(v);
    card.hidden = false;
    const right = node.offsetLeft + node.offsetWidth + 10, canvas = card.parentElement.offsetWidth;  // beside the take, where it fits
    card.style.left = `${right + card.offsetWidth <= Math.max(canvas, scroll.scrollLeft + scroll.clientWidth) ? right : Math.max(4, node.offsetLeft - card.offsetWidth - 10)}px`;
    card.style.top = `${node.offsetTop}px`;
  });
  scroll.addEventListener("pointerout", (e) => {
    const node = e.target.closest("[data-tree]");
    if (!node || node.contains(e.relatedTarget)) return;
    node.querySelector("video")?.remove();
    scroll.querySelectorAll(".way").forEach((n) => n.classList.remove("way"));
    scroll.querySelector(".tree-diff")?.setAttribute("hidden", "");
  });
  grow();
}
