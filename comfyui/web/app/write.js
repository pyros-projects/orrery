// The Write menu: the language model writes for the editor (the reel's next scene, the shot between two frames, a
// prompt from a picture). Each writer opens the 🎲 takes sheet (#334): N takes as the settings say, steered, one put
// in with Use selected; nothing in the menu waits for an input, the sheet says what came along. Write now writes a
// template's open libraries (#168).
import { inlineLibraries } from "../orrery-complete.js";
import { esc } from "./highlight.js";
import { openTakes, WRITERS } from "./takes.js";

export { WRITERS };

// The libraries a template still needs written: unknown ones, and `__name:N__` above what a library holds,
// as orrery.autolib finds them (the server applies the dials and @include when it writes them). `own`: @lib.
export function openLibraries(text, libraries, own = new Set()) {
  const counts = new Map(libraries.map((l) => [l.name, l.count]));
  const wanted = new Map();
  const src = text.split("\n").filter((l) => !/^\s*#/.test(l)).join("\n").replace(/<lora:[^<>]*>/g, "");
  for (const m of src.matchAll(/(?<!\\)__(\w+(?:\/\w+)*)(?:\[[^[\]\n]+\])?(?:#[\w-]+:\$?[\w.-]+)*(?::(\d+))?__/g)) {
    wanted.set(m[1], Math.max(wanted.get(m[1]) || 0, Number(m[2] || 0)));
  }
  return [...wanted].filter(([name, n]) => !own.has(name) && (!counts.has(name) || counts.get(name) < n)).map(([name]) => name);
}

export async function writeNow(app) {
  const open = openLibraries(app.text, app.data.completion?.libraries || [], new Set(inlineLibraries(app.text).map((l) => l.name)));
  if (app.state.writingNow || !open.length) return;
  app.state.writingNow = open.length;
  if (app.state.tab === "prompt") app.render();
  try {
    if (!app.llmApi()) {  // a text encoder: a run of its own per library, at the queue's front (#176)
      const notes = [];
      for (const name of open) {
        const got = await app.bridge.ask("library", name, "", { front: true });
        notes.push(...(got.error ? [`__${name}__: ${got.error}`] : got.notes || []));
        app.state.writingNow = Math.max(1, app.state.writingNow - 1);
        if (app.state.tab === "prompt") app.render();
      }
      await app.refreshCompletion();
      return app.toast(notes.length ? notes.map(esc).join("<br>") : "Nothing left to write: the libraries are there.",
        { label: "Review", run: () => app.go("libraries") });
    }
    const got = await app.api.writeLibraries({ template: app.text, params: app.bridge.getParams() });
    await app.refreshCompletion();
    app.toast(got.notes.length ? got.notes.map(esc).join("<br>") : "Nothing left to write: the libraries are there.",
      got.asked.length ? { label: "Review", run: () => app.go("libraries") } : undefined);
  } catch (err) { app.fail(err); } finally {
    app.state.writingNow = 0;
    if (app.state.tab === "prompt") app.render();
  }
}

// Why a writer cannot run now, or "": only without a language model (#334); the rest the sheet says.
export function writerBlock(app) {
  return app.llmActive() ? "" : "Needs a language model: pick one in the settings";
}

export function writeMenuHTML(app) {
  return `<div class="pop newpop" role="menu">${Object.entries(WRITERS).map(([k, w]) => {
    const why = writerBlock(app, k);
    return `<button role="menuitem" data-write="${k}" ${why ? "disabled" : ""}><b>${esc(w.label)}</b><span class="muted">${esc(why || w.hint)}</span></button>`;
  }).join("")}</div>`;
}

export function openWrite(app, task) {
  openTakes(app, { kind: task, what: "", directions: "" });
}
