// Syntax colouring for orrery templates. Pure: returns HTML for a <pre> under the editor.

import { castNames } from "../orrery-complete.js";

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const CLI_ONLY = "CLI only: in ComfyUI, use the Run count and the seed widget";
// a line's head: the screenplay words (the earlier CHUNK, HANDOFF:, GOTO:, SEND: too), IF before a
// condition, and a name with a colon (a CAST member, a speaker), `@` before it or not
const HEAD = /^(\s*)(SHOT\s+[\d.]+\s*s\b:?|EXPORT:|SFX:|MUSIC:|LORA:|END ON:|START WITH:|REMEMBER:|CUT TO:|AFTER:|HANDOFF:|SEND:|GOTO:|SET:|style:|summary:|voice:|keep:|context:|refmods:|(?:SCENE|CHUNK)(?=\s|$)|IF(?=\s+\$)|CAST(?=\s*$)|@?[A-Z][A-Z0-9 _-]*?(?:\s*\([^)]*\))?\s*:(?=\s))/;
const TOKEN = /(\\[{}|$_@#[\]\\<>])|((?<!\\)__([\w*]+(?:\/[\w*]+)*)(?:\[[^\[\]\n]+\])?(?:#[\w-]+:\$?[\w.-]+)*(?::\d+)?__(?:\([^()]*\))?)|(\$[A-Za-z_]\w*(?:~\d+)?(?:\.[A-Za-z_][\w-]*)?)|(\d+(?:-\d+)?\$\$)|([{}|])|([^_${}|]+|[_$])/g;

// A glob (`clothing/*`, `clothing/**`) is known when it matches a library.
function isKnown(name, known) {
  if (!name.includes("*")) return known.has(name);
  const part = (p) => (p === "**" ? ".+" : p.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/]*"));
  const rx = new RegExp(`^${name.split("/").map(part).join("/")}$`);
  return [...known].some((n) => rx.test(n));
}

const TO_MAKE = "Not a library yet: the language model creates it when the node runs";

// The members of the CAST, `@` before them or not, as a pattern (null without a CAST).
const memberPattern = (names) => (names.length
  ? new RegExp(`(?<![\\w@])@?(?:${[...names].sort((a, b) => b.length - a.length).map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?![\\w-])`, "g")
  : null);
const brass = (html, members) => (members ? html.replace(members, (m) => `<span class="t-cast">${m}</span>`) : html);

function line(text, known, llm, members) {
  if (/^\s*#/.test(text)) return `<span class="t-comment">${esc(text)}</span>`;
  if (/^\s*@h3\b/.test(text)) return `<span class="t-head">${esc(text)}</span>`;
  if (/^\s*>/.test(text)) return `<span class="t-enh">${esc(text)}</span>`;
  if (/^\s*@(seed|batch)\b/.test(text)) return `<span class="t-cli" title="${CLI_ONLY}">${esc(text)}</span>`;
  if (/^\s*(:\s*(x\d|seed=|w\d|h\d|grid\b|unique=)|@(grid|unique|size|seed|batch|rng)\b)/.test(text)) {
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
    const name = /^@?([A-Z][A-Z0-9 _-]*?)\s*(?:\(|:)/.exec(head[2]);
    const member = members && name && new RegExp(`^${members.source}$`).test(`${name[1]}`);
    out = esc(head[1]) + (member ? `<span class="t-kw">${brass(esc(head[2]), members)}</span>` : `<span class="t-kw">${esc(head[2])}</span>`);
    rest = text.slice(head[0].length);
  }
  // <lora:…> tags and their @name(0.8) short form are opaque (file names may contain __), as orrery's expander treats them
  const lora = (part) => (members && new RegExp(`^${members.source}\\(`).test(part) ? brass(esc(part), members)  // SET: @JINX(0.6)
    : `<span class="t-lora">${esc(part)}</span>`);
  return out + rest.split(/((?<!\\)<lora:[^<>]*>|(?<![\w@<\\])@[\w./\\-]+\([^()<>]*\))/).map((part, i) => (i % 2 ? lora(part)
    : part.replace(TOKEN, (m, escaped, lib, name, v, multi, brace) => {
      if (escaped) return `<span class="t-esc" title="Written as it is: the backslash keeps it from being syntax">${esc(m)}</span>`;
      if (lib) return isKnown(name, known) ? `<span class="t-lib">${esc(lib)}</span>`
        : llm ? `<span class="t-lib t-new" title="${TO_MAKE}">${esc(lib)}</span>` : `<span class="t-lib t-miss">${esc(lib)}</span>`;
      if (v) return `<span class="t-var">${esc(v)}</span>`;
      if (multi || brace) return `<span class="t-brace">${esc(m)}</span>`;
      return brass(esc(m), members);
    }))).join("");
}

// The divider on a SCENE line: absolutely placed, so the text keeps its place under the textarea's caret;
// first in the line, so its static top is the line's top.
function chunkLine(html, c, segment) {
  const now = segment !== null && (c.segs ? c.segs.includes(segment) : c.first !== null && segment >= c.first && segment <= c.last);
  const turn = !now ? "" : c.segs ? (c.segs.length > 1 ? ` ${c.segs.indexOf(segment) + 1}/${c.segs.length}${c.endless ? "+" : ""}` : "")
    : c.repeat > 1 ? ` ${segment - c.first + 1}/${c.repeat === Infinity ? "∞" : c.repeat}` : "";
  const label = `${now ? `▶ next${turn} · ` : ""}${c.label}`;
  return `<span class="chunkline${now ? " now" : ""}"><span class="chunkinfo"><span>${esc(label)}</span></span>${html}</span>`;
}

// options.llm: a language model is set, so unknown libraries are to be made, not missing.
// options.chunks (model.chunkInfo): SCENE lines get dividers; the one playing options.segment is marked.
// options.cast: the CAST's names, in brass (a cell passes the whole template's); else read from src.
// `hints`: line index → { text, replaced } drawn after the line (REMEMBER: lines say where their frames go);
// a hint takes no room, so the text wraps exactly as the textarea's.
export function highlight(src, known, { llm = false, chunks = null, segment = null, cast = null, hints = null } = {}) {
  const at = new Map((chunks || []).map((c) => [c.line, c]));
  const members = memberPattern(cast ?? castNames(src));
  const hint = (i) => (hints?.has(i) ? `<span class="hint${hints.get(i).replaced ? " replaced" : ""}${hints.get(i).kind ? ` ${hints.get(i).kind}` : ""}"><span>${esc(hints.get(i).text)}</span></span>` : "");
  return src.split("\n").map((l, i) => (at.has(i) ? chunkLine(line(l, known, llm, members), at.get(i), segment)
    : line(l, known, llm, members)) + hint(i)).join("\n");
}
