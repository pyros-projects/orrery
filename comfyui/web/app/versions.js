// A take made with another version of its scene (#242): the template it was made with, by its hash, read against
// the editor's text now. Switching takes never changes the editor; "Use this prompt" brings a take's scene back.
import { esc } from "./highlight.js";
import { splitCells, stripComments } from "./model.js";

// The templates behind the takes' hashes, each fetched once: a hash's text never changes. One the home has lost
// stays null, and its takes unmarked.
export async function fetchTemplates(app, takes) {
  const known = (app.data.templates ??= new Map());
  const wanted = [...new Set(takes.map((t) => t.template).filter((h) => h && !known.has(h)))];
  await Promise.all(wanted.map(async (h) => {
    try { known.set(h, (await app.api.template(h)).text); } catch { known.set(h, null); }
  }));
}

const heading = (cell) => cell.text.split("\n")[0].trim();

// A scene of a template: the one at its place, unless another is the only one with its heading.
export function sceneIn(text, scene, head = null) {
  const cells = splitCells(text).filter((c) => c.chunk >= 0), at = cells[scene];
  if (at && (head === null || heading(at) === head)) return at;
  const named = cells.filter((c) => heading(c) === head);
  return named.length === 1 ? named[0] : at ?? null;
}

const plain = (text) => stripComments(text).split("\n").map((l) => l.trim()).filter(Boolean).join("\n");

// The scene a take was made with where it reads otherwise than the editor's now (comments and blank lines are no
// change): {scene, then, now, at}, `now` and `at` null when the editor has no such scene. Else null.
export function versionOf(app, take) {
  const old = take.template && app.data.templates?.get(take.template);
  const then = old && take.scene != null ? sceneIn(old, take.scene) : null;
  if (!then) return null;
  const now = sceneIn(app.text, take.scene, heading(then));
  if (now && plain(now.text) === plain(then.text)) return null;
  return { scene: take.scene, then: then.text.replace(/\s+$/, ""), now: now ? now.text.replace(/\s+$/, "") : null, at: now?.chunk ?? null };
}

// Two lists as a diff, from `x` to `y`: [" ", item] in both, ["-", item] only in x, ["+", item] only in y.
function diff(x, y) {
  const n = x.length, m = y.length, common = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) common[i][j] = x[i] === y[j] ? common[i + 1][j + 1] + 1 : Math.max(common[i + 1][j], common[i][j + 1]);
  }
  const out = [];
  for (let i = 0, j = 0; i < n || j < m;) {
    if (i < n && j < m && x[i] === y[j]) out.push([" ", x[i++]]), j++;
    else if (i < n && (j === m || common[i + 1][j] >= common[i][j + 1])) out.push(["-", x[i++]]);
    else out.push(["+", y[j++]]);
  }
  return out;
}

// Two texts' lines as a diff, from `a` to `b`.
export const lineDiff = (a, b) => diff(a.split("\n"), b.split("\n"));

// A changed line and the one it became, their differing words marked: [a's html, b's html].
export function wordMarks(a, b) {
  const words = diff(a.split(/(\s+)/), b.split(/(\s+)/));
  const side = (k) => words.filter(([w]) => w === " " || w === k).map(([w, t]) => (w === k && t.trim() ? `<mark>${esc(t)}</mark>` : esc(t))).join("");
  return [side("-"), side("+")];
}

// How alike two lines are: the share of their words they have in common, in order.
function likeness(a, b) {
  const x = a.split(/\s+/).filter(Boolean), y = b.split(/\s+/).filter(Boolean);
  return diff(x, y).filter(([k]) => k === " ").length / Math.max(x.length, y.length, 1);
}

// What "Use this prompt" would change, the editor's scene now to the take's: changed lines with one line around
// them, the rest folded; a line changed in place has its changed words marked.
export function versionHTML(v) {
  const lines = v.now === null ? v.then.split("\n").map((l) => ["+", l]) : lineDiff(v.now, v.then);
  const html = lines.map(([k, line]) => [k, esc(line)]);
  for (let i = 0; i < lines.length;) {  // a run of cut lines and the added ones after it: each added line and the cut one most like it
    if (lines[i][0] !== "-") { i++; continue; }
    let cut = i;
    while (cut < lines.length && lines[cut][0] === "-") cut++;
    let add = cut;
    while (add < lines.length && lines[add][0] === "+") add++;
    const free = new Set(Array.from({ length: cut - i }, (_, k) => i + k));
    for (let a = cut; a < add; a++) {
      const [best, score] = [...free].map((c) => [c, likeness(lines[c][1], lines[a][1])]).sort((x, y) => y[1] - x[1])[0] ?? [];
      if (score >= 0.4) { free.delete(best); [html[best][1], html[a][1]] = wordMarks(lines[best][1], lines[a][1]); }
    }
    i = add;
  }
  const near = lines.map((_, i) => lines.slice(Math.max(0, i - 1), i + 2).some(([k]) => k !== " "));
  let body = "";
  html.forEach(([k, line], i) => {
    if (near[i]) body += `<span class="${k === "+" ? "add" : k === "-" ? "cut" : "same"}"><i>${k === "-" ? "−" : k}</i><span>${line || " "}</span></span>`;
    else if (i === 0 || near[i - 1]) body += `<span class="fold"><i></i><span>⋯</span></span>`;
  });
  const head = esc(v.then.split("\n")[0].trim());
  return `<div class="vcard"><div class="vhead"><b>✎ Made with another prompt</b><span>${head}</span></div>`
    + `<pre>${body}</pre><div class="vfoot"><span class="cut"><i>−</i>the editor now</span><span class="add"><i>+</i>this take's</span>`
    + `<span class="muted">${v.now === null ? "the editor lost this scene · ✎ puts it back" : "✎ on the take puts it in the editor"}</span></div></div>`;
}

// The same for a title: the lines that change, `+` the take's and `-` the editor's now.
export function versionText(v) {
  const lines = v.now === null ? v.then.split("\n").map((l) => ["+", l]) : lineDiff(v.now, v.then);
  return lines.filter(([k]) => k !== " ").map(([k, line]) => `${k} ${line}`).join("\n");
}

// The take's scene into the editor, in place of the scene now, or at the end when the editor has fewer scenes.
export function useVersion(app, v) {
  const prev = app.text, cells = splitCells(prev), k = cells.findIndex((c) => c.chunk === v.at);
  if (v.at !== null && k >= 0) cells[k] = { ...cells[k], text: v.then + cells[k].text.match(/\n*$/)[0] };
  app.text = k >= 0 ? cells.map((c) => c.text).join("\n") : `${prev.replace(/\s+$/, "")}\n\n${v.then}`;
  app.cellsSig = null;
  if (app.state.tab === "prompt") app.render();
  app.toast(`The take's prompt for scene ${v.scene + 1} is in the editor · an unsaved edit`, {
    label: "Undo", run: () => { app.text = prev; app.cellsSig = null; if (app.state.tab === "prompt") app.render(); },
  });
}
