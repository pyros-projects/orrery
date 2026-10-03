import { test } from "node:test";
import assert from "node:assert/strict";
import { suggest, missingLibraries, inlineLibraries, globMatches, castNames } from "../../comfyui/web/orrery-complete.js";

const DATA = {
  libraries: [
    { name: "creature", count: 24, source: "builtin", tags: ["deep_sea", "myth"], sample: ["axolotl"],
      props: { habitat: [{ value: "sea", count: 9, sample: "a manta ray" }, { value: "forest", count: 6, sample: "a red fox" }],
               size: [{ value: "small", count: 3, sample: "an axolotl" }] } },
    { name: "camera", count: 12, source: "builtin", tags: [], sample: [] },
    { name: "animal", count: 12, source: "user", tags: [], sample: ["fox"] },
  ],
  h3: { camera: ["push in", "pull out", "arc", "static"], modifiers: ["small", "large", "slow", "fast"],
        transitions: ["cut", "dissolve", "fade", "wipe"] },
  loras: [
    { name: "H3-PK-Parasyte-Turbo", folder: "minimax/turbo" },
    { name: "indie90s_style_h3_ep35", folder: "style" },
    { name: "Motion_Repair", folder: "" },
  ],
  refmods: ["allie_refMod", "orrery_abc_salon", "salon_old/abc", "Zelda_refMod"],
};

const at = (text) => suggest(text, text.length, DATA);

test("__ lists all libraries", () => {
  const s = at("a __");
  assert.deepEqual(s.items.map((i) => i.insert), ["__animal__", "__camera__", "__creature__"]);
  assert.equal(s.replaceFrom, 2);
});

test("__cr filters by prefix and shows count and origin", () => {
  const [item] = at("a __cr").items;
  assert.equal(item.insert, "__creature__");
  assert.match(item.detail, /24/);
  assert.match(item.detail, /builtin/);
});

test("closed wildcards do not trigger", () => {
  assert.equal(at("a __creature__ in").items.length, 0);
});

test("__lib[ lists that library's tags", () => {
  const s = at("a __creature[d");
  assert.deepEqual(s.items.map((i) => i.insert), ["__creature[deep_sea]__"]);
});

test("$ lists bindings defined in the template", () => {
  const text = "$hero = __creature__\n$place = __animal__\nthe $h";
  assert.deepEqual(at(text).items.map((i) => i.insert), ["$hero"]);
});

test("camera vocabulary after SHOT 5s:", () => {
  const first = at("@h3 t2va\nSHOT 5s: pu").items.map((i) => i.insert);
  assert.ok(first.includes("push in") && first.includes("pull out"));
  const mods = at("@h3 t2va\nSHOT 5s: push in, s").items.map((i) => i.insert);
  assert.deepEqual(mods, ["small", "slow"]);
});

test("the colon opens the camera words at once, and the old | still works", () => {
  assert.ok(at("@h3 t2va\nSHOT 5s:").items.some((i) => i.insert === "push in"));
  assert.ok(at("@h3 t2va\nSHOT 5s | pu").items.some((i) => i.insert === "push in"));
});

test("a fully typed word is not offered again", () => {
  assert.ok(!at("@h3 t2va\nSHOT 5s: push in").items.some((i) => i.insert === "push in"));
});

test("transitions are offered first on later shots", () => {
  const items = at("@h3 t2va\nSHOT 3s\nA.\nSHOT 3s: ").items.map((i) => i.insert);
  assert.ok(items.includes("dissolve") && items.includes("push in"));
});

test("screenplay keywords at line start", () => {
  const items = at("@h3 t2va\nSHOT 5s\nA.\nS").items.map((i) => i.insert);
  assert.ok(items.includes("SHOT ") && items.includes("SFX: ") && items.includes("style: "));
});

test("no keyword suggestions outside screenplays", () => {
  assert.equal(at("a fox\nS").items.length, 0);
});

test("missing libraries are reported", () => {
  assert.deepEqual(missingLibraries("a __creature__ in __weather2__ and __creature[myth]__", DATA),
                   ["weather2"]);
});

