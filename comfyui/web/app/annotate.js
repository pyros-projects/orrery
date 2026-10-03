// Annotations at line ends (#163): what a line gives at the node's seed, from /orrery/annotate. A binding
// shows what it rolled, an EXPORT what it keeps, a grid its cells, a CAST member where its pictures go.

const BINDING = /^\s*\$([A-Za-z_]\w*)\s*=\s*(.*)$/;
const EXPORT = /^\s*EXPORT:\s*(.*)$/;
const EXPORT_LINE = /^\s+(?:\$([A-Za-z_]\w*)|([A-Za-z_]\w*)\s*=)/;
const GRID = /^\s*(?:@grid\b|:\s*grid\b)/;
const MEMBER = /^\s*@?([A-Z][A-Z0-9 _-]*?)\s*(?:\([^)]*\))?\s*:\s*\S/;
const ENDS_CAST = /^\s*(?:SHOT|SCENE|CHUNK)\b/;

// line index → { text, kind: "note" }; `offset` is where `text` starts in the template (a cell's lines).
export function annotationLines(text, ann) {
  const out = new Map();
  if (!ann) return out;
  const put = (i, value) => { if (value) out.set(i, { text: value, kind: "note" }); };
  let block = false, cast = false;
  text.split("\n").forEach((line, i) => {
    if (block && EXPORT_LINE.test(line)) {
      const m = EXPORT_LINE.exec(line);
      return put(i, ann.exports?.[m[1] || m[2]] && `→ ${ann.exports[m[1] || m[2]]}`);
    }
    block = false;
    if (line.trim() === "CAST") { cast = true; return; }
    if (ENDS_CAST.test(line)) cast = false;
    let m;
    if ((m = EXPORT.exec(line))) {
      if (!m[1].trim()) { block = true; return; }
      const names = /^\s*([A-Za-z_]\w*)\s*=/.exec(m[1]) ? [/^\s*([A-Za-z_]\w*)/.exec(m[1])[1]]
        : [...m[1].matchAll(/\$([A-Za-z_]\w*)/g)].map((x) => x[1]);
      return put(i, names.map((n) => ann.exports?.[n]).filter(Boolean).map((v) => `→ ${v}`).join("  "));
    }
    if ((m = BINDING.exec(line))) {
      const value = ann.bindings?.[m[1]];
      return put(i, value && value.trim() !== m[2].trim() ? `= ${value}` : "");  // a plain text says itself
    }
    if (GRID.test(line)) return put(i, ann.grid && `→ ${ann.grid}`);
    if (cast && (m = MEMBER.exec(line)) && ann.cast?.[m[1].trim()]) return put(i, `→ ${ann.cast[m[1].trim()]}`);
  });
  return out;
}

// REMEMBER's hints win where a line has both; `lines` maps a cell's lines into the template's (offset).
export function mergeHints(first, second) {
  const out = new Map(second);
  for (const [i, h] of first) out.set(i, h);
  return out;
}
