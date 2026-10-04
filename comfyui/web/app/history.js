// History tab: every run of the node as it resolved (seed, segment, dials, picks, the prompt), newest
// first, so a lucky roll can be found and run again even when its output was not kept.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { withDice } from "./model.js";
import { copyText } from "./parts.js";

const PAGE = 50;

async function fetchRuns(app, more = false) {
  const s = app.state, have = more ? app.data.hRuns || [] : [];
  const got = await app.api.history({ q: s.hQuery || "", limit: PAGE, offset: have.length });
  app.data.hRuns = [...have, ...got.runs];
  app.data.hTotal = got.total;
  if (!s.hQuery) app.data.hAll = got.total;  // the tab's count: every run, not a search's
}

// Fetched again when the tab opens and after every run while it is open.
export async function refreshHistory(app) {
  try { await fetchRuns(app); } catch (err) { return app.fail(err); }
  if (app.state.tab === "history") app.render();
}

function when(ts) {
  const d = new Date(ts), today = new Date().toDateString() === d.toDateString();
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return today ? time : `${d.toLocaleDateString([], { day: "numeric", month: "short" })} ${time}`;
}

function rowHTML(r, open) {
  const first = (r.text || "").replace(/\s+/g, " ").slice(0, 160);
  return `<div class="hrow${open ? " open" : ""}" data-hid="${esc(r.id)}">
    <button class="hhead" data-hopen="${esc(r.id)}" aria-expanded="${open}">
      <span class="hwhen mono">${esc(when(r.ts))}</span>
      <span class="tagchip">seed ${esc(String(r.seed))}</span>${r.segment != null ? `<span class="tagchip">clip ${r.segment + 1}</span>` : ""}
      ${r.preset ? `<span class="tagchip">@${esc(r.preset)}${r.edited ? " · edited" : ""}</span>` : ""}
      ${r.issues ? `<span class="warn" title="Lint warnings when it ran">${r.issues} ⚠</span>` : ""}
      <span class="htext">${esc(first)}</span></button>
    ${open ? `<div class="hbody">
      ${(r.picks || []).length ? `<div class="hpicks">${r.picks.map((p) => `<span class="tagchip mono"><b>${esc(p.label)}</b> ${esc(p.value)}</span>`).join("")}</div>` : ""}
      ${Object.keys(r.params || {}).length ? `<p class="muted flush">Dials: ${Object.entries(r.params).map(([k, v]) => `<code>$${esc(k)} = ${esc(v)}</code>`).join(" ")}</p>` : ""}
      <pre class="codebox">${esc(r.text || "")}</pre>
      <div class="acts"><button class="btn primary" data-hact="use" title="The template, its dials and this seed (and segment) back in the Prompt tab, control after generate fixed">${icon("undo")}Use template + seed</button>
        <button class="btn" data-hact="copyp">${icon("copy")}Copy prompt</button><button class="btn" data-hact="copys">${icon("copy")}Copy seed</button></div>
    </div>` : ""}</div>`;
}

export async function renderHistory(app) {
  const s = app.state;
  if (!app.data.hRuns || !s.hFetched) {
    s.hFetched = true;
    if (!app.data.hRuns) app.view.innerHTML = '<div class="empty">Loading the history…</div>';
    return refreshHistory(app);
  }
  const runs = app.data.hRuns, more = runs.length < (app.data.hTotal || 0);
  const scroll = app.view.querySelector(".hist .scroll")?.scrollTop || 0;
  app.view.innerHTML = `<div class="hist">
    <div class="bar"><input class="input" data-hq placeholder="Search prompts, picks, presets, seeds" value="${esc(s.hQuery || "")}" aria-label="Search the history">
      <span class="stat"><b>${app.data.hTotal || 0}</b> run${app.data.hTotal === 1 ? "" : "s"}</span>
      <button class="icon-btn" data-hact="reload" title="Reload the history">${icon("reload")}</button></div>
    <div class="scroll"><p class="rule">Every run of this orrery home as it resolved: the seed, the picks and the prompt, kept even when the output was not (the last 2000 runs).</p>
      ${runs.map((r) => rowHTML(r, r.id === s.hOpen)).join("") || `<div class="empty">${s.hQuery ? "No run matches." : "No runs yet: queue the prompt, and every run lands here."}</div>`}
      ${more ? `<button class="btn ghost hmore" data-hact="more">Show ${Math.min(PAGE, app.data.hTotal - runs.length)} more</button>` : ""}
    </div></div>`;
  app.view.querySelector(".hist .scroll").scrollTop = scroll;
  const q = app.view.querySelector("[data-hq]");
  q.oninput = () => {
    clearTimeout(s.hTimer);
    s.hTimer = setTimeout(async () => {
      s.hQuery = q.value;
      s.hOpen = null;
      try { await fetchRuns(app); } catch (err) { return app.fail(err); }
      renderHistory(app);
      const again = app.view.querySelector("[data-hq]");
      again.focus();
      again.setSelectionRange(again.value.length, again.value.length);
    }, 250);
  };
  app.view.onclick = (e) => onClick(app, e);
}

async function onClick(app, e) {
  const s = app.state, opener = e.target.closest("[data-hopen]");
  if (opener) {
    s.hOpen = s.hOpen === opener.dataset.hopen ? null : opener.dataset.hopen;
    return renderHistory(app);
  }
  const act = e.target.closest("[data-hact]")?.dataset.hact;
  if (act === "reload") return refreshHistory(app);
  if (act === "more") {
    try { await fetchRuns(app, true); } catch (err) { return app.fail(err); }
    return renderHistory(app);
  }
  const r = (app.data.hRuns || []).find((x) => x.id === s.hOpen);
  if (!r) return;
  if (act === "copyp") copyText(app, r.text || "", "Prompt");
  if (act === "copys") copyText(app, String(r.seed), "Seed");
  if (act === "use" && !app.busy()) {
    let kept = false;
    try {
      const text = (await app.api.template(r.template)).text;
      app.text = withDice(text, r);
      kept = app.text !== text;
      app.preset = r.preset || null;
      app.base = r.preset ? text : null;
      app.bridge.setSeed(r.seed);
      app.bridge.setControl("fixed");
      app.bridge.setParams(r.params || {});
      if (r.segment != null) app.bridge.setSegment(r.segment);
    } catch (err) { return app.fail(err); }
    app.go("prompt");
    app.toast(`Template and seed ${r.seed}${r.segment != null ? `, clip ${r.segment + 1}` : ""} restored · control after generate set to <b>fixed</b>: the next run rolls it again with today's libraries and learned weights (they may have changed since; the prompt it made is a copy away)`
      + (kept ? " · replayed as it was made: <b>@rng 1</b> or <b>full</b> added (the dice and the format of back then)" : ""));
  }
}
