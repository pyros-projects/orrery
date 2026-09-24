# The orrery node app: spec and plan

Status: approved 2026-09-24 ("bau mir die node bitte so wie im mock").
Design: the clickable mock at https://claude.ai/artifact/V2dGVzCEwNi1QCgUrfvKhm
(source: `docs/mock/orrery-node-mock.html`). Research that shaped it: three
installed node packs (NO8D prompt libraries, Pixaroma, Camera H3, Deno, Bernini
Studio) and the ComfyUI frontend 1.53.6 source.

## Goal

One node, one app. The Orrery Prompt node becomes the whole of orrery inside
ComfyUI: write templates, manage presets, edit wildcard libraries by hand,
rate outputs so the dice learn, and look up the DSL. No second app, no
sidebar, no separate web page.

## Decisions

1. **Five tabs:** Prompt, Presets, Libraries, Galaxy, Help. **⤢** moves the
   same app element into a full-window overlay; Esc or ⤡ moves it back.
2. **The editor is the truth.** A preset loads *into* the editor. The node
   remembers which preset it came from (`node.properties.orrery_preset`) and
   shows ● when the text differs. Save, Save as…, Revert; destructive actions
   show a toast with Undo instead of a confirm dialog. Built-in presets are
   read-only; "Save a copy" writes a user preset with the same name, which
   shadows the built-in.
3. **Thumbnails come from the galaxy.** A preset's preview is the newest
   galaxy output whose `template` hash equals the preset's hash. No output yet:
   an orbit glyph generated from the preset name.
4. **Ratings teach the dice.** love ×1.5, like ×1.2, nope ×0.8, hate ×0.5 on
   every pick key of the rated output. Re-rating replaces the old factor
   (multiply by new/old), so ratings never stack and clearing restores.
5. **Use template + seed** sets the seed widget and switches
   `control_after_generate` to `fixed`, so the next run reproduces the image.
6. **Libraries by hand.** Inline edit of entries, tags and static weights;
   the learned weight is shown next to each entry. Built-ins are read-only
   until "Make it mine" copies them into `<home>/library/`. Renaming an entry
   carries its learned weight along.
7. **Help** is a DSL reference with Insert buttons, the twelve tutorial
   lessons, and model-specific writing tips.
8. **Stage 5 (not in this plan):** LLM features run inside the ComfyUI queue.
   Krea 2's text encoder (Qwen3-VL-4B) can generate via `clip.generate()`
   (needs `skip_template=True`); MiniMax H3's encoder cannot (truncated, no
   `lm_head`), so H3 users need a separate small model.

## Architecture

### Backend: `src/orrery/`

Pure functions, tested with pytest; the ComfyUI glue only adapts HTTP.

- `webapi.py`: every route's logic as `fn(home: Home, args: dict) -> dict`,
  raising `ApiError(status, message, **extra)`.
- `galaxy.py`: read rows with stable ids, rate, weights, thumbnails.
- `uistate.py`: favorites and recents in `<home>/ui.json` (atomic writes).
- `presets.py`: gains `rename_preset` and `set_meta`.
- `comfyui/__init__.py`: registers the routes with one generic adapter
  (`GET` → query args, `POST` → JSON body; `ApiError` → JSON error response).
  Every route accepts an optional `home` (query or body) passed to
  `resolve_home(home or None)`.

### API contract

All responses are JSON unless noted. Errors: HTTP 4xx with
`{"error": "<sentence the UI can show>"}` plus optional fields.

Types:

```
PresetCard = {name, folder, title, note, tags, builtin, hash, outputs, thumb}
             # folder "" for top level; note = front matter note or lesson;
             # outputs = number of galaxy rows with this hash;
             # thumb = id of the newest such row, or null
PresetFull = PresetCard + {text}
Entry      = {value, tags, weight, learned}   # learned = weights["__lib__=value"] or 1.0
Library    = {name, source: "builtin"|"user"|"llm", entries: [Entry], tags: [..]}
GalaxyRow  = {id, ts, seed, target, template, text, picks, rating,
              media_name, kind: "image"|"video"|"none", preset}
             # id = sha1(f"{ts}|{media}|{seed}")[:12]; preset = name of a preset
             # whose hash equals template, else null
Roll       = {seed, text, picks: [{label, value, keys}], lint: [{severity, message}]}
```

Routes:

