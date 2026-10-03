// Prompt tab: preset bar, the highlighted editor with completion, dials, and a way into Test.
import { KEYWORDS, inlineLibraries, suggest } from "../orrery-complete.js";
import { chosen, closeMenu, drawMenu, joinChoices } from "./dialmenu.js";
import { esc, highlight } from "./highlight.js";
import { annotationLines, mergeHints } from "./annotate.js";
import { wireHover } from "./hover.js";
import { hintsFor } from "./remember.js";
import { icon } from "./icons.js";
import { applyDials, chunkInfo, dials, hasGoto, plays, folderColor, pickerGroups, shape, stats, stripComments, PLAN_HINT, matches, templateHash } from "./model.js";
import { thumbHTML } from "./parts.js";
import { openSave } from "./save.js";
import { STARTERS } from "./starters.js";
import { runRolls } from "./test.js";
import { caretPoint, cellStart, inCell, jumpCell, paintCells, renderCells, wireCells } from "./cells.js";
import { layoutTimeline, loadChain, scrollTimeline, wireTimeline } from "./timeline.js";
import { openWrite, writeMenuHTML } from "./write.js";

function statsHTML(app) {
  const st = stats(app.text), out = shape(app.text), plan = planOf(app), planned = planData(app);
  // with GOTO lines the clips are the walked path's (all of it when it ends, else on and on)
  const walked = st.h3?.reel && hasGoto(app.text) ? app.reelPath() : null;
  const reel = !st.h3?.reel ? null : !hasGoto(app.text) ? st.h3.reel
    : { ...st.h3.reel, clips: walked ? (walked.ended ? walked.path.length : Infinity) : NaN, goto: true };
  const wired = /^\s*(:\s*.*\b[wh]\d|@size\b)/m.test(app.text) ? [] : app.bridge.frames?.() || [];  // `@size` wins
  const outs = (app.data.rows || []).filter((r) => r.template === templateHash(app.text)).length;
  const forever = reel && reel.clips === Infinity, clips = !reel ? "" : forever ? "∞" : Number.isNaN(reel.clips) ? "?" : reel.clips;
  const how = !reel ? "" : "Wire the picks into Orrery Continue (and the clip into Orrery Film). The segment widget counts up by itself (increment): "
    + (forever ? "Run (Instant) plays clip after clip until you stop it." : `a Run count of ${clips} plays the whole reel${reel.goto ? " at this seed (its GOTO lines may jump on what rolls)" : ""}; after the last clip nothing downstream runs.`);
  const timing = reel
    ? `<span class="stat" title="${esc(how)}"><b>Reel</b> · ${reel.secs.map((s, i) => `<b>${s.toFixed(1)} s</b>${reel.repeats[i] === 1 ? "" : ` ×${reel.repeats[i] === Infinity ? "∞" : reel.repeats[i]}`}`).join(" + ")}${reel.goto ? " · GOTO" : ""} · <b>${clips}</b> clip${reel.clips === 1 ? "" : "s"}</span>`
    : st.h3 ? `<span class="stat"><b>H3</b> · ${st.h3.shots} shot${st.h3.shots === 1 ? "" : "s"} · <b>${st.h3.secs.toFixed(1)} s</b> · ${st.h3.voices} voice${st.h3.voices === 1 ? "" : "s"}</span>` : "";
  const frames = reel ? ` · <b>${out.lengths.join(" / ")}</b> frames per scene` : st.h3 ? ` · <b>${out.length}</b> frames = ${(out.length / 24).toFixed(2)} s` : "";
  return timing
    + `<span class="stat"><b>${st.rolls}</b> rolls · <b>${st.libs}</b> libraries · <b>${st.binds}</b> bindings${setDials(app) ? ` · <b>${setDials(app)}</b> dialed` : ""}</span>`
    + `${app.llmActive() ? `<span class="stat" title="Unknown __libraries__ and __name:N__ are made by this model when the node runs">LLM <b>${esc(app.data.llm.file.replace(/\.[a-z]+$/, ""))}</b></span>` : ""}`
    + (wired.length
      ? `<span class="stat" title="Width and height take the shape of the ${wired[0].replace("_", " ")} wired into the node, at the header's megapixels or H3's canvas area, so H3 does not stretch or crop it; the size is known when the node runs">→ size from the <b>${wired[0].replace("_", " ")}</b>${headerMP(app.text) ? ` · ${out.megapixels} MP` : ""}${frames}</span>`
      : `<span class="stat" title="The node's width, height, length and megapixels outputs${reel ? "; from the second clip on, length includes the 22 frames the clip continues from" : ""}">→ <b>${out.width}×${out.height}</b> · ${out.megapixels} MP${frames}</span>`)
    + (planned?.error ? `<span class="stat warn" title="${esc(planned.error)}">${esc(planned.error)}</span>` : "")
    + `${out.cli.length ? `<span class="stat cli" title="In ComfyUI, use the Run count and the seed widget">${esc(out.cli.join(" "))}: CLI only</span>` : ""}<span class="grow"></span>`
    + `${outs ? `<button class="btn ghost" data-act="outputs">${icon("image")}${outs} output${outs === 1 ? "" : "s"}</button>` : ""}`
    + `<button class="btn" data-act="test" title="Roll it in the Test tab: a few seeds, or a reel's clips">${icon("dice")}Test</button>`
    + (reel ? (app.run
      ? `<span class="stat live" title="The clip of the reel this node is rendering now (its segment widget counts from 0)">Rolling clip <b>${Number(app.run.segment) + 1}</b></span>`
      : `<span class="stat" title="The clip Roll plays next: the node's segment widget, which counts from 0">Next clip <b>${Number(app.bridge.getSegment()) + 1}</b></span>`)
      + `<button class="btn ghost" data-act="jump" title="Scroll the editor to the scene that plays the next clip">${icon("jump")}Jump</button>`
      + (app.data.timeline === false ? "" : `<button class="btn ghost" data-act="tlview" aria-pressed="${cellsView(app)}" title="${cellsView(app)
        ? "Clips under each scene: show them in a column beside the editor instead" : "Clips in a column beside the editor: show them under each scene instead"}">${icon("film")}${cellsView(app) ? "Clips below" : "Clips beside"}</button>`)
      + `<button class="btn" data-act="restart" title="Cancel this node's queued and running clips, set segment to 0 and generate from the start">${icon("undo")}Restart</button>` : "")
    + (app.state.sweepQueue
      ? `<button class="btn primary" data-act="stopsweep" title="Stop queueing the sweep; what is queued already still runs">${icon("x")}Stop<small class="sweep">${app.state.sweepQueue.done}/${app.state.sweepQueue.total} queued</small></button>`
      : plan
      ? `<button class="btn primary" data-act="generate" title="The sweep: every LoRA strength (solo LoRAs in turn) and every cell of the grid, one seed per sweep; the outputs go to a gallery folder of their own">${icon("play")}Roll ×${plan.runs * repeats(app)}<small class="sweep">sweep ${esc(plan.formula)}</small></button>`
        + `<label class="rep" title="How many seeds: each runs the whole sweep, the seed stepping between them and after the last as its control after generate says">next<input type="number" min="1" max="999" value="${repeats(app)}" data-rep aria-label="Seeds per sweep">${plural(repeats(app), "seed")}</label>`
      : `<button class="btn primary" data-act="generate" title="Queue only what this node feeds, up to its Save nodes; their files go to the gallery">${icon("play")}Roll</button>`
        + `<label class="rep" title="How many runs Roll queues, one after another; seed and segment step between them as their control after generate says, so a reel plays that many clips">next<input type="number" min="1" max="999" value="${repeats(app)}" data-rep aria-label="Runs per Roll">${plural(repeats(app), reel ? "clip" : st.h3 ? "video" : "image")}</label>`);
}