test("cast keywords at line start in screenplays", () => {
  const items = at("@h3 ref2va\nC").items.map((i) => i.insert);
  assert.ok(items.includes("CAST"));
  assert.ok(at("@h3 ref2va\nCAST\nA (image 1): a dancer\nv").items.some((i) => i.insert === "voice: "));
});

test("reel keywords at line start in screenplays", () => {
  const items = at("@h3 t2va\nSHOT 5s\nA.\n").items.map((i) => i.insert);
  assert.ok(["CHUNK", "HANDOFF: ", "SEND: ", "LORA: ", "context: "].every((k) => at(`@h3 t2va\n${k[0]}`).items.some((i) => i.insert === k)), items.join());
});

test("LORA: lists your loras in the syntax LoRA Text Loader reads", () => {
  const s = at("@h3 t2va\nLORA: ");
  assert.deepEqual(s.items.map((i) => i.insert), ["<lora:H3-PK-Parasyte-Turbo:1.00>", "<lora:indie90s_style_h3_ep35:1.00>", "<lora:Motion_Repair:1.00>"]);
  assert.deepEqual(s.items.map((i) => i.detail), ["minimax/turbo", "style", "lora"]);
  assert.deepEqual([s.kind, s.items[0].label, s.items[0].preview], ["lora", "H3-PK-Parasyte-Turbo", "minimax/turbo/H3-PK-Parasyte-Turbo"]);
  assert.equal(s.replaceFrom, "@h3 t2va\nLORA: ".length);
});

test("LORA: filters by any part of the name, prefix matches first", () => {
  assert.deepEqual(at("@h3 t2va\nLORA: mot").items.map((i) => i.insert), ["<lora:Motion_Repair:1.00>"]);
  const h3 = at("@h3 t2va\nLORA: <lora:h3");
  assert.deepEqual(h3.items.map((i) => i.insert), ["<lora:H3-PK-Parasyte-Turbo:1.00>", "<lora:indie90s_style_h3_ep35:1.00>"]);
  assert.equal(h3.replaceFrom, "@h3 t2va\nLORA: ".length);
});

test("LORA: completes the next lora on the same line, not inside a strength", () => {
  const next = at("@h3 t2va\nCHUNK\nLORA: <lora:Motion_Repair:1.00> ind");
  assert.deepEqual(next.items.map((i) => i.insert), ["<lora:indie90s_style_h3_ep35:1.00>"]);
  assert.equal(at("@h3 t2va\nLORA: <lora:Motion_Repair:0.").items.length, 0);
  assert.equal(at("a fox\nLORA: mo").items.length, 0);
});

test("lora tags never count as missing libraries", () => {
  assert.deepEqual(missingLibraries("LORA: <lora:bf16__apply__x:1.00> __weather2__", DATA), ["weather2"]);
});

test("a minimum count does not hide a missing library", () => {
  assert.deepEqual(missingLibraries("__creature:30__ and __shoes:20__", DATA), ["shoes"]);
});

test("__folder/ completes the libraries in that folder", () => {
  const data = { ...DATA, libraries: [...DATA.libraries, { name: "film/genre", count: 4, source: "user", tags: [], sample: ["noir"] }] };
  const inFolder = suggest("a __film/", 9, data).items.map((i) => i.insert);
  assert.deepEqual(inFolder, ["__film/*__", "__film/genre__"]);  // a library of the folder at random, first
  assert.ok(suggest("a __fi", 6, data).items.some((i) => i.insert === "__film/genre__"));
  assert.deepEqual(missingLibraries("__film/genre__ and __film/new__", data), ["film/new"]);
});

test("__ matches any part of a library name: start first, then a folder or word start, then anywhere", () => {
  const libs = ["chair", "hair_color", "characters/gothic/hair", "looks/face_hair_female", "animal"];
  const data = { ...DATA, libraries: libs.map((name) => ({ name, count: 1, source: "user", tags: [], sample: [] })) };
  const want = ["__hair_color__", "__characters/gothic/hair__", "__looks/face_hair_female__", "__chair__"];
  const s = suggest("a __hai", 7, data);
  assert.deepEqual(s.items.map((i) => i.insert), want);
  assert.equal(s.replaceFrom, 2);
  assert.deepEqual(suggest("a __HAI", 7, data).items.map((i) => i.insert), want);
});

