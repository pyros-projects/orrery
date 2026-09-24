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

export function stats(text) {
  const libs = [...text.matchAll(/__(\w+)(?:\[[\w-]+\])?__/g)];
  const rolls = (text.match(/\{/g) || []).length + libs.length;
  const binds = (text.match(/^\s*\$\w+\s*=/gm) || []).length;
  let h3 = null;
  if (/^\s*@h3/.test(text)) {
    const shots = [...text.matchAll(/^\s*SHOT\s+([\d.]+)\s*s/gm)];
    const voices = new Set([...text.matchAll(/^\s*([A-Z][A-Z0-9 _-]*?)\s*(?:\([^)]*\))?\s*:\s/gm)]
      .map((m) => m[1]).filter((n) => !["SFX", "MUSIC", "SHOT"].includes(n)));
    h3 = { shots: shots.length, secs: shots.reduce((s, m) => s + Number(m[1]), 0), voices: voices.size };
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

export function filterRows(rows, { scope = "all", hash, presetHash, rating, pick }) {
  let out = rows;
  if (scope === "prompt") out = out.filter((r) => r.template === hash);
  if (scope === "preset") out = out.filter((r) => presetHash && r.template === presetHash);
  if (rating === "unrated") out = out.filter((r) => !r.rating);
  else if (rating) out = out.filter((r) => r.rating === rating);
  if (pick) out = out.filter((r) => r.picks.some((p) => p.keys.includes(pick)));
  return out;
}

// Mirrors orrery.comfy.shape: what the node's width, height and length outputs will carry.
function h3Canvas(ratio) {
  const m = /^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/.exec(ratio || "");
  if (!m || !Number(m[2])) return null;
  const r = Number(m[1]) / Number(m[2]);
  let [w, h] = r >= 1 ? [768 * r, 768] : [768, 768 / r];
  if (w * h > 768 * 1344) { const s = Math.sqrt((768 * 1344) / (w * h)); w *= s; h *= s; }
  return [Math.max(32, Math.round(w / 32) * 32), Math.max(32, Math.round(h / 32) * 32)];
}

export function shape(text) {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const params = lines.filter((l) => /^:\s*(x\d|seed=|w\d|h\d)/.test(l)).join(" ");
  const num = (re) => { const m = re.exec(params); return m ? Number(m[1]) : null; };
  const header = /^@h3\s+\w+(?:\s+(\S+))?/i.exec(lines[0] || "");
  const canvas = (header && h3Canvas(header[1])) || [1024, 1024];
  const seconds = lines.reduce((s, l) => { const m = /^SHOT\s+(\d+(?:\.\d+)?)\s*s\b/i.exec(l); return s + (m ? Number(m[1]) : 0); }, 0);
  let length = 124;
  if (seconds) { length = Math.max(5, Math.ceil(seconds * 24 - 1e-9)); length += (((5 - length) % 17) + 17) % 17; }
  return {
    width: num(/\bw(\d+)/) ?? canvas[0], height: num(/\bh(\d+)/) ?? canvas[1], length,
    cli: params.split(/\s+/).filter((w) => /^(x\d+|seed=\d+)$/.test(w)),
  };
}