// What Roll's number counts: "next 1 clip", "next 3 clips".
const plural = (n, noun) => (n === 1 ? noun : `${noun}s`);

// The cells view: each chunk its own cell with its clips under it (a reel, the timeline on, chosen in the footer).
// The clips under each scene unless the node was set to beside them (Pyro, 3 October: the default).
const cellsView = (app) => app.data.timeline !== false && app.bridge.props.orrery_tl_view !== "beside" && !!app.chunks();

// `0.6MP` in the @h3 line: the area a frame-shaped clip gets.
const headerMP = (text) => /^\s*@h3\b[^\n]*\s\d+(?:\.\d+)?mp\b/im.test(stripComments(text));

// Runs per Roll, kept in the node's properties so the workflow remembers it.
const repeats = (app) => Math.min(999, Math.max(1, Math.floor(Number(app.bridge.props.repeat) || 1)));

function chipHTML(app) {
  const card = app.preset && app.card(app.preset), d = app.dirty();
  const head = card
    ? `<span class="fold" style="--c:${folderColor(card.folder)}">${esc(card.folder || "mine")}</span><span class="ptitle">${esc(card.title)}</span>`
      + `${card.builtin ? `<span class="muted flex" title="Built-in, read-only">${icon("lock")}</span>` : ""}`
    : app.preset ? `<span class="ptitle">@${esc(app.preset)}</span><span class="warn">missing</span>` : '<span class="ptitle">Untitled prompt</span>';
  return `${head}${d ? `<span class="dirty">${card ? "edited" : "unsaved"}</span>` : ""}<span class="caret">${icon("chev")}</span>`;
}

