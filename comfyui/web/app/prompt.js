// Prompt tab: preset bar, the highlighted editor with completion, dials, and a way into Test.
import { suggest } from "../orrery-complete.js";
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";
import { applyDials, dials, folderColor, pickerGroups, shape, stats, templateHash } from "./model.js";
import { thumbHTML } from "./parts.js";
import { openSave } from "./save.js";
import { runRolls } from "./test.js";

function statsHTML(app) {
  const st = stats(app.text), out = shape(app.text), reel = st.h3?.reel;
  const outs = (app.data.rows || []).filter((r) => r.template === templateHash(app.text)).length;
  const forever = reel && reel.clips === Infinity;
  const how = !reel ? "" : "Wire load_index into Load Latent's clip_index and save_index into Save Latent's. The segment widget counts up by itself (increment): "
    + (forever ? "Run (Instant) plays clip after clip until you stop it." : `a Run count of ${reel.clips} plays the whole reel; after the last clip nothing downstream runs.`);
  const timing = reel
    ? `<span class="stat" title="${esc(how)}"><b>Reel</b> · ${reel.secs.map((s, i) => `<b>${s.toFixed(1)} s</b>${reel.repeats[i] === 1 ? "" : ` ×${reel.repeats[i] === Infinity ? "∞" : reel.repeats[i]}`}`).join(" + ")} · <b>${forever ? "∞" : reel.clips}</b> clip${reel.clips === 1 ? "" : "s"}</span>`
    : st.h3 ? `<span class="stat"><b>H3</b> · ${st.h3.shots} shot${st.h3.shots === 1 ? "" : "s"} · <b>${st.h3.secs.toFixed(1)} s</b> · ${st.h3.voices} voice${st.h3.voices === 1 ? "" : "s"}</span>` : "";
  const frames = reel ? ` · <b>${out.lengths.join(" / ")}</b> frames per chunk` : st.h3 ? ` · <b>${out.length}</b> frames = ${(out.length / 24).toFixed(2)} s` : "";
  return timing
    + `<span class="stat"><b>${st.rolls}</b> rolls · <b>${st.libs}</b> libraries · <b>${st.binds}</b> bindings${setDials(app) ? ` · <b>${setDials(app)}</b> dialed` : ""}</span>`
    + `${app.llmActive() ? `<span class="stat" title="Unknown __libraries__ and __name:N__ are made by this model when the node runs">LLM <b>${esc(app.data.llm.file.replace(/\.[a-z]+$/, ""))}</b></span>` : ""}`
    + `<span class="stat" title="The node's width, height, length and megapixels outputs${reel ? "; from the second chunk on, length includes the frames Motion Context pins" : ""}">→ <b>${out.width}×${out.height}</b> · ${out.megapixels} MP${frames}</span>`
    + `${out.cli.length ? `<span class="stat cli" title="In ComfyUI, use the Run count and the seed widget">${esc(out.cli.join(" "))}: CLI only</span>` : ""}<span class="grow"></span>`
    + `${outs ? `<button class="btn ghost" data-act="outputs">${icon("image")}${outs} output${outs === 1 ? "" : "s"}</button>` : ""}`
    + `<button class="btn" data-act="test" title="Roll it in the Test tab: a few seeds, or a reel's clips">${icon("dice")}Test</button>`
    + (reel ? (app.run
      ? `<span class="stat live" title="The reel segment this node is generating now">Generating segment <b>${app.run.segment}</b></span>`
      : `<span class="stat" title="The segment Generate plays next: the node's segment widget">Next segment <b>${esc(String(app.bridge.getSegment()))}</b></span>`)
      + `<button class="btn" data-act="restart" title="Cancel this node's queued and running clips, set segment to 0 and generate from the start">${icon("undo")}Restart</button>` : "")
    + `<label class="rep" title="How many runs Generate queues, one after another; seed and segment step between them as their control after generate says, so a reel plays that many clips">×<input type="number" min="1" max="999" value="${repeats(app)}" data-rep aria-label="Runs per Generate"></label>`
    + `<button class="btn primary" data-act="generate" title="Queue only what this node feeds, up to its Save nodes; their files go to the galaxy">${icon("play")}Generate</button>`;
}

