// The Write menu: the language model writes for the editor (the reel's next chunk, the shot between two
// frames, a prompt from a picture). Each idea is a short run of its own (Orrery Write), browsed in a
// sheet: ‹ › through the ideas so far, Another idea, Insert. A run writes once, so an idea that does not
// fit is shown with what is wrong with it, and the next one is a click away.
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";
import { stats } from "./model.js";

export const WRITERS = {
  continue: { label: "Continue the reel", hint: "The next scene, after the scenes as they roll at this seed", goes: "It is appended to the reel as its next scene." },
  story: { label: "Story between frames", hint: "The shot from the first frame to the last (fl2va)", goes: "It takes the place of the shots below the header." },
  describe: { label: "Prompt from image", hint: "A prompt for the picture in first_frame", goes: "It takes the place of the prompt; comments and `: …` lines stay." },
};

const WRITING = "The language model is writing. It loads first (a while the first time), and a run already in ComfyUI's queue goes before it.";

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
  try { got = await app.bridge.write(w.task, idea, w.sent); } catch (err) { got = { error: err?.message || String(err) }; }
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
    ${cur ? ideaHTML(app, cur) : `<div class="empty">${WRITING}</div>`}
    <p class="muted flush">${cur && w.pending ? `${WRITING} ` : ""}${esc(WRITERS[w.task].goes)} Insert makes it an unsaved edit.</p>
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
