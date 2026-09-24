// Prompt tab: preset bar, highlighted editor with completion, and Roll 3.
import { suggest } from "../orrery-complete.js";
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";
import { folderColor, markPicks, pickerGroups, shape, stats, templateHash } from "./model.js";
import { thumbHTML } from "./parts.js";
import { openSave } from "./save.js";

function statsHTML(app) {
  const st = stats(app.text), out = shape(app.text);
  const outs = (app.data.rows || []).filter((r) => r.template === templateHash(app.text)).length;
  return `${st.h3 ? `<span class="stat"><b>H3</b> · ${st.h3.shots} shot${st.h3.shots === 1 ? "" : "s"} · <b>${st.h3.secs.toFixed(1)} s</b> · ${st.h3.voices} voice${st.h3.voices === 1 ? "" : "s"}</span>` : ""}`
    + `<span class="stat"><b>${st.rolls}</b> rolls · <b>${st.libs}</b> libraries · <b>${st.binds}</b> bindings</span>`
    + `<span class="stat" title="The node's width, height and length outputs">→ <b>${out.width}×${out.height}</b>${st.h3 ? ` · <b>${out.length}</b> frames = ${(out.length / 24).toFixed(2)} s` : ""}</span>`
    + `${out.cli.length ? `<span class="stat cli" title="In ComfyUI, use the Run count and the seed widget">${esc(out.cli.join(" "))}: CLI only</span>` : ""}<span class="grow"></span>`
    + `${outs ? `<button class="btn ghost" data-act="outputs">${icon("image")}${outs} output${outs === 1 ? "" : "s"}</button>` : ""}`
    + `<button class="btn" data-act="roll">${icon("dice")}Roll 3</button>`;
}

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
      <button class="btn" data-act="save" ${card && d ? "" : "disabled"}>${icon("save")}${card?.builtin ? "Save a copy" : "Save"}</button>
      <button class="btn primary" data-act="saveas">Save as…</button>
    </div>
    ${card?.note ? `<p class="pnote"><b>${esc(card.title)}.</b> ${esc(card.note)}</p>` : '<p class="pnote">Type a template, or open a preset. <b>__</b> lists your libraries, <b>$</b> your bindings.</p>'}
    <div class="editor"><pre class="hl" aria-hidden="true"></pre><textarea spellcheck="false" aria-label="Template"></textarea></div>
    <div class="pfoot">${statsHTML(app)}</div>
    <div class="scroll"><div class="rolls"></div></div>
    ${app.state.pick ? pickerHTML(app) : ""}`;

  const ed = app.view.querySelector("textarea"), pre = app.view.querySelector("pre.hl");
  const paint = () => { pre.innerHTML = `${highlight(app.text, app.known())}\n`; };
  ed.value = app.text;
  paint();
  ed.addEventListener("input", () => {
    app.text = ed.value;
    paint();
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
    if (act === "saveas") openSave(app, { text: app.text, from: app.preset, link: true });
    if (act === "roll") roll(app);
    if (act === "outputs") { app.state.gScope = "prompt"; app.go("galaxy"); }
    if (act === "browse") app.go("presets");
  };
  if (app.state.pick) wirePicker(app);
  renderRolls(app);
}

function refreshBar(app) {
  const card = app.preset && app.card(app.preset), d = app.dirty();
  app.view.querySelector(".pchip").innerHTML = chipHTML(app);
  app.view.querySelector('[data-act="revert"]').disabled = !(card && d);
  app.view.querySelector('[data-act="save"]').disabled = !(card && d);
  app.view.querySelector(".pfoot").innerHTML = statsHTML(app);
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
  if (card.builtin) return openSave(app, { text: app.text, from: card.name, copyOf: true, link: true });
  try {
    await app.api.savePreset({ name: card.name, text: app.text, title: card.title, tags: card.tags, note: card.note, overwrite: true });
    app.base = app.text;
    await app.refreshPresets();
    renderPrompt(app);
    app.toast(`Saved <b>@${esc(card.name)}</b>`);
  } catch (e) { app.fail(e); }
}

async function roll(app) {
  const seed = Number(app.bridge.getSeed()) || 0;
  try {
    const { rolls } = await app.api.roll({ template: app.text, seed, n: 3, target: app.bridge.getTarget() });
    app.state.rolls = rolls;
  } catch (e) { app.state.rolls = null; app.fail(e); }
  renderRolls(app);
}

function renderRolls(app) {
  const box = app.view.querySelector(".rolls");
  if (!box) return;
  const seed = Number(app.bridge.getSeed()) || 0;
  box.innerHTML = app.state.rolls
    ? app.state.rolls.map((r) => `<div class="roll"><span class="seed">seed ${r.seed}</span>${markPicks(r.text, r.picks)}`
      + `${r.lint.map((l) => `<span class="lint ${l.severity}">${esc(l.severity)}: ${esc(l.message)}</span>`).join("")}</div>`).join("")
    : `<div class="empty">Roll 3 shows what this template makes at seeds ${seed}–${seed + 2} for the ${esc(app.bridge.getTarget())} target, without queueing anything.</div>`;
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
  const { items, i, ta } = app.ac, { x, y } = caretPoint(ta), item = items[i];
  const box = document.createElement("div");
  box.className = "ac";
  box.style.left = `${Math.max(4, Math.min(x + 8, ta.clientWidth - 250))}px`;
  box.style.top = `${y + 12}px`;
  box.innerHTML = `<ul>${items.map((it, n) => `<li class="${n === i ? "on" : ""}" data-i="${n}"><span>${esc(it.insert.trim())}</span><span>${esc(it.detail)}</span></li>`).join("")}</ul>`
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
