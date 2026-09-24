// Test tab: what the template makes, without queueing anything. Rolls show a few seeds (or a
// reel's clips at one seed); Frequencies roll it many times and count every value it picks.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { markPicks, stats } from "./model.js";

const COUNTS = [50, 200, 500];
const SHOWN_VALUES = 24;

function state(app) {
  app.state.test ??= { mode: "rolls", offset: 0, start: 0, n: 200, across: "seeds", rolls: null, freq: null, busy: false };
  return app.state.test;
}

const request = (app) => ({ template: app.text, target: app.bridge.getTarget(), params: app.bridge.getParams() });
const isReel = (app) => !!stats(app.text).h3?.reel && app.bridge.getTarget() !== "text";

export async function runRolls(app) {
  const t = state(app);
  t.mode = "rolls";
  t.busy = true;
  renderTest(app);
  try {
    const seed = (Number(app.bridge.getSeed()) || 0) + (isReel(app) ? 0 : t.offset);
    t.rolls = (await app.api.roll({ ...request(app), seed, n: 3, start: t.start })).rolls;
  } catch (e) { t.rolls = null; app.fail(e); }
  t.busy = false;
  if (app.state.tab === "test") renderTest(app);
}

async function runFrequency(app) {
  const t = state(app);
  t.busy = true;
  renderTest(app);
  try {
    const across = isReel(app) ? t.across : "seeds";
    t.freq = { ...(await app.api.frequency({ ...request(app), seed: Number(app.bridge.getSeed()) || 0, n: t.n, across })), across };
  } catch (e) { t.freq = null; app.fail(e); }
  t.busy = false;
  if (app.state.tab === "test") renderTest(app);
}

function rollsHTML(app, t) {
  const seed = Number(app.bridge.getSeed()) || 0, reel = isReel(app);
  const what = reel ? `clips ${t.start + 1}–${t.start + 6} at seed ${seed}` : `seeds ${seed + t.offset}–${seed + t.offset + 2}`;
  const head = `<button class="btn primary" data-t="roll">${icon("dice")}Roll</button>`
    + `<span class="stat">${esc(what)} · ${esc(app.bridge.getTarget())}</span><span class="grow"></span>`
    + `<button class="btn ghost" data-t="prev" ${(reel ? t.start : t.offset) ? "" : "disabled"}>‹ ${reel ? "Earlier clips" : "Earlier seeds"}</button>`
    + `<button class="btn ghost" data-t="next">${reel ? "Later clips" : "Next seeds"} ›</button>`;
  const body = t.rolls
    ? `<div class="rolls">${t.rolls.map((r) => `<div class="roll"><span class="seed">${r.segment !== undefined ? `clip ${r.segment + 1} · ` : ""}seed ${r.seed}</span>${markPicks(r.text, r.picks)}`
      + `${r.lint.map((l) => `<span class="lint ${l.severity}">${esc(l.severity)}: ${esc(l.message)}</span>`).join("")}</div>`).join("")}</div>`
    : `<div class="empty">Roll shows what this template makes at the node's seed and the two after it${reel ? " (for a reel: its clips at that seed)" : ""}, without queueing anything.</div>`;
  return [head, body];
}

function freqHTML(app, t) {
  const reel = isReel(app);
  const chip = (attr, value, label, on) => `<button class="chip" aria-pressed="${on}" ${attr}="${value}">${label}</button>`;
  const head = `<button class="btn primary" data-t="count">${icon("dice")}Count</button>`
    + COUNTS.map((n) => chip("data-tn", n, `${n}×`, t.n === n)).join("")
    + (reel ? `<span class="sep"></span>${chip("data-ta", "seeds", "across seeds", t.across === "seeds")}${chip("data-ta", "clips", "across clips", t.across === "clips")}` : "")
    + `<span class="grow"></span>`;
  if (!t.freq) {
    return [head, `<div class="empty">Count rolls the template ${t.n} times${reel ? ", over seeds or over the reel's clips at one seed," : ""} and shows how often every value comes up: which options dominate, which never appear, what your ratings have done to the odds.</div>`];
  }
  const { runs, labels, lint } = t.freq;
  const warnings = lint.length ? `<div class="flint">${lint.map((l) => `<span class="lint warn">${esc(l.message)} <b>${l.count}/${runs}</b></span>`).join("")}</div>` : "";
  const groups = labels.map(({ label, values }) => {
    const total = values.reduce((a, v) => a + v.count, 0), top = values[0]?.count || 1;
    const rows = values.slice(0, SHOWN_VALUES).map((v) => `<div class="fbar" style="--w:${(100 * v.count / top).toFixed(1)}%">`
      + `<span class="fv">${esc(v.value)}</span><span class="fc">${(100 * v.count / total).toFixed(v.count / total < 0.1 ? 1 : 0)}%</span></div>`).join("");
    const more = values.length > SHOWN_VALUES ? `<span class="muted">…and ${values.length - SHOWN_VALUES} more</span>` : "";
    return `<section class="fgroup"><h5><code>${esc(label)}</code><span class="muted">${values.length} value${values.length === 1 ? "" : "s"}</span></h5>${rows}${more}</section>`;
  }).join("");
  const summary = `<p class="muted fsum">${runs} ${t.freq.across === "clips" ? "clips" : "runs"} · ${labels.length} rolled slot${labels.length === 1 ? "" : "s"}</p>`;
  return [head, `${summary}${warnings}<div class="freq">${groups || '<div class="empty">This template rolls nothing.</div>'}</div>`];
}

export function renderTest(app) {
  const t = state(app);
  const tab = (k, label) => `<button class="chip" aria-pressed="${t.mode === k}" data-tm="${k}">${label}</button>`;
  const [head, body] = t.mode === "freq" ? freqHTML(app, t) : rollsHTML(app, t);
  app.view.innerHTML = `<div class="bar">${tab("rolls", "Rolls")}${tab("freq", "Frequencies")}<span class="sep"></span>${head}</div>`
    + `<div class="scroll${t.busy ? " busy" : ""}">${body}</div>`;
  app.view.onclick = (e) => {
    const el = e.target.closest("[data-tm],[data-t],[data-tn],[data-ta]");
    if (!el || t.busy) return;
    if (el.dataset.tm) { t.mode = el.dataset.tm; return renderTest(app); }
    if (el.dataset.tn) { t.n = Number(el.dataset.tn); return renderTest(app); }
    if (el.dataset.ta) { t.across = el.dataset.ta; return renderTest(app); }
    const reel = isReel(app);
    if (el.dataset.t === "roll") return runRolls(app);
    if (el.dataset.t === "count") return runFrequency(app);
    if (el.dataset.t === "next") { if (reel) t.start += 6; else t.offset += 3; return runRolls(app); }
    if (el.dataset.t === "prev") { if (reel) t.start = Math.max(0, t.start - 6); else t.offset = Math.max(0, t.offset - 3); return runRolls(app); }
  };
}
