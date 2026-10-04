# orrery

orrery is a seeded prompt language that records every decision it makes. A template rolls
libraries, choices and bindings from a seed; every pick stays addressable, so a run can be
reproduced, rated, and the ratings steer the next rolls (the gallery). On top of the language sit
compilers: plain text (Krea 2 and other image models) and MiniMax H3 screenplays (`@h3`: shots,
voices, sound, a CAST of references, and reels of chained clips with `SCENE`, `END ON:`, `AFTER:`,
`CUT TO:`, `REMEMBER:` and `SET:`). In ComfyUI it is one node, Orrery Prompt, with an app in it (Prompt, Test, Gallery,
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

While you work, `scripts/check` runs all three in seconds: pytest in parallel over every core, the
tests that failed last time first, stopping at the first failure.

All three pass in full before a PR. CI (`.github/workflows/ci.yml`) runs them on every PR and on
`main`:

```
uv run pytest
uv run ruff check src tests
node --test tests/js/*.mjs
```

## Development process

**Feature → tasks → one branch and one PR → feature closed.**

1. **Every change starts as an issue**, from a template: Feature, Task, Bug or Risk. A feature, a
   bug or a risk also goes on the project board (below); a task does not.
2. **A feature** describes a result and may take as long as it takes. Its title starts with an
   emoji that fits it (`🧠 RefMod memory for reels`), so features stand out in every list. It is
   split into **tasks**, attached as its sub-issues. Every task belongs to a feature: there are
   no tasks on their own.
3. **What is learned goes into the feature's comments.** Tasks get no comments; features do, and
   so do bugs and risks. Write one whenever knowledge comes up that the issue does not hold yet:
   an experiment and its results, a learning, a problem that came up and the issue it led to. A
   comment may link tasks, but it carries the point itself, so nobody has to dig through tasks to
   find it:
   - good: "While implementing #12 we found that WebGPU does not work in this system's browser;
     in #13 we fixed it by starting the browser with `--enable-unsafe-webgpu`."
   - bad: "There was an issue in #12, we solved it in #13."
4. **One branch per feature, from `main`**, named `<feature number>-<short-slug>`
   (`4-refmod-memory`). Tasks don't get branches of their own; each commit names the task it
   does (`Refs #9`). Creating the branch moves the feature to *In progress* on the board.
5. **One PR per feature.** Its body says `Closes #4` for the feature and for each task done in it,
   so the merge closes them together. It carries its tests and its doc updates, and merges only
   with the three checks green. Opening it moves the feature to *In review*; the merge closes it,
   and GitHub sets *Done*.
6. **A bug** stands on its own: its own branch and PR. **A risk** names the feature it threatens
   and stays open while it matters.
7. **Pyro merges.** Nothing is pushed to `main` directly.

**The project board.** The GitHub Project [orrery](https://github.com/users/pyros-projects/projects/3)
(owner `pyros-projects`, number 3, linked to this repository) holds the order of the work and
where each piece stands. The chat is where an order is agreed; the board is where it is kept.
Read it at the start of a session to know what comes next.

- **On the board:** every feature, bug and risk, open and done. Tasks stay off it: they are a
  feature's sub-issues and show as its *Sub-issues progress*. The project's built-in workflow
  "Auto-add sub-issues to project" is off for that reason; if a task shows up anyway, take it
  off again with `gh project item-delete`.
- **Status**, one field with five values:

  | Status | Means | It moves there |
  |---|---|---|
  | Backlog | known and written down, not planned yet | when the issue is created, unless an order was agreed for it |
  | Next | planned, in the agreed order: the top one comes first | when the human confirms an order (see "Pause for the human") |
  | In progress | its branch exists | when the branch is created |
  | In review | its PR is up, for the human to test or merge | when the PR is opened; back to In progress while changes they asked for are made |
  | Done | merged or closed | the built-in workflow "Item closed" sets it; set it yourself if it has not |

- **Who moves it:** the agent, at the moments in the table, in the same step as the work itself.
  The human may move or reorder anything at any time, and their moves win: re-read the board
  rather than trusting an earlier plan.
- **The order in Next** is the order of the items on the board. When the human confirms an
  order, move the items to match it (the API's `updateProjectV2ItemPosition`, `afterId` the item
  above). A risk stays in Backlog while it matters and goes when it is closed.
- **Views:** *Backlog*, a table of every item, done ones included, in board order (Title,
  Status, Sub-issues progress, Labels, Linked pull requests); *Board*, one column per status.
- **Commands** (`GH_TOKEN=$(gh auth token -u pyros-projects)`; the token has the `project` scope):

  ```
  gh project field-list 3 --owner pyros-projects                  # the Status field's id and options
  gh project item-add 3 --owner pyros-projects --url <issue url> --format json -q .id
  gh project item-edit --id <item id> --project-id <project id> --field-id <Status id> \
    --single-select-option-id <option id>
  gh project item-list 3 --owner pyros-projects --limit 300 --format json
  ```

Scope: build what the issue asks. Anything else you notice (a missing feature, a refactor, a test,
a fix next door) becomes a new issue or a question, not part of the PR.

Pause for the human. Stop and wait in two cases, so nothing they have to act on gets lost in the
output:

- **A new task while two or more are queued:** recommend an order and wait until it is
  confirmed. Work the human waits on (something to test, a decision, a merge) comes first.
- **A PR ready for review or merge:** say so, with its link, and stop. Don't go on with other
  work in the same turn.

Test live, with the human watching. A change they can see in ComfyUI is shown to them in the
running instance before its PR, in a browser window of its own (Playwright), and they approve it
test by test:

1. **The plan first.** A numbered list of the tests. Each gets one line: what you do and what they
   should see. They may strike one ("that needs no watching") or add one. Start on their go.
2. **One test at a time.** Announce it ("Test 2: the filter on the outfit dial …") and run it at
   human speed. Then say in one line what you expected and what came, and ask whether it passes.
   Wait for the answer before the next test.
3. **A failing test stops the run.** Say what happened and what you would change. Fix it only when
   they agree, then run that test again.
4. **What a test is:** one behaviour a user checks by eye, from its start to its result (pick a
   dial's choice, and the row and the sidebar's head change). Mostly 3 to 10 actions and under two
   minutes. Never one test per click, and never so long that a failure is hard to place.
5. **Human speed:** they follow every step.
   - Put what the test is about on screen first (scroll, zoom the canvas), and keep it there.
   - Wait about 1.5 s between two actions.
   - Type at about 15 characters a second (Playwright: `delay: 60`).
   - Move the pointer to what you click, so they see where.
   - Leave each result on screen 3 s before you name it or go on.

   When they say "faster" or "the rest without me", run the rest at normal speed and report.
6. **The usual limits hold.** Nothing that loads a model runs without their OK (see the running
   ComfyUI under Conventions). The test leaves the home as it found it: discard what a test wrote,
   and set back the settings it changed.

## Conventions

- Code, docs, issues, commits and PRs are in English.
- The language is frozen at DSL 2.0 (`docs/dsl.md`, `docs/h3.md`). New things come as libraries,
  presets and operators (`@include`), compiler targets or UI, not as syntax. A fix where two existing
  constructs don't work together (a dial that loses an entry's properties) is allowed, with the
  golden corpus showing what moved. New syntax comes only when a real preset cannot be written
  without it, and never in the earlier words (`CHUNK`, `HANDOFF:`, `SEND:`, `GOTO:`, `?`,
  `__name__(directions)`): they still work, and nothing new is built on them.
- Write like the surrounding code: its naming, its comment density, its idiom.
- A Krea 2 preset follows the format in `docs/presets.md` ("Writing a Krea 2 preset"): the medium and the shot
  first, only what the shot can show, a second subject in a sentence of its own.
- A user-visible change updates its docs in the same PR (`docs/`, the in-app help in
  `comfyui/web/app/help.js`, and the example workflows when their templates or nodes change), and
  adds its line to `CHANGELOG.md` under Unreleased (Added, Changed or Fixed), naming its feature
  or bug. Dev-flow and check changes stay out of it.
- Determinism is a promise: the same template and seed give the same picks. A change that moves
  existing picks needs a reason in the PR and a way back (as `@rng 1` keeps the old dice).
- The golden corpus (`tests/test_golden.py`, snapshots in `tests/golden/`) pins what every built-in
  preset rolls: its text, its picks and a reel's path. When it fails, either the change is a mistake,
  or it is meant: then the PR says what moved and why, and `uv run python tests/test_golden.py --write`
  rewrites the snapshots. A new built-in preset gets its snapshot the same way. The corpus is the
  presets, so a language feature no preset uses yet gets a preset worth shipping, not a dry test case.
- Test ComfyUI changes in the ComfyUI that is already running, and only after asking. Never start
  a second instance, or any other process that loads models on the GPU next to it: two at once
  freeze the machine.
- `~/.orrery` holds Pyro's own libraries and presets: don't change them unless asked.
