// Syntax colouring for orrery templates. Pure: returns HTML for a <pre> under the editor.

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const CLI_ONLY = "CLI only: in ComfyUI, use the Run count and the seed widget";
const HEAD = /^(\s*)(SHOT\s+[\d.]+\s*s\b:?|SFX:|MUSIC:|style:|summary:|voice:|keep:|context:|CHUNK(?=\s|$)|CAST(?=\s*$)|[A-Z][A-Z0-9 _-]*?(?:\s*\([^)]*\))?\s*:(?=\s))/;
const TOKEN = /(\\[{}|$_@#[\]\\<>])|((?<!\\)__(\w+(?:\/\w+)*)(?:\[[\w,|!-]+\])?(?:#[\w-]+:\$?[\w.-]+)*(?::\d+)?__(?:\([^()]*\))?)|(\$[A-Za-z_]\w*(?:~\d+)?(?:\.[A-Za-z_][\w-]*)?)|(\d+(?:-\d+)?\$\$)|([{}|])|([^_${}|]+|[_$])/g;

const TO_MAKE = "Not a library yet: the language model creates it when the node runs";

function line(text, known, llm) {
  if (/^\s*#/.test(text)) return `<span class="t-comment">${esc(text)}</span>`;
  if (/^\s*@h3\b/.test(text)) return `<span class="t-head">${esc(text)}</span>`;
  if (/^\s*>/.test(text)) return `<span class="t-enh">${esc(text)}</span>`;
  if (/^\s*:\s*(x\d|seed=|w\d|h\d|grid\b|unique=)/.test(text)) {
    return text.replace(/(\S+)|(\s+)/g, (m, word) => {
      if (!word) return m;
      if (/^(x\d+|seed=\d+)$/.test(word)) return `<span class="t-cli" title="${CLI_ONLY}">${esc(word)}</span>`;
      return `<span class="t-param">${esc(word)}</span>`;
    });
  }
  let out = "";
  let rest = text;
  const head = text.match(HEAD);
  if (head) {
    out = esc(head[1]) + `<span class="t-kw">${esc(head[2])}</span>`;
    rest = text.slice(head[0].length);
  }
  // <lora:…> tags and their @name(0.8) short form are opaque (file names may contain __), as orrery's expander treats them
  return out + rest.split(/((?<!\\)<lora:[^<>]*>|(?<![\w@<\\])@[\w./\\-]+\([^()<>]*\))/).map((part, i) => (i % 2 ? `<span class="t-lora">${esc(part)}</span>`
    : part.replace(TOKEN, (m, escaped, lib, name, v, multi, brace) => {
      if (escaped) return `<span class="t-esc" title="Written as it is: the backslash keeps it from being syntax">${esc(m)}</span>`;
      if (lib) return known.has(name) ? `<span class="t-lib">${esc(lib)}</span>`
        : llm ? `<span class="t-lib t-new" title="${TO_MAKE}">${esc(lib)}</span>` : `<span class="t-lib t-miss">${esc(lib)}</span>`;
      if (v) return `<span class="t-var">${esc(v)}</span>`;
      if (multi || brace) return `<span class="t-brace">${esc(m)}</span>`;
      return esc(m);
    }))).join("");
}

// The divider on a CHUNK line: absolutely placed, so the text keeps its place under the textarea's caret;
// first in the line, so its static top is the line's top.
function chunkLine(html, c, segment) {
  const now = segment !== null && c.first !== null && segment >= c.first && segment <= c.last;
  const turn = now && c.repeat > 1 ? ` ${segment - c.first + 1}/${c.repeat === Infinity ? "∞" : c.repeat}` : "";
  const label = `${now ? `▶ next${turn} · ` : ""}${c.label}`;
  return `<span class="chunkline${now ? " now" : ""}"><span class="chunkinfo"><span>${esc(label)}</span></span>${html}</span>`;
}

// options.llm: a language model is set, so unknown libraries are to be made, not missing.
// options.chunks (model.chunkInfo): CHUNK lines get dividers; the one playing options.segment is marked.
export function highlight(src, known, { llm = false, chunks = null, segment = null } = {}) {
  const at = new Map((chunks || []).map((c) => [c.line, c]));
  return src.split("\n").map((l, i) => (at.has(i) ? chunkLine(line(l, known, llm), at.get(i), segment) : line(l, known, llm))).join("\n");
}
