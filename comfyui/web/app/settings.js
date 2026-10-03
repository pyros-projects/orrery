// Settings sheet: where orrery keeps its libraries, presets and galaxy (the home folder), and the
// language model it uses (a text encoder from ComfyUI's text_encoders folder, as in Pixaroma's
// prompt nodes) with how many entries a library it creates starts with.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";

const gb = (bytes) => (bytes ? `${(bytes / 1e9).toFixed(1)} GB` : "");

// What the Write menu sends the model: each writer a prompt of its own, with only its own rules.
const WRITER_TEXTS = { continue: "Continue the reel", story: "Story between frames", describe: "Prompt from image: an image prompt",
  describe_shot: "Prompt from image: an @h3 i2va shot" };

const HOME_NOTE = {
  env: (h) => `ORRERY_HOME is set to <code>${esc(h)}</code> and wins over this setting; unset it to use the folder below.`,
  setting: () => "Libraries, presets, the gallery and these settings live here. Existing files are not moved when you change it.",
  default: () => "Libraries, presets, the gallery and these settings live here; empty means <code>~/.orrery</code>. Existing files are not moved when you change it.",
};

export async function openSettings(app) {
  let s, h, wr;
  try { [s, h, wr] = await Promise.all([app.api.llm(), app.api.homeFolder(), app.api.writers()]); } catch (e) { return app.fail(e); }
  const drafts = Object.fromEntries(Object.keys(WRITER_TEXTS).map((k) => [k, wr[k].text]));
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
    <div class="row spread"><h5 class="label">Writers</h5></div>
    <p class="muted flush">What the <b>Write</b> menu sends the language model: each writer its own prompt, with only the rules it needs.
      <code>{world}</code> <code>{chunks}</code> <code>{next}</code> <code>{handoff}</code> <code>{seconds}</code> are filled in when it runs; Picture 1 and 2 are the frames it sees.
      An edit is kept in the home folder, so an update of orrery leaves it alone.</p>
    <div class="field"><div class="row"><select class="input" id="oa-wr" aria-label="Writer text">${Object.entries(WRITER_TEXTS).map(([k, label]) =>
      `<option value="${k}">${esc(label)}${wr[k].edited ? " · edited" : ""}</option>`).join("")}</select>
      <button type="button" class="btn ghost" data-wreset title="Back to the text orrery ships">${icon("undo")}Reset to default</button></div>
      <textarea class="input mono wtext" id="oa-wt" spellcheck="false" aria-label="The writer text"></textarea></div>
    <div class="row spread"><h5 class="label">Editor</h5></div>
    <label class="check"><input type="checkbox" id="oa-qs" ${app.data.quickstart !== false ? "checked" : ""}>
      <span><b>New</b> templates open with a quickstart: the essentials as <code># …</code> comments above the template</span></label>
    <label class="check"><input type="checkbox" id="oa-div" ${app.data.dividers !== false ? "checked" : ""}>
      <span><b>Scene dividers</b>: a reel's SCENE lines say which clips they play, when, and how much film is left; the scene of the next clip is marked</span></label>
    <label class="check"><input type="checkbox" id="oa-tl" ${app.data.timeline !== false ? "checked" : ""}>
      <span><b>Timeline</b>: a reel's clips as the reel keeps them (Orrery Film or Chain Video), under each scene or beside the editor (Clips below / beside in the footer), and the frames its <code>REMEMBER:</code> lines take</span></label>
    <div class="field"><label class="label" for="oa-clipmin">Clip size</label>
      <div class="row"><input class="input narrow" id="oa-clipmin" type="number" min="96" max="1600" step="8" value="${app.data.clip_min ?? 360}"><span class="muted">px: a clip's shorter side under its scene, as far as the editor is wide</span></div></div>
    <label class="check"><input type="checkbox" id="oa-log" ${app.data.log_prompts !== false ? "checked" : ""}>
      <span><b>Log each run</b> to ComfyUI's console: its seed, every pick and the resolved prompt (the <b>History</b> tab keeps them either way)</span></label>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("save")}Save</button></div>
  </form>`);
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  const wsel = sheet.querySelector("#oa-wr"), wtext = sheet.querySelector("#oa-wt");
  let wcur = wsel.value;
  wtext.value = drafts[wcur];
  wsel.onchange = () => { drafts[wcur] = wtext.value; wcur = wsel.value; wtext.value = drafts[wcur]; };
  sheet.querySelector("[data-wreset]").onclick = () => { wtext.value = wr[wcur].default; };
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
      const clipMin = Number(sheet.querySelector("#oa-clipmin").value) || 360;
      if (clipMin !== (app.data.clip_min ?? 360)) { Object.assign(app.data, await app.api.saveUi({ clip_min: clipMin })); app.cellsSig = null; }
      drafts[wcur] = wtext.value;
      const edits = Object.keys(drafts).filter((k) => drafts[k] !== wr[k].text);
      for (const k of edits) await app.api.saveWriter(k, drafts[k]);
      app.data.llm = await app.api.saveLlm({ file: sheet.querySelector("#oa-llm").value, entries: Number(sheet.querySelector("#oa-llm-n").value) || 12,
        max_tokens: Number(sheet.querySelector("#oa-llm-t").value) || 16000 });
      app.closeSheet();
      app.render();
      if (app.data.llm.file !== s.file) app.toast(app.data.llm.file ? `Language model: <b>${esc(app.data.llm.file)}</b>` : "No language model: unknown libraries stay an error");
    } catch (err) { app.fail(err); }
  });
}
