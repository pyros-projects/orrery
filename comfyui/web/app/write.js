// The Write menu: the language model writes for the editor (the reel's next chunk, the shot between two
// frames, a prompt from a picture). Each idea is a short run of its own (Orrery Write), browsed in a
// sheet: ‹ › through the ideas so far, Another idea, Insert. A run writes once, so an idea that does not
// fit is shown with what is wrong with it, and the next one is a click away. With an API endpoint the
// server asks it directly, beside ComfyUI's queue (#167); and Write now writes a template's open libraries (#168).
import { inlineLibraries } from "../orrery-complete.js";
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";
import { stats } from "./model.js";

export const WRITERS = {
  continue: { label: "Continue the reel", hint: "The next scene, after the scenes as they roll at this seed", goes: "It is appended to the reel as its next scene." },
  story: { label: "Story between frames", hint: "The shot from the first frame to the last (fl2va)", goes: "It takes the place of the shots below the header." },
  describe: { label: "Prompt from image", hint: "A prompt for the picture in first_frame", goes: "It takes the place of the prompt; comments and `: …` lines stay." },
};

const WRITING = "The language model is writing. It loads first (a while the first time), and a run already in ComfyUI's queue goes before it.";
const WRITING_API = "The language model is writing, over the API, beside ComfyUI's queue.";

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

// One idea: over the API directly when the frames it needs are files ComfyUI holds (Load Image), else in a
// run of its own (Orrery Write), which computes the frames.
async function writeOne(app, task, idea, template) {
  if (app.llmApi()) {
    const files = task === "continue" ? { names: {} } : await app.bridge.frameFiles?.();
    if (files && !files.other) {
      return app.api.writeIdea({ task, idea, template, seed: Number(app.bridge.getSeed()) || 0, params: app.bridge.getParams(), frames: files.names });
    }
  }
  return app.bridge.write(task, idea, template);
}

// Why a writer cannot run on this node now, or "" when it can.
export function writerBlock(app, task) {
  if (!app.llmActive() && !app.bridge.wired("clip")) return "Needs a language model: pick one in the settings, or wire a text encoder into clip";
  const h3 = stats(app.text).h3, reel = h3?.reel, frames = app.bridge.frames();
  if (task === "continue") return !reel ? "Needs a reel: a screenplay with SCENE lines" : reel.clips === Infinity ? "The reel repeats a scene forever: there is no next scene" : "";
  if (reel) return "Writes one shot, so not for a reel";
  if (task === "story") return !h3 ? "Needs an @h3 screenplay (fl2va)" : frames.length < 2 ? "Wire the first and the last frame into first_frame and last_frame" : "";
  return frames.length ? "" : "Wire a picture into first_frame";
}

export function writeMenuHTML(app) {
  return `<div class="pop newpop" role="menu">${Object.entries(WRITERS).map(([k, w]) => {
    const why = writerBlock(app, k);
    return `<button role="menuitem" data-write="${k}" ${why ? "disabled" : ""}><b>${esc(w.label)}</b><span class="muted">${esc(why || w.hint)}</span></button>`;
  }).join("")}</div>`;
}

// The ideas stay while the template is the one they were written for: close the sheet, open it again.
export function openWrite(app, task) {
  const w = app.state.ideas;
  if (!w || w.task !== task || w.sent !== app.text) app.state.ideas = { task, sent: app.text, list: [], i: 0, next: 0, pending: false };
  showIdeas(app);
  if (!app.state.ideas.list.length && !app.state.ideas.pending) ask(app);
}

async function ask(app) {
  const w = app.state.ideas;
  w.pending = true;
  const idea = w.next++;
  showIdeas(app);
  let got;
  try { got = await writeOne(app, w.task, idea, w.sent); } catch (err) { got = { error: err?.message || String(err) }; }
  w.pending = false;
  if (app.state.ideas !== w) return;  // another writer or another template since
  w.list.push({ ...got, idea });
  w.i = w.list.length - 1;
  if (app.$(".sheet .ideas")) showIdeas(app);
  else app.toast(`${esc(WRITERS[w.task].label)}: an idea is ready`, { label: "Show", run: () => showIdeas(app) });
}

function ideaHTML(app, cur) {
  if (cur.error) return `<p class="warn bad flush">${esc(cur.error)}</p>${cur.raw ? `<pre class="codebox">${esc(cur.raw)}</pre>` : ""}`;
  return `${cur.problem ? `<p class="warn flush">${esc(cur.problem)}</p>` : ""}<pre class="codebox">${highlight(cur.text || "", app.known(), {})}</pre>`;
}

function showIdeas(app) {
  const w = app.state.ideas, cur = w.list[w.i], n = w.list.length;
  const html = `<div class="panel ideas"><div class="row spread"><h4>${esc(WRITERS[w.task].label)}</h4>
      ${n ? `<span class="row"><button class="icon-btn" data-wact="prev" aria-label="Previous idea" ${w.i > 0 ? "" : "disabled"}>‹</button>`
        + `<span class="muted">idea ${w.i + 1} of ${n}</span><button class="icon-btn" data-wact="next" aria-label="Next idea" ${w.i < n - 1 ? "" : "disabled"}>›</button></span>` : ""}</div>
    ${cur ? ideaHTML(app, cur) : `<div class="empty">${app.llmApi() ? WRITING_API : WRITING}</div>`}
    <p class="muted flush">${cur && w.pending ? `${app.llmApi() ? WRITING_API : WRITING} ` : ""}${esc(WRITERS[w.task].goes)} Insert makes it an unsaved edit.</p>
    <div class="acts"><button class="btn ghost" data-wact="close">Close</button>
      <button class="btn" data-wact="again" ${w.pending ? "disabled" : ""}>${icon("spark")}${w.pending ? "Writing…" : "Another idea"}</button>
      <button class="btn primary" data-wact="insert" ${cur?.template && !app.busy() ? "" : "disabled"}>${cur?.problem ? "Insert anyway" : "Insert"}</button></div></div>`;
  const sheet = app.$(".sheet .ideas") ? app.$(".sheet") : app.openSheet("");
  sheet.innerHTML = html;
  sheet.onclick = (e) => onClick(app, e);
}

function onClick(app, e) {
  const w = app.state.ideas, act = e.target.closest("[data-wact]")?.dataset.wact;
  if (!act || !w) return;
  if (act === "close") return app.closeSheet();
  if (act === "prev" || act === "next") {
    w.i = Math.max(0, Math.min(w.list.length - 1, w.i + (act === "next" ? 1 : -1)));
    return showIdeas(app);
  }
  if (act === "again") return ask(app);
  if (act === "insert") {
    const cur = w.list[w.i], prev = app.text;
    if (!cur?.template) return;
    app.text = cur.template;
    app.closeSheet();
    if (app.state.tab === "prompt") app.render();
    else app.go("prompt");
    app.toast(`Inserted the idea · an unsaved edit${cur.problem ? " with a problem: see the editor" : ""}`, {
      label: "Undo", run: () => { app.text = prev; if (app.state.tab === "prompt") app.render(); },
    });
  }
}