| Method, path | Body or query | Returns | Errors |
|---|---|---|---|
| GET `/orrery/completions` | | unchanged | |
| GET `/orrery/presets` | | `{presets: [PresetCard], favorites: [name], recent: [name]}` | |
| GET `/orrery/preset` | `name` | `PresetFull` | 404 |
| POST `/orrery/preset/save` | `{name, text, title?, tags?, note?, overwrite?}` | `PresetFull` | 400 bad name; 409 `{exists: true}` when a user preset exists and `overwrite` is not true |
| POST `/orrery/preset/delete` | `{name}` | `{ok: true}` | 403 built-in; 404 |
| POST `/orrery/preset/rename` | `{name, to}` | `PresetFull` | 403 built-in; 409 target exists; 404 |
| POST `/orrery/preset/meta` | `{name, title?, tags?, note?}` | `PresetFull` | 403 built-in; 404 |
| POST `/orrery/favorite` | `{name, on}` | `{favorites}` | |
| POST `/orrery/recent` | `{name}` | `{recent}` (newest first, max 12) | |
| GET `/orrery/libraries` | | `{libraries: [Library]}` | |
| POST `/orrery/library/save` | `{name, entries: [{value, tags, weight}], renames?: {old: new}}` | `Library` | 400 bad name, empty or duplicate values; 403 built-in not owned |
| POST `/orrery/library/own` | `{name}` | `Library` (now `user`) | 404 |
| POST `/orrery/library/delete` | `{name}` | `{ok: true}` | 403 built-in; 404 |
| GET `/orrery/galaxy` | `template?`, `limit?` (200) | `{rows: [GalaxyRow]}` newest first | |
| POST `/orrery/galaxy/rate` | `{id, rating}` (`love`/`like`/`nope`/`hate`/`null`) | `{row, weights: {key: w}}` for the row's keys | 400; 404 |
| GET `/orrery/galaxy/thumb` | `id` | `image/webp`, long side ≤ 384 px, cached in `<home>/thumbs/<id>.webp` | 404 no media, video, or missing file |
| GET `/orrery/galaxy/media` | `id` | the original file; only paths recorded in galaxy.jsonl | 404 |
| POST `/orrery/roll` | `{template, seed, n?: 3, target?: "text"}` | `{rolls: [Roll]}` | 400 missing library (message from `MissingLibrary`) |

Preset rename and delete keep `ui.json` in step. `library/save` keeps the
file's `meta` (an LLM-made library stays `llm`), writes with `save_library`,
and moves learned weights for `renames`. Rating rewrites galaxy.jsonl and
weights.json atomically (temp file + `os.replace`).

### Frontend: `comfyui/web/`

ComfyUI imports every `.js` below `WEB_DIRECTORY`, so helper modules must be
side-effect free.

- `orrery.js`: the extension. On `OrreryPrompt` creation: hide the native
  `template` and `preset` widgets (`widget.hidden = true`), mount the app with
  `addDOMWidget("orrery_app", …, {serialize: false})`, migrate old workflows
  (a `preset` value other than `(none)` is loaded into the template, then the
  combo is reset). Loads `orrery.css`.
- `orrery-complete.js`: completion logic (exists).
- `app/*.js`: `shell` (tabs, toasts, sheet, big view, event isolation), `api`,
  pure `highlight` and `model` modules (tested with `node --test`), one module
  per view, `icons`.

Event isolation (from Pixaroma, Deno and the frontend source): stop `keydown`
propagation at the app root except Ctrl/Cmd+Enter; swallow Delete/Backspace
outside text fields; forward the wheel to `app.canvas.processMouseWheel`
unless the target can scroll in that direction; the app sits in the node's DOM
layer, so popovers are absolutely positioned inside it and scale with the
canvas.

## Stages

Each stage leaves the node working.

- **B (backend, parallel):** `uistate`, preset additions, `galaxy`,
  `webapi`, route glue. TDD per route.
- **F1:** shell, Prompt tab (editor with highlighting and completion, preset
  bar, quick picker, save sheet, Roll 3), Help tab, migration.
- **F2:** Presets tab. **F3:** Libraries tab. **F4:** Galaxy tab.
- **F5:** big view, wheel and key handling, sizing, README.

## Testing

- pytest for every `webapi` function, including error statuses.
- `node --test tests/js/*.test.mjs` for `highlight`, `model`, completion.
- The node itself in a real ComfyUI (restart needed), driven through the
  mock's tour: open a preset, edit, save as, browse, edit a library, rate,
  big view.
