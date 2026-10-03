// Pure helpers shared by the views: hashing, stats, filters, pick marks, glyphs.
import { esc } from "./highlight.js";

export const FACTORS = { love: 1.5, like: 1.2, nope: 0.8, hate: 0.5 };
const FOLDER_COLORS = { tutorial: "#b8b5cc", krea: "#e2b45c", h3: "#7fb4ff", stills: "#5cc8c2", mine: "#cfcde0" };

export function hashNum(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

export function mulberry(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// SHA-256, because crypto.subtle is missing when ComfyUI is opened over plain http on a LAN.
const K = Uint32Array.from([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function sha256(bytes) {
  const h = Uint32Array.from([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const len = bytes.length, padded = new Uint8Array(((len + 72) >> 6) << 6);
  padded.set(bytes); padded[len] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 4, len * 8); view.setUint32(padded.length - 8, Math.floor(len / 0x20000000));
  const w = new Uint32Array(64), rot = (x, n) => (x >>> n) | (x << (32 - n));
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rot(w[i - 15], 7) ^ rot(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rot(w[i - 2], 17) ^ rot(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rot(e, 6) ^ rot(e, 11) ^ rot(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
      const t2 = ((rot(a, 2) ^ rot(a, 13) ^ rot(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    [a, b, c, d, e, f, g, hh].forEach((v, i) => { h[i] = (h[i] + v) | 0; });
  }
  return [...h].map((v) => v.toString(16).padStart(8, "0")).join("");
}

export const templateHash = (text) => sha256(new TextEncoder().encode(text)).slice(0, 16);

// `# …` lines are comments (as in wildcard files): the node drops them before anything rolls.
export const stripComments = (text) => text.split("\n").filter((l) => !/^\s*#/.test(l)).join("\n");

// A run is replayed as it was made: one recorded before every pick had dice of its own (no rng in
// its row) gets `@rng 1` (under the @h3 line, which stays the first), and a screenplay recorded before
// lite was the default (no format in its row) gets `full` on its @h3 line.
export function withDice(text, row) {
  const lines = text.split("\n"), head = lines.findIndex((l) => /^\s*@h3\b/.test(l));
  if (head >= 0 && !row?.format && !/\b(lite|full)\b/.test(lines[head])) lines[head] = `${lines[head].trimEnd()} full`;
  if (!row?.rng && !/^\s*@rng\b/m.test(text)) lines.splice(head + 1, 0, "@rng 1");
  return lines.join("\n");
}

// `@style(0.8)` is `<lora:style:0.8>`, as orrery.loras.long_form writes it (not @include or @h3).
export const longForm = (text) => text.replace(/(?<![\w@<\\])@([\w./\\-]+)\(([^()<>]*)\)/g,
  (m, name, spec) => (/^(include|h3)$/i.test(name) ? m : `<lora:${name}:${spec.trim()}>`));

// A brace's options: split at `|`, but not inside `[...]` (`{__a[x|y]__|b}` has two). Mirrors orrery.dsl.split_options.
export function splitOptions(inner) {
  const out = [];
  let depth = 0, start = 0;
  [...inner].forEach((ch, i) => {
    if (ch === "[") depth++;
    else if (ch === "]" && depth) depth--;
    else if (ch === "|" && !depth) { out.push(inner.slice(start, i)); start = i + 1; }
  });
  return [...out, inner.slice(start)];
}

// `[myth]` · `[myth,!bird]` every term holds · `[water|deep_sea]` either does. Mirrors orrery.dsl.tags_match.
// `myth, !bird, habitat=sea, size=small|tiny`: mirrors orrery.dsl.matches. A `$var` value is not known
// here, so it holds.
export function matches(spec, tags, props = {}) {
  if (!spec || !spec.trim()) return true;
  return spec.split(",").every((term) => {
    let key = null;
    const alts = term.split("|").map((a) => a.trim()).filter(Boolean);
    return !alts.length || alts.some((alt) => {
      let neg = alt.startsWith("!"), body = alt.replace(/^!+\s*/, ""), value = null;
      if (body.includes("!=")) { [key, value] = body.split("!=").map((x) => x.trim()); neg = !neg; }
      else if (body.includes("=")) [key, value] = body.split("=").map((x) => x.trim());
      else if (key !== null) value = body;
      const ok = value === null ? tags.includes(body)
        : value.startsWith("$") || String(props?.[key] ?? "").trim().toLowerCase() === value.toLowerCase();
      return ok !== neg;
    });
  });
}
export const tagsMatch = (spec, tags) => matches(spec, tags);

export function stats(raw) {
  const text = longForm(stripComments(raw)).replace(/<lora:[^<>]*>/g, "<lora>");
  const libs = [...text.matchAll(/__([\w*]+(?:\/[\w*]+)*)(?:\[[^\[\]\n]+\])?(?:#[\w-]+:\$?[\w.-]+)*(?::\d+)?__/g)];
  const rolls = (text.match(/\{/g) || []).length + libs.length;
  const binds = (text.match(/^\s*\$\w+\s*=/gm) || []).length;
  let h3 = null;
  if (/^\s*@h3/.test(text)) {
    const shots = [...text.matchAll(/^\s*SHOT\s+([\d.]+)\s*s/gm)];
    const firstShot = text.search(/^\s*SHOT\b/m);
    const voices = new Set([...text.slice(Math.max(firstShot, 0)).matchAll(/^\s*([A-Z][A-Z0-9 _-]*?)\s*(?:\([^)]*\))?\s*:\s/gm)]
      .map((m) => m[1]).filter((n) => !["SFX", "MUSIC", "SHOT", "LORA", "HANDOFF", "SEND"].includes(n)));
    h3 = { shots: shots.length, secs: shots.reduce((s, m) => s + Number(m[1]), 0), voices: voices.size, reel: reelSecs(text) };
  }
  return { rolls, libs: new Set(libs.map((m) => m[1])).size, binds, h3 };
}

export function markPicks(text, picks) {
  let parts = [{ t: text, p: false }];
  const values = [...new Set(picks.flatMap((p) => p.value.split(", ")))]
    .filter((v) => v.length > 1).sort((a, b) => b.length - a.length);
  for (const v of values) {
    parts = parts.flatMap((x) => {
      if (x.p) return [x];
      const out = [];
      x.t.split(v).forEach((s, i, all) => {
        if (s) out.push({ t: s, p: false });
        if (i < all.length - 1) out.push({ t: v, p: true });
      });
      return out;
    });
  }
  return parts.map((x) => (x.p ? `<mark>${esc(x.t)}</mark>` : esc(x.t))).join("");
}

export const folderOf = (name) => (name.includes("/") ? name.split("/")[0] : "");
export const folderColor = (f) => FOLDER_COLORS[f || "mine"] || `hsl(${hashNum(f) % 360} 55% 70%)`;

export function glyph(key, color) {
  const r = mulberry(hashNum(key));
  let orbits = "";
  for (let i = 0; i < 3; i++) {
    const rx = 17 + i * 11, ry = rx * (0.32 + r() * 0.3), rot = Math.floor(r() * 180), a = r() * Math.PI * 2;
    orbits += `<g transform="rotate(${rot} 50 50)"><ellipse cx="50" cy="50" rx="${rx}" ry="${ry.toFixed(1)}" fill="none" stroke="${color}" stroke-opacity=".32" stroke-width=".8"/>`
      + `<circle cx="${(50 + rx * Math.cos(a)).toFixed(1)}" cy="${(50 + ry * Math.sin(a)).toFixed(1)}" r="${(1.8 + r() * 2.6).toFixed(1)}" fill="${color}" fill-opacity="${(0.55 + r() * 0.45).toFixed(2)}"/></g>`;
  }
  return `<svg class="glyph" viewBox="0 0 100 125" preserveAspectRatio="xMidYMid slice"><rect width="100" height="125" fill="#15161d"/>`
    + `<g transform="translate(0 12)"><circle cx="50" cy="50" r="4.5" fill="${color}"/>${orbits}</g></svg>`;
}

const haystack = (c) => [c.name, c.title, c.note, (c.tags || []).join(" "), c.text || ""].join(" ").toLowerCase();

export function filterPresets(cards, { filter = "all", search = "", favorites = new Set(), recent = [] }) {
  let list = cards;
  if (filter === "fav") list = cards.filter((c) => favorites.has(c.name));
  else if (filter === "recent") list = recent.map((n) => cards.find((c) => c.name === n)).filter(Boolean);
  else if (filter.startsWith("f:")) list = cards.filter((c) => (c.folder || "mine") === filter.slice(2));
  const q = search.trim().toLowerCase();
  return q ? list.filter((c) => haystack(c).includes(q)) : list;
}

export function pickerGroups(cards, { query, favorites, recent }) {
  const q = query.trim().toLowerCase();
  const groups = [];
  if (!q) {
    groups.push(["Favorites", cards.filter((c) => favorites.has(c.name))]);
    groups.push(["Recent", recent.map((n) => cards.find((c) => c.name === n)).filter(Boolean)]);
  }
  const folders = [...new Set(cards.map((c) => c.folder || "mine"))];
  for (const f of folders) groups.push([f, cards.filter((c) => (c.folder || "mine") === f && (!q || haystack(c).includes(q)))]);
  return groups.filter((g) => g[1].length);
}

export function filterRows(rows, { scope = "all", hash, preset, rating, pick }) {
  let out = rows;
  if (scope === "prompt") out = out.filter((r) => r.template === hash);
  if (scope === "preset") out = out.filter((r) => preset && r.preset === preset);
  if (rating === "unrated") out = out.filter((r) => !r.rating);
  else if (rating) out = out.filter((r) => r.rating === rating);
  if (pick) out = out.filter((r) => r.picks.some((p) => p.keys.includes(pick)));
  return out;
}

// The galaxy's folders ([{path, count}]) as a tree of {path, name, count, children}, sorted by name.
export function folderTree(folders) {
  const nodes = new Map();
  const node = (path) => {
    if (!nodes.has(path)) nodes.set(path, { path, name: path.split("/").pop(), count: 0, children: [] });
    return nodes.get(path);
  };
  for (const f of folders) {
    const parts = f.path.split("/");
    for (let i = 1; i < parts.length; i++) node(parts.slice(0, i).join("/"));
    node(f.path).count = f.count;
  }
  const roots = [];
  for (const n of nodes.values()) {
    const cut = n.path.lastIndexOf("/");
    (cut < 0 ? roots : nodes.get(n.path.slice(0, cut)).children).push(n);
  }
  const sort = (list) => { list.sort((a, b) => a.name.localeCompare(b.name)); list.forEach((n) => sort(n.children)); return list; };
  return sort(roots);
}

// Shift-click: the cards from the anchor to the clicked one, in the order shown; without an anchor
// on screen, just the clicked card.
export function rangeIds(ids, anchor, id) {
  const a = ids.indexOf(anchor), b = ids.indexOf(id);
  return a < 0 || b < 0 ? [id] : ids.slice(Math.min(a, b), Math.max(a, b) + 1);
}

// Where a folder lands when dropped on another ("" is the top level), or null when it would move
// into itself or stay where it is.
export function folderDropPath(path, target) {
  if (target === path || target.startsWith(`${path}/`)) return null;
  const name = path.split("/").pop();
  const to = target ? `${target}/${name}` : name;
  return to === path ? null : to;
}

// A scene's heading (CHUNK, the earlier word) and how often it plays: `×4`, `x4`, `forever`, or the
// earlier `repeat 4` / `repeat forever`. Mirrors orrery.reel.
const SCENE = /^(?:SCENE|CHUNK)\b\s*(.*)$/;
const REPEAT = /^(.*?)\s*(?:\brepeat\s+(\d+|forever)|(?<!\S)[×x]\s*(\d+)|(?<!\S)(forever))\s*$/i;

const TEST = /(?<!\S)\(test\)(?!\S)/i;  // `SCENE the forest (test)`: kept, left out of the film

// The title of a scene's heading, how often it plays (Infinity for forever) and whether it is a test scene.
function heading(rest) {
  const plain = rest.replace(TEST, " ").split(/\s+/).filter(Boolean).join(" ");
  const r = REPEAT.exec(plain), times = r && (r[2] ?? r[3] ?? "forever");
  return { title: (r ? r[1] : plain).trim(), repeat: !r ? 1 : times.toLowerCase() === "forever" ? Infinity : Math.max(1, Number(times)),
    test: TEST.test(rest) };
}

// A reel's scenes: the seconds of their shots (without the pinned context), how often each plays
// (Infinity for forever), the clips in all, and which start afresh, with no pinned context: the
// first scene, a test scene without AFTER:, a scene with only test scenes before it. Null without
// SCENE lines. Mirrors orrery.reel.
function reelSecs(text) {
  let secs = null;
  const repeats = [], fresh = [], tests = [], after = [];
  for (const l of text.split("\n").map((x) => x.trim())) {
    const c = SCENE.exec(l);
    if (c) {
      const h = heading(c[1]);
      (secs ??= []).push(0);
      repeats.push(h.repeat);
      tests.push(h.test);
      after.push(false);
    }
    if (secs && /^AFTER:/.test(l)) after[secs.length - 1] = true;
    const m = /^SHOT\s+(\d+(?:\.\d+)?)\s*s\b/i.exec(l);
    if (m && secs) secs[secs.length - 1] += Number(m[1]);
  }
  if (!secs) return null;
  secs.forEach((_, i) => fresh.push(!after[i] && (tests[i] || tests.slice(0, i).every(Boolean))));
  return { chunks: secs.length, secs, repeats, fresh, clips: repeats.reduce((a, b) => a + b, 0) };
}

// Each SCENE line of a reel, for the editor's dividers and the timeline: the line it is on, its
// title, the images its SEND: lines fill, the segments it plays (last Infinity when it repeats forever; first null when a chunk before
// it does), the seconds of one clip (kept without the pinned frames), where it starts
// and ends in the film, the seconds left after it (null when the film runs forever) and a label.
// Null without SCENE lines. Mirrors orrery.reel.
export function chunkInfo(text, walked = null) {
  const out = [];
  text.split("\n").forEach((raw, line) => {
    const l = raw.trim(), c = SCENE.exec(l);
    if (c) out.push({ line, ...heading(c[1]), secs: 0, images: [] });
    const m = /^SHOT\s+(\d+(?:\.\d+)?)\s*s\b/i.exec(l), send = /^(?:SEND:.*\bto|REMEMBER:.*\bas)\s+image\s+(\d+)/i.exec(l);
    if (m && out.length) out[out.length - 1].secs += Number(m[1]);
    if (send && out.length && !out[out.length - 1].images.includes(Number(send[1]))) out[out.length - 1].images.push(Number(send[1]));
  });
  if (!out.length) return null;
  if (hasGoto(text)) return walkedInfo(out, walked);
  let segment = 0, at = 0;
  for (const c of out) {
    if (segment === null) Object.assign(c, { first: null, last: null, start: null, end: null });
    else {
      Object.assign(c, { first: segment, last: segment + c.repeat - 1, start: at, end: at + c.secs * c.repeat });
      segment = c.repeat === Infinity ? null : segment + c.repeat;
      at = c.end;
    }
  }
  for (const c of out) {
    c.left = segment === null || c.end === null ? null : at - c.end;
    c.label = chunkLabel(c);
  }
  return out;
}

// A reel with CUT TO: lines plays a scene wherever the server's walk at the node's seed puts it
// (`walked`: {path: chunk index per segment, ended}): each chunk its list of segments, `segs`.
export const hasGoto = (text) => /^\s*(?:\?[^\n]*?:\s*)?(?:CUT\s+TO|GOTO):/im.test(stripComments(text));

function walkedInfo(out, walked) {
  if (!walked) {
    for (const c of out) Object.assign(c, { segs: [], first: null, last: null, start: null, end: null, left: null, label: "CUT TO: walking the reel at this seed…" });
    return out;
  }
  const at = [0];
  walked.path.forEach((chunk, t) => at.push(at[t] + (out[chunk]?.secs ?? 0)));
  const total = walked.ended ? at[walked.path.length] : null;
  out.forEach((c, i) => {
    const segs = walked.path.flatMap((chunk, t) => (chunk === i ? [t] : []));
    const first = segs.length ? segs[0] : null, last = segs.length ? segs[segs.length - 1] : null;
    Object.assign(c, { segs, endless: !walked.ended, first, last, start: first === null ? null : at[first],
      end: last === null ? null : at[last] + c.secs, left: last === null || total === null ? null : total - at[last] - c.secs });
    c.label = chunkLabel(c);
  });
  return out;
}

// Does chunk c play segment s? On its range, or on its list when GOTO lines set the path.
export const plays = (c, s) => s != null && (c.segs ? c.segs.includes(s) : c.first !== null && s >= c.first && s <= c.last);

// 1, 3–4, 7: a scene's clips in short, counted from 1 (segments from 0).
function runs(segs) {
  const parts = [];
  for (const s of segs) {
    const last = parts[parts.length - 1];
    if (last && s === last[1] + 1) last[1] = s;
    else parts.push([s, s]);
  }
  return parts.map(([a, b]) => (a === b ? `${a + 1}` : `${a + 1}–${b + 1}`)).join(", ");
}

// The cells view: the text cut before every SCENE line, the world above the first one its own cell
// (chunk -1). Joined with newlines, the cells are the text again.
export function splitCells(text) {
  const lines = text.split("\n");
  const starts = lines.flatMap((l, i) => (SCENE.test(l.trim()) ? [i] : []));
  if (!starts.length) return [{ line: 0, chunk: -1, text }];
  const cells = starts[0] > 0 ? [{ line: 0, chunk: -1, text: lines.slice(0, starts[0]).join("\n") }] : [];
  starts.forEach((s, k) => cells.push({ line: s, chunk: k, text: lines.slice(s, starts[k + 1] ?? lines.length).join("\n") }));
  return cells;
}

const clock = (secs) => {
  const s = Math.round(secs * 10) / 10, m = Math.floor(s / 60), r = Math.round((s - m * 60) * 10) / 10;
  return `${m}:${Number.isInteger(r) ? String(r).padStart(2, "0") : r.toFixed(1).padStart(4, "0")}`;
};
const span = (secs) => `${Math.round(secs * 100) / 100} s`;

// `clip 5 · 0:20 → 0:25 · 1:35 left`, `clips 2–5 · 4 × 5 s · …`, `clip 8 → ∞ · 6 s each · from 0:35`:
// clips count from 1, the segments behind them from 0.
export function chunkLabel(c) {
  if (c.segs) {
    if (!c.segs.length) return c.endless ? "not on the path yet: the reel loops before it" : "never plays at this seed";
    const shown = c.segs.slice(0, 12), more = c.segs.length > 12 || c.endless ? ", …" : "";
    const left = c.left === null ? "" : c.left > 0 ? ` · ${clock(c.left)} left` : " · the end";
    return `clip${c.segs.length > 1 ? "s" : ""} ${runs(shown)}${more} · ${c.segs.length > 1 ? `${c.segs.length}${c.endless ? "+" : ""} × ` : ""}${span(c.secs)} · from ${clock(c.start)}${left}`;
  }
  if (c.first === null) return "never plays: a scene before it repeats forever";
  if (c.repeat === Infinity) return `clip ${c.first + 1} → ∞ · ${span(c.secs)} each · from ${clock(c.start)}`;
  const segs = c.repeat > 1 ? `clips ${c.first + 1}–${c.last + 1} · ${c.repeat} × ${span(c.secs)}` : `clip ${c.first + 1}`;
  const left = c.left === null ? "" : c.left > 0 ? ` · ${clock(c.left)} left` : " · the end";
  return `${segs} · ${clock(c.start)} → ${clock(c.end)}${left}`;
}

function h3Length(seconds) {
  const frames = Math.max(5, Math.ceil(seconds * 24 - 1e-4));
  return frames + ((((5 - frames) % 17) + 17) % 17);
}

// Mirrors orrery.comfy.shape: what the node's width, height and length outputs will carry.
function h3Canvas(ratio, megapixels) {
  const m = /^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/.exec(ratio || "");
  if ((!m || !Number(m[2])) && !megapixels) return null;
  const r = m && Number(m[2]) ? Number(m[1]) / Number(m[2]) : 1;
  const snap = (v) => Math.max(32, Math.round(v / 32) * 32);
  if (megapixels) return [snap(Math.sqrt(megapixels * 1e6 * r)), snap(Math.sqrt((megapixels * 1e6) / r))];
  let [w, h] = r >= 1 ? [768 * r, 768] : [768, 768 / r];
  if (w * h > 768 * 1344) { const s = Math.sqrt((768 * 1344) / (w * h)); w *= s; h *= s; }
  return [Math.max(32, Math.round(w / 32) * 32), Math.max(32, Math.round(h / 32) * 32)];
}

export function shape(raw) {
  const text = stripComments(raw);
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  // `: x8 seed=100 w832 h1216`, and their directives: `@batch 8`, `@seed 100`, `@size 832x1216`
  const params = lines.filter((l) => /^:\s*(x\d|seed=|w\d|h\d)/.test(l)).join(" ") + " "
    + lines.map((l) => /^@size\s+(\d+)\s*[x×*\s]\s*(\d+)\s*$/.exec(l)).filter(Boolean).map((m) => `w${m[1]} h${m[2]}`).join(" ");
  const cliDirectives = lines.filter((l) => /^@(seed|batch)\b/.test(l));
  const num = (re) => { const m = re.exec(params); return m ? Number(m[1]) : null; };
  const header = /^@h3\s+[\w-]+(.*)$/i.exec(lines[0] || "");
  const tokens = header ? header[1].split(/\s+/) : [];
  const mp = tokens.map((t) => /^(\d+(?:\.\d+)?)mp$/i.exec(t)).find(Boolean);
  const megapixels = mp ? Number(mp[1]) : null;
  const canvas = h3Canvas(tokens.find((t) => h3Canvas(t)), megapixels) || [1024, 1024];
  const seconds = lines.reduce((s, l) => { const m = /^SHOT\s+(\d+(?:\.\d+)?)\s*s\b/i.exec(l); return s + (m ? Number(m[1]) : 0); }, 0);
  const reel = header ? reelSecs(text) : null;
  const ctx = Number((/^context:\s*(\d+)/im.exec(text) || [0, 22])[1]);
  const lengths = reel && reel.secs.map((s, i) => (s ? h3Length(s + (reel.fresh[i] ? 0 : ctx / 24)) : 124));
  const length = lengths ? lengths[0] : seconds ? h3Length(seconds) : 124;
  const width = num(/\bw(\d+)/) ?? canvas[0], height = num(/\bh(\d+)/) ?? canvas[1];
  return {
    width, height, length, megapixels: megapixels ?? Math.round((width * height) / 1e3) / 1e3,
    cli: [...params.split(/\s+/).filter((w) => /^(x\d+|seed=\d+)$/.test(w)), ...cliDirectives],
    ...(lengths ? { lengths } : {}),
  };
}

// Dials: a template's bindings are its parameters. Mirrors orrery.dsl.bindings / override.
const BINDING_LINE = /^(\s*)\$([A-Za-z_]\w*)(\s*=\s*)(.+)$/;

export function dials(text) {
  const seen = new Set();  // a binding set in several chunks is one dial; override() turns them all
  return text.split("\n").map((l) => BINDING_LINE.exec(l)).filter((m) => m && !seen.has(m[2]) && seen.add(m[2])).map((m) => {
    const expr = m[4].trim(), lib = /^__([\w*]+(?:\/[\w*]+)*)(?:\[([^\[\]\n]+)\])?(?:#[\w-]+:\$?[\w.-]+)*(?::\d+)?__(?:\([^()]*\))?$/.exec(expr), brace = /^\{([^{}]*)\}$/.exec(expr);
    const range = brace && (/^\s*-?\d+(\.\d+)?\s*-\s*-?\d+(\.\d+)?\s*$/.test(brace[1])  // {0.4-0.9} rolls a number: no list
      || (/^\s*\d+(\.\d+)?%\s/.test(brace[1]) && splitOptions(brace[1]).length === 1));  // {30% …}: on or off
    const options = brace && !range && !brace[1].includes("$$") ? splitOptions(brace[1]).map((o) => o.replace(/:\d+(\.\d+)?$/, "").replace(/^\s*\d+(\.\d+)?::/, "").trim()).filter(Boolean) : [];
    return { name: m[2], expr, lib: lib ? lib[1] : null, tag: lib ? lib[2] || null : null, options };
  });
}

export function applyDials(text, values) {
  const set = Object.fromEntries(Object.entries(values || {}).map(([k, v]) => [k.replace(/^\$/, ""), String(v).trim()]).filter(([, v]) => v));
  return text.split("\n").map((l) => {
    const m = BINDING_LINE.exec(l);
    return m && set[m[2]] ? `${m[1]}$${m[2]}${m[3]}${set[m[2]]}` : l;
  }).join("\n");
}

// The Libraries list: what the language model wrote and waits for review first, then folders, then
// the rest. A folder is a real one (film/genre → film: genre) or, for flat names such as the
// built-ins, a shared prefix (couture_form, couture_house → couture: form, house). Each item carries
// its name without the folder.
export function libraryGroups(libs) {
  const review = libs.filter((l) => l.pending || (l.pending_entries || []).length);
  const rest = libs.filter((l) => !review.includes(l));
  const dir = (name) => (name.includes("/") ? name.slice(0, name.lastIndexOf("/")) : null);
  const prefix = (name) => name.split("_")[0];
  const counts = rest.filter((l) => !dir(l.name)).reduce((c, l) => ({ ...c, [prefix(l.name)]: (c[prefix(l.name)] || 0) + 1 }), {});
  const keyOf = (l) => dir(l.name) ?? (counts[prefix(l.name)] > 1 ? prefix(l.name) : "");
  const short = (l, key) => (key && l.name !== key ? l.name.slice(key.length + 1) : l.name);
  const byName = (a, b) => a.name.localeCompare(b.name);
  const keys = [...new Set(rest.map(keyOf))].sort((a, b) => (!a) - (!b) || a.localeCompare(b));
  return [
    ...(review.length ? [{ key: "review", items: [...review].sort(byName).map((l) => ({ lib: l, short: l.name })) }] : []),
    ...keys.map((k) => ({ key: k, items: rest.filter((l) => keyOf(l) === k).sort(byName).map((l) => ({ lib: l, short: short(l, k) })) })),
  ];
}

// Libraries tab: a big library (a folder of wildcards merged into one) shows a page at a time, and a
// search that is not the library's own name shows only the entries that match it.
export const LIB_PAGE = 200;

export function entryPage(entries, { name = "", query = "", tag = null, shown = LIB_PAGE } = {}) {
  const q = query.trim().toLowerCase();
  const rows = entries.map((e, i) => ({ e, i }))
    .filter(({ e }) => (!tag || e.tags.includes(tag)) && (!q || name.includes(q) || e.value.toLowerCase().includes(q)));
  return { rows: rows.slice(0, shown), total: rows.length };
}

// Generate: the output nodes downstream of the orrery node (only those are queued), and whether an
// Orrery Log is among them (then it logs to the galaxy itself). `nodes`: {id, type, output, targets}.
export function downstream(nodes, start) {
  const byId = new Map(nodes.map((n) => [n.id, n])), seen = new Set([start]), queue = [start], outputs = [];
  while (queue.length) {
    for (const t of byId.get(queue.shift())?.targets || []) {
      if (seen.has(t)) continue;
      seen.add(t); queue.push(t);
      if (byId.get(t)?.output) outputs.push(t);
    }
  }
  outputs.sort((a, b) => a - b);
  return { outputs, log: outputs.some((id) => byId.get(id)?.type === "OrreryLog") };
}

// The seed for the next run, as the seed's control after generate would step it.
export function nextSeed(seed, mode) {
  seed = Number(seed) || 0;
  if (mode === "increment") return seed + 1;
  if (mode === "decrement") return Math.max(0, seed - 1);
  if (mode === "randomize") return Math.floor(Math.random() * 2 ** 32);
  return seed;
}

// A sweep's queue loop: every run once per seed, the seed held within a seed's runs and stepped as its
// control says between seeds and once after the last run, as control after generate does after every
// queue, so the next Roll starts on a new seed. `live()` turns false when a newer Roll or Stop ends it.
export async function queueSweep({ count, seeds, mode, getSeed, setSeed, queue, live = () => true, progress = () => {} }) {
  let queued = 0;
  for (let s = 0; s < seeds && live(); s++) {
    if (s > 0) setSeed(nextSeed(getSeed(), mode));
    for (let i = 0; i < count && live(); i++) {
      await queue(i);
      progress(++queued);
    }
  }
  if (queued) setSeed(nextSeed(getSeed(), mode));
  return queued;
}

// What Generate queues is planned by the server (orrery.batch.plan, /orrery/plan): a LoRA sweep's runs
// times a grid's cells. It is asked only when the template may hold one: a LoRA tag with several
// strengths, a solo or test tag, or a grid.
export const PLAN_HINT = /<lora:[^<>]*[,;][^<>]*>|<lora:[^<>]*:(?:solo|test)\b|(?<![\w@<\\])@[\w./\\-]+\([^()<>]*[,;][^()<>]*\)|^\s*(?:@grid|:\s*grid)\b/m;

