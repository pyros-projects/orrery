import { test } from "node:test";
import assert from "node:assert/strict";
import { highlight } from "../../comfyui/web/app/highlight.js";
import {
  applyDials, dials, entryPage, filterPresets, libraryGroups, filterRows, glyph, markPicks, pickerGroups, shape, stats, templateHash,
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
  const html = highlight("@h3 t2va 16:9\nSHOT 5s | push in\nKEEPER (warm voice): Hi\nSFX: rain\nThe start of <Picture 1>.", known);
  assert.match(html, /<span class="t-head">@h3 t2va 16:9<\/span>/);
  assert.match(html, /<span class="t-kw">SHOT 5s<\/span>/);
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
  assert.deepEqual(shape("a fox"), { width: 1024, height: 1024, length: 124, cli: [] });
  assert.deepEqual(shape("a fox\n: x8 seed=100 w832 h1216"), { width: 832, height: 1216, length: 124, cli: ["x8", "seed=100"] });
  assert.deepEqual(shape("@h3 t2va 16:9\nSHOT 5s\nA."), { width: 1344, height: 768, length: 124, cli: [] });
  assert.deepEqual(shape("@h3 t2va 9:16\nSHOT 4s\nA.\nSHOT 3s\nB.\nSHOT 4s\nC."), { width: 768, height: 1344, length: 277, cli: [] });
  assert.equal(shape("@h3 t2va 21:9\nSHOT 4s\nA.").width, 1536);
  assert.equal(shape("@h3 ref2va lite 9:16\nSHOT 4s\nA.").height, 1344);
});

test("template hash matches orrery's sha256 prefix", () => {
  assert.equal(templateHash("a __creature__"), "f8ad7a7fd793fbc4");
  assert.equal(templateHash(""), "e3b0c44298fc1c14");
  assert.equal(templateHash("Späti 🌙\n$x = {a|b}"), "7fe816c6c2103fe3");
});

test("stats count rolls, libraries, bindings and H3 timing", () => {
  const s = stats("$a = __creature__\n{x|y} in __place__ and __creature__");
  assert.deepEqual([s.rolls, s.libs, s.binds, s.h3], [4, 2, 1, null]);
  const h = stats("@h3 t2va\nSHOT 3s | static\nA.\nNARRATOR (voiceover): Hi\nSHOT 2.5s | cut, arc\nB.\nSFX: wind");
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
  const reel = "@h3 t2va 16:9\nLORA: <lora:a:1>\ncontext: 22\nCHUNK\nSHOT 5s\nA.\nHANDOFF: b\nCHUNK the hall\nSHOT 3s\nB.\nSHOT 1s\nC.";
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