test("comments neither complete nor count as missing libraries", () => {
  assert.deepEqual(missingLibraries("# try __nothing__ here\n__creature__", DATA), []);
  const text = "# __cre";
  assert.equal(suggest(text, text.length, DATA).items.length, 0);
  const h3 = "# a comment first\n@h3 t2va\nSHOT 5s: ";
  assert.ok(suggest(h3, h3.length, DATA).items.some((i) => i.insert === "push in"));
});

test("after __lib# the library's property keys, after #key: its values", () => {
  const keys = suggest("a __creature#", 13, DATA);
  assert.deepEqual(keys.items.map((i) => i.insert), ["#habitat:", "#size:"]);
  assert.equal(keys.replaceFrom, 12);
  const text = "a __creature[myth]#size:small#habitat:s";
  const values = suggest(text, text.length, DATA);
  assert.deepEqual(values.items.map((i) => [i.insert, i.label, i.detail, i.preview]), [["#habitat:sea__", "sea", "9×", "a manta ray"]]);
  assert.equal(text.slice(0, values.replaceFrom), "a __creature[myth]#size:small");
  assert.deepEqual(suggest("__animal#", 9, DATA).items, []);  // a library without properties offers nothing
});

test("a tag after others completes in place: [myth,!de…", () => {
  const s = at("a __creature[myth,!de");
  assert.deepEqual(s.items.map((i) => i.insert), ["__creature[myth,!deep_sea]__"]);
  assert.equal(s.replaceFrom, 2);
  assert.deepEqual(at("__creature[deep_sea|m").items.map((i) => i.insert), ["__creature[deep_sea|myth]__"]);
});


test("inside the brackets: tags and keys, a key's values, another value of the key", () => {
  const keys = at("__creature[myth, ha").items.map((i) => i.insert);
  assert.deepEqual(keys, ["__creature[myth, habitat="]);
  assert.deepEqual(at("__creature[habitat=s").items.map((i) => i.insert), ["__creature[habitat=sea]__"]);
  assert.deepEqual(at("__creature[habitat=sea|f").items.map((i) => i.insert), ["__creature[habitat=sea|forest]__"]);
  assert.deepEqual(at("__creature[!d").items.map((i) => i.insert), ["__creature[!deep_sea]__"]);
});

test("@ at the start of a line offers the directives", () => {
  const s = at("a fox\n@g");
  assert.deepEqual(s.items.map((i) => i.insert), ["@grid "]);
  assert.equal(s.replaceFrom, 6);
  assert.equal(at("a fox @g").items.length, 0);
});

test("the template's own libraries complete, highlight and are not missing", () => {
  const text = "@lib crowd\n  a few __animal__s\n  - a lone __animal__\nA meadow with __cr";
  assert.deepEqual(inlineLibraries(text), [{ name: "crowd", entries: ["a few __animal__s", "a lone __animal__"] }]);
  assert.ok(suggest(text, text.length, DATA).items.some((i) => i.insert === "__crowd__"));
  assert.deepEqual(missingLibraries("@lib crowd\n  x\n__crowd__ __nope__", DATA), ["nope"]);
});

test("globs: ** offered when it reaches further, known when they match, missing when they match nothing", () => {
  const data = { ...DATA, libraries: [...DATA.libraries, { name: "clothing/hats", count: 2, source: "user", tags: [], sample: [] },
    { name: "clothing/winter/coats", count: 1, source: "user", tags: [], sample: [] }] };
  assert.deepEqual(suggest("__clothing/", 11, data).items.slice(0, 2).map((i) => i.insert), ["__clothing/*__", "__clothing/**__"]);
  assert.deepEqual(missingLibraries("__clothing/*__ __clothing/**__ __shoes/*__", data), ["shoes/*"]);
  assert.deepEqual(globMatches("clothing/**", data.libraries.map((l) => l.name)), ["clothing/hats", "clothing/winter/coats"]);
});