export function renderPrompt(app) {
  const card = app.preset && app.card(app.preset);
  const d = app.dirty();
  app.view.innerHTML = `
    <div class="pbar">
      <button class="pchip" data-act="pick" aria-haspopup="listbox" aria-expanded="${app.state.pick}">${chipHTML(app)}</button>
      <button class="icon-btn" data-act="revert" title="Revert to the saved preset" ${card && d ? "" : "disabled"}>${icon("undo")}</button>
      <button class="btn" data-act="save" ${card && (d || setDials(app)) ? "" : "disabled"}>${icon("save")}${card?.builtin ? "Save a copy" : "Save"}</button>
      <button class="btn primary" data-act="saveas">Save as…</button>
      <button class="btn" data-act="new" aria-haspopup="menu" aria-expanded="${!!app.state.newMenu}">${icon("plus")}New</button>
      <button class="btn" data-act="write" aria-haspopup="menu" aria-expanded="${!!app.state.writeMenu}" title="The language model writes: the reel's next scene, the shot between two frames, a prompt from a picture">${icon("spark")}Write</button>
      ${app.state.newMenu ? `<div class="pop newpop" role="menu">${Object.entries(STARTERS).map(([k, s]) => `<button role="menuitem" data-new="${k}"><b>${esc(s.label)}</b><span class="muted">${esc(s.hint)}</span></button>`).join("")}</div>` : ""}
      ${app.state.writeMenu ? writeMenuHTML(app) : ""}
    </div>
    ${card?.note ? `<p class="pnote"><b>${esc(card.title)}.</b> ${esc(card.note)}</p>` : '<p class="pnote">Type a template, or open a preset. <b>__</b> lists your libraries, <b>$</b> your bindings.</p>'}
    <div class="edrow"${app.bridge.props.orrery_tl_w ? ` style="--tl-w:${Number(app.bridge.props.orrery_tl_w)}px"` : ""}>${cellsView(app)
      ? `<div class="editor cells${app.data.dividers === false ? " nodiv" : ""}"></div>`
      : `<div class="editor${app.data.dividers === false ? " nodiv" : ""}"><pre class="hl" aria-hidden="true"></pre><textarea spellcheck="false" aria-label="Template"></textarea></div>
      ${app.data.timeline === false ? "" : '<div class="tl-grip" role="separator" aria-orientation="vertical" tabindex="0" title="Drag to resize the timeline"></div><div class="timeline" hidden aria-label="The reel\'s clips"><div class="tl-track"></div></div>'}`}</div>
    <div class="dials"></div>
    <div class="pfoot">${statsHTML(app)}</div>
    ${app.state.pick ? pickerHTML(app) : ""}`;

  const paint = () => paintEditor(app);
  const afterEdit = (ta) => {
    fixReelSeed(app);
    fixUniqueSeed(app);
    if (dialKey(app.text) !== app.state.dialKey) renderDials(app);
    refreshBar(app);
    if (ta) complete(app, ta);
    else closeCompletion(app);
  };
  // only this textarea's completion: in the cells view focus moves between textareas while typing goes on
  const blur = (ta) => setTimeout(() => { if (!app.ac || app.ac.ta === ta) closeCompletion(app); }, 120);
  const focus = () => app.refreshCompletion().then(paint).catch(() => {});
  app.edResize?.disconnect();
  if (cellsView(app)) {
    renderCells(app);
    wireCells(app, { onEdit: afterEdit, onKey: (e) => completionKey(app, e), onFocus: focus, onBlur: blur });
  } else {
    const ed = app.view.querySelector(".editor textarea"), pre = app.view.querySelector(".editor pre.hl");
    ed.value = app.text;
    ed.readOnly = !!app.state.sweepQueue;
    paint();
    ed.addEventListener("input", () => {
      app.text = ed.value;
      paint();
      afterEdit(ed);
    });
    ed.addEventListener("scroll", () => { pre.scrollTop = ed.scrollTop; scrollTimeline(app); });
    app.edResize = new ResizeObserver(() => layoutTimeline(app, app.chunks()));  // wrapped lines move the chunks
    app.edResize.observe(ed);
    wireTimeline(app);
    ed.addEventListener("keydown", (e) => completionKey(app, e));
    ed.addEventListener("blur", () => blur(ed));
    ed.addEventListener("focus", focus);
  }
  wireHover(app, app.view.querySelector(".editor"));
  if (app.data.timeline !== false && app.chunks()) loadChain(app).then(paint);

  app.view.onclick = (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    const load = e.target.closest("[data-load]");
    if (load) return app.loadPreset(load.dataset.load);
    if (act === "pick") { app.state.pick = !app.state.pick; app.state.pickQ = ""; app.state.pickI = 0; renderPrompt(app); app.$("#oa-pq")?.focus(); }
    if (act === "revert") revert(app);
    if (act === "save") save(app);
    if (act === "saveas") openSave(app, { text: applyDials(app.text, app.bridge.getParams()), from: app.preset, link: true });
    if (act === "test") { app.go("test"); runRolls(app); }
    if (act === "stopsweep") return app.bridge.stopGenerate();
    if (act === "generate") return generate(app);
    if (act === "restart") restart(app);
    if (act === "jump") jumpToChunk(app);
    if (act === "tlview") { app.bridge.props.orrery_tl_view = cellsView(app) ? "beside" : "below"; return renderPrompt(app); }
    if (act === "new") { app.state.newMenu = !app.state.newMenu; app.state.writeMenu = false; return renderPrompt(app); }
    if (act === "write") { app.state.writeMenu = !app.state.writeMenu; app.state.newMenu = false; return renderPrompt(app); }
    const writer = e.target.closest("[data-write]")?.dataset.write;
    if (writer) { app.state.writeMenu = false; renderPrompt(app); return openWrite(app, writer); }
    const starter = e.target.closest("[data-new]")?.dataset.new;
    if (starter) startNew(app, starter);
    if (act === "outputs") { app.state.gScope = "prompt"; app.go("galaxy"); }
    if (act === "browse") app.go("presets");
  };
  app.view.onchange = (e) => {
    if (e.target.dataset.rep === undefined) return;
    app.bridge.props.repeat = Number(e.target.value) || 1;
    e.target.value = repeats(app);
    refreshFoot(app);  // the sweep button counts runs × seeds, and the noun after the number follows it
  };
  if (app.state.pick) wirePicker(app);
  renderDials(app);
  wireDials(app);
  fixReelSeed(app);
  fixUniqueSeed(app);
  refreshPlan(app);
  refreshRemembered(app);  // the hints and the remembered frames of a reel just opened
  refreshAnnotations(app);
}

async function generate(app) {
  await ensurePlan(app);
  if (planOf(app)) return generateSweep(app);
  const runs = repeats(app);
  app.bridge.generate(runs).then((n) => {
    if (!n) app.toast("Nothing to generate: connect this node's outputs toward a Save or Preview node.");
    else if (runs > 1 && n === runs) app.toast(`Queued <b>${runs}</b> runs`);  // fewer: Restart stopped it and says so
    refreshFoot(app);
  }).catch((err) => app.fail(err));
}

async function restart(app) {
  try {
    await app.bridge.stopGenerate();
    const cancelled = await app.bridge.cancelRuns();
    app.run = null;
    app.bridge.setSegment(0);
    await ensurePlan(app);
    if (planOf(app)) return generateSweep(app, cancelled);
    const runs = repeats(app);
    if (!(await app.bridge.generate(runs))) return app.toast("Nothing to generate: connect this node's outputs toward a Save or Preview node.");
    app.toast(`Restarted at clip <b>1</b>${runs > 1 ? ` · ${runs} runs queued` : ""}${cancelled ? ` · cancelled ${cancelled} earlier run${cancelled === 1 ? "" : "s"} of this node` : ""}`);
    refreshFoot(app);
  } catch (err) { app.fail(err); }
}

