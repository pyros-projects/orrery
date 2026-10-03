// Pure completion logic for the Orrery Prompt editor (no DOM; tested with node --test).
//
// suggest(text, caret, data) -> { items: [{ insert, detail, preview }], replaceFrom }
// Accepting an item replaces text[replaceFrom:caret] with item.insert.

// The words the editor teaches, each with what it does and its forms: typing a keyword's start offers
// the keyword and every form of it (`REME` → all of REMEMBER:'s). The earlier CHUNK, HANDOFF:, GOTO:
// and SEND: still work, unoffered. `where`: screenplays, text templates or both.
export const KEYWORDS = [
  { word: "SHOT ", where: "h3", says: "a shot: its length, then the camera", forms: [
    ["SHOT 5s: static", "a held shot"], ["SHOT 4s: push in, small, slow", "a camera move, its amplitude and speed"],
    ["SHOT 5s: from image 1", "opens on a picture (a frame anchor)"], ["SHOT 5s: to image 2", "ends on a picture"],
    ["SHOT 5s: after video 1", "continues a video from its last frame"]] },
  { word: "SFX: ", where: "h3", says: "the shot's sounds", forms: [["SFX: rain on the glass, a spoon against a mug", "sounds, comma by comma"], ["SFX: silence", "no sound at all"]] },
  { word: "MUSIC: ", where: "h3", says: "music under the clip", forms: [["MUSIC: a slow piano, far away", "what plays and how"]] },
  { word: "style: ", where: "h3", says: "the look of the whole clip", forms: [["style: live-action, warm evening light, handheld", "medium, light, camera"]] },
  { word: "summary: ", where: "h3", says: "the references' summary (full format)", forms: [["summary: The target video shows @NAME in @PLACE.", "who and where, by CAST name"]] },
  { word: "CAST", where: "h3", says: "who and what the clip has: a member per line", forms: [
    ["CAST\n@NAME (image 1): who they are", "a member with a picture"], ["CAST\n@NAME (image __pictures/krea/09_character_creator__): $hero.who", "a member from the gallery"],
    ["CAST\n@NAME (refmod NAME): who they are", "a member made of a RefMod"]] },
  { word: "voice: ", where: "h3", says: "after a member: the voice it speaks with", forms: [["voice: audio 1, a calm low voice", "a recorded voice and a note"], ["voice: video 1 audio", "the voice of a video's soundtrack"]] },
  { word: "keep: ", where: "h3", says: "what a reference keeps", forms: [
    ["keep: face, outfit", "only these"], ["keep: all", "everything"], ["keep: style", "only its style"], ["keep: place", "a place: layout, surfaces, light"],
    ["keep: loose", "a loose reference"], ["keep: fully_preserved - the reason", "a marker and its reason"]] },
  { word: "SCENE ", where: "h3", says: "starts a clip of a reel", forms: [
    ["SCENE the title", "a clip, named for CUT TO: and AFTER:"], ["SCENE the title ×3", "played three times"], ["SCENE the title forever", "until you stop"],
    ["SCENE the title (test)", "a test scene, left out of the film"]] },
  { word: "END ON: ", where: "h3", says: "how a scene ends, and the next one opens", forms: [["END ON: @NAME turns toward the door", "its closing sentence"]] },
  { word: "START WITH: ", where: "h3", says: "this scene's own opening", forms: [["START WITH: @NAME already at the window", "in place of the END ON: before it"]] },
  { word: "AFTER: ", where: "h3", says: "which clip this one continues", forms: [["AFTER: 2", "scene 2's last clip (by title or number)"], ["AFTER: the input video", "the video wired into the Orrery Prompt"]] },
  { word: "CUT TO: ", where: "h3", says: "at a scene's end: jump there instead", forms: [
    ["CUT TO: the title", "a jump, for good"], ["CUT TO: the title ×2", "twice"], ["CUT TO: the title (30%)", "that often"],
    ["IF $w is storm: CUT TO: the title", "on what this clip rolled"]] },
  { word: "REMEMBER: ", where: "h3", says: "frames of this clip, kept for the clips after it", forms: [
    ["REMEMBER: first frame as @NAME", "the first frame becomes the member's picture"], ["REMEMBER: last frame as @NAME", "its last frame"],
    ["REMEMBER: frames 0, 50 as @NAME", "a picture of the member per frame"], ["REMEMBER: frame at 1s as image 3", "a numbered picture of the CAST"],
    ["REMEMBER: every 10th frame as refmod NAME", "a RefMod made of the frames"], ["REMEMBER: last frame as image 5 in clips 5+", "only for those clips"],
    ["REMEMBER: frame 0 as image 7 until the title", "until a scene first plays"]] },
  { word: "SET: ", where: "h3", says: "turns a member's or a picture's strength", forms: [
    ["SET: @NAME(0.6)", "all its pictures and RefMods"], ["SET: @NAME(0.6, 35%)", "a strength and when it starts"],
    ["SET: @NAME(1, 35%, 80%)", "strength, start and end"], ["SET: @NAME(0.5, refmods)", "only its RefMods"],
    ["SET: image_1(0.5, 35%)", "one picture by its name"], ["SET: refmods(1, 35%)", "the RefMods without their own"]] },
  { word: "IF $", where: "both", says: "a line kept only when its condition holds", forms: [
    ["IF $x is a, b: the line", "x rolled either"], ["IF $x is not a: the line", "x rolled something else"],
    ["IF $x[myth]: the line", "a tag or a property of what x rolled"], ["IF $w.kind is rain: the line", "a property's value"]] },
  { word: "EXPORT: ", where: "text", says: "kept with the picture, never in the prompt", forms: [
    ["EXPORT: mood = __moods__", "one value"], ["EXPORT: $who", "a binding, with its entry's fields"],
    ["EXPORT:\n  who = $who\n  mood = __moods__", "a block: one per line"], ["EXPORT: backstory = --two sentences of backstory for $who--", "written by the language model"]] },
  { word: "LORA: ", where: "h3", says: "LoRAs for this clip", forms: [["LORA: <lora:NAME:0.8>", "a LoRA and its strength"], ["LORA: __my_lora_sets__", "a library of LoRA sets"]] },
  { word: "context: ", where: "h3", says: "how many frames a continuation pins", forms: [["context: 22", "the last 22 frames"]] },
  { word: "refmods: ", where: "h3", says: "the RefMods' defaults", forms: [["refmods: at 1 from 35%", "strength and start"]] },
];
const NONE = { items: [], replaceFrom: 0 };