// Runs per Generate, kept in the node's properties so the workflow remembers it.
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
      ${app.state.newMenu ? `<div class="pop newpop" role="menu">${Object.entries(STARTERS).map(([k, s]) => `<button role="menuitem" data-new="${k}"><b>${esc(s.label)}</b><span class="muted">${esc(s.hint)}</span></button>`).join("")}</div>` : ""}
    </div>
    ${card?.note ? `<p class="pnote"><b>${esc(card.title)}.</b> ${esc(card.note)}</p>` : '<p class="pnote">Type a template, or open a preset. <b>__</b> lists your libraries, <b>$</b> your bindings.</p>'}
    <div class="editor"><pre class="hl" aria-hidden="true"></pre><textarea spellcheck="false" aria-label="Template"></textarea></div>
    <div class="dials"></div>
    <div class="pfoot">${statsHTML(app)}</div>
    ${app.state.pick ? pickerHTML(app) : ""}`;

  const ed = app.view.querySelector("textarea"), pre = app.view.querySelector("pre.hl");
  const paint = () => { pre.innerHTML = `${highlight(app.text, app.known(), { llm: app.llmActive() })}\n`; };
  ed.value = app.text;
  paint();
  ed.addEventListener("input", () => {
    app.text = ed.value;
    paint();
    fixReelSeed(app);
    if (dialKey(app.text) !== app.state.dialKey) renderDials(app);
    refreshBar(app);
    complete(app, ed);
  });
  ed.addEventListener("scroll", () => { pre.scrollTop = ed.scrollTop; });
  ed.addEventListener("keydown", (e) => completionKey(app, e));
  ed.addEventListener("blur", () => setTimeout(() => closeCompletion(app), 120));
  ed.addEventListener("focus", () => app.refreshCompletion().then(paint).catch(() => {}));

  app.view.onclick = (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    const load = e.target.closest("[data-load]");
    if (load) return app.loadPreset(load.dataset.load);
    if (act === "pick") { app.state.pick = !app.state.pick; app.state.pickQ = ""; app.state.pickI = 0; renderPrompt(app); app.$("#oa-pq")?.focus(); }
    if (act === "revert") revert(app);
    if (act === "save") save(app);
    if (act === "saveas") openSave(app, { text: applyDials(app.text, app.bridge.getParams()), from: app.preset, link: true });
    if (act === "test") { app.go("test"); runRolls(app); }
    if (act === "generate") {
      const runs = repeats(app);
      app.bridge.generate(runs).then((n) => {
        if (!n) app.toast("Nothing to generate: connect this node's outputs toward a Save or Preview node.");
        else if (runs > 1 && n === runs) app.toast(`Queued <b>${runs}</b> runs`);  // fewer: Restart stopped it and says so
        refreshFoot(app);
      }).catch((err) => app.fail(err));
    }
    if (act === "restart") restart(app);
    if (act === "new") { app.state.newMenu = !app.state.newMenu; return renderPrompt(app); }
    const starter = e.target.closest("[data-new]")?.dataset.new;
    if (starter) startNew(app, starter);
    if (act === "outputs") { app.state.gScope = "prompt"; app.go("galaxy"); }
    if (act === "browse") app.go("presets");
  };
  app.view.onchange = (e) => {
    if (e.target.dataset.rep === undefined) return;
    app.bridge.props.repeat = Number(e.target.value) || 1;
    e.target.value = repeats(app);
  };
  if (app.state.pick) wirePicker(app);
  renderDials(app);
  wireDials(app);
  fixReelSeed(app);
}

async function restart(app) {
  try {
    await app.bridge.stopGenerate();
    const cancelled = await app.bridge.cancelRuns();
    app.run = null;
    app.bridge.setSegment(0);
    const runs = repeats(app);
    if (!(await app.bridge.generate(runs))) return app.toast("Nothing to generate: connect this node's outputs toward a Save or Preview node.");
    app.toast(`Restarted at segment <b>0</b>${runs > 1 ? ` · ${runs} runs queued` : ""}${cancelled ? ` · cancelled ${cancelled} earlier run${cancelled === 1 ? "" : "s"} of this node` : ""}`);
    refreshFoot(app);
  } catch (err) { app.fail(err); }
}

export function refreshFoot(app) {
  const foot = app.view.querySelector(".pfoot");
  if (foot) foot.innerHTML = statsHTML(app);
}

// A reel runs as one clip per queue; a seed that changes between clips would reroll its bindings.
function fixReelSeed(app) {
  if (!stats(app.text).h3?.reel || ["fixed", ""].includes(app.bridge.getControl())) return;
  app.bridge.setControl("fixed");
  app.toast("Reel: control after generate set to <b>fixed</b>, so every chunk rolls the same bindings");
}

/* dials: every binding can be turned without editing the template; empty = its default roll */

const dialKey = (text) => dials(text).map((d) => `${d.name}=${d.expr}`).join("\n");
const setDials = (app) => Object.keys(app.bridge.getParams()).length;

function dialChoices(app, d) {
  if (d.options.length) return d.options;
  if (!d.lib) return [];
  if (!app.data.libraries) {
    app.libsLoading ??= app.api.libraries().then((r) => { app.data.libraries = r.libraries; renderDials(app); })
      .catch(() => { app.data.libraries = []; });
    return [];
  }
  const lib = app.data.libraries.find((l) => l.name === d.lib);
  return (lib?.entries || []).filter((e) => !d.tag || e.tags.includes(d.tag)).map((e) => e.value);
}

function renderDials(app) {
  const box = app.view.querySelector(".dials");
  if (!box) return;
  const list = dials(app.text), values = app.bridge.getParams();
  const kept = Object.fromEntries(Object.entries(values).filter(([k]) => list.some((d) => d.name === k)));
  if (Object.keys(kept).length !== Object.keys(values).length) app.bridge.setParams(kept);
  app.state.dialKey = dialKey(app.text);
  box.innerHTML = list.length ? `<span class="label" title="Turn a binding without editing the template. Empty means its default roll; saving bakes the dials in.">Dials</span>`
    + list.map((d) => {
      const v = kept[d.name] || "", id = `oa-${app.uid}-dl-${d.name}`;
      return `<label class="dial${v ? " on" : ""}" title="$${esc(d.name)} = ${esc(d.expr)}"><span class="dn">$${esc(d.name)}</span>`
        + `<input class="dv" data-dial="${esc(d.name)}" list="${id}" value="${esc(v)}" placeholder="${esc(d.expr)}" spellcheck="false" autocomplete="off">`
        + `<button type="button" class="mini" data-dreset="${esc(d.name)}" aria-label="Back to the default roll">${icon("x")}</button>`
        + `<datalist id="${id}">${dialChoices(app, d).map((c) => `<option value="${esc(c)}"></option>`).join("")}</datalist></label>`;
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
  box.addEventListener("input", (e) => { if (e.target.dataset.dial) put(e.target.dataset.dial, e.target.value); });
  box.addEventListener("click", (e) => {
    const r = e.target.closest("[data-dreset]");
    if (!r) return;
    e.preventDefault();
    box.querySelector(`[data-dial="${CSS.escape(r.dataset.dreset)}"]`).value = "";
    put(r.dataset.dreset, "");
  });
}

// Fresh templates: no preset linked, so nothing can be overwritten by accident.
const STARTERS = {
  h3: {
    label: "H3 screenplay", hint: "@h3 header, one shot, sound", target: "h3-base",
    text: "@h3 t2va 16:9\nstyle: live-action, cinematic\n\nSHOT 5s | push in, slow\nWhat the camera sees, and what happens in it.\nSFX: the ambience; one clear sound\n",
  },
  krea: {
    label: "Krea prompt", hint: "a still, medium named, size", target: "text",
    text: "a photograph of {a quiet street|an empty diner|a greenhouse} at {dawn|dusk}, 35mm film, soft grain\n: w832 h1216\n",
  },
};

function startNew(app, kind) {
  const s = STARTERS[kind], prev = { preset: app.preset, base: app.base, text: app.text, params: app.bridge.getParams(), target: app.bridge.getTarget() };
  const hadWork = app.dirty();
  app.preset = null;
  app.base = null;
  app.text = s.text;
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

function caretPoint(ta) {
  const mirror = document.createElement("div"), css = getComputedStyle(ta);
  for (const k of ["boxSizing", "width", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "fontFamily",
    "fontSize", "fontWeight", "lineHeight", "letterSpacing", "overflowWrap", "tabSize", "scrollbarGutter"]) mirror.style[k] = css[k];
  Object.assign(mirror.style, { position: "absolute", visibility: "hidden", top: "0", left: "-9999px", whiteSpace: "pre-wrap", overflowY: "scroll" });
  mirror.textContent = ta.value.slice(0, ta.selectionEnd);
  const mark = document.createElement("span");
  mark.textContent = "​";
  mirror.appendChild(mark);
  document.body.appendChild(mirror);
  const p = { x: mark.offsetLeft - ta.scrollLeft, y: mark.offsetTop - ta.scrollTop + mark.offsetHeight };
  mirror.remove();
  return p;
}

function complete(app, ta) {
  const found = suggest(ta.value, ta.selectionEnd, app.data.completion);
  if (!found.items.length) return closeCompletion(app);
  app.ac = { ...found, i: 0, ta };
  drawCompletion(app);
}

function drawCompletion(app) {
  app.view.querySelector(".ac")?.remove();
  const { items, i, ta, kind } = app.ac, { x, y } = caretPoint(ta), item = items[i], wide = kind === "lora";
  const box = document.createElement("div");
  box.className = wide ? "ac wide" : "ac";
  box.style.left = `${Math.max(4, Math.min(x + 8, ta.clientWidth - (wide ? 480 : 250)))}px`;
  box.style.top = `${y + 12}px`;
  box.innerHTML = `<ul>${items.map((it, n) => `<li class="${n === i ? "on" : ""}" data-i="${n}"><span>${esc((it.label ?? it.insert).trim())}</span><span>${esc(it.detail)}</span></li>`).join("")}</ul>`
    + `${item.preview ? `<div class="pv">${esc(item.preview)}</div>` : ""}`;
  box.addEventListener("mousedown", (e) => {
    const li = e.target.closest("[data-i]");
    if (!li) return;
    e.preventDefault();
    app.ac.i = Number(li.dataset.i);
    acceptCompletion(app);
  });
  app.view.querySelector(".editor").appendChild(box);
  box.querySelector(".on")?.scrollIntoView({ block: "nearest" });
}

function closeCompletion(app) {
  app.view.querySelector(".ac")?.remove();
  app.ac = null;
}

function completionKey(app, e) {
  if (!app.ac) return;
  const n = app.ac.items.length;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); app.ac.i = (app.ac.i + (e.key === "ArrowDown" ? 1 : -1) + n) % n; drawCompletion(app); }
  else if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); acceptCompletion(app); }
  else if (e.key === "Escape") { e.preventDefault(); closeCompletion(app); }
}

function acceptCompletion(app) {
  const { ta, replaceFrom, items, i } = app.ac, insert = items[i].insert, caret = ta.selectionEnd;
  ta.value = ta.value.slice(0, replaceFrom) + insert + ta.value.slice(caret);
  ta.selectionStart = ta.selectionEnd = replaceFrom + insert.length;
  closeCompletion(app);
  ta.dispatchEvent(new Event("input"));
}