const SWEEP_ASK = 50;  // above this many runs, Generate asks first

// A LoRA sweep: every run, once per seed, its outputs in a galaxy folder named after the first swept LoRA.
function generateSweep(app, cancelled = 0) {
  const plan = planOf(app), seeds = repeats(app), total = plan.runs * seeds;
  const stamp = new Date(), pad = (n) => String(n).padStart(2, "0");
  const folder = `sweeps/${plan.first.split("/").pop().slice(0, 40)} ${stamp.getFullYear()}-${pad(stamp.getMonth() + 1)}-${pad(stamp.getDate())} ${pad(stamp.getHours())}.${pad(stamp.getMinutes())}`;
  const lock = (on) => {
    app.state.sweepQueue = on ? { done: 0, total } : null;
    if (app.state.tab === "prompt") app.view.querySelectorAll(".editor textarea").forEach((ed) => { ed.readOnly = on; });
    refreshFoot(app);
  };
  const progress = (done) => {
    if (app.state.sweepQueue) app.state.sweepQueue.done = done;
    const stop = app.state.tab === "prompt" && app.view.querySelector('[data-act="stopsweep"] .sweep');
    if (stop) stop.textContent = `${done}/${total} queued`;
  };
  const go = () => {
    lock(true);
    return app.bridge.generateSweep(plan.runs, seeds, folder, progress).finally(() => lock(false)).then((n) => report(n));
  };
  const report = (n) => {
    if (!n) return app.toast("Nothing to generate: connect this node's outputs toward a Save or Preview node.");
    app.toast(`Queued <b>${n}</b> runs · sweep ${esc(plan.formula)}${seeds > 1 ? ` × ${seeds} seeds` : ""} · gallery folder <b>${esc(folder)}</b>`
      + `${cancelled ? ` · cancelled ${cancelled} earlier run${cancelled === 1 ? "" : "s"} of this node` : ""}`
      + `${n < total ? ` · stopped after ${n} of ${total}` : ""}`);
  };
  if (total <= SWEEP_ASK) return go().catch((err) => app.fail(err));
  const sheet = app.openSheet(`<form class="panel"><div class="row spread"><h4>Queue ${total} runs?</h4></div>
    <p class="muted flush">The sweep makes ${plan.runs} runs (${esc(plan.formula)})${seeds > 1 ? `, for each of ${seeds} seeds` : ""}.</p>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("play")}Queue ${total}</button></div></form>`);
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  sheet.querySelector("form").onsubmit = (e) => { e.preventDefault(); app.closeSheet(); go().catch((err) => app.fail(err)); };
  sheet.querySelector("button.primary").focus();
}

// The highlight with the reel's chunk dividers, the next segment's chunk marked, and the timeline level with them.
function paintEditor(app) {
  if (app.view.querySelector(".editor.cells")) return paintCells(app);
  const pre = app.view.querySelector(".editor pre.hl");
  if (!pre) return;
  const chunks = app.chunks();
  pre.innerHTML = `${highlight(app.text, app.known(), { llm: app.llmActive(), chunks, segment: chunks && Number(app.bridge.getSegment()),
    hints: mergeHints(hintsFor(app.text, app.remembered()), annotationLines(app.text, app.annotations(), app.api.thumbURL)) })}\n`;
  layoutTimeline(app, chunks);
  if (chunks && app.data.timeline !== false && app.data.chain === undefined) {  // a reel typed or pasted in
    app.data.chain = null;
    loadChain(app).then(() => paintEditor(app));
  }
}

// The segment moved or a run finished: the marked chunk, the timeline and the footer follow.
export function refreshReel(app, { chain = false } = {}) {
  if (app.state.tab !== "prompt") return;
  refreshFoot(app);
  if (chain && app.data.timeline !== false && app.chunks()) loadChain(app).then(() => paintEditor(app));
  else paintEditor(app);
}

// Jump: the caret and the view to the CHUNK line of the segment Generate plays next.
function jumpToChunk(app) {
  const segment = Number(app.bridge.getSegment()), chunks = app.chunks() || [];
  const i = chunks.findIndex((c) => plays(c, segment));
  if (i < 0) return app.toast(`No scene plays clip <b>${segment + 1}</b>: the reel ends before it. Restart plays it from the beginning.`);
  if (jumpCell(app, i)) return;
  const ed = app.view.querySelector(".editor textarea"), head = app.view.querySelectorAll(".editor .chunkinfo")[i];
  const at = app.text.split("\n").slice(0, chunks[i].line).reduce((n, l) => n + l.length + 1, 0);
  ed.focus({ preventScroll: true });
  ed.setSelectionRange(at, at);
  ed.scrollTop = Math.max(0, head.offsetTop - 10 - head.offsetHeight);  // one line of what comes before
}

export function refreshFoot(app) {
  refreshPlan(app);  // a dial or an edit can change what Generate queues
  refreshReelPath(app);
  refreshRemembered(app);
  refreshAnnotations(app);
  const foot = app.view.querySelector(".pfoot");
  if (foot) foot.innerHTML = statsHTML(app);
}

// `unique=` walks a shuffled order one step per seed: the seeds of a batch have to come in a row.
function fixUniqueSeed(app) {
  if (!/^\s*(:.*\bunique=|@unique\b)/m.test(stripComments(app.text)) || ["increment", ""].includes(app.bridge.getControl())) return;
  app.bridge.setControl("increment");
  app.toast("@unique: control after generate set to <b>increment</b>, so each run of a batch gets another value");
}

