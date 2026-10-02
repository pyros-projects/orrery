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
    <div class="row spread"><h5 class="label">Editor</h5></div>
    <label class="check"><input type="checkbox" id="oa-qs" ${app.data.quickstart !== false ? "checked" : ""}>
      <span><b>New</b> templates open with a quickstart: the essentials as <code># …</code> comments above the template</span></label>
    <label class="check"><input type="checkbox" id="oa-div" ${app.data.dividers !== false ? "checked" : ""}>
      <span><b>Chunk dividers</b>: a reel's CHUNK lines say which segments they play, when, and how much film is left; the chunk of the next segment is marked</span></label>
    <label class="check"><input type="checkbox" id="oa-tl" ${app.data.timeline !== false ? "checked" : ""}>
      <span><b>Timeline</b>: a reel's clips as the reel keeps them (Orrery Film or Chain Video), beside the editor or under each chunk (Clips beside / below in the footer), and the frames its <code>SEND:</code> lines handed on</span></label>
    <label class="check"><input type="checkbox" id="oa-log" ${app.data.log_prompts !== false ? "checked" : ""}>
      <span><b>Log each run</b> to ComfyUI's console: its seed, every pick and the resolved prompt (the <b>History</b> tab keeps them either way)</span></label>
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
      const flags = { quickstart: sheet.querySelector("#oa-qs").checked, dividers: sheet.querySelector("#oa-div").checked,
        timeline: sheet.querySelector("#oa-tl").checked, log_prompts: sheet.querySelector("#oa-log").checked };
      if (Object.entries(flags).some(([k, on]) => on !== (app.data[k] !== false))) Object.assign(app.data, await app.api.saveUi(flags));
      app.data.llm = await app.api.saveLlm({ file: sheet.querySelector("#oa-llm").value, entries: Number(sheet.querySelector("#oa-llm-n").value) || 12,
        max_tokens: Number(sheet.querySelector("#oa-llm-t").value) || 16000 });
      app.closeSheet();
      app.render();
      if (app.data.llm.file !== s.file) app.toast(app.data.llm.file ? `Language model: <b>${esc(app.data.llm.file)}</b>` : "No language model: unknown libraries stay an error");
    } catch (err) { app.fail(err); }
  });
}
