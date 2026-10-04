import { test } from "node:test";
import assert from "node:assert/strict";
import { highlight } from "../../comfyui/web/app/highlight.js";
import { openLibraries, writerBlock } from "../../comfyui/web/app/write.js";
import {
  applyDials, dials, downstream, nextSeed, queueSweep, entryPage, libraryHead, filterPresets, folderDropPath, folderTree, libraryGroups, filterRows, glyph, markPicks, pickerGroups,
  chunkInfo, chunkLabel, splitCells, rangeIds, shape, stats, PLAN_HINT, templateHash, hasGoto, plays, longForm, matches, splitOptions, tagsMatch, withDice,
} from "../../comfyui/web/app/model.js";

const known = new Set(["creature", "place"]);

test("libraries are coloured, unknown ones flagged", () => {
  const html = highlight("a __creature__ in __nowhere__", known);
  assert.match(html, /<span class="t-lib">__creature__<\/span>/);
  assert.match(html, /<span class="t-lib t-miss">__nowhere__<\/span>/);
});

test("bindings, braces and multi-picks are coloured", () => {
  const html = highlight("$hero = {1-2$$a|b}", known);
  assert.match(html, /<span class="t-var">\$hero<\/span>/);
  assert.match(html, /<span class="t-brace">1-2\$\$<\/span>/);
  assert.equal((html.match(/t-brace/g) || []).length, 4);
});

test("screenplay lines get keyword colours and html is escaped", () => {
  const html = highlight("@h3 t2va 16:9\nSHOT 5s: push in\nKEEPER (warm voice): Hi\nSFX: rain\nThe start of <Picture 1>.", known);
  assert.match(html, /<span class="t-head">@h3 t2va 16:9<\/span>/);
  assert.match(html, /<span class="t-kw">SHOT 5s:<\/span>/);
  assert.match(highlight("@h3 t2va\nSHOT 5s | push in", known), /<span class="t-kw">SHOT 5s<\/span>/);
  assert.match(html, /<span class="t-kw">KEEPER \(warm voice\):<\/span>/);
  assert.match(html, /<span class="t-kw">SFX:<\/span>/);
  assert.match(html, /&lt;Picture 1&gt;/);
});

test("keyword lines keep their colour without a space after the colon", () => {
  const html = highlight("LORA:<lora:a:0.8>\nHANDOFF:she waves\nSEND:frame 0 to image 3\nGOTO:the walk\nSET:image_1(0.5)", known);
  for (const kw of ["LORA:", "HANDOFF:", "SEND:", "GOTO:", "SET:"]) assert.match(html, new RegExp(`<span class="t-kw">${kw}</span>`));
  assert.match(html, /<span class="t-lora">&lt;lora:a:0.8&gt;<\/span>/);
});

test("screenplay cast lines are keywords", () => {
  const html = highlight("CAST\nsummary: MAYA meets DOG.\nvoice: audio 1", known);
  assert.match(html, /<span class="t-kw">CAST<\/span>/);
  assert.match(html, /<span class="t-kw">summary:<\/span>/);
  assert.match(html, /<span class="t-kw">voice:<\/span>/);
});

test("enhance line, and the params line marks CLI-only parts", () => {
  const html = highlight("> moody\n: x8 seed=100 w832 h1216", known);
  assert.match(html, /<span class="t-enh">&gt; moody<\/span>/);
  assert.match(html, /<span class="t-cli" title="[^"]*">x8<\/span>/);
  assert.match(html, /<span class="t-cli" title="[^"]*">seed=100<\/span>/);
  assert.match(html, /<span class="t-param">w832<\/span>/);
});

test("shape mirrors the node's width, height and H3 length outputs", () => {
  assert.deepEqual(shape("a fox"), { width: 1024, height: 1024, length: 124, megapixels: 1.049, cli: [] });
  assert.deepEqual(shape("a fox\n: x8 seed=100 w832 h1216"), { width: 832, height: 1216, length: 124, megapixels: 1.012, cli: ["x8", "seed=100"] });
  assert.deepEqual(shape("@h3 t2va 16:9\nSHOT 5s\nA."), { width: 1344, height: 768, length: 124, megapixels: 1.032, cli: [] });
  assert.deepEqual(shape("@h3 t2va 9:16\nSHOT 4s\nA.\nSHOT 3s\nB.\nSHOT 4s\nC."), { width: 768, height: 1344, length: 277, megapixels: 1.032, cli: [] });
  assert.equal(shape("@h3 t2va 21:9\nSHOT 4s\nA.").width, 1536);
  assert.equal(shape("@h3 ref2va lite 9:16\nSHOT 4s\nA.").height, 1344);
  const mp = shape("@h3 ref2va 16:9 0.6MP\nSHOT 4s\nA.");
  assert.deepEqual([mp.width, mp.height, mp.megapixels], [1024, 576, 0.6]);
  assert.deepEqual([shape("@h3 t2va 0.5mp\nSHOT 4s\nA.").width, shape("@h3 t2va 0.5mp\nSHOT 4s\nA.").height], [704, 704]);
  assert.deepEqual([shape("@h3 t2va 16:9 0.6MP\n: w1216 h832\nA.").width, shape("@h3 t2va 16:9 0.6MP\n: w1216 h832\nA.").height], [1216, 832]);
});

test("template hash matches orrery's sha256 prefix", () => {
  assert.equal(templateHash("a __creature__"), "f8ad7a7fd793fbc4");
  assert.equal(templateHash(""), "e3b0c44298fc1c14");
  assert.equal(templateHash("Späti 🌙\n$x = {a|b}"), "7fe816c6c2103fe3");
});

test("stats count rolls, libraries, bindings and H3 timing", () => {
  const s = stats("$a = __creature__\n{x|y} in __place__ and __creature__");
  assert.deepEqual([s.rolls, s.libs, s.binds, s.h3], [4, 2, 1, null]);
  const h = stats("@h3 t2va\nSHOT 3s: static\nA.\nNARRATOR (voiceover): Hi\nSHOT 2.5s: cut, arc\nB.\nSFX: wind");
  assert.deepEqual(h.h3, { shots: 2, secs: 5.5, voices: 1, reel: null });
  const r = stats("@h3 ref2va\nCAST\nMAYA (video 1): a woman\nDOG (image 1): a dog\nSHOT 5s\nMAYA waves.\nMAYA (warm): Hi.\nSFX: wind");
  assert.equal(r.h3.voices, 1);
});

test("picks are marked once each, longest first", () => {
  const html = markPicks("a red panda and a panda", [{ value: "red panda" }, { value: "panda" }]);
  assert.equal(html, "a <mark>red panda</mark> and a <mark>panda</mark>");
  assert.equal(markPicks("wax, marble", [{ value: "wax, marble" }]), "<mark>wax</mark>, <mark>marble</mark>");
});

test("glyph is deterministic per key", () => {
  assert.equal(glyph("krea/a", "#fff"), glyph("krea/a", "#fff"));
  assert.notEqual(glyph("krea/a", "#fff"), glyph("krea/b", "#fff"));
  assert.match(glyph("x", "#fff"), /^<svg/);
});

const cards = [
  { name: "krea/tiny", folder: "krea", title: "Tiny world", note: "diorama", tags: ["krea"], text: "", builtin: true },
  { name: "stills/forest", folder: "stills", title: "Forest", note: "", tags: ["moody"], text: "", builtin: false },
  { name: "top", folder: "", title: "Top", note: "", tags: [], text: "", builtin: false },
];

test("preset filters: favorites, recent order, folder, search", () => {
  const fav = new Set(["stills/forest"]);
  const recent = ["top", "krea/tiny"];
  assert.deepEqual(filterPresets(cards, { filter: "fav", favorites: fav }).map(c => c.name), ["stills/forest"]);
  assert.deepEqual(filterPresets(cards, { filter: "recent", recent }).map(c => c.name), ["top", "krea/tiny"]);
  assert.deepEqual(filterPresets(cards, { filter: "f:mine" }).map(c => c.name), ["top"]);
  assert.deepEqual(filterPresets(cards, { filter: "all", search: "DIORAMA" }).map(c => c.name), ["krea/tiny"]);
});

test("picker groups favorites and recents first, folders after", () => {
  const groups = pickerGroups(cards, { query: "", favorites: new Set(["krea/tiny"]), recent: ["top"] });
  assert.deepEqual(groups.map(g => g[0]), ["Favorites", "Recent", "krea", "stills", "mine"]);
  assert.deepEqual(pickerGroups(cards, { query: "forest", favorites: new Set(), recent: [] }).map(g => g[0]), ["stills"]);
});

