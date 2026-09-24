// Pure completion logic for the Orrery Prompt editor (no DOM; tested with node --test).
//
// suggest(text, caret, data) -> { items: [{ insert, detail, preview }], replaceFrom }
// Accepting an item replaces text[replaceFrom:caret] with item.insert.

const KEYWORDS = ["SHOT ", "SFX: ", "MUSIC: ", "style: ", "summary: ", "CAST", "voice: ", "keep: ",
  "CHUNK", "HANDOFF: ", "LORA: ", "context: "];
const NONE = { items: [], replaceFrom: 0 };

const startsWith = (word, prefix) => word.toLowerCase().startsWith(prefix.toLowerCase());

function libraryItems(before, data) {
  let m = before.match(/(?:^|[^\w])(__(\w+)\[([\w-]*))$/);
  if (m) {
    const lib = data.libraries.find((l) => l.name === m[2]);
    const tags = (lib?.tags ?? []).filter((t) => startsWith(t, m[3]));
    return {
      items: tags.map((t) => ({ insert: `__${m[2]}[${t}]__`, detail: "tag", preview: "" })),
      replaceFrom: before.length - m[1].length,
    };
  }
  m = before.match(/(?:^|[^\w])(__(\w*))$/);
  if (!m) return null;
  return {
    items: data.libraries
      .filter((l) => startsWith(l.name, m[2]))
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((l) => ({
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
  const m = line.match(/^\s*SHOT\s+[\d.]+s?\s*\|(.*)$/i);
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

export function suggest(text, caret, data) {
  if (!data) return NONE;
  const before = text.slice(0, caret);
  const line = before.slice(before.lastIndexOf("\n") + 1);
  const screenplay = text.trimStart().startsWith("@h3");
  const found = (screenplay ? loraItems(before, line, data) : null)
    ?? libraryItems(before, data)
    ?? bindingItems(before, text)
    ?? (screenplay ? shotItems(before, line, data) ?? keywordItems(before, line) : null)
    ?? NONE;
  const typed = before.slice(found.replaceFrom);
  return { ...found, items: found.items.filter((i) => i.insert !== typed) };
}

export function missingLibraries(text, data) {
  const known = new Set(data.libraries.map((l) => l.name));
  const names = [...text.replace(/<lora:[^<>]*>/g, "").matchAll(/__(\w+)(?:\[[\w-]+\])?(?::\d+)?__/g)].map((m) => m[1]);
  return [...new Set(names)].filter((n) => !known.has(n));
}