test("GOTO: completes the chunk titles, after a condition too", () => {
  const text = "@h3 t2va\nCHUNK the gate\nSHOT 5s\nA.\nCHUNK the stairs repeat 2\nSHOT 5s\nB.\nGOTO: the s";
  assert.deepEqual(suggest(text, text.length, DATA).items.map((i) => i.insert), ["the stairs"]);
  const cond = text.replace("GOTO: the s", "? $w[rain]: GOTO: ");
  assert.deepEqual(suggest(cond, cond.length, DATA).items.map((i) => i.insert), ["the gate", "the stairs"]);
  assert.ok(suggest("@h3 t2va\nCHUNK a\nGO", 19, DATA).items.some((i) => i.insert === "GOTO: "));
});

test("two capitals complete a CAST name; at a line's start also as a line of speech", () => {
  const head = "@h3 ref2va 16:9\nCAST\nKEEPER (image 1): an old lighthouse keeper\nMAYA: a young woman\n\nSHOT 5s: static\n";
  const inProse = head + "The light finds KE";
  assert.deepEqual(suggest(inProse, inProse.length, DATA).items.map((i) => i.insert), ["KEEPER"]);
  const atStart = head + "MA";
  assert.deepEqual(suggest(atStart, atStart.length, DATA).items.map((i) => i.insert), ["MAYA", "MAYA ("]);
  assert.equal(suggest(head + "A K", head.length + 3, DATA).items.length, 0);  // one capital is a word
  const chunkCast = "@h3 ref2va\nCHUNK a\nCAST\nGIRL (image 1): a girl\nSHOT 5s\nGI";
  assert.deepEqual(suggest(chunkCast, chunkCast.length, DATA).items.map((i) => i.insert), ["GIRL", "GIRL ("]);
  assert.deepEqual(castNames(head), ["KEEPER", "MAYA"]);
});

const CAST_HEAD = "@h3 ref2va\nCAST\n";
const names = (text) => at(text).items.map((i) => i.insert);

test("refmod in a CAST member's parentheses lists the RefMods, prefix matches first", () => {
  assert.deepEqual(names(`${CAST_HEAD}SALON (refmod `), ["allie_refMod", "orrery_abc_salon", "salon_old/abc", "Zelda_refMod"]);
  assert.deepEqual(names(`${CAST_HEAD}SALON (refmod sal`), ["salon_old/abc", "orrery_abc_salon"]);
  assert.equal(at(`${CAST_HEAD}SALON (refmod sal`).replaceFrom, `${CAST_HEAD}SALON (refmod `.length);
});

test("the parentheses offer refmod and global, then a RefMod's strength and start", () => {
  assert.deepEqual(names(`${CAST_HEAD}SALON (re`), ["refmod "]);
  assert.deepEqual(names(`${CAST_HEAD}SALON (image 1, gl`), ["global"]);
  assert.deepEqual(names(`${CAST_HEAD}SALON (refmod orrery_abc_salon `), ["at 1", "from 35%"]);
  assert.deepEqual(names(`${CAST_HEAD}SALON (refmod orrery_abc_salon at 0.5 f`), ["from 35%"]);
});

test("a line of speech in a shot gets no RefMod words", () => {
  assert.deepEqual(names("@h3 ref2va\nSHOT 5s\nMAYA (g"), []);
});

test("the refmods: line completes as a keyword, then its defaults", () => {
  assert.ok(names("@h3 ref2va\nref").includes("refmods: "));
  assert.deepEqual(names("@h3 ref2va\nrefmods: "), ["at 1 from 0%", "at 0.5", "from 35%"]);
});

test("SET: lists the CAST's RefMods and pictures as name(strength, start)", () => {
  const head = `${CAST_HEAD}EMMA (refmod emma_canon, image 1): a woman\nTOM (image 3): a man\nCHUNK\nSHOT 5s: static\n`;
  assert.deepEqual(names(`${head}SET: `), ["emma_canon(1, 0%)", "image_1(1, 0%)", "image_3(1, 0%)"]);
  assert.deepEqual(names(`${head}SET: image_1(0.5, 35%), em`), ["emma_canon(1, 0%)"]);
  assert.deepEqual(names(`${head}SET: image_1(0.`), []);
});
