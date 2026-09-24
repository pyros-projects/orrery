// Libraries tab: edit wildcard lists by hand; learned weights shown next to each entry.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";

async function ensure(app) {
  if (app.data.libraries) return;
  try { app.data.libraries = (await app.api.libraries()).libraries; } catch (e) { app.data.libraries = []; app.fail(e); }
}

const libBy = (app, name) => app.data.libraries.find((l) => l.name === name);

export async function renderLibraries(app) {
  if (!app.data.libraries) {
    app.view.innerHTML = '<div class="empty">Loading libraries…</div>';
    await ensure(app);
    if (app.state.tab !== "libraries") return;
  }
  const s = app.state;
  const q = s.libSearch.toLowerCase();
  const libs = app.data.libraries.filter((l) => !q || l.name.includes(q) || l.entries.some((e) => e.value.toLowerCase().includes(q)));
  const L = libBy(app, s.lib) || app.data.libraries[0];
  if (!L) { app.view.innerHTML = '<div class="empty">No libraries yet.</div>'; return; }
  s.lib = L.name;
  const ro = L.source === "builtin";
  const tags = [...new Set(L.entries.flatMap((e) => e.tags))].sort();
  const rows = L.entries.map((e, i) => ({ e, i })).filter(({ e }) => !s.libTag || e.tags.includes(s.libTag));
  const badge = (src) => `<span class="src ${src}">${src === "llm" ? "llm" : src === "user" ? "mine" : "built-in"}</span>`;
  app.view.innerHTML = `<div class="libs">
    <div class="liblist"><label class="search">${icon("search")}<input class="input" id="oa-ls" placeholder="Library or entry…" value="${esc(s.libSearch)}"></label>
      <div class="scroll"><ul>${libs.map((l) => `<li><button class="${l.name === L.name ? "on" : ""}" data-lib="${esc(l.name)}"><span class="ln">__${esc(l.name)}__</span>${badge(l.source)}<span class="lc">${l.entries.length}</span></button></li>`).join("")}</ul></div>
      <div class="addrow">${s.libNew !== null ? '<input class="input mono" id="oa-newlib" placeholder="name, e.g. weather2">' : `<button class="btn wide" data-lact="new">${icon("plus")}New library</button>`}</div></div>
    <div class="libmain">
      <div class="libhead"><h3>__${esc(L.name)}__</h3><span class="stat">${L.entries.length} entries</span>
        ${ro ? '<button class="btn primary" data-lact="own">Make it mine</button>' : `<button class="btn ghost danger" data-lact="del">${icon("trash")}Delete</button>`}</div>
      ${ro ? `<div class="banner">${icon("lock")}Built-in and read-only. <b>Make it mine</b> copies it into your library folder, where yours wins over the built-in.</div>` : ""}
      ${tags.length ? `<div class="bar flat"><span class="label">Tags</span>${tags.map((t) => `<button class="chip" aria-pressed="${s.libTag === t}" data-ltag="${esc(t)}">${esc(t)}</button>`).join("")}</div>` : ""}
      <div class="scroll"><table class="entries"><thead><tr><th class="label">Entry</th><th class="label">Tags</th><th class="label" title="Static weight in the file">Weight</th><th class="label" title="Learned from your galaxy ratings">Learned</th><th></th></tr></thead><tbody>
      ${rows.map(({ e, i }) => rowHTML(e, i, ro)).join("") || '<tr><td colspan="5" class="empty">No entries yet. Add some below.</td></tr>'}
      </tbody></table></div>
      ${ro ? "" : `<div class="addrow"><input class="input" id="oa-add" placeholder="Add entries: one per line or comma-separated, then ↵"><button class="btn" data-lact="add">${icon("plus")}Add</button></div>`}
      <div class="ask">${icon("spark")}<span>Ask the LLM, e.g. “remove all cats and make them a new list feline”: coming in stage 5. It runs in the ComfyUI queue and shows a diff before anything changes.</span></div>
    </div></div>`;
  wire(app, L);
}

