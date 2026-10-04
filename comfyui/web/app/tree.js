// The take tree (#241): every take of the reel's run as a graph with videos, like a git graph. A column per clip,
// a node per take in the clip's shape (hover plays it), curves from each take to the takes made on it, and the
// film's path lit in brass along the top. A click makes the film the path through a take (to it from clip 1,
// then on as it was last walked); ✂ ends the film after it. Hovering a take shows the way the film would go. A take
// made with another version of its scene carries ✎ (#242): hovering it shows what changed, ✎ brings that prompt back.
// ▶ Film plays the film clicked together (#243), the take playing lit in the tree.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { clock } from "./model.js";
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
const FPS = 24;  // Orrery Film's clips

// The film's clips as film.mp4 plays them, test takes left out: [{folder, n, start, end}] in seconds.
export function filmClips(tree) {
  const by = new Map(tree.takes.map((t) => [t.folder, t])), out = [];
  let at = 0;
  tree.path.forEach((folder, i) => {
    const t = by.get(folder);
    if (!t || t.test) return;
    const secs = (Number(t.frames) || 0) / FPS;
    out.push({ folder, n: i + 1, start: at, end: at + secs });
    at += secs;
  });
  return out;
}

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

// The diff card beside its take where the view has room: right of it, else left, else under it; always in view.
function placeCard(card, node, scroll) {
  const view = { left: scroll.scrollLeft + 6, right: scroll.scrollLeft + scroll.clientWidth - 6, top: scroll.scrollTop + 6,
    bottom: scroll.scrollTop + scroll.clientHeight - 6 };
  const w = card.offsetWidth, h = card.offsetHeight, right = node.offsetLeft + node.offsetWidth + 12, left = node.offsetLeft - w - 12;
  let x = right, y = node.offsetTop;
  if (right + w > view.right) {
    if (left >= view.left) x = left;
    else { x = node.offsetLeft; y = node.offsetTop + node.offsetHeight + 10; }
  }
  card.style.left = `${Math.max(view.left, Math.min(x, view.right - w))}px`;
  card.style.top = `${Math.max(view.top, Math.min(y, view.bottom - h))}px`;
}

export function openTree(app) {
  const size = () => Number(app.bridge.props.orrery_tree_size) || SIZE;
  const sheet = app.openSheet(`<div class="panel tree-panel"><div class="row spread"><h4>${icon("tree")} The take tree</h4>`
    + `<span class="muted" data-tstat></span><span class="grow"></span>`
    + `<button class="btn ghost" data-tfilm aria-pressed="false" title="Play the film as it is clicked together, its takes joined">${icon("play")}Film</button>`
    + `<input type="range" min="48" max="240" step="8" value="${size()}" data-tsize title="The takes' size" aria-label="The takes' size">`
    + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
    + `<div class="tree-scroll"><p class="muted tree-none">Growing the tree…</p></div>`
    + `<div class="tree-film" hidden><video controls playsinline preload="auto"></video><div class="tf-side"><div class="tf-now"></div><div class="tf-ribbon"></div></div></div>`
    + `<p class="muted flush tree-hint">A click on a take: the film goes the path through it, to it from clip 1 and on as it was last walked. `
    + `✂ ends the film after a take of it. Hover plays a take and shows the way. ✎ marks a take made with another prompt: `
    + `hover shows what changed, ✎ puts that prompt in the editor. Switching takes never changes the editor.</p></div>`);
  const scroll = sheet.querySelector(".tree-scroll"), player = sheet.querySelector(".tree-film"), video = player.querySelector("video");
  let tree = null, clips = [];
  // The film's clip at the player's time: lit in the tree and on the ribbon.
  const playing = () => {
    const t = video.currentTime, now = clips.find((c) => t < c.end) ?? clips[clips.length - 1];
    scroll.querySelectorAll("[data-tree]").forEach((n) => n.classList.toggle("playing", !player.hidden && n.dataset.tree === now?.folder));
    player.querySelectorAll("[data-tseek]").forEach((b) => b.classList.toggle("on", b.dataset.tseek === now?.folder));
    player.querySelector(".tf-now").textContent = now ? `clip ${now.n} of ${tree.path.length} · ${clock(t)} / ${clock(clips[clips.length - 1].end)}` : "";
  };
  const film = () => {  // the film again, from the start: after a click it is another
    clips = filmClips(tree);
    if (player.hidden) return;
    if (!clips.length) {
      player.hidden = true;
      sheet.querySelector("[data-tfilm]").setAttribute("aria-pressed", "false");
      return app.toast("The film has no clips yet (a test scene's take is left out of it).");
    }
    const total = clips[clips.length - 1].end || 1;
    player.querySelector(".tf-ribbon").innerHTML = clips.map((c) => `<button type="button" data-tseek="${esc(c.folder)}" style="flex:${(c.end - c.start) / total}" `
      + `title="Clip ${c.n} · from ${clock(c.start)}">${c.n}</button>`).join("");
    video.src = app.api.filmURL(app.bridge.chain(), Date.now());
    video.play().catch(() => {});
  };
  const draw = () => {
    scroll.innerHTML = treeHTML(app, tree, size());
    if (!player.hidden) playing();
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
      film();
    } catch (err) { app.fail(err); }
  };
  sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
  sheet.querySelector("[data-tfilm]").onclick = (e) => {
    if (!tree) return;
    const on = player.hidden;
    player.hidden = !on;
    e.currentTarget.setAttribute("aria-pressed", String(on));
    if (on) return film();
    video.pause();
    video.removeAttribute("src");
    scroll.querySelectorAll(".tnode.playing").forEach((n) => n.classList.remove("playing"));
  };
  video.addEventListener("timeupdate", playing);
  player.querySelector(".tf-ribbon").addEventListener("click", (e) => {
    const c = clips.find((x) => x.folder === e.target.closest("[data-tseek]")?.dataset.tseek);
    if (!c) return;
    video.currentTime = c.start + 0.01;
    video.play().catch(() => {});
  });
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
    placeCard(card, node, scroll);
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
