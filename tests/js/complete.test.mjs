import { test } from "node:test";
import assert from "node:assert/strict";
import { suggest, missingLibraries } from "../../comfyui/web/orrery-complete.js";

const DATA = {
  libraries: [
    { name: "creature", count: 24, source: "builtin", tags: ["deep_sea", "myth"], sample: ["axolotl"] },
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

test("camera vocabulary after SHOT |", () => {
  const first = at("@h3 t2va\nSHOT 5s | pu").items.map((i) => i.insert);
  assert.ok(first.includes("push in") && first.includes("pull out"));
  const mods = at("@h3 t2va\nSHOT 5s | push in, s").items.map((i) => i.insert);
  assert.deepEqual(mods, ["small", "slow"]);
});

test("a fully typed word is not offered again", () => {
  assert.ok(!at("@h3 t2va\nSHOT 5s | push in").items.some((i) => i.insert === "push in"));
});

test("transitions are offered first on later shots", () => {
  const items = at("@h3 t2va\nSHOT 3s\nA.\nSHOT 3s | ").items.map((i) => i.insert);
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
  assert.ok(["CHUNK", "HANDOFF: ", "LORA: ", "context: "].every((k) => at(`@h3 t2va\n${k[0]}`).items.some((i) => i.insert === k)), items.join());
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
  assert.deepEqual(inFolder, ["__film/genre__"]);
  assert.ok(suggest("a __fi", 6, data).items.some((i) => i.insert === "__film/genre__"));
  assert.deepEqual(missingLibraries("__film/genre__ and __film/new__", data), ["film/new"]);
});

test("comments neither complete nor count as missing libraries", () => {
  assert.deepEqual(missingLibraries("# try __nothing__ here\n__creature__", DATA), []);
  const text = "# __cre";
  assert.equal(suggest(text, text.length, DATA).items.length, 0);
  const h3 = "# a comment first\n@h3 t2va\nSHOT 5s | ";
  assert.ok(suggest(h3, h3.length, DATA).items.some((i) => i.insert === "push in"));
});