function rowHTML(e, i, ro) {
  const lw = e.learned ?? 1, pct = Math.min(50, (Math.abs(Math.log(lw)) / Math.log(4)) * 50);
  const bar = lw >= 1 ? `left:50%;width:${pct}%` : `left:${50 - pct}%;width:${pct}%`;
  return `<tr><td class="v"><input value="${esc(e.value)}" data-ev="${i}" ${ro ? "disabled" : ""} aria-label="Entry"></td>
    <td class="t"><div class="row nowrap">${e.tags.map((t) => `<span class="tagchip">${esc(t)}${ro ? "" : `<button data-rmtag="${i}" data-tag="${esc(t)}" aria-label="Remove tag">${icon("x")}</button>`}</span>`).join("")}`
    + `${ro ? "" : `<input class="tagadd" data-addtag="${i}" placeholder="+ tag">`}</div></td>
    <td class="w"><input type="number" step="0.1" min="0" value="${e.weight}" data-ew="${i}" ${ro ? "disabled" : ""} aria-label="Weight"></td>
    <td><span class="learn ${lw > 1.001 ? "up" : lw < 0.999 ? "dn" : ""}"><span class="bar2"><i class="${lw < 1 ? "down" : ""}" style="${bar}"></i></span>×${lw.toFixed(2)}</span></td>
    <td>${ro ? "" : `<button class="mini" data-rm="${i}" aria-label="Delete entry">${icon("x")}</button>`}</td></tr>`;
}

// Every edit saves the whole list; the previous list is kept for Undo.
async function commit(app, L, entries, { renames, message } = {}) {
  const before = L.entries.map((e) => ({ value: e.value, tags: [...e.tags], weight: e.weight }));
  try {
    const saved = await app.api.saveLibrary({ name: L.name, entries, ...(renames ? { renames } : {}) });
    app.data.libraries = app.data.libraries.map((l) => (l.name === L.name ? saved : l));
    app.refreshCompletion().catch(() => {});
  } catch (e) { app.fail(e); }
  renderLibraries(app);
  if (message) {
    app.toast(message, {
      label: "Undo",
      run: () => {
        const back = renames ? Object.fromEntries(Object.entries(renames).map(([a, b]) => [b, a])) : undefined;
        commit(app, libBy(app, L.name), before, { renames: back });
      },
    });
  }
}

const plain = (L) => L.entries.map((e) => ({ value: e.value, tags: [...e.tags], weight: e.weight }));

