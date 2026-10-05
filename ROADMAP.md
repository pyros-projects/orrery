# Roadmap

What orrery's docs promise, plan or dream of that no issue holds yet and the release plan does not cover, sorted for
the release. The [project board](https://github.com/users/pyros-projects/projects/3) keeps the order of the work in
hand; this file keeps what is not on it yet. When an item becomes an issue, it leaves this file (with the issue's
number in the commit).

Made on 2026-10-05 from an audit of every file in `docs/` against all issues (#1 to #355, open and closed), the
release plan and the code. **Verified** marks a finding checked by hand, not only by the audit.

## On the board now

- **Next:** #104 🎭 a cast of our own for examples, tutorials and the corpus; #216 🪄 an inline library grows on request.
- **In progress:** #143 🏞️ places for the characters, and the refbias bench (#146 needs GPU runs; the uncommitted
  `experiments/director-blind/` goes in with it).
- **Risk:** #5 RefMods may bring back a place's composition instead of its identity.
- **The release plan** (an artifact on claude.ai, 2026-10-04): six questions wait for answers before its issues are
  filed. 0.9 as an open beta or straight to 1.0? Windows from day one? Which presets may go? A landing page (GitHub
  Pages now, a domain later, or nothing beyond the README)? What ships for people without Pyro's packs (which H3 extras
  are required)? Who tests the beta?

## 1. Before the release: what the docs promise and orrery does not do

- **`__cut__` is documented as shipped and does not exist** (verified). `docs/h3.md:622-625` lists it beside
  `__camera__` and `__h3style__`; `src/orrery/builtin/` has only `camera.yaml` and `h3style.yaml`. Ship it, or take
  the line out.
- **The anchor view is lost** (verified). The Prompt tab's timeline showed the frames each `REMEMBER:` stored
  (`docs/orrery-refs.md:309-311`); bac51f4 (the dials sidebar, the clips column moved) dropped the rendering, and
  `anchorURL` in `comfyui/web/app/api.js:116` is defined but called nowhere. A regression: bring it back, or say it went.
- **The optional densifier is described as offered** (verified). `docs/h3.md:607-616` ("orrery offers it per field")
  and the open question at `docs/h3.md:649-650` lean on it; nothing builds it. See also group 3, writers.
- **The Krea example workflow loads Turbo** (verified). `example_workflows/orrery_krea2_t2i.json` loads
  `krea2_turbo_fp8_scaled`, while `docs/presets.md:155-157` says to judge expressions on Krea 2 Raw with the turbo
  LoRA (Turbo flattens faces).
