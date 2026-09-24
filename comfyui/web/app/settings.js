// Settings sheet: the language model orrery uses (a text encoder from ComfyUI's text_encoders
// folder, as in Pixaroma's prompt nodes) and how many entries a library it creates starts with.
import { esc } from "./highlight.js";
import { icon } from "./icons.js";

const gb = (bytes) => (bytes ? `${(bytes / 1e9).toFixed(1)} GB` : "");

export async function openSettings(app) {
  let s;
  try { s = await app.api.llm(); } catch (e) { return app.fail(e); }
  const options = [`<option value="">None: unknown libraries stay an error</option>`]
    .concat(s.files.map((f) => `<option value="${esc(f.name)}" ${f.name === s.file ? "selected" : ""} ${f.can_write ? "" : "disabled"}>`
      + `${esc(f.name)}${f.size ? ` · ${gb(f.size)}` : ""}${f.can_write ? "" : " · can't write"}</option>`)).join("");
  const sheet = app.openSheet(`<form class="panel">
    <div class="row spread"><h4>Language model</h4></div>
    <p class="muted flush">A text encoder that is a whole language model can write: Krea 2's <code>qwen3vl_4b</code> or a Qwen3-VL 8B build.
      MiniMax H3's encoder is cut short and cannot. The model loads when the node runs, writes, and unloads again.
      A text encoder wired into the node's <b>clip</b> input wins over this choice.</p>
    <div class="field"><label class="label" for="oa-llm">Model</label><select class="input" id="oa-llm">${options}</select>
      ${s.files.length ? "" : '<span class="warn">No text encoders found (is this running inside ComfyUI?).</span>'}</div>
    <div class="field"><label class="label" for="oa-llm-n">A library it creates starts with</label>
      <div class="row"><input class="input narrow" id="oa-llm-n" type="number" min="1" max="200" value="${s.entries}"><span class="muted">entries · <code>__name:30__</code> asks for at least 30</span></div></div>
    <div class="acts"><button type="button" class="btn ghost" data-cancel>Cancel</button><button class="btn primary">${icon("save")}Save</button></div>
  </form>`);
  sheet.querySelector("[data-cancel]").onclick = () => app.closeSheet();
  sheet.querySelector("form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      app.data.llm = await app.api.saveLlm({ file: sheet.querySelector("#oa-llm").value, entries: Number(sheet.querySelector("#oa-llm-n").value) || 12 });
      app.closeSheet();
      app.render();
      app.toast(app.data.llm.file ? `Language model: <b>${esc(app.data.llm.file)}</b>` : "No language model: unknown libraries stay an error");
    } catch (err) { app.fail(err); }
  });
}
