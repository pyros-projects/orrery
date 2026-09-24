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