// What Generate queues (a LoRA sweep's runs times a grid's cells) is planned by the server, which knows
// the libraries; the plan, or why it cannot run, is kept for the template and dials it was made for.
const planKey = (app) => `${app.text}\n${JSON.stringify(app.bridge.getParams())}`;
const planData = (app) => (app.data.plan?.key === planKey(app) ? app.data.plan : null);
const planOf = (app) => { const p = planData(app); return p && !p.error && p.runs ? p : null; };

async function fetchPlan(app) {
  const key = planKey(app);
  let got;
  try { got = await app.api.plan({ template: app.text, target: app.bridge.getTarget(), params: app.bridge.getParams() }); }
  catch (err) { got = { error: err.message }; }
  if (planKey(app) === key) app.data.plan = { ...got, key };
}

function refreshPlan(app) {
  if (!PLAN_HINT.test(stripComments(app.text))) { app.data.plan = null; return; }
  const key = planKey(app);
  if (app.data.plan?.key === key || app.state.planKey === key) return;
  app.state.planKey = key;
  clearTimeout(app.state.planTimer);
  app.state.planTimer = setTimeout(async () => {
    await fetchPlan(app);
    if (app.state.planKey === key) app.state.planKey = null;
    if (app.state.tab === "prompt") refreshFoot(app);
  }, 250);
}

// A reel with GOTO lines: its path at the node's seed comes from the server (a jump may wait on a roll);
// the dividers, the timeline and the cells follow it once it is there.
function refreshReelPath(app) {
  if (!hasGoto(app.text)) { app.data.reelPath = null; return; }
  const key = app.reelKey();
  if (app.data.reelPath?.key === key || app.state.reelKey === key) return;
  app.state.reelKey = key;
  clearTimeout(app.state.reelTimer);
  app.state.reelTimer = setTimeout(async () => {
    let got;
    try { got = await app.api.reel({ template: app.text, target: app.bridge.getTarget(), params: app.bridge.getParams(), seed: app.bridge.getSeed() }); }
    catch (err) { got = { error: err.message }; }
    if (app.state.reelKey === key) app.state.reelKey = null;
    if (app.reelKey() !== key) return;
    app.data.reelPath = { ...got, key };
    if (app.state.tab === "prompt") { paintEditor(app); refreshFoot(app); }
  }, 250);
}

// Where a reel's REMEMBER: lines put their frames, at the node's seed: from the server, which resolves them as
// the compile does; the hints at their ends and the frames under each scene follow once it is there.
// Annotations at line ends (#163): what each line gives at the node's seed (and clip), from the server; they
// wait a moment after typing stops, and a newer template's answer wins.
function refreshAnnotations(app) {
  const key = `${app.reelKey()}\n${app.bridge.getSegment?.() ?? 0}`;
  if (app.data.annotations?.key === key || app.state.annotateKey === key) return;
  app.state.annotateKey = key;
  clearTimeout(app.state.annotateTimer);
  app.state.annotateTimer = setTimeout(async () => {
    let got;
    try {
      got = await app.api.annotate({ template: app.text, target: app.bridge.getTarget(), params: app.bridge.getParams(),
        seed: app.bridge.getSeed(), segment: app.bridge.getSegment?.() ?? 0 });
    } catch { got = {}; }
    if (app.state.annotateKey === key) app.state.annotateKey = null;
    app.data.annotations = { ...got, key };
    if (app.state.tab === "prompt" && `${app.reelKey()}\n${app.bridge.getSegment?.() ?? 0}` === key) paintEditor(app);
  }, 450);
}

function refreshRemembered(app) {
  if (!app.chunks() || !/^\s*(REMEMBER|SEND):/im.test(stripComments(app.text))) { app.data.remembered = null; return; }
  const key = app.reelKey();
  if (app.data.remembered?.key === key || app.state.rememberedKey === key) return;
  app.state.rememberedKey = key;
  clearTimeout(app.state.rememberedTimer);
  app.state.rememberedTimer = setTimeout(async () => {
    let got;
    try { got = await app.api.remembered({ template: app.text, target: app.bridge.getTarget(), params: app.bridge.getParams(), seed: app.bridge.getSeed() }); }
    catch (err) { got = { error: err.message, lines: [] }; }
    if (app.state.rememberedKey === key) app.state.rememberedKey = null;
    if (app.reelKey() !== key) return;
    app.data.remembered = { ...got, key };
    if (app.state.tab === "prompt") paintEditor(app);
  }, 300);
}

// Generate can come before the plan: it waits for it.
async function ensurePlan(app) {
  if (PLAN_HINT.test(stripComments(app.text)) && !planData(app)) await fetchPlan(app);
}

// A reel runs as one clip per queue; a seed that changes between clips would reroll its bindings.
function fixReelSeed(app) {
  if (!stats(app.text).h3?.reel || ["fixed", ""].includes(app.bridge.getControl())) return;
  app.bridge.setControl("fixed");
  app.toast("Reel: control after generate set to <b>fixed</b>, so every scene rolls the same bindings");
}

/* dials: every binding can be turned without editing the template; empty = its default roll */

const dialKey = (text) => dials(text).map((d) => `${d.name}=${d.expr}`).join("\n");
const setDials = (app) => Object.keys(app.bridge.getParams()).length;

const DIAL_CHOICES = 500;  // a dial lists this many of its library's entries; any other can be typed