const startsWith = (word, prefix) => word.toLowerCase().startsWith(prefix.toLowerCase());

// A library reference up to where a property filter starts: __lib, __lib[tag], earlier #key:value.
const LIB_HEAD = String.raw`__([\w/]+)(?:\[[^\[\]\n]+\])?(?:#[\w-]+:\$?[\w.-]+)*`;

// After __lib#key: the values that library's entries carry; after __lib# its keys.
function propItems(before, data) {
  let m = before.match(new RegExp(String.raw`(?:^|[^\w])${LIB_HEAD}#([\w-]+):([\w.-]*)$`));
  if (m) {
    const values = (data.libraries.find((l) => l.name === m[1])?.props?.[m[2]] ?? []).filter((v) => startsWith(v.value, m[3]));
    return {
      items: values.map((v) => ({ insert: `#${m[2]}:${v.value}__`, label: v.value, detail: `${v.count}×`, preview: v.sample })),
      replaceFrom: before.length - m[2].length - m[3].length - 2,
    };
  }
  m = before.match(new RegExp(String.raw`(?:^|[^\w])${LIB_HEAD}#([\w-]*)$`));
  if (!m) return null;
  const props = data.libraries.find((l) => l.name === m[1])?.props ?? {};
  return {
    items: Object.keys(props).filter((k) => startsWith(k, m[2])).map((k) => ({
      insert: `#${k}:`, label: `#${k}`, detail: `${props[k].length} value${props[k].length === 1 ? "" : "s"}`,
      preview: props[k].slice(0, 6).map((v) => v.value).join(", ") + (props[k].length > 6 ? ", …" : ""),
    })),
    replaceFrom: before.length - m[2].length - 1,
  };
}

// Where a query hits a library name: 0 at its start, 1 at the start of a folder or word (after / or _),
// 2 anywhere else, -1 nowhere.
function nameRank(name, query) {
  const n = name.toLowerCase(), q = query.toLowerCase();
  if (n.startsWith(q)) return 0;
  let at = n.indexOf(q);
  if (at < 0) return -1;
  for (; at >= 0; at = n.indexOf(q, at + 1)) if ("/_".includes(n[at - 1])) return 1;
  return 2;
}

