// Settings sheet: where orrery keeps its libraries, presets and galaxy (the home folder), and the
// language model it uses (a text encoder from ComfyUI's text_encoders folder, as in Pixaroma's
// prompt nodes) with how many entries a library it creates starts with.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";

const gb = (bytes) => (bytes ? `${(bytes / 1e9).toFixed(1)} GB` : "");

const HOME_NOTE = {
  env: (h) => `ORRERY_HOME is set to <code>${esc(h)}</code> and wins over this setting; unset it to use the folder below.`,
  setting: () => "Libraries, presets, the galaxy and these settings live here. Existing files are not moved when you change it.",
  default: () => "Libraries, presets, the galaxy and these settings live here; empty means <code>~/.orrery</code>. Existing files are not moved when you change it.",
};

export async function openSettings(app) {
  let s, h;
  try { [s, h] = await Promise.all([app.api.llm(), app.api.homeFolder()]); } catch (e) { return app.fail(e); }
  const options = [`<option value="">None: unknown libraries stay an error</option>`]
    .concat(s.files.map((f) => `<option value="${esc(f.name)}" ${f.name === s.file ? "selected" : ""} ${f.can_write ? "" : "disabled"}>`
      + `${esc(f.name)}${f.size ? ` · ${gb(f.size)}` : ""}${f.can_write ? "" : " · can't write"}</option>`)).join("");
  const sheet = app.openSheet(`<form class="panel">
    <div class="row spread"><h4>Settings</h4></div>
    <div class="field"><label class="label" for="oa-home">Orrery home folder</label>
      <input class="input mono" id="oa-home" value="${esc(h.setting || h.home)}" placeholder="/path/to/orrery" ${h.source === "env" ? "disabled" : ""} spellcheck="false">
      <span class="muted">${HOME_NOTE[h.source](h.home)}</span></div>
    <div class="row spread"><h5 class="label">Language model</h5></div>
    <p class="muted flush">A text encoder that is a whole language model can write: Krea 2's <code>qwen3vl_4b</code> or a Qwen3-VL 8B build.
      MiniMax H3's encoder is cut short and cannot. The model loads when the node runs and writes once; ComfyUI moves it out when the video model needs the room.
      A text encoder wired into the node's <b>clip</b> input wins over this choice.</p>
    <div class="field"><label class="label" for="oa-llm">Model</label><select class="input" id="oa-llm">${options}</select>
      ${s.files.length ? "" : '<span class="warn">No text encoders found (is this running inside ComfyUI?).</span>'}</div>
    <div class="field"><label class="label" for="oa-llm-n">A library it creates starts with</label>
      <div class="row"><input class="input narrow" id="oa-llm-n" type="number" min="1" max="200" value="${s.entries}"><span class="muted">entries · <code>__name:30__</code> asks for at least 30</span></div></div>
    <div class="field"><label class="label" for="oa-llm-t">Max tokens</label>
      <div class="row"><input class="input narrow" id="oa-llm-t" type="number" min="500" max="131072" step="500" value="${s.max_tokens}"><span class="muted">the longest answer it may write in one run; long entries need room</span></div></div>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("save")}Save</button></div>
  </form>`);
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  sheet.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const wanted = sheet.querySelector("#oa-home").value.trim();
      if (h.source !== "env" && wanted !== (h.setting || h.home)) {
        const moved = await app.api.saveHomeFolder(wanted);
        Object.assign(app.data, { libraries: null, rows: null });
        await Promise.all([app.refreshPresets(), app.refreshCompletion()]);
        app.toast(`Home folder: <b>${esc(moved.home)}</b>`);
      }
      app.data.llm = await app.api.saveLlm({ file: sheet.querySelector("#oa-llm").value, entries: Number(sheet.querySelector("#oa-llm-n").value) || 12,
        max_tokens: Number(sheet.querySelector("#oa-llm-t").value) || 16000 });
      app.closeSheet();
      app.render();
      if (app.data.llm.file !== s.file) app.toast(app.data.llm.file ? `Language model: <b>${esc(app.data.llm.file)}</b>` : "No language model: unknown libraries stay an error");
    } catch (err) { app.fail(err); }
  });
}