test("galaxy rows filter by scope, rating and pick", () => {
  const rows = [
    { id: "1", template: "aaa", rating: "love", picks: [{ keys: ["__c__=fox"] }] },
    { id: "2", template: "bbb", rating: null, picks: [{ keys: ["__c__=owl"] }] },
  ];
  assert.deepEqual(filterRows(rows, { scope: "prompt", hash: "bbb" }).map(r => r.id), ["2"]);
  assert.deepEqual(filterRows(rows, { scope: "all", rating: "unrated" }).map(r => r.id), ["2"]);
  assert.deepEqual(filterRows(rows, { scope: "all", rating: "love" }).map(r => r.id), ["1"]);
  assert.deepEqual(filterRows(rows, { scope: "all", pick: "__c__=owl" }).map(r => r.id), ["2"]);
  const owned = [{ id: "1", template: "aaa", preset: "krea/x", rating: null, picks: [] }, { id: "2", template: "bbb", preset: null, rating: null, picks: [] }];
  assert.deepEqual(filterRows(owned, { scope: "preset", preset: "krea/x" }).map(r => r.id), ["1"]);
  assert.deepEqual(filterRows(owned, { scope: "preset", preset: null }).map(r => r.id), []);
});

test("galaxy folders become a tree: parents first, children sorted by name, own counts", () => {
  const tree = folderTree([{ path: "b", count: 2 }, { path: "a/z", count: 1 }, { path: "a", count: 0 }, { path: "a/Y/deep", count: 4 }]);
  const flat = (nodes, depth = 0) => nodes.flatMap((n) => [`${"  ".repeat(depth)}${n.name}:${n.count}`, ...flat(n.children, depth + 1)]);
  assert.deepEqual(flat(tree), ["a:0", "  Y:0", "    deep:4", "  z:1", "b:2"]);
  assert.equal(tree[0].children[0].children[0].path, "a/Y/deep");
});

test("shift-click selects from the anchor to the card, in the order shown", () => {
  const ids = ["a", "b", "c", "d"];
  assert.deepEqual(rangeIds(ids, "b", "d"), ["b", "c", "d"]);
  assert.deepEqual(rangeIds(ids, "d", "b"), ["b", "c", "d"]);
  assert.deepEqual(rangeIds(ids, "gone", "c"), ["c"]);
  assert.deepEqual(rangeIds(ids, null, "a"), ["a"]);
});

test("a folder dropped on a folder nests; on the top level it moves up; never into itself", () => {
  assert.equal(folderDropPath("a/b", "c"), "c/b");
  assert.equal(folderDropPath("a/b", ""), "b");
  assert.equal(folderDropPath("a/b", "a"), null);
  assert.equal(folderDropPath("a", "a/b"), null);
  assert.equal(folderDropPath("a", "a"), null);
  assert.equal(folderDropPath("ab", "a"), "a/ab");
});

test("dials are the bindings, with choices for a library or a brace", () => {
  const d = dials("$hero = __creature[myth]__\n  $mood = {calm|eerie:3}\n$n = {1-2$$a|b}\n$x = a fox\n$hero at dusk");
  assert.deepEqual(d.map((x) => x.name), ["hero", "mood", "n", "x"]);
  assert.deepEqual(d[0], { name: "hero", expr: "__creature[myth]__", lib: "creature", tag: "myth", options: [] });
  assert.deepEqual(d[1].options, ["calm", "eerie"]);
  assert.deepEqual([d[2].lib, d[2].options, d[3].options], [null, [], []]);
});

test("applyDials mirrors orrery's override", () => {
  const t = "$hero = __animal__\n  $place = {a|b}\n$hero in $place";
  assert.equal(applyDials(t, { hero: "owl", place: " " }), "$hero = owl\n  $place = {a|b}\n$hero in $place");
  assert.equal(applyDials(t, {}), t);
});

test("reels: chunk timing, per-chunk lengths, keywords are not voices", () => {
  const reel = "@h3 t2va 16:9\nLORA: <lora:a:1>\ncontext: 22\nCHUNK\nSHOT 5s\nA.\nHANDOFF: b\nSEND: frame 0 to image 3\nCHUNK the hall\nSHOT 3s\nB.\nSHOT 1s\nC.";
  const st = stats(reel);
  assert.deepEqual([st.h3.voices, st.h3.reel], [0, { chunks: 2, secs: [5, 4], repeats: [1, 1], fresh: [true, false], clips: 2 }]);
  const out = shape(reel);
  assert.deepEqual([out.length, out.lengths], [124, [124, 124]]);
  assert.deepEqual(shape(reel.replace("context: 22", "context: 56")).lengths, [124, 158]);
  assert.equal(stats("@h3 t2va\nSHOT 5s\nA.").h3.reel, null);
});

test("reel lines are keywords", () => {
  const html = highlight("CHUNK the hall\nHANDOFF: the door\nLORA: <lora:a:1>\ncontext: 22", known);
  for (const kw of ["CHUNK", "HANDOFF:", "LORA:", "context:"]) assert.match(html, new RegExp(`<span class="t-kw">${kw}`));
});

test("lora tags are coloured as loras, not as libraries, and are not counted", () => {
  const html = highlight("LORA: <lora:bf16__apply__x:1.00> __creature__", known);
  assert.match(html, /<span class="t-lora">&lt;lora:bf16__apply__x:1.00&gt;<\/span>/);
  assert.doesNotMatch(html, /t-miss/);
  assert.deepEqual([stats("LORA: <lora:a__b__c:1.00>").libs, stats("LORA: <lora:a__b__c:1.00>").rolls], [0, 0]);
});

test("repeated chunks count as clips; forever has no end", () => {
  const loop = "@h3 t2va\nCHUNK intro\nSHOT 5s\nA.\nCHUNK walk repeat 8\nSHOT 6s\nB.";
  assert.deepEqual(stats(loop).h3.reel, { chunks: 2, secs: [5, 6], repeats: [1, 8], fresh: [true, false], clips: 9 });
  const forever = stats(loop.replace("repeat 8", "repeat forever")).h3.reel;
  assert.deepEqual([forever.repeats, forever.clips], [[1, Infinity], Infinity]);
});

test("history references are coloured as variables", () => {
  assert.match(highlight("$look~1 walks back", known), /<span class="t-var">\$look~1<\/span>/);
});

test("a binding repeated in several chunks is one dial", () => {
  assert.deepEqual(dials("$a = x\nCHUNK\n$b = __creature__\nCHUNK\n$b = __creature__\n$a = y").map((d) => d.name), ["a", "b"]);
});

test("__name:N__ is a library everywhere; with an LLM an unknown one is to be made", () => {
  assert.match(highlight("a __creature:30__", known), /<span class="t-lib">__creature:30__<\/span>/);
  assert.match(highlight("a __shoes:20__", known), /t-lib t-miss/);
  assert.match(highlight("a __shoes__", known, { llm: true }), /<span class="t-lib t-new" title="[^"]*">__shoes__<\/span>/);
  assert.equal(stats("__creature:30__ and __shoes__").libs, 2);
  assert.deepEqual(dials("$s = __shoes:20__")[0].lib, "shoes");
});

test("libraries group: review first, then folders by prefix, then the rest", () => {
  const lib = (name, extra = {}) => ({ name, entries: [], pending: false, pending_entries: [], ...extra });
  const groups = libraryGroups([lib("couture_form"), lib("animal"), lib("couture_house"), lib("film_scene", { pending: true }),
    lib("bh_route"), lib("style", { pending_entries: ["ink"] }), lib("bh_host"), lib("h3style")]);
  assert.deepEqual(groups.map((g) => [g.key, g.items.map((i) => i.short)]), [
    ["review", ["film_scene", "style"]],
    ["bh", ["host", "route"]],
    ["couture", ["form", "house"]],
    ["", ["animal", "h3style"]],
  ]);
  const withRoot = libraryGroups([lib("curator"), lib("curator_line"), lib("h3style")]);
  assert.deepEqual(withRoot.map((g) => [g.key, g.items.map((i) => i.short)]), [["curator", ["curator", "line"]], ["", ["h3style"]]]);
});

test("directions after a library belong to it", () => {
  assert.match(highlight("__film__(30 words, the set)", known), /<span class="t-lib t-miss">__film__\(30 words, the set\)<\/span>/);
  assert.equal(dials("$s = __film:5__(long)")[0].lib, "film");
});

test("libraries in folders: highlighted, counted, dialed and grouped by their folder", () => {
  const withFilm = new Set([...known, "film/genre"]);
  assert.match(highlight("a __film/genre__ noir", withFilm), /<span class="t-lib">__film\/genre__<\/span>/);
  assert.equal(stats("__film/genre__ and __film/moods:3__").libs, 2);
  assert.equal(dials("$g = __film/genre__")[0].lib, "film/genre");
  const lib = (name) => ({ name, entries: [], pending: false, pending_entries: [] });
  const groups = libraryGroups([lib("film/genre"), lib("style"), lib("film/moods"), lib("couture_form"), lib("couture_house")]);
  assert.deepEqual(groups.map((g) => [g.key, g.items.map((i) => i.short)]),
    [["couture", ["form", "house"]], ["film", ["genre", "moods"]], ["", ["style"]]]);
});