- **Passages out of date:**
  - `docs/orrery-refs.md:170-172`: a world CAST member counts in every clip. Now a clip leaves out members it does not
    name, unless they are `always` (`cast.py:12`, `docs/h3.md:552`).
  - `docs/orrery-refs.md:225, :450`: `REMEMBER:` only inside a `SCENE`. Now a reel's head keeps frames of the input
    video (#83).
  - `docs/orrery-refs.md:446`: the example names the chain `h3_context`; a reel's folder is named after the reel now
    (#197, #198).
  - `docs/wildcard-manager.md:123-125`: a run sends everything to the model in one request. With a text encoder, Roll
    queues an Orrery Ask mini-run per task (#171, #177); only ComfyUI's own Run asks all at once.
  - `docs/llm.md:53`: "With a text encoder the takes come with #171", as if still to come; shipped with #178.
  - `docs/configuration.md:36`: `takes` lists four kinds; there are seven (`takes.py`: continue, story, describe too).
    `docs/llm.md:18-26` describes `takes` twice.
- **The test checklist was never run.** `docs/llm.md:103-131` has 29 items, none ticked in its history; #172, which
  asked for the list, is closed.
- **A linked install shows no example workflows.** With the repo linked in as the `comfyui` folder
  (`docs/comfyui.md:25-27`), ComfyUI's template browser finds none (`comfyui/` has no `example_workflows`). The Comfy
  Registry install of the release plan fixes it for registry installs only.

## 2. For the release: worth an issue

- **The CLI on PyPI under a name of its own**: `orrery` is taken there (`docs/concept-brand.md:116`). The release plan
  ships to the Comfy Registry only.
- **Sharing:** preset packs as `.orrery` files (`docs/backlog.md:186`); a portable gallery, with media paths relative
  to the home (`docs/backlog.md:189`; `galaxy.py` stores absolute ones); a preset's history with a diff
  (`docs/backlog.md:181`; `save_preset` overwrites).
- **Credit the template's author** on every preset, and ship a workflow with each (`docs/concept-brand.md:178`;
  preset front matter has no author).
- **The Gallery** (`docs/plan-galaxy-organize.md:107-108`): a trash view, Delete in the detail panel, a "Move to…" menu,
  rubber-band selection. Today collections take drags only and the trash is on disk only.
- **Reach:** a seed of the day (`docs/concept-brand.md:182`; the release plan has a weekly preset); a playground in
  the browser, Pyodide (`docs/concept-brand.md:189`; the plan stops at a landing page); ComfyHub and the tutorial
  makers (Pixaroma, Kamph, Sarikas, Mickmumpitz) beside the planned channels (`docs/concept-brand.md:214`).

## 3. After the release: feature families never filed

- **🧠 The learning loop.** Ratings only multiply weights today (`galaxy.py`). From `docs/backlog.md`: more like this
  (:61), an exploration dial (:64), Thompson sampling (:67), ablation pairs (:72), duels (:75), passive signals (:77),
  a diversity budget (:80), rejected combinations (:83), taste drift (:86), weight scopes (:88), pair weights (:91);
  libraries that grow from ratings (:164; #216 grows from a request, not from ratings); a quality-diversity grid
  (:127); a taste report with mean rating and count per value (:132, partly: the Libraries tab shows the weights).
- **🌌 The noise and conditioning space** (`docs/backlog.md`): conditioning travel (:101), breeding (:105), seed
  jitter (:111), token gravity (:113), a star map (:117, also `docs/concept.md:137` and the 2D map of
  `docs/mock/prompt-galaxy-mock.html:408`).
- **✍️ Writers:**
  - From an idea or a logline to a whole reel (`docs/plan-llm-writers.md:112`). #343 writes the scenes between two
    ends, #334 makes a reel of a screenplay; nothing writes a reel from an idea.
  - A chat with the language model (`docs/plan-llm-writers.md:113`); the takes sheet's steer comes closest.
  - The densifier per field with the official guide and a lint after it (`docs/backlog.md:152`, `docs/h3.md` §5); `>`
    rewrites the prose and keeps it (#279).
- **🎞️ Reels:**
  - Picture and sound drift over six or more Masked AV clips, tested against Motion Context, and what helps against it
    (`docs/plan-continuation.md:107-109, :114`). #115 and #116 measure the seam between two clips only.
  - A second pass, hires, for a reel's clips (`docs/plan-continuation.md:114`).
  - Continuum's sampler that renders a whole reel in one run (`docs/plan-continuation.md:113-114`).
  - Anchors without a `REMEMBER:` line, set by orrery itself (`docs/plan-send-frames.md:103`).
  - `REMEMBER:` into a reference video, carrying voice and sound (`docs/plan-send-frames.md:103`); Orrery Refs routes
    pictures only, no video or audio per clip (`docs/orrery-refs.md:461-464`).
  - A branching reel's film along one path: Orrery Film strings every branch together (`docs/h3.md:345-346`); #244
    exports the film, it does not choose the path.
  - The RefMod start thresholds checked at 20 steps; only the 4-step turbo setup was (`docs/long-video.md:227`; #65 and
    #146 calibrate the strength).
- **🎛️ Sweeps:** your own sweep macros, beside `test` (`docs/plan-lora-sweep.md:63`, `sweep.py:26`); a contact sheet,
  a labelled image of a sweep to save or share (same line; #297 shows a sweep as an album, the strip as a mosaic).
- **🎬 The studio:** the `/orrery/studio` page with ComfyUI as its engine, and its three open questions
  (`docs/concept-studio.md:97, :128`; "not planned" in `docs/llm.md:138-140`). The release plan only moves the doc.
- **Model variants:** detect the model and route negative prompts (`docs/concept.md:63`). Low value.

## 4. Small gaps in the language and the compiler

- `EXPORT:` in a screenplay: it works in text templates only (`docs/dsl.md:30`).
- A library file with `-` or spaces in its path is found only through `lib import` (`docs/dsl.md:79-80`).
- H3's group speech `(S1,S2)`, `<scenetrans>` and `<cutoff>` in the screenplay (`docs/h3.md:645-648`).
- Orrery Continue always pins 22 frames; another `context:` only warns, though Motion Context also takes 5, 39, 56 and
  0 (`docs/comfyui.md:365`, `docs/h3.md:249`).
- Which prompt format H3 follows better, `lite` or `full`, was never compared (`docs/h3.md:224-226`).
- Under H3SLAAttention, a strength other than 1 runs those steps dense, slower (`docs/comfyui.md:410-415`).

## 5. Half done: what is missing

- **Lock a pick** from the Gallery or Test with a click (`docs/backlog.md:58`); dials (#183) fix a binding to a value.
- **Seeds as coordinates:** a seed lottery grid and a `__seed__` library of loved seeds (`docs/backlog.md:97`); 📌
  keeps a prompt over N noise seeds (#206).
- **Reverse prompting:** match a picture's phrases to library entries and propose a template (`docs/backlog.md:120`);
  Prompt from image writes a prompt.
- **Compare:** outputs side by side with the picks that differ marked (`docs/backlog.md:135`); takes play together
  (#238).
- **Lineage:** a preset that remembers the roll it came from, and its versions (`docs/backlog.md:139`); runs keep the
  template's hash and the take tree (#240, #242).
- **Animate this:** a still to I2VA in one click (`docs/backlog.md:144`); EXPORT and `image <preset>/*` carry a still's
  picks into a reel (#157, #148).
- **Library edits in words** (remove, rename, split into new lists) outside the CLI's `orrery lib edit`
  (`docs/backlog.md:162`).
- **The template doctor:** a Krea lint and suggestions (`docs/backlog.md:167`); the H3 lint is there (#112).
- **Corpora:** Hugging Face datasets as a source (`docs/concept.md:163`); `orrery lib import --merge` reads folders.
- **The cast describes itself:** a vision model's description of a wired `image N` (`docs/long-video.md:175`); #131
  writes from a gallery picture's prompt, #82 covers the input video.
- **Takes as images:** the contact sheet (group 3, sweeps); the brand study's one-click sharing
  (`docs/mock/orrery-brand.html:159`).

## Dropped on purpose

The DSL is frozen at 2.0 (AGENTS.md): what needs new syntax stays out unless a real preset cannot be written without
it. Inline-library weights and properties, a CUT TO: into the middle of a scene and arithmetic
(`docs/plan-dsl-2.md:47-48`); Continuum's Reference Context route and its model patch
(`docs/plan-continuation.md:66`); wildcards, bindings or slots in what the writers write
(`docs/plan-llm-writers.md:10-11`).