// A dial's choices: its braces' options, or its library's entries (null while they are on their way).
function dialChoices(app, d) {
  if (d.options.length) return d.options;
  if (!d.lib) return [];
  const own = inlineLibraries(app.text).find((l) => l.name === d.lib);  // the template's @lib wins
  if (own) return own.entries;
  const lib = app.data.libFull?.[d.lib] || app.dialLibs?.[d.lib];  // only this library, once (#152: the home was 30 MB)
  if (!lib) {
    (app.libsLoading ??= {})[d.lib] ??= app.api.library(d.lib)
      .then((got) => { (app.dialLibs ??= {})[d.lib] = got; })
      .catch(() => { (app.dialLibs ??= {})[d.lib] = { entries: [] }; })
      .finally(() => { delete app.libsLoading[d.lib]; refreshMenu(app); });  // asked again after a run empties the cache
    return null;
  }
  return lib.entries.filter((e) => matches(d.tag, e.tags, e.props)).slice(0, DIAL_CHOICES).map((e) => e.value);
}

function renderDials(app) {
  const box = app.view.querySelector(".dials");
  if (!box) return;
  if (app.dm) shutMenu(app);
  const list = dials(app.text), values = app.bridge.getParams();
  const kept = Object.fromEntries(Object.entries(values).filter(([k]) => list.some((d) => d.name === k)));
  if (Object.keys(kept).length !== Object.keys(values).length) app.bridge.setParams(kept);
  app.state.dialKey = dialKey(app.text);
  box.innerHTML = list.length ? `<span class="label" title="Turn a binding without editing the template. Empty means its default roll; saving bakes the dials in.">Dials</span>`
    + list.map((d) => {
      const v = kept[d.name] || "", id = `oa-${app.uid}-dl-${d.name}`;
      return `<label class="dial${v ? " on" : ""}" title="$${esc(d.name)} = ${esc(d.expr)}"><span class="dn">$${esc(d.name)}</span>`
        + `<input class="dv" id="${id}" data-dial="${esc(d.name)}" value="${esc(v)}" placeholder="${esc(d.expr)}" spellcheck="false" autocomplete="off" role="combobox" aria-expanded="false">`
        + `<button type="button" class="mini" data-dreset="${esc(d.name)}" aria-label="Back to the default roll">${icon("x")}</button></label>`;
    }).join("") : "";
}

function wireDials(app) {
  const box = app.view.querySelector(".dials");
  const put = (name, value) => {
    const values = app.bridge.getParams();
    if (value.trim()) values[name] = value.trim(); else delete values[name];
    app.bridge.setParams(values);
    box.querySelector(`[data-dial="${CSS.escape(name)}"]`)?.closest(".dial").classList.toggle("on", !!value.trim());
    refreshBar(app);
  };
  box.addEventListener("input", (e) => {
    if (!e.target.dataset.dial) return;
    put(e.target.dataset.dial, e.target.value);
    openMenu(app, e.target, -1);
  });
  box.addEventListener("focusin", (e) => { if (e.target.dataset.dial) openMenu(app, e.target, -1); });
  box.addEventListener("mousedown", (e) => { if (e.target.dataset.dial && !app.dm) openMenu(app, e.target, -1); });
  box.addEventListener("focusout", (e) => { if (e.target.dataset.dial) setTimeout(() => { if (app.dm?.input === e.target) shutMenu(app); }, 0); });
  box.addEventListener("keydown", (e) => {
    const input = e.target;
    if (!input.dataset.dial) return;
    const n = app.dm?.items.length || 0;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const down = e.key === "ArrowDown", was = app.dm ? app.dm.at : -1;
      openMenu(app, input, !n ? -1 : was < 0 ? (down ? 0 : n - 1) : (was + (down ? 1 : n - 1)) % n);
    } else if (e.key === "Enter" && app.dm && app.dm.at >= 0 && app.dm.items[app.dm.at] !== undefined) {
      e.preventDefault();
      pickChoice(app, input, app.dm.items[app.dm.at]);
    } else if (e.key === " " && app.dm && app.dm.at >= 0 && app.dm.items[app.dm.at] !== undefined) {
      e.preventDefault();
      toggleChoice(app, input, app.dm.items[app.dm.at]);
    } else if (e.key === "Escape" && app.dm) {
      e.preventDefault();
      shutMenu(app);
    }
  });
  app.pickChoice = (input, value) => { input.value = value; put(input.dataset.dial, value); };
  box.addEventListener("click", (e) => {
    const r = e.target.closest("[data-dreset]");
    if (!r) return;
    e.preventDefault();
    box.querySelector(`[data-dial="${CSS.escape(r.dataset.dreset)}"]`).value = "";
    put(r.dataset.dreset, "");
  });
}

// The dial's menu: drawn in the app (the dials row scrolls and would cut it off), kept in app.dm.
const menuHost = (app) => app.view.closest(".orrery-app") || app.view;

function openMenu(app, input, at) {
  const d = dials(app.text).find((x) => x.name === input.dataset.dial);
  if (!d) return;
  const lib = d.lib && (app.data.libFull?.[d.lib] || app.dialLibs?.[d.lib]);
  const gallery = lib && d.lib.startsWith("pictures/") ? new Map(lib.entries.map((e) => [e.value, e.props || {}])) : null;
  const describe = gallery && ((c) => {
    const p = gallery.get(c);
    const id = p?.ids?.split("\n")[0];
    return p && { sub: p.who || (p.prompt || "").slice(0, 110), thumb: id && app.api.thumbURL(id) };
  });
  const state = drawMenu(menuHost(app), input, dialChoices(app, d), at, describe);
  app.dm = { ...state, input };
  input.setAttribute("aria-expanded", "true");
  state.box.addEventListener("mousedown", (e) => {
    const item = e.target.closest("[data-n]"), box = e.target.closest("[data-toggle]");
    e.preventDefault();  // the box keeps the focus
    if (box) toggleChoice(app, input, app.dm.items[Number(box.dataset.toggle)]);
    else if (item) pickChoice(app, input, app.dm.items[Number(item.dataset.n)]);
  });
}

