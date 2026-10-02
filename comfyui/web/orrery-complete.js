// Pure completion logic for the Orrery Prompt editor (no DOM; tested with node --test).
//
// suggest(text, caret, data) -> { items: [{ insert, detail, preview }], replaceFrom }
// Accepting an item replaces text[replaceFrom:caret] with item.insert.

const KEYWORDS = ["SHOT ", "SFX: ", "MUSIC: ", "style: ", "summary: ", "CAST", "voice: ", "keep: ",
  "CHUNK", "HANDOFF: ", "SEND: ", "LORA: ", "context: "];
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
  return {
    items: data.libraries
      .map((l) => ({ l, rank: nameRank(l.name, m[2]) }))
      .filter((x) => x.rank >= 0)
      .sort((a, b) => a.rank - b.rank || a.l.name.localeCompare(b.l.name))
      .map(({ l }) => ({
        insert: `__${l.name}__`,
        detail: `${l.count} · ${l.source}`,
        preview: l.sample.join(", ") + (l.count > l.sample.length ? ", …" : ""),
      })),
    replaceFrom: before.length - m[1].length,
  };
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

function keywordItems(before, line) {
  const m = line.match(/^([A-Za-z]+)$/);
  if (!m) return null;
  return {
    items: KEYWORDS.filter((k) => startsWith(k, m[1]))
      .map((k) => ({ insert: k, detail: "screenplay", preview: "" })),
    replaceFrom: before.length - m[1].length,
  };
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

// `@` at the start of a line: the directives, each on a line of its own.
const DIRECTIVES = [
  ["@grid ", "every combination, one run each: @grid __style__ × {dawn|noon}"],
  ["@unique ", "seeds in a row never repeat it: @unique $hero"],
  ["@size ", "the node's width and height: @size 832x1216"],
  ["@include ", "embed a preset where it stands"],
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

export function suggest(text, caret, data) {
  if (!data) return NONE;
  const before = text.slice(0, caret);
  const line = before.slice(before.lastIndexOf("\n") + 1);
  if (/^\s*#/.test(line)) return NONE;
  const screenplay = uncommented(text).trimStart().startsWith("@h3");
  const directive = directiveItems(line);
  if (directive) directive.replaceFrom += before.length;
  const found = directive ?? (screenplay ? loraItems(before, line, data) : null)
    ?? libraryItems(before, data)
    ?? bindingItems(before, text)
    ?? (screenplay ? shotItems(before, line, data) ?? keywordItems(before, line) : null)
    ?? NONE;
  const typed = before.slice(found.replaceFrom);
  return { ...found, items: found.items.filter((i) => i.insert !== typed) };
}

export function missingLibraries(text, data) {
  const known = new Set(data.libraries.map((l) => l.name));
  const names = [...uncommented(text).replace(/<lora:[^<>]*>/g, "").matchAll(/__(\w+(?:\/\w+)*)(?:\[[^\[\]\n]+\])?(?:#[\w-]+:\$?[\w.-]+)*(?::\d+)?__/g)].map((m) => m[1]);
  return [...new Set(names)].filter((n) => !known.has(n));
}