function wire(app, L) {
  const s = app.state;
  const ls = app.$("#oa-ls");
  ls.addEventListener("input", () => {
    const pos = ls.selectionEnd;
    s.libSearch = ls.value;
    renderLibraries(app);
    const n = app.$("#oa-ls");
    n.focus();
    n.setSelectionRange(pos, pos);
  });
  app.view.onclick = async (e) => {
    const lib = e.target.closest("[data-lib]");
    if (lib) { s.lib = lib.dataset.lib; s.libTag = null; return renderLibraries(app); }
    const t = e.target.closest("[data-ltag]");
    if (t) { s.libTag = s.libTag === t.dataset.ltag ? null : t.dataset.ltag; return renderLibraries(app); }
    const rm = e.target.closest("[data-rm]");
    if (rm) {
      const entries = plain(L), [gone] = entries.splice(Number(rm.dataset.rm), 1);
      return commit(app, L, entries, { message: `Removed <b>${esc(gone.value)}</b>` });
    }
    const rt = e.target.closest("[data-rmtag]");
    if (rt) {
      const entries = plain(L), entry = entries[Number(rt.dataset.rmtag)];
      entry.tags = entry.tags.filter((x) => x !== rt.dataset.tag);
      return commit(app, L, entries);
    }
    const act = e.target.closest("[data-lact]")?.dataset.lact;
    if (act === "own") {
      try {
        const own = await app.api.ownLibrary(L.name);
        app.data.libraries = app.data.libraries.map((l) => (l.name === L.name ? own : l));
        app.toast(`<b>__${esc(L.name)}__</b> is yours now; edits go to your library folder`);
      } catch (err) { app.fail(err); }
      return renderLibraries(app);
    }
    if (act === "del") {
      const gone = plain(L), name = L.name;
      try { await app.api.deleteLibrary(name); } catch (err) { return app.fail(err); }
      app.data.libraries = app.data.libraries.filter((l) => l.name !== name);
      s.lib = null;
      app.refreshCompletion().then(() => app.render()).catch(() => {});
      renderLibraries(app);
      return app.toast(`Deleted <b>__${esc(name)}__</b>`, {
        label: "Undo",
        run: async () => {
          try {
            const back = await app.api.saveLibrary({ name, entries: gone });
            app.data.libraries = [...app.data.libraries, back].sort((a, b) => a.name.localeCompare(b.name));
            s.lib = name;
            renderLibraries(app);
          } catch (err) { app.fail(err); }
        },
      });
    }
    if (act === "new") { s.libNew = ""; renderLibraries(app); app.$("#oa-newlib").focus(); }
    if (act === "add") addEntries(app, L);
  };
  app.view.onchange = (e) => {
    const v = e.target.dataset.ev, w = e.target.dataset.ew;
    if (v !== undefined) {
      const entries = plain(L), old = entries[Number(v)].value, value = e.target.value.trim();
      if (!value || value === old) { e.target.value = old; return; }
      entries[Number(v)].value = value;
      commit(app, L, entries, { renames: { [old]: value }, message: `Renamed <b>${esc(old)}</b> → <b>${esc(value)}</b>; its learned weight moved along` });
    }
    if (w !== undefined) {
      const entries = plain(L);
      entries[Number(w)].weight = Math.max(0, Number(e.target.value) || 0);
      commit(app, L, entries);
    }
  };
  app.view.onkeydown = (e) => {
    const t = e.target;
    if (t.dataset.addtag !== undefined && e.key === "Enter" && t.value.trim()) {
      const entries = plain(L), entry = entries[Number(t.dataset.addtag)];
      const tag = t.value.trim().toLowerCase().replace(/\s+/g, "_");
      if (!entry.tags.includes(tag)) entry.tags.push(tag);
      commit(app, L, entries);
    }
    if (t.id === "oa-add" && e.key === "Enter") { e.preventDefault(); addEntries(app, L); }
    if (t.id === "oa-newlib" && e.key === "Enter") createLibrary(app, t.value);
    if (t.id === "oa-newlib" && e.key === "Escape") { e.preventDefault(); s.libNew = null; renderLibraries(app); }
  };
}

async function createLibrary(app, raw) {
  const s = app.state, name = raw.trim().toLowerCase().replace(/[^\w]+/g, "_");
  s.libNew = null;
  if (!name) return renderLibraries(app);
  if (libBy(app, name)) { s.lib = name; return renderLibraries(app); }
  try {
    const lib = await app.api.saveLibrary({ name, entries: [] });
    app.data.libraries = [...app.data.libraries, lib].sort((a, b) => a.name.localeCompare(b.name));
    s.lib = name;
  } catch (e) { app.fail(e); }
  await renderLibraries(app);
  app.$("#oa-add")?.focus();
}

function addEntries(app, L) {
  const box = app.$("#oa-add");
  const values = box.value.split(/\n|,/).map((v) => v.trim()).filter(Boolean);
  if (!values.length) return;
  const known = new Set(L.entries.map((e) => e.value.toLowerCase()));
  const fresh = [...new Set(values)].filter((v) => !known.has(v.toLowerCase()));
  const skipped = values.length - fresh.length;
  commit(app, L, [...plain(L), ...fresh.map((value) => ({ value, tags: [], weight: 1 }))], {
    message: `Added ${fresh.length} entr${fresh.length === 1 ? "y" : "ies"}${skipped ? ` · ${skipped} already there` : ""}`,
  }).then(() => app.$("#oa-add")?.focus());
}
