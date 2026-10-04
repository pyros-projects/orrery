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

test("reel keywords at line start in screenplays, the film words and not the earlier ones", () => {
  const offered = (k) => at(`@h3 text\n${k.slice(0, 2)}`).items.some((i) => i.insert === k);
  assert.ok(["SCENE ", "END ON: ", "CUT TO: ", "AFTER: ", "START WITH: ", "REMEMBER: ", "IF $", "LORA: ", "context: "].every(offered));
  assert.ok(!["CHUNK", "HANDOFF: ", "GOTO: ", "SEND: "].some(offered));
});

test("the @h3 line completes the mode words", () => {
  assert.deepEqual(names("@h3 "), ["text", "references", "image", "first-last", "last"]);
  assert.deepEqual(names("@h3 fi"), ["first-last"]);
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


test("GOTO: (the earlier CUT TO:) completes the titles, after a condition too", () => {
  const text = "@h3 t2va\nCHUNK the gate\nSHOT 5s\nA.\nCHUNK the stairs repeat 2\nSHOT 5s\nB.\nGOTO: the s";
  assert.deepEqual(suggest(text, text.length, DATA).items.map((i) => i.insert), ["the stairs"]);
  const cond = text.replace("GOTO: the s", "? $w[rain]: GOTO: ");
  assert.deepEqual(suggest(cond, cond.length, DATA).items.map((i) => i.insert), ["the gate", "the stairs"]);
  assert.ok(suggest("@h3 t2va\nCHUNK a\nCU", 19, DATA).items.some((i) => i.insert === "CUT TO: "));
});

test("CUT TO: completes the scene titles, as GOTO: does", () => {
  const text = "@h3 text\nSCENE the gate\nSHOT 5s\nA.\nSCENE the stairs (test) ×2\nSHOT 5s\nB.\nCUT TO: the s";
  assert.deepEqual(suggest(text, text.length, DATA).items.map((i) => i.insert), ["the stairs"]);
  const cond = text.replace("CUT TO: the s", "? $w[rain]: CUT TO: ");
  assert.deepEqual(suggest(cond, cond.length, DATA).items.map((i) => i.insert), ["the gate", "the stairs"]);
});

test("a CAST member written with @ is a name like any other, and the block goes on after it", () => {
  assert.deepEqual(castNames("@h3 references\nCAST\n@KEEPER (image 1): a keeper\nMAYA: a woman\n@lib x\nGHOST: no member"), ["KEEPER", "MAYA"]);
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

test("the parentheses offer refmod and always, then a RefMod's strength and start", () => {
  assert.deepEqual(names(`${CAST_HEAD}SALON (re`), ["refmod "]);
  assert.deepEqual(names(`${CAST_HEAD}@SALON (image 1, al`), ["always"]);
  assert.deepEqual(names(`${CAST_HEAD}SALON (refmod orrery_abc_salon `), ["at 1", "from 35%", "to 50%"]);
  assert.deepEqual(names(`${CAST_HEAD}SALON (refmod orrery_abc_salon at 0.5 f`), ["from 35%"]);
});

test("a line of speech in a shot gets no RefMod words", () => {
  assert.deepEqual(names("@h3 ref2va\nSHOT 5s\nMAYA (g"), []);
});

test("the refmods: line completes as a keyword, then its defaults", () => {
  assert.ok(names("@h3 ref2va\nref").includes("refmods: "));
  assert.deepEqual(names("@h3 ref2va\nrefmods: "), ["at 1 from 0%", "at 0.5", "from 35%", "to 50%"]);
});

test("SET: lists the CAST's RefMods and pictures as name(strength, start)", () => {
  const head = `${CAST_HEAD}EMMA (refmod emma_canon, image 1): a woman\nTOM (image 3): a man\nCHUNK\nSHOT 5s: static\n`;
  assert.deepEqual(names(`${head}SET: `), ["@EMMA(1)", "@TOM(1)", "emma_canon(1, 0%)", "image_1(1, 0%)", "image_3(1, 0%)", "refmods(1, 0%)"]);
  assert.deepEqual(names(`${head}SET: image_1(0.5, 35%), em`), ["emma_canon(1, 0%)"]);
  assert.deepEqual(names(`${head}SET: image_1(0.`), []);
  assert.deepEqual(names(`${head}SET: @EMMA(0.6, `), ["refmods", "images", "refmod emma_canon", "image 1"]);
  assert.deepEqual(names(`${head}SET: @EMMA(0.6, re`), ["refmods", "refmod emma_canon"]);
});

test("@ names a CAST member: in prose, in a line of speech, and next to the directives at a line's start", () => {
  const head = `${CAST_HEAD}JINX (refmod jinx): a young woman\nOLD_MAN: a fisher\nSHOT 5s: static\n`;
  assert.deepEqual(names(`${head}The light finds @J`), ["@JINX"]);
  assert.deepEqual(names(`${head}@`).slice(0, 4), ["@JINX", "@JINX (", "@OLD_MAN", "@OLD_MAN ("]);
  assert.ok(names(`${head}@`).includes("@grid "));
  assert.deepEqual(names("@h3 text\nSHOT 5s\nA @"), []);  // no CAST: nothing to name
});

test("AFTER: completes the scene titles, and REMEMBER: what to keep, as whom, for which clips", () => {
  const reel = `${CAST_HEAD}KEEPER: an old keeper\nSCENE the gate\nSHOT 5s\nA.\nSCENE the stairs (test)\nSHOT 5s\nB.\n`;
  assert.deepEqual(names(`${reel}AFTER: the s`), ["the stairs"]);
  assert.deepEqual(names(`${reel}AFTER: the `), ["the gate", "the stairs", "the input video"]);
  assert.deepEqual(names(`${reel}CUT TO: the `), ["the gate", "the stairs"]);  // a jump never goes to the video
  assert.deepEqual(names(`${reel}REMEMBER: `), ["first frame as ", "last frame as ", "frame at 1s as ", "frames 34-46 as ", "every 10th frame as "]);
  assert.deepEqual(names(`${reel}REMEMBER: first frame as `), ["@KEEPER", "image ", "refmod "]);
  assert.deepEqual(names(`${reel}REMEMBER: first frame as @KEEPER `), ["in clips 2-5", "until "]);
  assert.deepEqual(names(`${reel}REMEMBER: first frame as @KEEPER until the g`), ["the gate"]);
});

test("a keyword's start offers the keyword and every form of it (#135)", () => {
  const items = at("@h3 references\nSHOT 5s\nA.\nREME").items.map((i) => i.insert);
  assert.equal(items[0], "REMEMBER: ");
  assert.ok(items.includes("REMEMBER: frames 0, 50 as @NAME") && items.includes("REMEMBER: every 10th frame as refmod NAME"));
  const set = at("@h3 references\nSHOT 5s\nA.\nSET").items;
  assert.ok(set.some((i) => i.insert === "SET: @NAME(1, 35%, 80%)" && i.detail === "strength, start and end"));
  assert.equal(at("@h3 references\nSHOT 5s\nA.\nR").items.filter((i) => i.insert.startsWith("REMEMBER: ") && i.insert.length > 10).length, 0,
    "one letter offers the keywords only, not every form");
});

test("text templates get their own keywords: EXPORT:, IF $ (#135)", () => {
  const items = at("$who = a heron\nEXP").items.map((i) => i.insert);
  assert.ok(items.includes("EXPORT: ") && items.includes("EXPORT:\n  who = $who\n  mood = __characters/creator/mood__"));
  assert.ok(at("a fox\nIF").items.some((i) => i.insert === "IF $x is a, b: the line"));
  assert.ok(!at("@h3 t2va\nSHOT 5s\nA.\nEXP").items.some((i) => i.insert.startsWith("EXPORT")));  // a screenplay leaves it out
});

test("after $name. the fields of what the binding rolls, and @h3 and @lib among the directives (#135)", () => {
  const data = { ...DATA, libraries: [...DATA.libraries, { name: "pictures/krea/x", count: 2, source: "builtin", tags: [], sample: [],
    props: {}, fields: ["mood", "pictures", "prompt", "who"] }] };
  const atEnd = (t) => suggest(t, t.length, data).items.map((i) => i.insert);
  const fields = atEnd("$hero = __pictures/krea/x[exported]__\n$hero.");
  assert.deepEqual(fields, ["who", "mood", "prompt"]);  // what a character carries first; ids and pictures are the app's
  const now = suggest("$hero = __pictures/krea/x__\n$hero.", 34, { ...data, fieldValues: { hero: { who: "a tall heron" } } }).items[0];
  assert.deepEqual([now.insert, now.detail], ["who", "now: a tall heron"]);
  assert.deepEqual(atEnd("$hero = __pictures/krea/x__\n$hero.wh"), ["who"]);
  const directives = at("@").items.map((i) => i.insert);
  assert.ok(directives.includes("@h3 ") && directives.includes("@lib "));
});

test("after image in a CAST: the gallery's presets to roll from and its characters, with their pictures (#137)", () => {
  const data = { ...DATA, pictures: [{ preset: "krea/09_character_creator", count: 2, characters: [
    { name: "krea/09_character_creator/7", ids: ["a1", "a2"], views: 2, tags: ["exported"], who: "a tall heron in a red coat" },
    { name: "krea/09_character_creator/9", ids: ["b1"], views: 1, tags: [], who: "an old fox" }] }] };
  const text = "@h3 references\nCAST\n@HERO (image ";
  const items = suggest(text, text.length, data).items;
  assert.equal(items[0].insert, "__pictures/krea/09_character_creator__");
  assert.deepEqual(items[0].thumbIds, ["a1", "b1"]);
  assert.deepEqual(items.slice(1).map((i) => [i.insert, i.thumbId]), [["krea/09_character_creator/7", "a1"], ["krea/09_character_creator/9", "b1"]]);
  const fox = suggest(`${text}fox`, text.length + 3, data).items.map((i) => i.insert);
  assert.deepEqual(fox, ["krea/09_character_creator/9"]);  // who matches too
  const typed = "@h3 references\nCAST\n@HERO (i";
  assert.ok(suggest(typed, typed.length, data).items.some((i) => i.insert === "image "));
});

test("after as image and from image: the slots, each saying what has it already", () => {
  const text = "@h3 references\nCAST\n@HERO (image 1, image 3): a heron\nSHOT 5s: static\nREMEMBER: frame 0 as image 4\nREMEMBER: first frame as image ";
  const items = suggest(text, text.length, DATA).items;
  assert.deepEqual(items.slice(0, 5).map((i) => [i.label, i.detail]), [["image 1", "HERO's picture"], ["image 2", "free"],
    ["image 3", "HERO's picture"], ["image 4", "a REMEMBER: line's frames"], ["image 5", "free"]]);
  assert.equal(items.length, 9);
  const shot = "@h3 references\nCAST\n@HERO (image 2): a heron\nSHOT 5s: from image ";
  assert.equal(suggest(shot, shot.length, DATA).items[1].detail, "HERO's picture");
});

test("the knobs' long forms complete: < offers their kinds, then each kind its names (#227)", () => {
  assert.deepEqual(names("@h3 ref2va\nSET: <"), ["<lora:", "<refmod:", "<image:", "<cast:", "<Image "]);
  assert.deepEqual(names("@h3 ref2va\nSET: <re"), ["<refmod:"]);
  assert.deepEqual(names("@h3 ref2va\nSET: <Im"), ["<image:", "<Image "]);
  assert.deepEqual(names("@h3 ref2va\nSET: <refmod:sal"), ["<refmod:salon_old/abc:1>", "<refmod:orrery_abc_salon:1>"]);
  assert.deepEqual(names("@h3 ref2va\nSET: <lora:mot").slice(0, 1), ["<lora:Motion_Repair:1.00>"]);
  assert.deepEqual(names("@h3 ref2va\nCAST\n@JINX (image 1): a woman\n\nSET: <cast:"), ["<cast:JINX:1>"]);
  assert.equal(names("@h3 ref2va\nSET: <image:").length, 9);
  assert.deepEqual(names("a cat <"), ["<lora:"]);  // a text prompt: LoRAs only
  assert.ok(!names("@h3 ref2va\nSHOT 5s: static\na cat with fur").some((n) => n.startsWith("<")));  // no <, no knobs
});
