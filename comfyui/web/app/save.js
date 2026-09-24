// The "Save as preset" sheet, used from the editor, the preset detail and galaxy outputs.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";
import { folderColor } from "./model.js";

// text: what gets saved; from: preset name to prefill from; copyOf: saving a built-in under its own
// name; link: afterwards, the editor follows the new preset.
export function openSave(app, { text, from = null, copyOf = false, link = false }) {
  const card = from && app.card(from);
  const userFolders = [...new Set(app.data.presets.filter((p) => !p.builtin && p.folder).map((p) => p.folder))];
  const folder = card?.folder || userFolders[0] || "stills";
  const st = {
    name: copyOf || (card && !card.builtin) ? from : `${folder}/${card ? `${card.name.split("/").pop()}_v2` : ""}`,
    title: card ? card.title + (copyOf ? "" : " (v2)") : "",
    tags: [...(card?.tags || [])],
    note: card?.note || "",
    overwrite: false,
    error: "",
  };
  const allTags = () => [...new Set(app.data.presets.flatMap((p) => p.tags || []))].sort();

  const draw = () => {
    const name = st.name.trim().toLowerCase();
    const existing = app.data.presets.find((p) => p.name === name);
    const shadows = existing?.builtin, clash = existing && !existing.builtin && !st.overwrite;
    const folders = [...new Set([...userFolders, folder, "stills", "h3", "krea"])];
    const sheet = app.openSheet(`<form class="panel">
      <div class="row spread"><h4>${copyOf ? "Make this preset yours" : "Save as preset"}</h4></div>
      <div class="field"><label class="label" for="oa-name">Name · folders are path segments</label>
        <div class="namebox"><span>@</span><input id="oa-name" value="${esc(st.name)}" autocomplete="off" spellcheck="false"></div>
        <div class="row">${folders.map((f) => `<button type="button" class="chip" data-folder="${esc(f)}"><span class="sw" style="background:${folderColor(f)}"></span>${esc(f)}/</button>`).join("")}</div>
        ${shadows ? '<span class="warn">Your copy sits in front of the built-in preset of the same name; the built-in stays untouched.</span>' : ""}
        ${clash ? `<span class="warn">@${esc(name)} already exists. <button type="button" class="btn slim" data-overwrite>Overwrite it</button></span>` : ""}
        ${st.error ? `<span class="warn bad">${esc(st.error)}</span>` : ""}</div>
      <div class="field"><label class="label" for="oa-title">Title</label><input class="input" id="oa-title" value="${esc(st.title)}" placeholder="What you will look for later"></div>
      <div class="field"><span class="label">Tags</span>
        <div class="row">${st.tags.map((t) => `<span class="tagchip">${esc(t)}<button type="button" data-untag="${esc(t)}" aria-label="Remove ${esc(t)}">${icon("x")}</button></span>`).join("")}<input class="tagadd" id="oa-tag" placeholder="+ tag"></div>
        <div class="row">${allTags().filter((t) => !st.tags.includes(t)).slice(0, 12).map((t) => `<button type="button" class="chip" data-tag="${esc(t)}">${esc(t)}</button>`).join("")}</div></div>
      <div class="field"><label class="label" for="oa-note">Note</label><textarea class="input" id="oa-note" rows="2" placeholder="Why this one works">${esc(st.note)}</textarea></div>
      <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button>
        <button class="btn primary" ${clash || !name || name.endsWith("/") ? "disabled" : ""}>${icon("save")}Save @${esc(name || "…")}</button></div>
    </form>`);
    const keep = () => {
      st.name = sheet.querySelector("#oa-name").value;
      st.title = sheet.querySelector("#oa-title").value;
      st.note = sheet.querySelector("#oa-note").value;
    };
    const nameBox = sheet.querySelector("#oa-name");
    nameBox.addEventListener("input", () => {
      const pos = nameBox.selectionEnd;
      keep(); st.overwrite = false; st.error = ""; draw();
      const n = app.$("#oa-name"); n.focus(); n.setSelectionRange(pos, pos);
    });
    sheet.addEventListener("click", (e) => {
      const f = e.target.closest("[data-folder]"), t = e.target.closest("[data-tag]"), u = e.target.closest("[data-untag]");
      if (f) { keep(); st.name = `${f.dataset.folder}/${st.name.split("/").pop()}`; draw(); app.$("#oa-name").focus(); }
      else if (t) { keep(); st.tags.push(t.dataset.tag); draw(); }
      else if (u) { keep(); st.tags = st.tags.filter((x) => x !== u.dataset.untag); draw(); }
      else if (e.target.closest("[data-overwrite]")) { keep(); st.overwrite = true; draw(); }
      else if (e.target.closest("[data-cancel]")) app.closeSheet();
    });
    sheet.querySelector("#oa-tag").addEventListener("keydown", (e) => {
      const v = e.target.value.trim().toLowerCase().replace(/\s+/g, "_");
      if (e.key === "Enter" && v) { e.preventDefault(); keep(); if (!st.tags.includes(v)) st.tags.push(v); draw(); app.$("#oa-tag").focus(); }
    });
    sheet.querySelector("form").addEventListener("submit", async (e) => {
      e.preventDefault();
      keep();
      try {
        const saved = await app.api.savePreset({ name: st.name.trim(), text, title: st.title, tags: st.tags, note: st.note, overwrite: st.overwrite });
        await app.refreshPresets();
        if (link) { app.preset = saved.name; app.base = text; }
        app.closeSheet();
        app.render();
        app.toast(`Saved <b>@${esc(saved.name)}</b>${st.overwrite ? " (overwritten)" : ""}`);
      } catch (err) {
        if (err.status === 409) { st.error = ""; st.overwrite = false; await app.refreshPresets().catch(() => {}); }
        else st.error = err.message;
        draw();
      }
    });
  };
  draw();
  app.$("#oa-name").focus();
}