function libraryItems(before, data) {
  const props = propItems(before, data);
  if (props) return props;
  // inside the brackets, the term being typed: a tag or a key (`[myth, !bi…`, `[hab…`), a key's value
  // (`[habitat=s…`), or another value of the key before it (`[size=small|ti…`)
  let m = before.match(/(?:^|[^\w])(__([\w/]+)\[([^\]\n]*))$/);
  if (m) {
    const lib = data.libraries.find((l) => l.name === m[2]), inner = m[3];
    const cut = Math.max(inner.lastIndexOf(","), inner.lastIndexOf("|")), head = inner.slice(0, cut + 1);
    const lead = inner.slice(cut + 1).match(/^\s*!?\s*/)[0], atom = inner.slice(cut + 1 + lead.length);
    const term = inner.slice(inner.lastIndexOf(",") + 1), keyed = /([\w-]+)\s*!?=/.exec(term);
    const kv = /^([\w-]+)\s*(!?=)\s*(.*)$/.exec(atom);
    const key = kv ? kv[1] : inner[cut] === "|" && keyed ? keyed[1] : null;
    const at = (text) => ({ insert: `__${m[2]}[${text}`, replaceFrom: before.length - m[1].length });
    if (key && lib?.props?.[key]) {
      const typed = kv ? kv[3] : atom, prefix = kv ? `${head}${lead}${kv[1]}${kv[2]}` : `${head}${lead}`;
      const values = lib.props[key].filter((v) => startsWith(v.value, typed));
      return { items: values.map((v) => ({ ...at(`${prefix}${v.value}]__`), label: v.value, detail: `${key} · ${v.count}×`, preview: v.sample })),
        replaceFrom: before.length - m[1].length };
    }
    const tags = (lib?.tags ?? []).filter((t) => startsWith(t, atom));
    const keys = Object.keys(lib?.props ?? {}).filter((k) => startsWith(k, atom));
    return {
      items: [...tags.map((t) => ({ insert: `__${m[2]}[${head}${lead}${t}]__`, detail: "tag", preview: "" })),
        ...keys.map((k) => ({ insert: `__${m[2]}[${head}${lead}${k}=`, label: `${k}=`, detail: `${lib.props[k].length} values`,
          preview: lib.props[k].slice(0, 6).map((v) => v.value).join(", ") }))],
      replaceFrom: before.length - m[1].length,
    };
  }
  m = before.match(/(?:^|[^\w])(__([\w/]*))$/);
  if (!m) return null;
  // a folder typed (`__clothing/`): `*` a library of this folder, `**` of it or below, then its entry
  const names = data.libraries.map((l) => l.name);
  const globs = !m[2].endsWith("/") ? [] : [["*", "this folder"], ["**", "this folder and below"]]
    .map(([g, where]) => ({ g: `${m[2]}${g}`, where, hits: globMatches(`${m[2]}${g}`, names) }))
    .filter((x, i, all) => x.hits.length && (i === 0 || x.hits.length > all[0].hits.length))
    .map(({ g, where, hits }) => ({ insert: `__${g}__`, detail: `${hits.length} libraries in ${where}, one at random`,
      preview: hits.slice(0, 4).join(", ") + (hits.length > 4 ? ", …" : "") }));
  return {
    items: [...globs, ...data.libraries
      .map((l) => ({ l, rank: nameRank(l.name, m[2]) }))
      .filter((x) => x.rank >= 0)
      .sort((a, b) => a.rank - b.rank || a.l.name.localeCompare(b.l.name))
      .map(({ l }) => ({
        insert: `__${l.name}__`,
        detail: `${l.count} · ${l.source}`,
        preview: l.sample.join(", ") + (l.count > l.sample.length ? ", …" : ""),
      }))],
    replaceFrom: before.length - m[1].length,
  };
}

