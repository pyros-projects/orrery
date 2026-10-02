import { test } from "node:test";
import assert from "node:assert/strict";
import { highlight } from "../../comfyui/web/app/highlight.js";
import { fitThumbs } from "../../comfyui/web/app/timeline.js";
import { writerBlock } from "../../comfyui/web/app/write.js";
import {
  applyDials, dials, downstream, entryPage, filterPresets, folderDropPath, folderTree, libraryGroups, filterRows, glyph, markPicks, pickerGroups,
  chunkInfo, chunkLabel, splitCells, rangeIds, shape, stats, sweepPlan, templateHash, longForm, splitOptions, tagsMatch,
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
  assert.deepEqual([st.h3.voices, st.h3.reel], [0, { chunks: 2, secs: [5, 4], repeats: [1, 1], clips: 2 }]);
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
  assert.deepEqual(stats(loop).h3.reel, { chunks: 2, secs: [5, 6], repeats: [1, 8], clips: 9 });
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

test("a LoRA sweep is planned like the node does: product, solo turns, zero is off, doubles once", () => {
  const plan = (t) => { const p = sweepPlan(t); return p && [p.runs, p.formula, p.first]; };
  assert.deepEqual(plan("<lora:a:0.5,1.0><lora:b:0.3,1>"), [4, "2 × 2", "a"]);
  assert.deepEqual(plan("<lora:AmateurHour_01_rank16:0.5,1.0:solo><lora:AmateurHour_H3_000017500:0.5,1.0:solo>"),
    [4, "2 + 2", "AmateurHour_01_rank16"]);
  assert.deepEqual(plan("<lora:c:0.2,0.4><lora:a:0.5:solo><lora:b:0.7,0.9:solo>"), [6, "2 × (1 + 2)", "c"]);
  assert.deepEqual(plan("<lora:a:0,1:solo><lora:b:0,1:solo>"), [3, "2 + 2", "a"]);
  assert.deepEqual(plan("<lora:H3-Icy-real-v1_000004200:test>"), [3, "3", "H3-Icy-real-v1_000004200"]);
  assert.deepEqual(plan("<lora:relim_v2_lora_500:0-1;0.1>"), [11, "11", "relim_v2_lora_500"]);
  assert.deepEqual(plan("<lora:s:0.5,1.0:0.5,1.0>"), [4, "4", "s"]);
  assert.equal(sweepPlan("a cat <lora:b:0.8> <lora:d:0.4:0.7>"), null);
  assert.equal(sweepPlan("# <lora:a:0.5,1.0>\na cat"), null);
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
  assert.equal(chunkLabel(info[0]), "seg 0 · 0:00 → 0:05 · 0:30 left");
  assert.equal(chunkLabel(info[1]), "seg 1–4 · 4 × 5 s · 0:05 → 0:25 · 0:10 left");
  assert.equal(chunkLabel(info[2]), "seg 5 · 0:25 → 0:35 · the end");
  assert.equal(chunkInfo("@h3 t2va\nSHOT 5s\nA."), null);
  const sends = chunkInfo("CHUNK a\nSHOT 5s\nSEND: frame 0 to image 1\nSEND: frames -1 to image 3 for segment 4+\nSEND: frame 9 to image 1 for segment 9\nA.");
  assert.deepEqual(sends[0].images, [1, 3]);
});

test("a chunk that repeats forever runs on, and the ones after it never play", () => {
  const info = chunkInfo("CHUNK a\nSHOT 5s\nA.\nCHUNK b repeat forever\nSHOT 6s\nB.\nCHUNK c\nSHOT 5s\nC.");
  assert.equal(chunkLabel(info[1]), "seg 1 → ∞ · 6 s each · from 0:05");
  assert.equal(chunkLabel(info[2]), "never plays: a chunk before it repeats forever");
  assert.equal(chunkLabel(info[0]), "seg 0 · 0:00 → 0:05");
});

test("CHUNK lines get a divider with their label, and the next segment's chunk is marked", () => {
  const info = chunkInfo(REEL_TEXT);
  const html = highlight(REEL_TEXT, new Set(), { chunks: info, segment: 2 });
  assert.equal(html.split("\n").length, REEL_TEXT.split("\n").length);  // no extra lines: the caret stays put
  assert.match(html, /<span class="chunkline"><span class="chunkinfo"><span>seg 0 · 0:00 → 0:05 · 0:30 left<\/span><\/span><span class="t-kw">CHUNK<\/span> the opening<\/span>/);
  assert.match(html, /<span class="chunkline now"><span class="chunkinfo"><span>▶ next 2\/4 · seg 1–4 [^<]*<\/span><\/span><span class="t-kw">CHUNK<\/span> the walk repeat 4/);
  assert.doesNotMatch(highlight(REEL_TEXT, new Set()), /chunkinfo/);
});

test("timeline thumbs keep the clips' aspect ratio, portrait as well as landscape, and always fit their chunk", () => {
  assert.deepEqual(fitThumbs(1, 120, 74, 16 / 9), { cols: 1, w: 120, h: 67 });
  assert.deepEqual(fitThumbs(1, 120, 74, 9 / 16), { cols: 1, w: 41, h: 74 });
  assert.deepEqual(fitThumbs(4, 120, 53, 9 / 16), { cols: 4, w: 27, h: 49 });  // portrait repeats side by side
  assert.deepEqual(fitThumbs(1, 120, 400, 9 / 16), { cols: 1, w: 101, h: 180 });  // a tall chunk stops at 180 px
  for (const ratio of [16 / 9, 1, 9 / 16]) {
    const { cols, w, h } = fitThumbs(20, 120, 53, ratio), rows = Math.ceil(20 / cols);
    assert.ok(cols * w + (cols - 1) * 3 <= 120 && rows * h + (rows - 1) * 3 <= 53, `ratio ${ratio}`);
  }
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

test("Generate plans a grid's cells, alone or times a LoRA sweep", () => {
  const grid = { cells: 6, formula: "3 × 2", axes: [{ text: "__style__", count: 3 }, { text: "{dawn|noon}", count: 2 }] };
  assert.deepEqual(sweepPlan("a __style__ at {dawn|noon}", grid), { runs: 6, formula: "grid 3 × 2", first: "__style__ × {dawn|noon}" });
  assert.deepEqual(sweepPlan("a @x(0.5,1.0) __style__", grid), { runs: 12, formula: "2 × grid 3 × 2", first: "x" });
  assert.equal(sweepPlan("a @x(0.5,1.0)").runs, 2);  // the short form sweeps too
  assert.equal(sweepPlan("a <lora:x:0.4-0.9>"), null);  // a range rolls per run: no sweep
});


test("a backslash keeps a character from being syntax, in the editor too", () => {
  const html = highlight("\\{a|b\\} \\__init__ __creature__ \\@x(1)", known);
  assert.match(html, /<span class="t-esc"[^>]*>\\\{<\/span>/);
  assert.doesNotMatch(html, /t-lib[^"]*">__init__/);
  assert.equal(longForm("\\@x(1) @y(2)"), "\\@x(1) <lora:y:2>");
});
