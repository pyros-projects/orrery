// Help tab: the DSL at a glance, the tutorial lessons, and model-specific writing tips.
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";

const REF = [
  ["Wildcards", [
    ["__creature__", "one entry from a library, weighted by what you rated", "a __creature__ at dusk"],
    ["__creature[myth]__", "only entries tagged myth", "a __creature[myth]__ asleep"],
    ["{misty|frozen:3}", "inline choice; :3 makes frozen three times as likely", "a {misty|frozen:3} forest"],
    ["{2$$__material__}", "two different picks, joined with commas", "built from {2$$__material__}"],
    ["{1-3$$a|b|c}", "one to three of the options", "a bouquet of {1-3$$roses|thistles|ferns}"],
    ["{a {b|c}|d}", "choices nest; inner ones roll first", "a {lighthouse {keeper|cat}|night ferry}"],
  ]],
  ["Bindings and extras", [
    ["$hero = __creature__", "roll once on its own line, reuse everywhere as $hero", "$hero = __creature__\n$hero meets another $hero"],
    ["> cinematic, moody", "enhancement note: recorded with the picks, not pasted into the prompt", "> cinematic, moody"],
    [": x8 seed=100 w1024 h1344", "batch and size for the CLI", ": x8 seed=100"],
    ["a __creature__", "a/an follows the picked word: “an axolotl”", ""],
  ]],
  ["H3 screenplays", [
    ["@h3 t2va 16:9", "first line: mode (t2va, i2va, fl2va, l2va) and ratio", "@h3 t2va 16:9"],
    ["style: live-action, cinematic", "the look; opens Shot 1", "style: __h3style__"],
    ["SHOT 5s | dissolve, arc, slow", "duration · optional transition · camera · small/large · slow/fast", "SHOT 4s | cut, push in, small, slow"],
    ["KEEPER (raspy voice, voiceover): [French] Bonjour.", "a line of speech; off-screen or voiceover after the voice", "KEEPER (warm, raspy old voice): The ships stopped coming."],
    ["SFX: rain drums on glass; a gong clatters", "sounds as clauses with verbs; they join into “A while B”", "SFX: wind worries the shutters"],
    ["MUSIC: solo cello at a slow tempo, fading out", "instruments, tempo, dynamics; no mood words", "MUSIC: a slow, sparse __instrument__ line that fades out"],
    ["<Picture 1>", "I2VA: anchor the start frame in Shot 1", "The scene begins exactly as in <Picture 1>."],
  ]],
];

const TIPS = [
  ["Krea 2", 'Write sentences, not tag lists. Name the medium, or Krea picks one for you. Put words to render in quotes: a sign reading "OPEN".'],
  ["H3 cuts", "Start shots 2+ with a noun phrase: the compiler writes “the camera cuts to …” in front of it."],
  ["H3 length", "All shots together: 4–15 s. Up to four SFX lines."],
  ["Weights", "(word:1.2) does nothing on H3 or Krea 2; use {a|b:3} to change the odds instead."],
];

export function renderHelp(app) {
  const known = app.known();
  const lessons = app.data.presets.filter((p) => p.name.startsWith("tutorial/"));
  app.view.innerHTML = `<div class="scroll"><div class="help">
    <section><h5 class="label">Lessons · open one, press Roll 3, change something</h5>
      <div class="lessons">${lessons.map((p) => {
        const [num, ...rest] = p.title.split(" · ");
        return `<button class="lesson" data-load="${esc(p.name)}"><span class="ln">${esc(rest.length ? num : "")}</span><span>${esc(rest.join(" · ") || p.title)}</span></button>`;
      }).join("")}</div></section>
    ${REF.map(([h, rows]) => `<section><h5 class="label">${h}</h5><div class="ref">${rows.map(([code, what, ex]) => `<div class="refrow"><pre class="codebox">${highlight(code, known)}</pre>`
      + `<span class="muted">${esc(what)}</span>${ex ? `<button class="btn ghost" data-insert="${esc(ex)}" title="Add to the end of your template">${icon("plus")}Insert</button>` : "<span></span>"}</div>`).join("")}</div></section>`).join("")}
    <section><h5 class="label">Writing for the models</h5><div class="tips">${TIPS.map(([k, t]) => `<p><b>${k}.</b> ${esc(t)}</p>`).join("")}</div></section>
    <section><h5 class="label">Keys in the editor</h5><p class="muted flush"><code>__</code> libraries · <code>__name[</code> tags · <code>$</code> bindings · <code>SHOT 5s |</code> camera words · ↑↓ choose · ↵ or Tab insert · Esc close</p></section>
  </div></div>`;
  app.view.onclick = (e) => {
    const lesson = e.target.closest("[data-load]");
    if (lesson) return app.loadPreset(lesson.dataset.load);
    const ins = e.target.closest("[data-insert]");
    if (!ins) return;
    const text = app.text.replace(/\s*$/, "");
    app.text = `${text}${text ? "\n" : ""}${ins.dataset.insert}`;
    app.go("prompt");
    const ed = app.view.querySelector("textarea");
    ed.focus();
    ed.setSelectionRange(ed.value.length, ed.value.length);
    app.toast("Added to the end of your template");
  };
}
