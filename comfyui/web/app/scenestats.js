// A scene in numbers (#219), its 📊: where and how often it plays on the walk at this seed, how long, what plays
// before and after it, what it rolls, and the clips it has made. The divider names one clip; this explains the rest.
import { inlineLibraries } from "../orrery-complete.js";
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { clock, span, splitCells } from "./model.js";

const STRIP = 240;  // the clips the strip draws; a walk that loops goes on past them
const STEERS = /\b(?:CUT TO|AFTER|GOTO|END ON):|^IF\b/;

// The reel as clips: which scene plays each, as far as it is known. A walk (CUT TO:) is the server's; else the
// scenes in order, each its repeats, until one repeats forever.
function reelPath(app, chunks) {
  const walked = app.reelPath?.();
  if (chunks.some((c) => c.segs)) return { path: walked?.path || [], ended: !!walked?.ended };
  const path = [];
  for (const [i, c] of chunks.entries()) {
    if (c.first === null) continue;
    for (let k = 0; k < c.repeat && path.length < STRIP; k++) path.push(i);
    if (c.repeat === Infinity) return { path, ended: false };
  }
  return { path, ended: true };
}

const counted = (names) => [...names.reduce((m, x) => m.set(x, (m.get(x) || 0) + 1), new Map())].sort((a, b) => b[1] - a[1]);

// What the sheet shows, worked out from the reel (for the tests, and the HTML below).
export function sceneStats(app, n) {
  const chunks = app.chunks() || [], c = chunks[n];
  if (!c) return null;
  const { path, ended } = reelPath(app, chunks), segment = Number(app.bridge.getSegment());
  const plays = path.flatMap((k, t) => (k === n ? [t] : []));
  const name = (k) => (k === n ? "itself" : chunks[k]?.title || `scene ${k + 1}`);
  const before = counted(plays.map((t) => (t === 0 ? "the start of the film" : name(path[t - 1]))));
  const after = counted(plays.flatMap((t) => (t + 1 < path.length ? [name(path[t + 1])] : ended ? ["the end of the film"] : [])));
  const lines = (splitCells(app.text).find((x) => x.chunk === n)?.text || "").split("\n").slice(1).map((l) => l.trim());
  const libs = new Map([...(app.data.completion?.libraries || []).map((l) => [l.name, l.count]),
    ...inlineLibraries(app.text).map((l) => [l.name, l.entries.length])]);
  const rolls = lines.flatMap((l) => {
    const b = /^\$([A-Za-z_]\w*)\s*=\s*(.+)$/.exec(l);
    if (!b) return [];
    const lib = /__([\w/-]+?)(?:[#:].*?)?__/.exec(b[2])?.[1], choice = /^\{([^{}]*)\}$/.exec(b[2].trim());
    return [{ name: b[1], what: b[2], count: lib ? libs.get(lib) ?? null : choice ? choice[1].split("|").length : null, lib: !!lib }];
  });
  const made = (app.data.chain?.clips || []).filter((x) => plays.includes(x.segment)).map((x) => x.segment);
  return {
    title: c.title, seed: app.bridge.getSeed(), path, ended, plays, segment, secs: c.secs, start: c.start, first: c.first,
    times: c.segs ? `${plays.length}${ended ? "" : "+"}` : c.repeat === Infinity ? "∞" : String(c.repeat ?? 1),
    before, after, steers: lines.filter((l) => STEERS.test(l)), rolls,
    made: made.map((s) => ({ clip: s + 1, takes: app.data.chain?.takes?.[s]?.length || 1 })),
  };
}

const list = (pairs) => pairs.map(([what, k]) => `${esc(what)} <b>${k}×</b>`).join(" · ") || "—";

export function sceneStatsHTML(app, n) {
  const s = sceneStats(app, n);
  if (!s) return "";
  const shown = s.path.slice(0, STRIP), chunks = app.chunks() || [];
  const strip = shown.map((k, t) => `<i class="${k === n ? "on" : ""}${t === s.segment ? " next" : ""}" title="clip ${t + 1}: ${esc(chunks[k]?.title || "")}"></i>`).join("");
  const share = s.path.length ? Math.round((s.plays.length / s.path.length) * 100) : 0;
  const filled = s.plays.length * s.secs, film = s.path.reduce((sum, k) => sum + (chunks[k]?.secs || 0), 0);
  const where = !s.plays.length ? "It never plays at this seed: the walk does not reach it."
    : `It plays <b>${s.times}</b> of the ${s.ended ? "" : "first "}<b>${s.path.length}</b> clips${s.ended ? " of the film" : " walked"} (${share} %)`
      + `${s.ended ? "." : "; the reel loops, so the walk goes on and it plays more."}`;
  return `<div class="panel scene-stats"><div class="row spread"><h4>${icon("chart")} SCENE ${esc(s.title)}</h4>`
    + `<button class="icon-btn" data-close title="Close">${icon("x")}</button></div>`
    + `<section><h5 class="label">Where it plays</h5><p class="muted flush">The film clip by clip, as the reel walks at seed ${esc(String(s.seed))}: `
    + `this scene's clips are lit, the next clip is outlined. Hover a clip for its scene.</p><div class="ss-strip">${strip}</div>`
    + `<p class="flush">${where}</p>${s.plays.length ? `<p class="muted flush">Its clips: ${s.plays.slice(0, 60).map((t) => t + 1).join(", ")}${s.plays.length > 60 ? ", …" : ""}</p>` : ""}</section>`
    + `<section><h5 class="label">How long</h5><p class="flush">Each of its clips is <b>${span(s.secs)}</b>`
    + `${s.start !== null && s.first !== null ? `; it first plays at <b>${clock(s.start)}</b> (clip ${s.first + 1})` : ""}.`
    + `${s.plays.length ? ` On the clips walked it fills ${clock(filled)} of ${clock(film)}.` : ""}</p></section>`
    + `<section><h5 class="label">Before and after</h5><p class="muted flush">What plays just before its clips and just after them on this walk; the lines `
    + `of the scene that steer the reel decide it.</p><dl><dt>after</dt><dd>${list(s.before)}</dd><dt>leads to</dt><dd>${list(s.after)}</dd></dl>`
    + `${s.steers.length ? `<pre class="ss-lines">${esc(s.steers.join("\n"))}</pre>` : ""}</section>`
    + `<section><h5 class="label">What it rolls</h5>${s.rolls.length ? `<dl>${s.rolls.map((r) => `<dt>$${esc(r.name)}</dt><dd>${esc(r.what)}`
      + `${r.count != null ? `<small>${r.count} ${r.lib ? "entries" : "choices"}</small>` : ""}</dd>`).join("")}</dl>`
      : `<p class="muted flush">No bindings of its own: it rolls what the lines above it roll.</p>`}</section>`
    + `<section><h5 class="label">Made</h5><p class="flush">${s.made.length ? `${s.made.length} of its clips are made: `
      + s.made.map((m) => `clip ${m.clip}${m.takes > 1 ? ` (${m.takes} takes)` : ""}`).join(", ") : "None of its clips is made yet."}</p></section></div>`;
}

export function openSceneStats(app, n) {
  const sheet = app.openSheet(sceneStatsHTML(app, n));
  sheet.querySelector("[data-close]").onclick = () => app.closeSheet();
}