function refreshMenu(app) {
  if (app.dm && app.dm.input.isConnected) openMenu(app, app.dm.input, app.dm.at);
}

function shutMenu(app) {
  closeMenu(menuHost(app));
  app.dm?.input.setAttribute("aria-expanded", "false");
  app.dm = null;
}

// A tick adds a choice to the ones the dial rolls among, or takes it out; the menu stays open.
function toggleChoice(app, input, value) {
  const d = dials(app.text).find((x) => x.name === input.dataset.dial), all = (d && dialChoices(app, d)) || [];
  const now = chosen(all, input.value), next = now.includes(value) ? now.filter((c) => c !== value) : [...now, value];
  app.pickChoice(input, joinChoices(all.filter((c) => next.includes(c))));  // in the list's order
  openMenu(app, input, app.dm ? app.dm.at : -1);
}

function pickChoice(app, input, value) {
  app.pickChoice(input, value);
  shutMenu(app);
}

// Fresh templates: no preset linked, so nothing can be overwritten by accident.

function startNew(app, kind) {
  if (app.busy()) return;
  const s = STARTERS[kind], prev = { preset: app.preset, base: app.base, text: app.text, params: app.bridge.getParams(), target: app.bridge.getTarget() };
  const hadWork = app.dirty();
  app.preset = null;
  app.base = null;
  app.text = app.data.quickstart === false ? stripComments(s.text).trimStart() : s.text;  // the gear turns it off
  app.bridge.setParams({});
  app.bridge.setTarget(s.target);
  app.state.newMenu = false;
  renderPrompt(app);
  app.view.querySelector("textarea")?.focus();
  app.toast(`New ${esc(s.label)}, not linked to a preset`, hadWork || prev.preset ? {
    label: "Undo",
    run: () => {
      app.preset = prev.preset; app.base = prev.base; app.text = prev.text;
      app.bridge.setParams(prev.params); app.bridge.setTarget(prev.target); renderPrompt(app);
    },
  } : null);
}

function refreshBar(app) {
  const card = app.preset && app.card(app.preset), d = app.dirty();
  app.view.querySelector(".pchip").innerHTML = chipHTML(app);
  app.view.querySelector('[data-act="revert"]').disabled = !(card && d);
  app.view.querySelector('[data-act="save"]').disabled = !(card && (d || setDials(app)));
  refreshFoot(app);
}

function revert(app) {
  if (app.busy()) return;
  const prev = app.text;
  app.text = app.base;
  renderPrompt(app);
  app.toast("Reverted to the saved preset", { label: "Undo", run: () => { app.text = prev; renderPrompt(app); } });
}

async function save(app) {
  const card = app.card(app.preset);
  if (!card) return;
  const text = applyDials(app.text, app.bridge.getParams());
  if (card.builtin) return openSave(app, { text, from: card.name, copyOf: true, link: true });
  try {
    await app.api.savePreset({ name: card.name, text, title: card.title, tags: card.tags, note: card.note, overwrite: true });
    app.text = text;
    app.base = text;
    app.bridge.setParams({});
    await app.refreshPresets();
    renderPrompt(app);
    app.toast(`Saved <b>@${esc(card.name)}</b>`);
  } catch (e) { app.fail(e); }
}

/* quick picker */

function pickerHTML(app) {
  let i = 0;
  const groups = pickerGroups(app.data.presets, { query: app.state.pickQ, favorites: app.data.favorites, recent: app.data.recent });
  const rows = groups.map(([g, cards]) => `<li class="grp label">${esc(g)}</li>` + cards.map((c) => {
    const on = i++ === app.state.pickI;
    return `<li><button data-load="${esc(c.name)}" class="${on ? "on" : ""}"><span class="th">${thumbHTML(app, c)}</span>`
      + `<span class="tt"><span>${esc(c.title)}</span><span class="pname">@${esc(c.name)}</span></span></button></li>`;
  }).join("")).join("");
  return `<div class="pop" role="listbox"><label class="search">${icon("search")}<input class="input" id="oa-pq" placeholder="Find a preset by name, tag or words in it…" value="${esc(app.state.pickQ)}" autocomplete="off"></label>`
    + `<ul>${rows || '<li class="empty">No preset matches.</li>'}</ul>`
    + `<div class="foot"><span>↑↓ choose · ↵ open · esc close</span><button class="btn ghost" data-act="browse">Browse with previews →</button></div></div>`;
}

function wirePicker(app) {
  const q = app.$("#oa-pq");
  q.addEventListener("input", () => {
    const pos = q.selectionEnd;
    app.state.pickQ = q.value;
    app.state.pickI = 0;
    renderPrompt(app);
    const nq = app.$("#oa-pq");
    nq.focus();
    nq.setSelectionRange(pos, pos);
  });
  q.addEventListener("keydown", (e) => {
    const btns = [...app.view.querySelectorAll(".pop [data-load]")];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      app.state.pickI = (app.state.pickI + (e.key === "ArrowDown" ? 1 : -1) + btns.length) % Math.max(btns.length, 1);
      btns.forEach((b, i) => b.classList.toggle("on", i === app.state.pickI));
      btns[app.state.pickI]?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      const b = btns[app.state.pickI];
      if (b) app.loadPreset(b.dataset.load);
    } else if (e.key === "Escape") {
      e.preventDefault();
      app.state.pick = false;
      renderPrompt(app);
    }
  });
}