// `$hero.` the fields of what the binding rolls: its library's properties (the gallery's pictures: who,
// mood …; weather: kind, sfx).
function fieldItems(before, text, data) {
  const m = before.match(/\$([A-Za-z_]\w*)\.([\w-]*)$/);
  if (!m) return null;
  const bound = new RegExp(`^\\s*\\$${m[1]}\\s*=\\s*__([\\w*/]+?)(?=__|\\[|#|:\\d)`, "m").exec(text);
  const lib = bound && data.libraries.find((l) => l.name === bound[1]);
  const fields = lib ? (lib.fields || Object.keys(lib.props || {})) : [];
  const items = fields.filter((f) => startsWith(f, m[2]) && f !== m[2]).map((f) => ({ insert: f, detail: `a field of __${lib.name}__`, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - m[2].length } : null;
}

function bindingItems(before, text) {
  const m = before.match(/(?:^|[^$\w])(\$(\w*))$/);
  if (!m) return null;
  const names = [...new Set([...text.matchAll(/^\s*\$([A-Za-z_]\w*)\s*=/gm)].map((b) => b[1]))];
  return {
    items: names.filter((n) => startsWith(n, m[2]))
      .map((n) => ({ insert: `$${n}`, detail: "binding", preview: "" })),
    replaceFrom: before.length - m[1].length,
  };
}

function shotItems(before, line, data) {
  const m = line.match(/^\s*SHOT\s+[\d.]+s?\s*[:|](.*)$/i);  // `|`: the older spelling
  if (!m) return null;
  const segments = m[1].split(",");
  const fragment = segments.pop().trimStart();
  const used = segments.map((s) => s.trim().toLowerCase());
  const { camera, modifiers, transitions } = data.h3;
  let words;
  if (used.length === 0) {
    const laterShot = /^\s*SHOT\b/im.test(before.slice(0, before.length - line.length));
    words = [...(laterShot ? transitions : []), ...camera];
  } else if (used.some((u) => camera.includes(u))) {
    words = modifiers.filter((w) => !used.includes(w));
  } else {
    words = camera;
  }
  return {
    items: words.filter((w) => startsWith(w, fragment))
      .map((w) => ({ insert: w, detail: transitions.includes(w) ? "transition" : "camera", preview: "" })),
    replaceFrom: before.length - fragment.length,
  };
}

// The reel's scene titles (a number for a scene without one), as CUT TO:, AFTER: and `until` name them.
const sceneTitles = (text) => text.split("\n")
  .map((l) => /^\s*(?:SCENE|CHUNK)\b\s*(.*?)(?:\s+repeat\s+(?:\d+|forever)|\s+[×x]\s*\d+|\s+forever)?\s*$/i.exec(l)).filter(Boolean)
  .map((c, i) => c[1].replace(/(?<!\S)\(test\)(?!\S)/i, " ").split(/\s+/).filter(Boolean).join(" ") || String(i + 1));

// CUT TO: (GOTO:, the earlier word; alone, or after `? cond:` / `IF …:`) and AFTER:: the scenes, by title;
// AFTER: also the input video.
function gotoItems(before, line, text) {
  const cut = /^\s*(?:(?:\?|IF\s+(?=\$))[^\n]*?:\s*)?(?:CUT\s+TO|GOTO):\s*([^×(]*)$/i.exec(line);
  const after = /^\s*AFTER:\s*(.*)$/.exec(line);
  const m = cut || after;
  if (!m) return null;
  const detail = cut ? "jump to this scene; ×N after it: N times, (30%) that often" : "continue this scene's last clip";
  const items = sceneTitles(text).filter((t) => startsWith(t, m[1])).map((t) => ({ insert: t, detail, preview: "" }));
  if (after && startsWith("the input video", m[1])) {
    items.push({ insert: "the input video", detail: "continue the video wired into the Orrery Prompt", preview: "" });
  }
  return { items, replaceFrom: before.length - m[1].length };
}

// REMEMBER: what to keep (first frame, frame at 1s, every 10th frame), then as whom or what, then for
// which clips (in clips 2-5, until a scene).
function rememberItems(before, line, text) {
  const m = /^\s*REMEMBER:\s*(.*)$/.exec(line);
  if (!m) return null;
  const said = m[1];
  const until = /\buntil\s+(.*)$/i.exec(said);
  let options, typed;
  if (until) {
    [typed, options] = [until[1], sceneTitles(text).map((t) => [t, "until that scene first plays"])];
  } else if (/\bas\s+\S+.*\s$/i.test(said)) {
    [typed, options] = ["", [["in clips 2-5", "only those clips, counted from 1"], ["until ", "until a scene first plays"]]];
  } else if (/\bas\s+(\S*)$/i.test(said)) {
    typed = /\bas\s+(\S*)$/i.exec(said)[1];
    options = [...castNames(text).map((n) => [`@${n}`, `${n}'s picture: the CAST's, or a free one`]),
               ["image ", "a picture: image N, as the CAST numbers them"], ["refmod ", "a RefMod made of the frames: refmod NAME"]];
  } else if (!/\bas\b/i.test(said) && !/\S\s+\S+\s/.test(said)) {
    typed = said;
    options = [["first frame as ", "the clip's first frame (after the pinned ones)"], ["last frame as ", "its last frame"],
               ["frame at 1s as ", "the frame at that second"], ["frames 34-46 as ", "frames by number, from 0; -1 the last"],
               ["every 10th frame as ", "every 10th frame of the clip; … of 1s-4s: of a range"]];
  } else return null;
  const items = options.filter(([o]) => startsWith(o, typed) && o !== typed).map(([insert, detail]) => ({ insert, detail, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - typed.length } : null;
}

// `@` in a screenplay: the CAST's members, as @NAME (the way to name one you don't know the letters of).
function atCastItems(before, line, text) {
  const m = /(?:^|[^\w@<\\])@([A-Z][A-Z0-9_]*)?$/.exec(before);
  if (!m) return null;
  const typed = m[1] || "";
  const names = castNames(text).filter((n) => n.startsWith(typed) && n !== typed);
  if (!names.length) return null;
  const lineStart = new RegExp(`^\\s*@${typed}$`).test(line);
  return {
    items: names.flatMap((n) => [
      { insert: `@${n}`, detail: "cast", preview: "" },
      ...(lineStart ? [{ insert: `@${n} (`, label: `@${n} (…): `, detail: "a line of speech: how it sounds, then the words", preview: "" }] : []),
    ]),
    replaceFrom: before.length - typed.length - 1,
  };
}

// The CAST's names (every CAST block, a chunk's own too): `KEEPER (image 1): …`, `MAYA: …`.
export function castNames(text) {
  const names = [];
  let inCast = false;
  for (const raw of uncommented(text).split("\n")) {
    const l = raw.trim();
    if (/^CAST\s*$/.test(l)) { inCast = true; continue; }
    if (/^(SHOT\b|SCENE\b|CHUNK\b|@(?![A-Z]))/.test(l) || (inCast && !l)) { inCast = false; continue; }
    const m = inCast && /^@?([A-Z][A-Z0-9 _-]*?)\s*(?:\([^)]*\))?\s*:\s*\S/.exec(l);
    if (m && !names.includes(m[1])) names.push(m[1]);
  }
  return names;
}

// Two capitals at a word's start (`KE`) complete a CAST name; at a line's start also as a line of
// speech (`KEEPER (…): `), next to the screenplay keywords that match.
function castItems(before, line, text) {
  const m = /(?:^|[^\w$])([A-Z][A-Z0-9_]+)$/.exec(before);
  if (!m) return null;
  const names = castNames(text).filter((n) => n.startsWith(m[1]) && n !== m[1]);
  const lineStart = new RegExp(`^\\s*${m[1]}$`).test(line);
  if (!names.length) return null;
  const items = names.flatMap((n) => [
    { insert: n, detail: "cast", preview: "" },
    ...(lineStart ? [{ insert: `${n} (`, label: `${n} (…): `, detail: "a line of speech: how it sounds, then the words", preview: "" }] : []),
  ]);
  const keywords = lineStart ? keywordForms(m[1], true) : [];
  return { items: [...items, ...keywords], replaceFrom: before.length - m[1].length };
}

// A keyword typed at a line's start: the keyword, then each of its forms (whole lines).
function keywordForms(typed, screenplay) {
  return KEYWORDS.filter((k) => k.where === "both" || k.where === (screenplay ? "h3" : "text"))
    .filter((k) => startsWith(k.word, typed))
    .flatMap((k) => [{ insert: k.word, detail: k.says, preview: "" },
      ...(typed.length >= 2 ? k.forms.map(([insert, detail]) => ({ insert, label: insert.replace(/\n/g, " ⏎ "), detail, preview: "" })) : [])]);
}

function keywordItems(before, line, screenplay = true) {
  const m = line.match(/^([A-Za-z]+)$/);
  if (!m) return null;
  const items = keywordForms(m[1], screenplay);
  return items.length ? { items, replaceFrom: before.length - m[1].length } : null;
}

// LORA: lines: your LoRA files as <lora:name:1.00>, the syntax LoraManager's LoRA Text Loader
// reads; any part of the name matches, prefix matches first.
const LORA_CAP = 80;

function loraItems(before, line, data) {
  const m = /^\s*LORA:(.*)$/.exec(line);
  if (!m) return null;
  const token = /(?:^|[\s>])([^\s>]*)$/.exec(m[1])[1];
  const query = token.replace(/^<(?:l(?:o(?:r(?:a(?::)?)?)?)?)?/i, "").toLowerCase();
  if (query.includes(":")) return null;
  const hits = (data.loras || []).filter((l) => l.name.toLowerCase().includes(query));
  const ranked = [...hits.filter((l) => l.name.toLowerCase().startsWith(query)), ...hits.filter((l) => !l.name.toLowerCase().startsWith(query))];
  return {
    kind: "lora",
    items: ranked.slice(0, LORA_CAP).map((l) => ({
      insert: `<lora:${l.name}:1.00>`, label: l.name, detail: l.folder || "lora", preview: l.folder ? `${l.folder}/${l.name}` : l.name,
    })),
    replaceFrom: before.length - token.length,
  };
}

const uncommented = (text) => text.split("\n").filter((l) => !/^\s*#/.test(l)).join("\n");  // `# …` lines

// Whether the caret's line is a member line of a CAST block (castNames' reading of the lines above).
function inCast(before) {
  let open = false;
  for (const raw of uncommented(before).split("\n").slice(0, -1)) {
    const l = raw.trim();
    if (/^CAST\s*$/.test(l)) open = true;
    else if (/^(SHOT\b|SCENE\b|CHUNK\b|@(?![A-Z]))/.test(l) || (open && !l)) open = false;
  }
  return open;
}

// Inside a CAST member's parentheses: `refmod ` and `global`; after `refmod ` the RefMods in
// models/refmods (any part of the name matches, prefix matches first); after the name its strength
// and its start.
const REFMOD_CAP = 80;

function refmodItems(before, line, data) {
  const m = /^\s*@?[A-Z][A-Z0-9 _-]*?\s*\(([^)]*)$/.exec(line);
  if (!m || !inCast(before)) return null;
  const token = m[1].split(",").pop().replace(/^\s+/, "");
  const named = /^refmod\s+(\S*)$/i.exec(token);
  if (named) {
    const query = named[1].toLowerCase();
    const hits = (data.refmods || []).filter((n) => n.toLowerCase().includes(query));
    const ranked = [...hits.filter((n) => n.toLowerCase().startsWith(query)), ...hits.filter((n) => !n.toLowerCase().startsWith(query))];
    return { kind: "refmod", items: ranked.slice(0, REFMOD_CAP).map((n) => ({ insert: n, detail: "refmod", preview: "" })),
             replaceFrom: before.length - named[1].length };
  }
  const after = /^refmod\s+\S+((?:\s+\S+)*)\s+(\w*)$/i.exec(token);
  const word = after ? after[2] : (/^([a-z]*)$/i.exec(token) || [])[1];
  if (word === undefined || (!after && !word)) return null;
  const options = after ? [
    ...(/\bat\b/i.test(after[1]) ? [] : [["at 1", "its strength: 1 as it is, 0.5 about half its share of attention"]]),
    ...(/\bfrom\b/i.test(after[1]) ? [] : [["from 35%", "it waits while the picture is laid out: a place drags less of its framing along"]]),
    ...(/\bto\b/i.test(after[1]) ? [] : [["to 50%", "it stops there, and the prompt takes over"]]),
  ] : [["refmod ", "a RefMod from models/refmods: refmod NAME at 1"],
       ["always", "the member goes with every clip, not only with the clips that name it"]];
  const items = options.filter(([o]) => startsWith(o, word)).map(([insert, detail]) => ({ insert, detail, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - word.length } : null;
}

// `SET: ` the CAST's members, RefMods and pictures as name(strength, start), and the RefMod defaults,
// one item after another; inside a member's parentheses, after a comma, the words that choose among
// its references.
function setItems(before, line, text) {
  const m = /^\s*SET:(.*)$/.exec(line);
  if (!m) return null;
  const inside = /@?([A-Z][A-Z0-9 _-]*?)\(([^()]*),\s*([a-z][\w ]*)?$/.exec(m[1]);
  if (inside && castNames(text).includes(inside[1])) return choiceItems(before, inside[1], inside[3] || "", text);
  const token = /(?:^|,)\s*([^,()]*)$/.exec(m[1]);
  if (!token) return null;  // inside the parentheses: the numbers are the user's
  const cast = uncommented(text);
  const refmods = [...new Set([...cast.matchAll(/\brefmod\s+([\w./-]+)/g)].map((r) => r[1]))];
  const images = [...new Set([...cast.matchAll(/^\s*[A-Z][A-Z0-9 _-]*?\s*\(([^)]*)\)\s*:/gm)]
    .flatMap((c) => [...c[1].matchAll(/\bimage\s+(\d+)/g)].map((i) => Number(i[1]))))].sort((a, b) => a - b);
  const targets = [...castNames(text).map((n) => [`@${n}(1)`, `all of ${n}'s pictures and RefMods; (0.6, refmods): only the RefMods`]),
                   ...refmods.map((r) => [`${r}(1, 0%)`, "a RefMod: (strength, start), or (strength, start, end)"]),
                   ...images.map((n) => [`image_${n}(1, 0%)`, "a picture: (strength, start), or (strength, start, end)"]),
                   ["refmods(1, 0%)", "the RefMods without their own dials, as a refmods: line"]];
  const items = targets.filter(([t]) => startsWith(t, token[1])).map(([insert, detail]) => ({ insert, detail, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - token[1].length } : null;
}

// The words that choose among a member's references in `SET: @NAME(0.6, …)`, in the CAST's own words.
function choiceItems(before, name, typed, text) {
  const line = uncommented(text).split("\n").find((l) => new RegExp(`^\\s*@?${name}\\s*\\(`).test(l)) || "";
  const own = [...line.matchAll(/\b(image\s+\d+|refmod\s+[\w./-]+)/g)].map((r) => r[1].replace(/\s+/, " "));
  const options = [["refmods", `all of ${name}'s RefMods`], ["images", `all of ${name}'s pictures`],
                   ...own.map((o) => [o, `just this one of ${name}'s`])];
  const items = options.filter(([o]) => startsWith(o, typed) && o !== typed).map(([insert, detail]) => ({ insert, detail, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - typed.length } : null;
}

// `@h3 ` the mode: what the clip is made from.
const MODES = [["text", "from the words alone (t2va)"], ["references", "from a CAST of pictures, videos and voices (ref2va)"],
               ["image", "from a first frame (i2va)"], ["first-last", "between a first and a last frame (fl2va)"],
               ["last", "toward a last frame (l2va)"]];

function modeItems(before, line) {
  const m = /^\s*@h3\s+([\w-]*)$/.exec(line);
  if (!m) return null;
  const items = MODES.filter(([o]) => startsWith(o, m[1]) && o !== m[1]).map(([insert, detail]) => ({ insert, detail, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - m[1].length } : null;
}

// The `refmods:` line: the defaults for RefMods without their own `at` or `from`.
function refmodsLineItems(before, line) {
  const m = /^\s*refmods:\s*(.*)$/.exec(line);
  if (!m) return null;
  const items = [["at 1 from 0%", "strength 1, from the first step: orrery's defaults"],
                 ["at 0.5", "every RefMod at half its share of attention"],
                 ["from 35%", "every RefMod waits while the picture is laid out: for places"],
                 ["to 50%", "every RefMod stops halfway, and the prompt takes over"]]
    .filter(([o]) => startsWith(o, m[1]) && o !== m[1]).map(([insert, detail]) => ({ insert, detail, preview: "" }));
  return items.length ? { items, replaceFrom: before.length - m[1].length } : null;
}

// `@` at the start of a line: the directives, each on a line of its own.
const DIRECTIVES = [
  ["@grid ", "every combination, one run each: @grid __style__ × {dawn|noon}"],
  ["@unique ", "seeds in a row never repeat it: @unique $hero"],
  ["@size ", "the node's width and height: @size 832x1216"],
  ["@include ", "embed a preset where it stands"],
  ["@h3 ", "a MiniMax H3 screenplay: @h3 text 16:9 (the first line)"],
  ["@lib ", "a library of the template's own: its entries on indented lines under it"],
  ["@rng 1", "the dice of before 2026-10-02 (one stream for every pick)"],
  ["@seed ", "CLI only: the first seed"],
  ["@batch ", "CLI only: how many seeds"],
];

function directiveItems(line) {
  const m = /^\s*(@\w*)$/.exec(line);
  if (!m) return null;
  const items = DIRECTIVES.filter(([d]) => d.startsWith(m[1])).map(([insert, detail]) => ({ insert, label: insert.trim(), detail, preview: "" }));
  return items.length ? { items, replaceFrom: -m[1].length } : null;
}

// `clothing/*` (a part of the path), `clothing/**` (across folders): mirrors orrery.dsl.glob_names.
export function globMatches(pattern, names) {
  const part = (p) => (p === "**" ? ".+" : p.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/]*"));
  const rx = new RegExp(`^${pattern.split("/").map(part).join("/")}$`);
  return names.filter((n) => rx.test(n));
}

// The template's own libraries: `@lib name` and its indented entry lines (mirrors orrery.dsl.inline_libraries).
export function inlineLibraries(text) {
  const out = [];
  let current = null;
  for (const raw of text.split("\n")) {
    const m = /^\s*@lib\s+(\w+(?:\/\w+)*)\s*$/.exec(raw);
    if (m) { current = { name: m[1], entries: [] }; out.push(current); continue; }
    if (current && (/^[ \t]/.test(raw) || !raw.trim())) {
      const entry = raw.trim().replace(/^- /, "");
      if (entry && !entry.startsWith("#")) current.entries.push(entry);
      continue;
    }
    current = null;
  }
  return out;
}

const withInline = (text, data) => {
  const inline = inlineLibraries(text);
  if (!inline.length) return data;
  const own = inline.map((l) => ({ name: l.name, count: l.entries.length, source: "template", tags: [], sample: l.entries.slice(0, 3), props: {} }));
  return { ...data, libraries: [...own, ...data.libraries.filter((l) => !inline.some((i) => i.name === l.name))] };
};

export function suggest(text, caret, data) {
  if (!data) return NONE;
  data = withInline(text, data);
  const before = text.slice(0, caret);
  const line = before.slice(before.lastIndexOf("\n") + 1);
  if (/^\s*#/.test(line)) return NONE;
  const screenplay = uncommented(text).trimStart().startsWith("@h3");
  const mode = modeItems(before, line);
  const directive = directiveItems(line);
  if (directive) directive.replaceFrom += before.length;
  const cast = screenplay ? atCastItems(before, line, text) : null;
  if (directive && cast) directive.items = [...cast.items, ...directive.items];  // `@` at a line's start: both
  const found = mode ?? directive ?? cast ?? (screenplay ? loraItems(before, line, data) : null)
    ?? libraryItems(before, data)
    ?? fieldItems(before, text, data)
    ?? bindingItems(before, text)
    ?? (screenplay ? refmodsLineItems(before, line) ?? setItems(before, line, text) ?? refmodItems(before, line, data) ?? gotoItems(before, line, text)
      ?? rememberItems(before, line, text)
      ?? castItems(before, line, text) ?? shotItems(before, line, data) ?? keywordItems(before, line) : keywordItems(before, line, false))
    ?? NONE;
  const typed = before.slice(found.replaceFrom);
  return { ...found, items: found.items.filter((i) => i.insert !== typed) };
}

export function missingLibraries(text, data) {
  const known = new Set([...data.libraries.map((l) => l.name), ...inlineLibraries(text).map((l) => l.name)]);
  const names = [...uncommented(text).replace(/<lora:[^<>]*>/g, "").matchAll(/__([\w*]+(?:\/[\w*]+)*)(?:\[[^\[\]\n]+\])?(?:#[\w-]+:\$?[\w.-]+)*(?::\d+)?__/g)].map((m) => m[1]);
  return [...new Set(names)].filter((n) => (n.includes("*") ? !globMatches(n, [...known]).length : !known.has(n)));
}