test("property filters are part of a library everywhere", () => {
  const withPeople = new Set([...known, "characters/cyberpunk"]);
  assert.match(highlight("a __characters/cyberpunk#gender:female__ runs", withPeople),
    /<span class="t-lib">__characters\/cyberpunk#gender:female__<\/span>/);
  assert.equal(stats("__characters/cyberpunk#gender:female#age:30s:2__").libs, 1);
  assert.equal(dials("$hero = __characters/cyberpunk#gender:female__")[0].lib, "characters/cyberpunk");
});

test("a big library shows a page at a time, and a search shows only matching entries", () => {
  const entries = Array.from({ length: 7071 }, (_, i) => ({ value: i === 4242 ? "neon pink tee" : `prompt ${i}`, tags: [] }));
  const page = entryPage(entries, { name: "pyro/general_prompts" });
  assert.equal(page.rows.length, 200); assert.equal(page.total, 7071);
  assert.equal(entryPage(entries, { name: "pyro/general_prompts", shown: 400 }).rows.length, 400);
  const hit = entryPage(entries, { name: "pyro/general_prompts", query: "Neon" });
  assert.deepEqual([hit.total, hit.rows[0].i], [1, 4242]);
  assert.equal(entryPage(entries, { name: "pyro/general_prompts", query: "general" }).total, 7071);  // the name matched
});

test("dynamic prompts weights are no part of a dial's choices", () => {
  assert.deepEqual(dials("$c = {3::red|1::blue|green}")[0].options, ["red", "blue", "green"]);
});

test("a property of a binding is coloured as part of the variable", () => {
  assert.match(highlight("steps: $w.sfx", known), /<span class="t-var">\$w\.sfx<\/span>/);
});

test("generate finds the output nodes downstream of the orrery node, and whether Orrery Log is there", () => {
  const nodes = [
    { id: 9, type: "OrreryPrompt", output: false, targets: [12, 20] },
    { id: 12, type: "CLIPTextEncode", output: false, targets: [30] },
    { id: 20, type: "EmptyImage", output: false, targets: [31] },
    { id: 30, type: "KSampler", output: false, targets: [31] },
    { id: 31, type: "SaveImage", output: true, targets: [] },
    { id: 40, type: "SaveImage", output: true, targets: [] },  // not downstream
  ];
  assert.deepEqual(downstream(nodes, 9), { outputs: [31], log: false });
  nodes[0].targets.push(41); nodes.push({ id: 41, type: "OrreryLog", output: true, targets: [] });
  assert.deepEqual(downstream(nodes, 9), { outputs: [31, 41], log: true });
});

test("a library's line in the list counts its entries and what waits for review, without carrying them", () => {
  const lib = { name: "film/genre", source: "user", entries: [{ value: "noir" }, { value: "western" }], tags: ["dark"],
    pending: false, pending_entries: ["western"], directions: "" };
  const head = libraryHead(lib);
  assert.deepEqual(head, { name: "film/genre", source: "user", count: 2, tags: ["dark"], pending: false, pending_count: 1, directions: "" });
  assert.equal(libraryGroups([head, libraryHead({ ...lib, name: "style", pending_entries: [] })])[0].key, "review");  // the count is enough
});

test("a sweep holds the seed for its runs, steps it between seeds and once after the last run", async () => {
  const sweep = async (mode, seeds, stopAfter = Infinity) => {
    let seed = 100, ran = 0;
    const used = [];
    const queued = await queueSweep({
      count: 3, seeds, mode, getSeed: () => seed, setSeed: (s) => { seed = s; },
      queue: async (i) => { used.push([seed, i]); ran++; }, live: () => ran < stopAfter,
    });
    return { queued, used, seed };
  };
  const inc = await sweep("increment", 2);
  assert.equal(inc.queued, 6);
  assert.deepEqual(inc.used, [[100, 0], [100, 1], [100, 2], [101, 0], [101, 1], [101, 2]]);
  assert.equal(inc.seed, 102);  // the next Roll starts on a seed of its own
  assert.equal((await sweep("fixed", 2)).seed, 100);
  const rnd = await sweep("randomize", 1);
  assert.deepEqual(rnd.used.map(([s]) => s), [100, 100, 100]);  // one character from every side
  assert.notEqual(rnd.seed, 100);
  const stopped = await sweep("increment", 3, 4);  // Stop after four runs: still a seed of its own next
  assert.deepEqual([stopped.queued, stopped.seed], [4, 102]);
  assert.equal(await queueSweep({ count: 2, seeds: 1, mode: "increment", getSeed: () => 7, setSeed: () => assert.fail(), queue: async () => {}, live: () => false }), 0);
  assert.equal(nextSeed(0, "decrement"), 0);
});

test("# lines are comments: grey, and nothing in them rolls, counts or opens a screenplay", () => {
  const src = "# Quickstart: __ideas__ and $x = __animal__\n@h3 t2va 16:9 0.6MP\n# SHOT 9s: pan left\nSHOT 5s: static\nA fox.";
  assert.match(highlight(src, new Set()), /<span class="t-comment"># Quickstart: __ideas__ and \$x = __animal__<\/span>/);
  const st = stats(src);
  assert.deepEqual([st.rolls, st.libs, st.binds, st.h3.shots, st.h3.secs], [0, 0, 0, 1, 5]);
  assert.deepEqual([shape(src).width, shape(src).height], [1024, 576]);
  assert.deepEqual(dials(src), []);
});

test("every New template opens with a quickstart and its dials come from code, not from comments", async () => {
  const { STARTERS } = await import("../../comfyui/web/app/starters.js");
  for (const [kind, s] of Object.entries(STARTERS)) {
    assert.match(s.text, /^# .+quickstart/i, kind);
    const code = s.text.split("\n").filter((l) => l && !l.startsWith("#"));
    assert.ok(code.length > 1, kind);
    assert.equal(dials(s.text).length, dials(code.join("\n")).length, kind);
    if (s.target === "h3-base") assert.ok(stats(s.text).h3, kind);
  }
  assert.equal(stats(STARTERS.reel.text).h3.reel.chunks, 2);
});


const REEL_TEXT = `@h3 t2va 16:9
# CHUNK in a comment is no chunk
CHUNK the opening
SHOT 5s: push in
A.
CHUNK the walk repeat 4
SHOT 4s: static
B.
SHOT 1s: cut
C.
CHUNK the end
SHOT 10s: static
D.`;

test("every CHUNK line knows its segments, where it sits in the film and what is left", () => {
  const info = chunkInfo(REEL_TEXT);
  assert.deepEqual(info.map((c) => [c.line, c.first, c.last, c.secs, c.start, c.end, c.left]),
    [[2, 0, 0, 5, 0, 5, 30], [5, 1, 4, 5, 5, 25, 10], [10, 5, 5, 10, 25, 35, 0]]);
  assert.equal(chunkLabel(info[0]), "clip 1 · 0:00 → 0:05 · 0:30 left");
  assert.equal(chunkLabel(info[1]), "clips 2–5 · 4 × 5 s · 0:05 → 0:25 · 0:10 left");
  assert.equal(chunkLabel(info[2]), "clip 6 · 0:25 → 0:35 · the end");
  assert.equal(chunkInfo("@h3 t2va\nSHOT 5s\nA."), null);
  const sends = chunkInfo("CHUNK a\nSHOT 5s\nSEND: frame 0 to image 1\nSEND: frames -1 to image 3 for segment 4+\nSEND: frame 9 to image 1 for segment 9\nA.");
  assert.deepEqual(sends[0].images, [1, 3]);
  assert.deepEqual(chunkInfo("SCENE a\nSHOT 5s\nREMEMBER: first frame as image 2\nA.")[0].images, [2]);
});

test("SCENE, ×N and forever give what CHUNK and repeat gave, and CUT TO: walks the reel as GOTO: did", () => {
  const film = REEL_TEXT.replaceAll("CHUNK", "SCENE").replace("repeat 4", "×4");
  const fields = (info) => info.map((c) => [c.line, c.title, c.repeat, c.first, c.last, c.secs, c.label]);
  assert.deepEqual(fields(chunkInfo(film)), fields(chunkInfo(REEL_TEXT)));
  assert.deepEqual(splitCells(film).map((c) => [c.line, c.chunk]), splitCells(REEL_TEXT).map((c) => [c.line, c.chunk]));
  assert.equal(stats(film).h3.reel.clips, 6);
  assert.deepEqual(chunkInfo("SCENE a forever\nSHOT 5s\nA.\nSCENE the 4x4 room\nSHOT 5s\nB.").map((c) => [c.title, c.repeat]),
    [["a", Infinity], ["the 4x4 room", 1]]);
  assert.ok(hasGoto("SCENE a\nSHOT 5s\nA.\nCUT TO: a ×2") && hasGoto("? $w[rain]: CUT TO: a") && !hasGoto("SCENE a\nSHOT 5s\nA."));
});

test("a test scene starts afresh, and so does the first scene after only tests: no pinned context", () => {
  const reel = "@h3 text\ncontext: 22\nSCENE forest (test)\nSHOT 5s\nA.\nSCENE beach (test)\nAFTER: forest\nSHOT 5s\nB.\n"
    + "SCENE walk\nSHOT 5s\nC.\nSCENE end\nSHOT 5s\nD.\nSCENE dune (test)\nSHOT 5s\nE.";
  assert.deepEqual(stats(reel).h3.reel.fresh, [true, false, true, false, true]);
  const [a, b, c, d, e] = shape(reel).lengths;
  assert.ok(b > a && c === a && d > a && e === a, `${a} ${b} ${c} ${d} ${e}`);
  assert.deepEqual(chunkInfo(reel).map((x) => x.title), ["forest", "beach", "walk", "end", "dune"]);
});

test("a chunk that repeats forever runs on, and the ones after it never play", () => {
  const info = chunkInfo("CHUNK a\nSHOT 5s\nA.\nCHUNK b repeat forever\nSHOT 6s\nB.\nCHUNK c\nSHOT 5s\nC.");
  assert.equal(chunkLabel(info[1]), "clip 2 → ∞ · 6 s each · from 0:05");
  assert.equal(chunkLabel(info[2]), "never plays: a scene before it repeats forever");
  assert.equal(chunkLabel(info[0]), "clip 1 · 0:00 → 0:05");
});

test("the film words are keywords, and a CAST member is brass, with @ or without, also in SET: and speech", () => {
  const text = "@h3 references\nCAST\n@JINX (refmod x): a woman\nSCENE the room (test)\nAFTER: 2\nSTART WITH: the door\nSHOT 5s\n"
    + "@JINX waves, JINXED stays.\nJINX (whispering): hi\nIF $m is tense: she runs\nREMEMBER: first frame as @JINX\n"
    + "SET: @JINX(0.6, refmods), @style(0.8)\nEND ON: done\nCUT TO: the room (30%)";
  const html = highlight(text, new Set());
  for (const kw of ["SCENE", "AFTER:", "START WITH:", "IF", "REMEMBER:", "SET:", "END ON:", "CUT TO:"]) assert.match(html, new RegExp(`<span class="t-kw">${kw}</span>`));
  assert.match(html, /<span class="t-cast">@JINX<\/span> waves, JINXED stays/);
  assert.match(html, /<span class="t-kw"><span class="t-cast">JINX<\/span> \(whispering\):<\/span>/);
  assert.match(html, /<span class="t-cast">@JINX<\/span>\(0\.6, refmods\), <span class="t-lora">@style\(0\.8\)<\/span>/);
  assert.doesNotMatch(highlight("a cat @JINX(0.6)", new Set()), /t-cast/);  // no CAST: a LoRA
});

test("CHUNK lines get a divider with their label, and the next segment's chunk is marked", () => {
  const info = chunkInfo(REEL_TEXT);
  const html = highlight(REEL_TEXT, new Set(), { chunks: info, segment: 2 });
  assert.equal(html.split("\n").length, REEL_TEXT.split("\n").length);  // no extra lines: the caret stays put
  // the divider names one clip (#219); its whole label is its hover
  assert.match(html, /<span class="chunkline"><span class="chunkinfo"><span title="clip 1 · 0:00 → 0:05 · 0:30 left">played as clip 1 · 5 s<\/span><\/span><span class="t-kw">CHUNK<\/span> the opening<\/span>/);
  assert.match(html, /<span class="chunkline now"><span class="chunkinfo"><span title="next 2\/4 · clips 2–5 [^"]*">▶ next: clip 3 · 5 s<\/span><\/span><span class="t-kw">CHUNK<\/span> the walk repeat 4/);
  assert.doesNotMatch(highlight(REEL_TEXT, new Set()), /chunkinfo/);
});

test("the cells view splits a reel at its CHUNK lines, and joining the cells gives the text back", () => {
  const cells = splitCells(REEL_TEXT);
  assert.deepEqual(cells.map((c) => [c.line, c.chunk, c.text.split("\n")[0]]),
    [[0, -1, "@h3 t2va 16:9"], [2, 0, "CHUNK the opening"], [5, 1, "CHUNK the walk repeat 4"], [10, 2, "CHUNK the end"]]);
  assert.equal(cells.map((c) => c.text).join("\n"), REEL_TEXT);
  const bare = "CHUNK a\nSHOT 5s\n  CHUNK b\n";
  assert.deepEqual(splitCells(bare).map((c) => [c.chunk, c.text]), [[0, "CHUNK a\nSHOT 5s"], [1, "  CHUNK b\n"]]);
  assert.deepEqual(splitCells("no chunks\nhere"), [{ line: 0, chunk: -1, text: "no chunks\nhere" }]);
});

test("the Write menu offers a writer only where it can write", () => {
  const app = (text, { llm = true, clip = false, frames = [] } = {}) => ({
    text, llmActive: () => llm, bridge: { wired: (n) => n === "clip" && clip, frames: () => frames },
  });
  const reel = "@h3 t2va\nCHUNK a\nSHOT 5s\nA.\nCHUNK b\nSHOT 5s\nB.", fl2va = "@h3 fl2va 16:9\nSHOT 5s\nA.";
  assert.match(writerBlock(app(reel, { llm: false }), "continue"), /language model/);
  assert.equal(writerBlock(app(reel, { llm: false, clip: true }), "continue"), "");
  assert.match(writerBlock(app("@h3 t2va\nCHUNK a repeat forever\nSHOT 5s\nA."), "continue"), /forever/);
  assert.match(writerBlock(app(fl2va), "continue"), /Needs a reel/);
  assert.match(writerBlock(app(reel, { frames: ["first_frame", "last_frame"] }), "story"), /not for a reel/);
  assert.match(writerBlock(app(fl2va, { frames: ["first_frame"] }), "story"), /first and the last frame/);
  assert.equal(writerBlock(app(fl2va, { frames: ["first_frame", "last_frame"] }), "story"), "");
  assert.match(writerBlock(app("a photo of a fox", { frames: ["first_frame", "last_frame"] }), "story"), /@h3/);
  assert.match(writerBlock(app("a photo of a fox"), "describe"), /first_frame/);
  assert.equal(writerBlock(app("a photo of a fox", { frames: ["last_frame"] }), "describe"), "");
});

test("a scene's buttons: the clip it generates and where the next scene starts (#204)", async () => {
  const { chunkInfo, nextSceneClip, sceneTarget } = await import("../../comfyui/web/app/model.js");
  const reel = "@h3 t2va\nSCENE a\nSHOT 5s\nA.\nSCENE b ×3\nSHOT 5s\nB.\nSCENE c forever\nSHOT 5s\nC.";
  const [a, b, c] = chunkInfo(reel), all = [a, b, c];
  assert.equal(sceneTarget(a, 2), 0);  // the next clip is elsewhere: the scene's first
  assert.equal(sceneTarget(b, 2), 2);  // the scene plays the next clip: that one
  assert.equal(sceneTarget(b, 0), 1);
  assert.equal(nextSceneClip(a, all), 1);
  assert.equal(nextSceneClip(b, all), 4);
  assert.equal(nextSceneClip(c, all), null);  // forever: nothing after it
  const [end] = chunkInfo("@h3 t2va\nSCENE only\nSHOT 5s\nA.");
  assert.equal(nextSceneClip(end, [end]), null);  // the reel's last scene
});

test("sample surfing numbers its takes on from the ones a clip has, or follows the seed's control (#206)", async () => {
  const { surfSeeds } = await import("../../comfyui/web/app/prompt.js");
  const app = (takes, { control = "fixed", numbered = true, clips = [] } = {}) => ({
    data: { chain: { takes, clips }, surf_numbered: numbered }, bridge: { getSeed: () => 100, getControl: () => control } });
  assert.deepEqual(surfSeeds(app({}), 2, 4, true), [0, 1, 2, 3]);  // a clip not rendered yet: the plain take first
  assert.deepEqual(surfSeeds(app({}, { clips: [{ segment: 2 }] }), 2, 2, true), [1, 2]);  // its one clip is take 0
  assert.deepEqual(surfSeeds(app({ 2: [{ take: 0, seed: 100 }, { take: 3, seed: 100 }] }), 2, 2, true), [4, 5]);
  assert.deepEqual(surfSeeds(app({ 2: [{ take: 0, seed: 100 }, { take: 0, seed: 102 }] }), 2, 2, false), [3, 4]);  // seeds, rolled anew
  assert.deepEqual(surfSeeds(app({}, { numbered: false, control: "fixed" }), 2, 2, true), [0, 0]);  // the same take again
  const random = surfSeeds(app({}, { numbered: false, control: "randomize" }), 2, 3, true);
  assert.equal(new Set(random).size, 3);
});

test("a scene that plays no clip says why: the walk not known yet, not reached, or after a forever (#210)", async () => {
  const { sectionHTML } = await import("../../comfyui/web/app/timeline.js");
  const app = (walked) => ({ reelPath: () => walked });
  assert.match(sectionHTML(app(null), { first: null, segs: [] }), /walking the reel at this seed/);
  assert.match(sectionHTML(app({ path: [0, 2] }), { first: null, segs: [] }), /walk does not reach it/);
  assert.match(sectionHTML(app(null), { first: null }), /a scene before it repeats forever/);
});

test("Write now counts the libraries a template still needs, as autolib does", () => {
  const libs = [{ name: "animal", count: 3 }, { name: "style", count: 2 }];
  const text = "# __commented__\na __animal:5__ in __style__ by __makers/new__ <lora:__x__:1>\n__style:2__ \\__escaped__ __clothing/*__ __mine__";
  assert.deepEqual(openLibraries(text, libs, new Set(["mine"])), ["animal", "makers/new"]);
  assert.deepEqual(openLibraries("__animal[tag=a]#k:v:2__ and __style__", libs), []);
});

test("tag algebra, brace options and the LoRA short form mirror the expander", () => {
  assert.ok(tagsMatch("myth,!bird", ["myth"]) && !tagsMatch("myth,!bird", ["myth", "bird"]));
  assert.ok(tagsMatch("water|deep_sea", ["deep_sea"]) && !tagsMatch("water|deep_sea", ["myth"]) && tagsMatch(null, []));
  assert.deepEqual(splitOptions("__a[x|y]__|b"), ["__a[x|y]__", "b"]);
  assert.equal(longForm("@ink(0.8) @include x @h3(1)"), "<lora:ink:0.8> @include x @h3(1)");
  const html = highlight("a __creature[myth,!bird]__ @ink(0.4-0.9)", known);
  assert.match(html, /<span class="t-lib">__creature\[myth,!bird\]__<\/span>/);
  assert.match(html, /<span class="t-lora">@ink\(0\.4-0\.9\)<\/span>/);
  assert.deepEqual(dials("$s = {0.4-0.9}\n$t = {a|__b[x|y]__}").map((d) => d.options), [[], ["a", "__b[x|y]__"]]);
});



test("a backslash keeps a character from being syntax, in the editor too", () => {
  const html = highlight("\\{a|b\\} \\__init__ __creature__ \\@x(1)", known);
  assert.match(html, /<span class="t-esc"[^>]*>\\\{<\/span>/);
  assert.doesNotMatch(html, /t-lib[^"]*">__init__/);
  assert.equal(longForm("\\@x(1) @y(2)"), "\\@x(1) <lora:y:2>");
});

test("a run made before every pick had its own dice replays with @rng 1", () => {
  assert.equal(withDice("a __creature__", {}), "@rng 1\na __creature__");
  assert.equal(withDice("a __creature__", { rng: 2 }), "a __creature__");
  assert.equal(withDice("@rng 1\na __creature__", {}), "@rng 1\na __creature__");
});

test("the predicate language mirrors the expander for the dials", () => {
  const e = { tags: ["myth"], props: { habitat: "Sea", size: "small" } };
  assert.ok(matches("myth, habitat=sea", e.tags, e.props) && matches("size=large|small", e.tags, e.props));
  assert.ok(!matches("myth, !habitat=sea", e.tags, e.props) && !matches("size!=small", e.tags, e.props));
  assert.ok(matches("habitat=$a.habitat", e.tags, e.props));  // a roll the browser cannot know holds
  assert.match(highlight("a __creature[myth, habitat=$a.habitat]__", known), /class="t-lib">__creature\[myth, habitat=\$a\.habitat\]__/);
});

test("directives: @size shapes the node, @seed and @batch are the CLI's, @rng 1 goes under @h3", () => {
  assert.deepEqual([shape("@h3 t2va 16:9\n@size 832x1216\nSHOT 5s\nA.").width, shape("@size 832x1216\na fox").height], [832, 1216]);
  assert.deepEqual(shape("a fox\n@seed 100\n@batch 8").cli, ["@seed 100", "@batch 8"]);
  assert.match(highlight("@batch 8", known), /t-cli/);
  assert.equal(withDice("@h3 t2va\nSHOT 5s\nA.", {}), "@h3 t2va full\n@rng 1\nSHOT 5s\nA.");  // the format of back then too
  assert.equal(withDice("@h3 t2va lite\nSHOT 5s\nA.", { rng: 2 }), "@h3 t2va lite\nSHOT 5s\nA.");
  assert.equal(withDice("@h3 t2va\nSHOT 5s\nA.", { rng: 2, format: "lite" }), "@h3 t2va\nSHOT 5s\nA.");
  assert.equal(withDice("@h3 t2va\nSHOT 5s\nA.", { rng: 2 }), "@h3 t2va full\nSHOT 5s\nA.");
});

test("a chance is on or off, not a list for the dials", () => {
  assert.deepEqual(dials("$r = {30% in the rain}\n$c = {30% off|half price}").map((d) => d.options), [[], ["30% off", "half price"]]);
});

test("a glob is a known library when it matches one", () => {
  const libs = new Set(["clothing/hats", "creature"]);
  assert.match(highlight("__clothing/*__", libs), /class="t-lib">__clothing\/\*__/);
  assert.match(highlight("__shoes/*__", libs), /t-miss/);
});

test("Generate asks the server for a plan only when there may be one", () => {
  for (const t of ["<lora:a:0.5,1.0>", "<lora:a:0-1;0.1>", "<lora:a:1:solo>", "<lora:a:test>", "@x(0.5,1.0)", "a\n@grid __s__", "a\n: grid {x|y}"]) {
    assert.ok(PLAN_HINT.test(t), t);
  }
  for (const t of ["a cat <lora:b:0.8>", "<lora:x:0.4-0.9>", "@x(0.8)", "a grid of tiles"]) assert.ok(!PLAN_HINT.test(t), t);
});


test("with GOTO lines the chunks follow the path the server walked", () => {
  const text = "@h3 t2va\nCHUNK the gate\nSHOT 5s\nA.\nCHUNK the stairs\nSHOT 4s\nB.\nCHUNK the lamp\nSHOT 6s\nC.\nGOTO: the stairs ×2";
  assert.ok(hasGoto(text) && !hasGoto("@h3 t2va\nCHUNK a\nSHOT 5s\nA."));
  assert.match(chunkInfo(text)[1].label, /walking the reel/);  // the path is not there yet
  const walked = chunkInfo(text, { path: [0, 1, 2, 1, 2, 1, 2], ended: true });
  assert.deepEqual(walked.map((c) => c.segs), [[0], [1, 3, 5], [2, 4, 6]]);
  assert.equal(walked[1].label, "clips 2, 4, 6 · 3 × 4 s · from 0:05 · 0:06 left");  // left after its last play
  assert.ok(plays(walked[2], 4) && !plays(walked[2], 3) && plays(chunkInfo("CHUNK a\nSHOT 5s\nA.")[0], 0));
  const endless = chunkInfo(text, { path: [0, 1, 2, 1, 2], ended: false });
  assert.match(endless[2].label, /^clips 3, 5, … · 2\+ × 6 s/);
  const html = highlight(text, known, { chunks: walked, segment: 3 });
  assert.match(html, /title="next 2\/3 · clips 2, 4, 6 [^"]*">▶ next: clip 4 · 4 s</);
  assert.match(html, />comes next as clip 5 · 6 s</);
});

test("a dial's menu lists every choice while the box holds one of them, and filters what is typed (#155)", async () => {
  const { menuItems } = await import("../../comfyui/web/app/dialmenu.js");
  const choices = ["everyday", "adventure", "fantasy", "cyberpunk", "spacefarer"];
  assert.deepEqual(menuItems(choices, ""), choices);
  assert.deepEqual(menuItems(choices, "spacefarer"), choices);  // the datalist showed only this one
  assert.deepEqual(menuItems(choices, "SpaceFarer "), choices);
  assert.deepEqual(menuItems(choices, "an"), ["fantasy"]);
  assert.deepEqual(menuItems(choices, "zz"), []);
});

test("a picture's sheet lists what it exported: texts, lists and an entry's fields (#160)", async () => {
  const { exportRows } = await import("../../comfyui/web/app/model.js");
  assert.deepEqual(exportRows({ who: "a tall heron", skills: ["fishing", "waiting"], job: { value: "a ferryman", tool: "a long pole" } }), [
    { name: "who", value: "a tall heron", items: [], fields: [] },
    { name: "skills", value: null, items: ["fishing", "waiting"], fields: [] },
    { name: "job", value: "a ferryman", items: [], fields: [["tool", "a long pole"]] },
  ]);
  assert.deepEqual(exportRows(undefined), []);
});

test("a dial ticks several choices into one that rolls among them (#156)", async () => {
  const { chosen, joinChoices, menuItems } = await import("../../comfyui/web/app/dialmenu.js");
  const genres = ["everyday", "noir", "gothic", "spacefarer"];
  assert.deepEqual(chosen(genres, "{noir|gothic}"), ["noir", "gothic"]);
  assert.deepEqual(chosen(genres, "Noir"), ["noir"]);
  assert.deepEqual(chosen(genres, "{noir|western}"), []);  // not all of them are choices: it is an expression
  assert.deepEqual(menuItems(genres, "{noir|gothic}"), genres);  // every choice stays listed to tick more
  const origins = ["Tamil descent, with {deep brown|dark brown} skin", "Greek descent"];
  assert.deepEqual(chosen(origins, `{${origins[0]}|${origins[1]}}`), origins);  // a choice with its own braces
  assert.equal(joinChoices([]), "");
  assert.equal(joinChoices(["noir"]), "noir");
  assert.equal(joinChoices(["noir", "gothic"]), "{noir|gothic}");
});

test("the dial menu's filter reads a choice's text, properties and tags, as a regex or as plain text (#186)", async () => {
  const { filterChoices, matchedBy, filterPattern } = await import("../../comfyui/web/app/dialmenu.js");
  const outfits = { "a trench coat": { props: { genre: "noir", fit: "all" }, tags: ["coat"] },
    "a corset gown": { props: { genre: "gothic", fit: "women" }, tags: [] }, "a flight suit": { props: { genre: "spacefarer" }, tags: ["space"] } };
  const names = Object.keys(outfits), info = (c) => outfits[c];
  assert.deepEqual(filterChoices(names, "noir|gothic", info), ["a trench coat", "a corset gown"]);
  assert.deepEqual(filterChoices(names, "^genre=goth", info), ["a corset gown"]);
  assert.deepEqual(filterChoices(names, "fit: women", info), ["a corset gown"]);
  assert.deepEqual(filterChoices(names, "SPACE", info), ["a flight suit"]);  // case-insensitive, a tag
  assert.deepEqual(filterChoices(names, "suit", info), ["a flight suit"]);
  assert.deepEqual(filterChoices(names, "coat (", info), []);  // no regex: plain text, which nothing holds
  assert.deepEqual(filterChoices(names, "  ", info), names);
  assert.deepEqual(filterChoices(["noir", "gothic"], "oi"), ["noir"]);  // a choice list without properties
  const rx = filterPattern("noir");
  assert.equal(matchedBy("a trench coat", rx, info), "genre: noir");
  assert.equal(matchedBy("noir", rx), "");
  assert.equal(matchedBy("a corset gown", rx, info), null);
});

test("annotations sit at the ends of the lines they belong to (#163)", async () => {
  const { annotationLines, mergeHints } = await import("../../comfyui/web/app/annotate.js");
  const text = ["$colour = __colours__", "$backdrop = a grey wall", "EXPORT:", "  mood = __moods__", "  $who", "EXPORT: $a, $b",
    "@grid $view", "@h3 references", "CAST", "@HERO (image $hero): $hero.who", "SHOT 5s: static", "HERO waits."].join("\n");
  const ann = { bindings: { colour: "violet", backdrop: "a grey wall" }, exports: { mood: "restless", who: "a heron", a: "1", b: "2" },
    grid: "4 runs: portrait · profile", cast: { HERO: "images 6–9 · krea/x/7" } };
  const got = Object.fromEntries([...annotationLines(text, ann)].map(([i, h]) => [i, h.text]));
  assert.deepEqual(got, { 0: "= violet", 3: "→ restless", 4: "→ a heron", 5: "→ 1  → 2", 6: "→ 4 runs: portrait · profile",
    9: "→ images 6–9 · krea/x/7" });  // the plain backdrop says itself; HERO waits. is no CAST line
  const merged = mergeHints(new Map([[0, { text: "frames → image 3" }]]), annotationLines(text, ann));
  assert.equal(merged.get(0).text, "frames → image 3");  // REMEMBER's hint wins
});

test("hover knows each keyword's forms and a picture's dials (#136, #147)", async () => {
  const { keywordHelp, directiveHelp, dialText } = await import("../../comfyui/web/app/hover.js");
  assert.equal(keywordHelp("REMEMBER:").word, "REMEMBER:");
  assert.ok(keywordHelp("REMEMBER:").forms.some(([f]) => f === "REMEMBER: frames 0, 50 as @NAME"));
  assert.equal(keywordHelp("SHOT 5s:").word, "SHOT");
  assert.equal(keywordHelp("IF").word, "IF");
  assert.equal(keywordHelp("EXPORT:").word, "EXPORT:");
  assert.equal(keywordHelp("style:").word, "style:");
  assert.equal(keywordHelp("@HERO (image 1):"), null);  // a CAST member's head is no keyword
  assert.equal(directiveHelp("@grid").word, "@grid");
  assert.equal(dialText({ strength: 0.6, from: 0.35, to: 1 }), "at 0.6 from 35%");
  assert.equal(dialText({ strength: 1 }), "");
});

test("a CAST line with gallery pictures shows them after it (#137)", async () => {
  const { annotationLines } = await import("../../comfyui/web/app/annotate.js");
  const ann = { cast: { HERO: "images 8–9 · krea/x/7" }, members: { HERO: { pictures: [{ image: 8, id: "a1" }, { image: 9, id: "a2" }] } } };
  const hint = annotationLines("CAST\n@HERO (image krea/x/7): a heron\nSHOT 5s", ann, (id) => `/t/${id}`).get(1);
  assert.deepEqual(hint.thumbs, ["/t/a1", "/t/a2"]);
});

test("a CAST line's note says nothing the line says itself", async () => {
  const { annotationLines, slotsText } = await import("../../comfyui/web/app/annotate.js");
  assert.equal(slotsText([9, 6, 7, 8]), "images 6–9");
  assert.equal(slotsText([2, 5]), "images 2, 5");
  const ann = { cast: { PLACE: "image 1", HERO: "image 9 · krea/x/7" } };
  const notes = annotationLines("CAST\n@PLACE (image 1): a street\n@HERO (image krea/x/7): a heron", ann);
  assert.deepEqual([...notes.keys()], [2]);
});

test("a scene is highlighted again only when something it shows changed (#218)", async () => {
  const { paintCells } = await import("../../comfyui/web/app/cells.js");
  const text = "@h3 text\n$x = __place__\n\nSCENE one\nSHOT 5s: static\nA room.\n\nSCENE two\nSHOT 5s: static\nA hall.\n";
  const writes = [];
  const cells = splitCells(text).map((_, i) => {
    const pre = { set innerHTML(_html) { writes.push(i); } };
    return { querySelector: () => pre };
  });
  const host = { querySelectorAll: (sel) => (sel === ".cell" ? cells : []) };
  let libraries = new Set(["place"]);
  const app = {
    text, view: { querySelector: () => host }, chunks: () => [], bridge: { getSegment: () => 0 }, remembered: () => null,
    annotations: () => null, known: () => libraries, llmActive: () => false, api: { thumbURL: () => "" }, data: {},
  };
  paintCells(app);
  assert.deepEqual(writes, [0, 1, 2]);
  writes.length = 0;
  paintCells(app);  // nothing changed: nothing is written
  assert.deepEqual(writes, []);
  app.text = text.replace("A hall.", "A long hall.");
  paintCells(app);  // only the scene typed in
  assert.deepEqual(writes, [2]);
  writes.length = 0;
  libraries = new Set(["place", "creature"]);
  paintCells(app);  // a library more: every scene may show it
  assert.deepEqual(writes, [0, 1, 2]);
});

test("deleting a take asks what it does: another take plays, or the film ends before the clip (#214)", async () => {
  const { deleteQuestion } = await import("../../comfyui/web/app/timeline.js");
  const host = (folder) => ({ dataset: { seg: "1" }, querySelector: () => ({ dataset: { del: folder } }) });
  const takes = [{ folder: "a", active: false }, { folder: "b", active: false }, { folder: "c", active: true }];
  const app = { data: { chain: { takes: { 1: takes } } } };
  assert.equal(deleteQuestion(app, host("a")), "Delete take 1?");
  assert.equal(deleteQuestion(app, host("c")), "Delete this take? Clip 2 then plays take 2.");
  assert.equal(deleteQuestion({ data: { chain: { takes: {} } } }, host("c")), "Delete clip 2? The film ends before it.");
});

test("a scene in numbers: where and how often it plays, before and after, what it rolls, what it made (#219)", async () => {
  const { sceneStats, sceneStatsHTML } = await import("../../comfyui/web/app/scenestats.js");
  const text = "@h3 text\nSCENE the gate\nSHOT 5s: static\nA gate.\nCUT TO: the stairs\n\nSCENE the stairs\n$step = __place__\n$mood = {calm|grim}\n"
    + "$luck = {40% lucky}\nSHOT 4s: static\nStairs.\nIF $mood is grim: CUT TO: the lamp\nCUT TO: the lamp\n\nSCENE the lamp\nSHOT 6s: static\nA lamp.\nCUT TO: the stairs\n";
  const walked = { path: [0, 1, 2, 1, 2, 1, 2], ended: true };
  const app = {
    text, chunks: () => chunkInfo(text, walked), reelPath: () => walked, bridge: { getSegment: () => 3, getSeed: () => 7 },
    data: { completion: { libraries: [{ name: "place", count: 12 }] }, chain: { clips: [{ segment: 1 }, { segment: 3 }], takes: { 1: [{}, {}, {}] } } },
  };
  const s = sceneStats(app, 1);
  assert.deepEqual(s.plays, [1, 3, 5]);
  assert.equal(s.times, "3");
  assert.deepEqual(s.before, [["the lamp", 2], ["the gate", 1]]);
  assert.deepEqual(s.after, [["the lamp", 3]]);
  assert.deepEqual(s.steers, ["IF $mood is grim: CUT TO: the lamp", "CUT TO: the lamp"]);
  assert.deepEqual(s.rolls.map((r) => [r.name, r.count, r.lib, r.chance]), [["step", 12, true, null], ["mood", 2, false, null], ["luck", null, false, 40]]);
  assert.deepEqual(s.made, [{ clip: 2, takes: 3 }, { clip: 4, takes: 1 }]);
  const html = sceneStatsHTML(app, 1);
  assert.match(html, /It plays <b>3<\/b> of the <b>7<\/b> clips of the film/);
  assert.equal((html.match(/<i class="on/g) || []).length, 3);
  assert.match(html, /<i class="on next" title="clip 4: the stairs">/);
  assert.match(html, /<small>a 40 % chance<\/small>/);
  assert.match(html, /<dt>comes after<\/dt><dd>the lamp <b>2×<\/b> · the gate <b>1×<\/b><\/dd>/);
});

test("a knob's sweep plans its runs, and its long forms are opaque like a LoRA tag (#227)", () => {
  for (const t of ["SET: image_1(0.3|0.6)", "SET: jinx(1, 0%, 0%-30%;10%)", "LORA: <refmod:jinx:0.6|0.8>", "LORA: <lora:x:0.6|0.8, 20%>", "@x(0.6|0.8)"]) {
    assert.ok(PLAN_HINT.test(t), t);
  }
  for (const t of ["SET: image_1(0.5, 35%)", "SET: x({0.3|0.6})", "<refmod:jinx:0.8, 0%, 10%>"]) assert.ok(!PLAN_HINT.test(t), t);
  assert.match(highlight("SET: <refmod:jinx_v1:0.8, 0%, 10%>", new Set()), /<span class="t-lora">&lt;refmod:jinx_v1:0\.8, 0%, 10%&gt;<\/span>/);
  assert.equal(longForm("@image_2(0.6) @style(0.8)"), "<image:2:0.6> <lora:style:0.8>");
});

test("the template's knobs, where they hold, written anew and put back (#226)", async () => {
  const { knobsOf, knobKey, withFields, applyKnobs } = await import("../../comfyui/web/app/model.js");
  const text = "@h3 ref2va\nLORA: <lora:turbo:0.8> @style(0.5)\nSET: image_1(0.3|0.6), jinx(1, 0%, 10%)\nCAST\n@JINX (image 1): a woman\n"
    + "SCENE the walk\nSET: turbo(1), @JINX(0.6, refmods), refmods(1, 35%)\nSHOT 5s: static\nx.\n";
  const knobs = knobsOf(text, { loras: ["minimax/turbo.safetensors"], refmods: ["jinx_Video.safetensors"], cast: ["JINX"] });
  assert.deepEqual(knobs.map((k) => [k.scope, k.kind, k.name, k.fields.join(" / ")]), [
    [-1, "lora", "turbo", "0.8"], [-1, "lora", "style", "0.5"], [-1, "image", "image_1", "0.3|0.6"], [-1, "refmod", "jinx", "1 / 0% / 10%"],
    [0, "lora", "turbo", "1"], [0, "cast", "JINX", "0.6 / refmods"],
  ]);
  assert.equal(knobs[4].scene, "the walk");
  assert.equal(withFields(knobs[0], ["0.6", "0%", "50%"]), "<lora:turbo:0.6, 0%, 50%>");
  assert.equal(withFields(knobs[3], ["0.8", "", ""]), "jinx(0.8)");
  assert.equal(withFields(knobs[1], ["0.4"]), "@style(0.4)");
  const turned = applyKnobs(text, { [knobKey(knobs[4])]: "turbo(0.5)", [knobKey(knobs[0])]: "<lora:turbo:0.6>", "~3|gone(1)": "x(2)" });
  assert.match(turned, /LORA: <lora:turbo:0\.6> @style\(0\.5\)/);
  assert.match(turned, /SCENE the walk\nSET: turbo\(0\.5\), @JINX/);
});

test("the take tree lays its takes out as a tidy tree, rows where they were made, and shows the way through a take (#241)", async () => {
  const { layoutTree, wayThrough } = await import("../../comfyui/web/app/tree.js");
  const t = (folder, segment, parent, created) => ({ folder, segment, parent, created });
  const takes = [t("a", 0, null, "1"), t("a1", 1, "a", "2"), t("a1x", 2, "a1", "3"), t("b", 0, null, "4"), t("b1", 1, "b", "5"), t("a2", 1, "a", "6")];
  const rows = layoutTree(takes);
  assert.deepEqual(["a", "a1", "a1x"].map((f) => rows.get(f)), [0, 0, 0]);  // a parent on its first child's row: a path runs straight
  assert.equal(rows.get("a2"), 1);  // a branch below
  assert.deepEqual([rows.get("b"), rows.get("b1")], [2, 2]);  // a later take of clip 1 below: whatever the film, no row moves
  assert.deepEqual(wayThrough({ takes, last: { a: "a1", a1: "a1x" } }, "a"), ["a", "a1", "a1x"]);
  assert.deepEqual(wayThrough({ takes, last: {} }, "a1x"), ["a", "a1", "a1x"]);
});

test("a take made with another version of its scene is told, its change shown, and Use this prompt brings it back (#242)", async () => {
  const { fetchTemplates, lineDiff, sceneIn, useVersion, versionHTML, versionOf, wordMarks } = await import("../../comfyui/web/app/versions.js");
  const old = "@h3 base 16:9\n\nSCENE the door\nSHOT 5s: static\na red door opens.\n\nSCENE the hall\nSHOT 5s: dolly in\na long hall.\n";
  const now = "@h3 base 16:9\n\nSCENE the hall\nSHOT 5s: dolly in\na long hall.\n\nSCENE the door\nSHOT 5s: static\n# a note\na blue door opens.\n";
  const asked = [];
  let toast = null, rendered = 0;
  const app = {
    text: now, data: {}, state: { tab: "prompt" }, render: () => { rendered++; }, toast: (html, action) => { toast = { html, action }; },
    api: { template: async (h) => { asked.push(h); if (h === "gone") throw new Error("404"); return { text: old }; } },
  };
  await fetchTemplates(app, [{ template: "old" }, { template: "old" }, { template: "gone" }, {}]);
  await fetchTemplates(app, [{ template: "old" }]);
  assert.deepEqual(asked.sort(), ["gone", "old"]);  // each hash once
  assert.equal(sceneIn(now, 0, "SCENE the door").text.split("\n")[0], "SCENE the door");  // by its heading, moved
  assert.equal(versionOf(app, { template: "old", scene: 1 }), null);  // the hall: the same text, moved and all
  assert.equal(versionOf(app, { template: "gone", scene: 0 }), null);  // a template the home has lost: no mark
  const v = versionOf(app, { template: "old", scene: 0 });
  assert.deepEqual([v.scene, v.at, v.then.split("\n").pop(), v.now.split("\n").pop()], [0, 1, "a red door opens.", "a blue door opens."]);
  assert.deepEqual(lineDiff("a\nb\nc", "a\nx\nc"), [[" ", "a"], ["-", "b"], ["+", "x"], [" ", "c"]]);
  const card = versionHTML(v);
  assert.match(card, /class="cut"><i>−<\/i><span>a <mark>blue<\/mark> door opens\.<\/span>/);  // the changed word marked
  assert.match(card, /class="add"><i>\+<\/i><span>a <mark>red<\/mark> door opens\.<\/span>/);
  assert.match(card, /SCENE the door/);
  assert.deepEqual(wordMarks("walks slowly on", "walks on"), ["walks <mark>slowly</mark> on", "walks on"]);
  useVersion(app, v);
  assert.ok(app.text.startsWith("@h3 base 16:9\n\nSCENE the hall\nSHOT 5s: dolly in\na long hall.\n\nSCENE the door\nSHOT 5s: static\na red door opens."));
  assert.equal(versionOf(app, { template: "old", scene: 0 }), null);
  assert.ok(rendered === 1 && toast.action.label === "Undo");
  toast.action.run();
  assert.equal(app.text, now);
  app.text = "@h3 base 16:9\n\nSCENE the door\nSHOT 5s: static\na red door opens.\n";  // the hall gone: it comes back at the end
  useVersion(app, versionOf(app, { template: "old", scene: 1 }));
  assert.equal(app.text, "@h3 base 16:9\n\nSCENE the door\nSHOT 5s: static\na red door opens.\n\nSCENE the hall\nSHOT 5s: dolly in\na long hall.");
});

test("the film plays in the tree: its clips in film.mp4's time, a test scene's take left out (#243)", async () => {
  const { filmClips } = await import("../../comfyui/web/app/tree.js");
  const takes = [{ folder: "a", frames: 240 }, { folder: "t", frames: 120, test: true }, { folder: "b", frames: 120 }, { folder: "x", frames: 99 }];
  assert.deepEqual(filmClips({ takes, path: ["a", "t", "b"] }), [{ folder: "a", n: 1, start: 0, end: 10 }, { folder: "b", n: 3, start: 10, end: 15 }]);
  assert.deepEqual(filmClips({ takes, path: [] }), []);
});

test("a clip's takes have a head that reads as content: play on top, the clip in numbers, deleting at the bottom (#245)", async () => {
  const { takesHeadHTML } = await import("../../comfyui/web/app/timeline.js");
  const app = { data: {}, text: "" };
  const takes = [{ folder: "a", seed: 3, created: "2026-10-04T05:01:02.1+02:00" }, { folder: "b", seed: 7, take: 2, active: true, created: "2026-10-04T05:09:12.5+02:00" }];
  const html = takesHeadHTML(app, 1, takes, "the walk");
  const at = (s) => html.indexOf(s);
  assert.ok(at("data-playall") < at("th-mid") && at("th-mid") < at('data-clear="others"'));  // play, numbers, deleting
  assert.match(html, /clip 2<\/span><span class="th-scene" title="the walk">the walk/);
  assert.match(html, /<i>takes<\/i><b>2<\/b>.*<i>in the film<\/i><b>#2<\/b>.*<i>seed<\/i><b>7 \+ 2<\/b>.*<i>newest<\/i><b>05:09<\/b>/);
  assert.doesNotMatch(html, /other prompt/);  // none made with another prompt
});

test("the take tree hides the dead ends: the film's, the last clip's and those a shown take came after stay (#246)", async () => {
  const { shownTakes } = await import("../../comfyui/web/app/tree.js");
  const t = (folder, segment, parent = null) => ({ folder, segment, parent });
  const takes = [t("a", 0), t("b", 0), t("c", 0), t("d", 0), t("a1", 1, "a"), t("a2", 1, "a"), t("c1", 1, "c"), t("a1x", 2, "a1"), t("c1x", 2, "c1"), t("c1y", 2, "c1")];
  const tree = { takes, path: ["b"] };
  const names = (least) => shownTakes(tree, least).map((x) => x.folder).sort().join(" ");
  assert.equal(names(0), takes.map((x) => x.folder).sort().join(" "));  // 0: all of them
  assert.equal(names(1), "a a1 a1x b c c1 c1x c1y");  // d goes; a2 too (no take after it, not the last clip); b is the film
  assert.equal(names(2), "a a1 a1x b c c1 c1x c1y");  // c has one take after it, but c1 has two: the path to it stays whole
  assert.equal(names(3), "a a1 a1x b c c1 c1x c1y");  // the last clip's takes stay, and the takes they came after
});

test("a template without scenes shows its results under the prompt, its takes kept on the node per preset (#211)", async () => {
  const R = await import("../../comfyui/web/app/results.js");
  const props = {};
  let seed = 10;
  const app = { preset: "krea/fox", props, state: {}, data: {}, bridge: { props, getSeed: () => seed, getControl: () => "fixed" },
    api: { viewURL: (m) => `/view?filename=${m.filename}&type=${m.type}` } };
  assert.equal(R.resultsHTML(app, "").includes("comes in here"), true);  // none yet: where they will come
  R.resultBegins(app, { prompt_id: "p1", seed: 10, take: 0 });
  assert.equal(R.resultMedia(app, { prompt_id: "other", output: { images: [{ filename: "x.png", type: "output" }] } }), false);
  assert.equal(R.resultMedia(app, { prompt_id: "p1", output: { images: [{ filename: "fox_0001.png", subfolder: "", type: "output" }] } }), true);
  R.resultBegins(app, { prompt_id: "p2", seed: 11, take: 0 });
  R.resultMedia(app, { prompt_id: "p2", output: { gifs: [{ filename: "fox.mp4", type: "output", format: "video/h264-mp4" }] } });
  R.resultMedia(app, { prompt_id: "p2", output: { images: [{ filename: "prev.png", type: "temp" }] } });  // a second node of the run
  assert.deepEqual(R.resultsOf(app).map((t) => [t.prompt, t.seed, t.media.map((m) => m.kind)]), [["p1", 10, ["image"]], ["p2", 11, ["video", "image"]]]);
  assert.equal(R.shownResult(app).prompt, "p2");  // the newest is shown
  const html = R.resultsHTML(app, "--take-w:96px");
  assert.match(html, /class="tl-clip big result" data-seg="-1"[^>]*><video[^>]*src="\/view\?filename=fox\.mp4&amp;type=output#t=0\.05"/);  // a saved file first
  assert.match(html, /data-result="p1"[^>]*>.*<img loading="lazy" alt="" src="\/view\?filename=fox_0001\.png/);
  assert.match(html, /<i>takes<\/i><b>2<\/b>.*<i>shown<\/i><b>#2<\/b>.*<i>seed<\/i><b>11<\/b>/);
  assert.deepEqual(R.resultSeeds(app, 2, false), [2, 3]);  // numbered on from the takes there are: seeds 12, 13
  assert.deepEqual(R.resultSeeds(app, 2, true), [1, 2]);  // with 📌 take numbers
  app.preset = "krea/owl";
  assert.deepEqual(R.resultsOf(app), []);  // another preset, its own takes
  R.resultBegins(app, { prompt_id: "p3", seed: 12, take: 0 });
  R.resultEnds(app, "p3");  // nothing written: no take
  assert.equal(R.resultMedia(app, { prompt_id: "p3", output: { images: [{ filename: "y.png" }] } }), false);
});

test("the settings are a tab of sections, and every setting of the old sheet is in one (#212)", async () => {
  const { SECTIONS, SECTION_HTML } = await import("../../comfyui/web/app/settings.js");
  assert.deepEqual(SECTIONS.map(([k]) => k), ["home", "llm", "writers", "editor", "clips", "log"]);
  const app = { data: { quickstart: true, dividers: false, timeline: true, log_prompts: true, clip_min: 400, preview_fps: 8, preview_edge: 768, preview_light: false, surf_numbered: true } };
  const st = {
    home: { home: "/h", setting: "/h", source: "setting" },
    llm: { source: "comfy", file: "qwen3vl_4b.safetensors", entries: 12, max_tokens: 16000, files: [{ name: "qwen3vl_4b.safetensors", size: 8e9, can_write: true }],
      api: { base_url: "https://api.openai.com/v1", model: "", key: "", key_from: "none", key_env: "OPENAI_API_KEY" } },
    writers: Object.fromEntries(["continue", "story", "describe", "describe_shot"].map((k) => [k, { text: "t", default: "d", edited: k === "story" }])),
    wcur: "continue",
  };
  const html = Object.fromEntries(SECTIONS.map(([k]) => [k, SECTION_HTML[k](app, st)]));
  const has = (k, ...bits) => bits.forEach((b) => assert.ok(html[k].includes(b), `${k} lacks ${b}`));
  has("home", 'id="oa-home"', "data-home", "Use this folder");  // moving the home keeps its own button
  has("llm", 'name="oa-src"', 'id="oa-llm"', 'id="oa-api-url"', 'id="oa-api-key"', "data-check", "data-useapi", 'id="oa-llm-n"', 'id="oa-llm-t"');
  has("writers", 'id="oa-wr"', 'id="oa-wt"', "data-wreset", "data-wsave", "Story between frames · edited");
  has("editor", 'data-flag="quickstart" checked', 'data-flag="dividers" >', 'data-flag="timeline" checked');
  has("clips", 'value="400"', 'id="oa-pvfps" type="number" min="1" max="24" step="1" value="8"', 'value="768"', 'value="smooth" checked', 'value="numbered" checked');
  has("log", 'data-flag="log_prompts" checked');
  assert.doesNotMatch(Object.values(html).join(""), /data-cancel|>Save</);  // no Save at the end of a long page
});

test("every library in a line says its roll, at the line's end, on hover or not at all (#202, #203)", async () => {
  const { annotationLines, shownHints } = await import("../../comfyui/web/app/annotate.js");
  const { highlight, onHover } = await import("../../comfyui/web/app/highlight.js");
  const text = "$a = __animal__\nSHOT 5s: static\nA __animal__ in an __arcade__ with __hair__ hair.";
  const ann = { bindings: { a: "fox" }, rolls: { 4: [[0, "heron"], [1, "arcade"], [2, "bob cut"]], 2: [[0, "owl"]] } };
  const cell = annotationLines(text, ann, null, 2);  // a cell from the template's line 2 on
  assert.equal(cell.get(2).text, "→ heron · arcade · bob cut");
  assert.equal(cell.get(0).text, "= fox");  // a binding's line says it as a binding, never its library's roll
  assert.equal(shownHints("none", cell).size, 0);
  assert.equal(shownHints("appended", cell), cell);
  const hover = shownHints("hover", cell);
  assert.ok(hover.get(2).hover && hover.get(0).note === "= fox");
  const known = new Set(["animal", "arcade", "hair"]);
  const html = highlight(text, known, { hints: hover });
  assert.doesNotMatch(html, /class="hint/);  // nothing at the line ends
  assert.match(html, /data-roll="at this seed: heron" class="t-has t-lib">__animal__/);
  assert.match(html, /data-roll="at this seed: bob cut" class="t-has t-lib">__hair__/);
  assert.match(html, /data-roll="= fox" class="t-has t-var">\$a/);
  assert.match(onHover('<span class="t-kw">REMEMBER:</span> x', { note: "→ image 3" }), /data-roll="→ image 3" class="t-has t-kw"/);
  assert.match(highlight(text, known, { hints: cell }), /class="hint note"><span>→ heron · arcade · bob cut/);
});
