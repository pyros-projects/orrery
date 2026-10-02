# orrery

orrery is a seeded prompt language that records every decision it makes. A template rolls
libraries, choices and bindings from a seed; every pick stays addressable, so a run can be
reproduced, rated, and the ratings steer the next rolls (the galaxy). On top of the language sit
compilers: plain text (Krea 2 and other image models) and MiniMax H3 screenplays (`@h3`: shots,
voices, sound, a CAST of references, and reels of chained clips with `CHUNK`, `HANDOFF`, `SEND:`
and `GOTO:`). In ComfyUI it is one node, Orrery Prompt, with an app in it (Prompt, Test, Galaxy,
History), plus Orrery Refs, Orrery Continue, Orrery Film and Orrery Log.

## Layout

| Path | What |
|---|---|
| `src/orrery/dsl.py`, `batch.py`, `rng.py`, `library.py` | the language: expansion, grid and unique, dice, libraries |
| `src/orrery/h3.py`, `cast.py`, `reel.py`, `h3_ref.py` | the H3 compiler: screenplays, the CAST, reels |
| `src/orrery/comfy*.py`, `webapi.py`, `film.py`, `chain.py` | the ComfyUI nodes and their HTTP routes |
| `src/orrery/cli.py` | the `orrery` command |
| `src/orrery/builtin/presets/` | the presets shipped with orrery |
| `comfyui/web/` | the node's app (plain ES modules) |
| `example_workflows/` | a ComfyUI workflow per mode |
| `docs/` | user docs (`dsl.md`, `h3.md`, `comfyui.md` …) and plans (`plan-*.md`) |
| `tests/`, `tests/js/` | pytest and `node --test` |

## Checks

All three pass before a PR:

```
uv run pytest
uv run ruff check src tests
node --test tests/js/*.mjs
```

## Development process

**Feature → tasks → one branch and one PR → feature closed.**

1. **Every change starts as an issue**, from a template: Feature, Task, Bug or Risk.
2. **A feature** describes a result and may take as long as it takes. Its title starts with an
   emoji that fits it (`🧠 RefMod memory for reels`), so features stand out in every list. It is
   split into **tasks**, attached as its sub-issues. Every task belongs to a feature: there are
   no tasks on their own.
3. **What is learned goes into the feature's comments.** Only features get comments. Write one
   whenever knowledge comes up that the feature does not hold yet: an experiment and its results,
   a learning, a problem that came up and the issue it led to. A comment may link tasks, but it
   carries the point itself, so nobody has to dig through tasks to find it:
   - good: "While implementing #12 we found that WebGPU does not work in this system's browser;
     in #13 we fixed it by starting the browser with `--enable-unsafe-webgpu`."
   - bad: "There was an issue in #12, we solved it in #13."
4. **One branch per feature, from `main`**, named `<feature number>-<short-slug>`
   (`4-refmod-memory`). Tasks don't get branches of their own; each commit names the task it
   does (`Refs #9`).
5. **One PR per feature.** Its body says `Closes #4` for the feature and for each task done in it,
   so the merge closes them together. It carries its tests and its doc updates, and merges only
   with the three checks green.
6. **A bug** stands on its own: its own branch and PR. **A risk** names the feature it threatens
   and stays open while it matters.
7. **Pyro merges.** Nothing is pushed to `main` directly.

Scope: build what the issue asks. Anything else you notice (a missing feature, a refactor, a test,
a fix next door) becomes a new issue or a question, not part of the PR.

## Conventions

- Code, docs, issues, commits and PRs are in English.
- Write like the surrounding code: its naming, its comment density, its idiom.
- A user-visible change updates its docs in the same PR (`docs/`, the in-app help in
  `comfyui/web/app/help.js`, and the example workflows when their templates or nodes change).
- Determinism is a promise: the same template and seed give the same picks. A change that moves
  existing picks needs a reason in the PR and a way back (as `@rng 1` keeps the old dice).
- Test ComfyUI changes on an isolated ComfyUI instance, never on the one Pyro works in.
- `~/.orrery` holds Pyro's own libraries and presets: don't change them unless asked.
