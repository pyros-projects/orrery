// Help tab: the DSL at a glance, the tutorial lessons, and model-specific writing tips.
import { esc, highlight } from "./highlight.js";
import { icon } from "./icons.js";

const REF = [
  ["Wildcards", [
    ["__creature__", "one entry from a library, weighted by what you rated", "a __creature__ at dusk"],
    ["__creature[myth]__", "only entries tagged myth", "a __creature[myth]__ asleep"],
    ["__film/genre__", "a library in a folder: library/film/genre.yaml or .txt (one entry per line); the language model creates folder and file when they don't exist", ""],
    ["__runway_shoes:20__", "with a language model set (the gear): an unknown library is created when the node runs, and :20 tops it up to at least 20 entries", ""],
    ["__film_scene__(30 words, set and cast)", "directions for the model that writes the library; they never reach the prompt. New entries wait in Libraries for Accept or Discard", ""],
    ["{misty|frozen:3}", "inline choice; :3 makes frozen three times as likely", "a {misty|frozen:3} forest"],
    ["{2$$__material__}", "two different picks, joined with commas", "built from {2$$__material__}"],
    ["{1-3$$a|b|c}", "one to three of the options", "a bouquet of {1-3$$roses|thistles|ferns}"],
    ["{a {b|c}|d}", "choices nest; inner ones roll first", "a {lighthouse {keeper|cat}|night ferry}"],
  ]],
  ["Bindings and extras", [
    ["$hero = __creature__", "roll once on its own line, reuse everywhere as $hero", "$hero = __creature__\n$hero meets another $hero"],
    ["$hero → dial", "every binding is a dial under the editor: pick an entry or type any expression, empty = its default roll; Save bakes dials in (CLI: --set hero=owl)", ""],
    ["> cinematic, moody", "enhancement note: recorded with the picks, not pasted into the prompt", "> cinematic, moody"],
    [": w832 h1216", "size: the node's width and height outputs (wire them into your latent)", ": w832 h1216"],
    [": x8 seed=100", "CLI only (orrery expand); in ComfyUI use the Run count and the seed widget", ""],
    ["a __creature__", "a/an follows the picked word: “an axolotl”", ""],
  ]],
  ["H3 screenplays", [
    ["@h3 t2va 16:9", "first line: mode (t2va, i2va, fl2va, l2va) and ratio", "@h3 t2va 16:9"],
    ["style: live-action, cinematic", "the look; opens Shot 1 as its own sentence", "style: __h3style__"],
    ["SHOT 5s | dissolve, arc, slow", "duration · optional transition · camera · small/large · slow/fast", "SHOT 4s | cut, push in, small, slow"],
    ["@h3 t2va 9:16", "the ratio sets width and height; all SHOT durations set length, in frames at 24 fps, for the MiniMax H3 latent", ""],
    ["KEEPER (raspy voice, voiceover): [French] Bonjour.", "a line of speech; off-screen or voiceover after the voice", "KEEPER (warm, raspy old voice): The ships stopped coming."],
    ["SFX: rain drums on glass; a gong clatters", "sounds separated by semicolons; they join into “A, B, and C”", "SFX: wind worries the shutters"],
    ["MUSIC: solo cello at a slow tempo, fading out", "instruments, tempo, dynamics; no mood words", "MUSIC: a slow, sparse __instrument__ line that fades out"],
    ["<Picture 1>", "I2VA: anchor the start frame in Shot 1", "The scene begins exactly as in <Picture 1>."],
  ]],
  ["Cast and Ref2VA", [
    ["CAST", "names your references once; mention them by name in shots and the summary", "CAST\nMAYA (image 1): the young blonde woman, in a light-pink shirt"],
    ["DOG (image 2, image 3): the white Samoyed, with a curved tail", "sources in parentheses (image N, video N, video N + audio, refmod NAME), then the description; later mentions use its head noun (“the white Samoyed”)", ""],
    ["@h3 ref2va 16:9 lite", "lite: <Subject N> = … definitions over the three base fields, the hand-written style; works in every mode, text-only subjects too", "@h3 ref2va 16:9 lite"],
    ["voice: audio 1", "on the line after a member: the voice timbre it speaks with", ""],
    ["keep: partial - only the fur colour is kept", "optional retention marker and reason (full, partial, transfer, weak)", ""],
    ["summary: MAYA feeds DOG in CAFE.", "full ref2va's summary; the task types are added for you (lite needs none)", "summary: "],
    ["SHOT 5s | from image 5", "ref2va: the shot begins from a reference picture (to image N: ends on it)", ""],
    ["[audio 1]", "a reference slot in prose; orrery writes the label the node uses", ""],
  ]],
  ["Reels (H3 Motion Context)", [
    ["CHUNK the salon", "one Motion Context clip; everything before the first CHUNK (style, CAST, bindings) is the world and holds for every clip", "CHUNK\nSHOT 5s | push in, slow\n"],
    ["CHUNK the walk repeat 8", "plays this chunk 8 times (repeat forever: until you stop); bindings inside a chunk roll anew every clip", "CHUNK the walk repeat forever\n"],
    ["$look~1", "$look as it was one clip ago (~2: two clips); the model who walks back keeps her look", "$look~1"],
    ["HANDOFF: MAYA reaches the door", "closes this chunk and opens the next with the same words", "HANDOFF: "],
    ["LORA: <lora:name:0.8>", "the lora_stack output, for any loader with a lora_stack input: lines before the first CHUNK always, a chunk's own only there; after LORA: the editor lists your LoRA files; <lora:name:model:clip> sets both strengths", "LORA: "],
    ["context: 22", "the frames Motion Context pins (5, 22, 39, 56); from the second chunk on, Shot 1 and length include them", "context: 22"],
    ["load_index · save_index", "wire them into Load and Save Latent's clip_index; segment counts up by itself, so Run count N (or Run Instant) plays the reel", ""],
  ]],
];

const TIPS = [
  ["Krea 2", 'Write sentences, not tag lists. Name the medium, or Krea picks one for you. Put words to render in quotes: a sign reading "OPEN".'],
  ["H3 cuts", "Start shots 2+ with a noun phrase: the compiler writes “the camera cuts to …” in front of it."],
  ["Any prompt on H3", "A template without SHOT lines (a Krea prompt, say) compiles for h3-base as one 5 s shot. Add a SHOT line when you want to set the duration or the camera."],
  ["H3 length", "All shots together: 4–15 s. Up to four SFX lines. Wire the node's width, height and length into the MiniMax H3 latent node instead of copying them."],
  ["Weights", "(word:1.2) does nothing on H3 or Krea 2; use {a|b:3} to change the odds instead."],
  ["Ref2VA labels", "orrery numbers <Subject N>, <Picture i>, <Video k> and <Audio j> exactly like the Reference to Video node: images and videos by slot, audio after the video soundtracks. In the other modes, cast names expand to their descriptions."],
];

export function renderHelp(app) {
  const known = app.known();
  const lessons = app.data.presets.filter((p) => p.name.startsWith("tutorial/"));
  app.view.innerHTML = `<div class="scroll"><div class="help">
    <section><h5 class="label">Lessons · open one, press Test, change something</h5>
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
