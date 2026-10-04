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

// Two texts' lines as a diff, from `a` to `b`: [" ", line] in both, ["-", line] only in a, ["+", line] only in b.
export function lineDiff(a, b) {
  const x = a.split("\n"), y = b.split("\n"), n = x.length, m = y.length;
  const common = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
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

// What "Use this prompt" would change, the editor's scene now to the take's: changed lines with one line around
// them, the rest folded.
export function versionHTML(v) {
  const diff = v.now === null ? v.then.split("\n").map((l) => ["+", l]) : lineDiff(v.now, v.then);
  const near = diff.map((_, i) => diff.slice(Math.max(0, i - 1), i + 2).some(([k]) => k !== " "));
  let html = "";
  diff.forEach(([k, line], i) => {
    if (near[i]) html += `<span class="${k === "+" ? "add" : k === "-" ? "cut" : ""}">${k} ${esc(line) || " "}</span>`;
    else if (i === 0 || near[i - 1]) html += `<span class="fold">  …</span>`;
  });
  return `<div class="vcard"><b>Made with another prompt</b><span class="muted">${v.now === null
    ? "The editor has no such scene now. Use this prompt puts it back:" : "Use this prompt changes the scene in the editor:"}</span>`
    + `<pre>${html}</pre></div>`;
}

// The same for a title: the lines that change, `+` the take's and `-` the editor's now.
export function versionText(v) {
  const diff = v.now === null ? v.then.split("\n").map((l) => ["+", l]) : lineDiff(v.now, v.then);
  return diff.filter(([k]) => k !== " ").map(([k, line]) => `${k} ${line}`).join("\n");
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