/* completion: the same rules as v0, drawn inside the editor so it scales with the canvas */

// In the cells view a cell sees the whole text (the world's bindings), at its offset in it.
function complete(app, ta) {
  const offset = inCell(ta) ? cellStart(app, ta) : 0;
  const ann = app.annotations() || app.data.annotations;  // while typing, the last ones still know slots and fields
  const data = app.data.completion && { ...app.data.completion, fieldValues: ann?.fields || {},
    taken: Object.fromEntries(Object.entries(ann?.members || {}).flatMap(([name, m]) => m.pictures
      .filter((p) => p.name).map((p) => [p.image, `${name}'s gallery picture (${p.name})`]))) };
  const found = suggest(inCell(ta) ? app.text : ta.value, offset + ta.selectionEnd, data);
  if (!found.items.length) return closeCompletion(app);
  for (const it of found.items) {  // gallery pictures: their thumbnails, by id
    if (it.thumbId) it.thumb = app.api.thumbURL(it.thumbId);
    if (it.thumbIds) it.thumbs = it.thumbIds.map((id) => app.api.thumbURL(id));
  }
  // a whole keyword typed (`CAST`, `SET`): nothing is chosen, so Enter is a new line; ↓ chooses
  const typed = (inCell(ta) ? app.text : ta.value).slice(found.replaceFrom, offset + ta.selectionEnd).trim().replace(/:$/, "");
  const whole = KEYWORDS.some((k) => k.word.trim().replace(/\s*\$$/, "").replace(/:$/, "") === typed);
  app.ac = { ...found, i: whole ? -1 : 0, ta, offset };
  drawCompletion(app);
}

// The popup: wide enough to read (labels and details wrap, nothing is cut), a preview of the highlighted
// item (its text in full, its pictures), under the caret or above it when the app has no room below.
function drawCompletion(app) {
  app.view.querySelector(".ac")?.remove();
  const { items, i, ta } = app.ac, { x, y } = caretPoint(ta), item = items[i] || {};
  const editor = ta.closest(".editor"), cell = ta.closest(".cell");
  const dx = cell ? cell.offsetLeft : 0, dy = cell ? cell.offsetTop - editor.scrollTop : 0;
  const box = document.createElement("div");
  box.className = "ac";
  const shown = item.thumbs?.length || item.preview;
  box.innerHTML = `<ul role="listbox">${items.map((it, n) => `<li class="${n === i ? "on" : ""}${it.thumb ? " thumbed" : ""}" data-i="${n}" role="option">`
    + (it.thumb ? `<img class="act" src="${esc(it.thumb)}" alt="" loading="lazy">` : "")
    + `<span class="acl">${esc((it.label ?? it.insert).trim())}</span>${it.detail ? `<span class="acd">${esc(it.detail)}</span>` : ""}</li>`).join("")}</ul>`
    + (shown ? `<div class="pv">${(item.thumbs || []).map((u) => `<img src="${esc(u)}" alt="">`).join("")}`
      + `${item.preview ? `<span>${esc(item.preview)}</span>` : ""}</div>` : "");
  box.addEventListener("mousedown", (e) => {
    const li = e.target.closest("[data-i]");
    if (!li) return;
    e.preventDefault();
    app.ac.i = Number(li.dataset.i);
    acceptCompletion(app);
  });
  editor.appendChild(box);
  const root = editor.closest(".orrery-app") || editor, er = editor.getBoundingClientRect(), rr = root.getBoundingClientRect();
  const k = er.width / editor.offsetWidth || 1, line = parseFloat(getComputedStyle(ta).lineHeight) || 20;
  box.style.left = `${Math.max(4, Math.min(x + 8 + dx, editor.clientWidth - box.offsetWidth - 4))}px`;
  const below = y + 4 + dy, above = y - line - box.offsetHeight - 4 + dy;
  const roomBelow = (rr.bottom - er.top) / k - below, roomAbove = (er.top - rr.top) / k + above;
  box.style.top = `${box.offsetHeight <= roomBelow || roomAbove < 0 ? below : above}px`;
  box.querySelector(".on")?.scrollIntoView({ block: "nearest" });
}

function closeCompletion(app) {
  app.view.querySelector(".ac")?.remove();
  app.ac = null;
}

// True when the completion took the key. Ctrl+Space opens it where the caret is.
function completionKey(app, e) {
  if (e.ctrlKey && (e.code === "Space" || e.key === " ") && e.target.tagName === "TEXTAREA") {
    e.preventDefault();
    complete(app, e.target);
    return true;
  }
  if (!app.ac) return false;
  const n = app.ac.items.length;
  if ((e.key === "Enter" || e.key === "Tab") && app.ac.i < 0) { closeCompletion(app); return false; }  // nothing chosen: the key is the editor's
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const down = e.key === "ArrowDown";
    app.ac.i = app.ac.i < 0 ? (down ? 0 : n - 1) : (app.ac.i + (down ? 1 : -1) + n) % n;
    drawCompletion(app);
  }
  else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); acceptCompletion(app); }
  else if (e.key === "Escape") { e.preventDefault(); closeCompletion(app); }
  else return false;
  return true;
}

function acceptCompletion(app) {
  const { ta, items, i, offset = 0 } = app.ac, insert = items[i].insert, caret = ta.selectionEnd;
  const from = Math.max(0, app.ac.replaceFrom - offset);
  ta.value = ta.value.slice(0, from) + insert + ta.value.slice(caret);
  ta.selectionStart = ta.selectionEnd = from + insert.length;
  closeCompletion(app);
  ta.dispatchEvent(new Event("input", { bubbles: true }));  // the cells view listens on their container
}
