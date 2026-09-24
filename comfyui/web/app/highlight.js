// Syntax colouring for orrery templates. Pure: returns HTML for a <pre> under the editor.

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const CLI_ONLY = "CLI only: in ComfyUI, use the Run count and the seed widget";
const HEAD = /^(\s*)(SHOT\s+[\d.]+\s*s\b|SFX:|MUSIC:|style:|summary:|voice:|keep:|context:|CHUNK(?=\s|$)|CAST(?=\s*$)|[A-Z][A-Z0-9 _-]*?(?:\s*\([^)]*\))?\s*:(?=\s))/;
const TOKEN = /(__(\w+(?:\/\w+)*)(?:\[[\w-]+\])?(?::\d+)?__(?:\([^()]*\))?)|(\$[A-Za-z_]\w*(?:~\d+)?)|(\d+(?:-\d+)?\$\$)|([{}|])|([^_${}|]+|[_$])/g;

const TO_MAKE = "Not a library yet: the language model creates it when the node runs";

function line(text, known, llm) {
  if (/^\s*@h3\b/.test(text)) return `<span class="t-head">${esc(text)}</span>`;
  if (/^\s*>/.test(text)) return `<span class="t-enh">${esc(text)}</span>`;
  if (/^\s*:\s*(x\d|seed=|w\d|h\d)/.test(text)) {
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
  // <lora:…> tags are opaque (file names may contain __), like orrery's expander treats them
  return out + rest.split(/(<lora:[^<>]*>)/).map((part, i) => (i % 2 ? `<span class="t-lora">${esc(part)}</span>`
    : part.replace(TOKEN, (m, lib, name, v, multi, brace) => {
      if (lib) return known.has(name) ? `<span class="t-lib">${esc(lib)}</span>`
        : llm ? `<span class="t-lib t-new" title="${TO_MAKE}">${esc(lib)}</span>` : `<span class="t-lib t-miss">${esc(lib)}</span>`;
      if (v) return `<span class="t-var">${esc(v)}</span>`;
      if (multi || brace) return `<span class="t-brace">${esc(m)}</span>`;
      return esc(m);
    }))).join("");
}

// options.llm: a language model is set, so unknown libraries are to be made, not missing
export function highlight(src, known, { llm = false } = {}) {
  return src.split("\n").map((l) => line(l, known, llm)).join("\n");
}
