# orrery backlog: toward the optimal orrery

Status: brainstorm, 2026-09-24. Nothing here is scheduled. The approved build is
[plan-node-app.md](plan-node-app.md).

## Thesis

Every output knows its coordinates, and exploration gets smarter the more you
rate. Today orrery steers one of three spaces: **prompt space** (picks). The
other two are **conditioning space** (what the text encoder makes of the
words) and **noise space** (the seed). The optimal orrery puts all three under
the same loop, *roll → look → react → the dice change*. It keeps you
reacting to proposals instead of writing specs, because recognising what you
like is cheap and describing it up front is expensive. It also keeps the weird
regions alive long enough to be judged, because taste collapses toward the
familiar if nothing protects the unfamiliar.

Effort: **S** = an evening for an agent, verifiable by tests; **M** = a stage;
**L** = a project. ⚗ marks a wild idea.

## 1. DSL power

- **LoRAs as coordinates.** `@style(0.8)`, `{@ink|@clay}` and strength ranges
  `@style(0.4-0.9)`, recorded as picks, with a `loras` output for a LoRA stack
  node. *Why:* LoRA dials are Pyro's main lever, and a dial that isn't recorded
  can't learn. The syntax comes from z-explorer. · M · partly built
  (2026-09-24): `LORA:` lines, the `lora_stack` output, completion of your
  LoRA files, and `{<lora:a:1.00>|<lora:b:1.00>}` rolls and records the real
  tags. Open: strength ranges and the short `@style(0.8)` form.
- **Numeric ranges.** `{0.4-0.9}` and `{2-6}` roll a number and bin it for
  learning (e.g. `0.4–0.5`). *Why:* strength, CFG and time of day are dials
  too. · S
- **Structured library entries.** Entries with fields, e.g.
  `{value: snow, sfx: "footsteps crunch", light: "flat white"}`, read back as
  `$w = __weather__ … $w.sfx`. *Why:* correlated picks without new control
  flow. The H3 templates already needed this: rain in the picture has to match
  rain in the soundscape. · M
- **Tag algebra.** `__creature[myth,!bird]__`, `__creature[water|deep_sea]__`.
  *Why:* finer regions without new libraries. · S
- **Recursive entries.** Library values may contain DSL
  (`a __color__ scarf`), expanded with a depth limit. *Why:* libraries become
  grammars, not word lists. · S
- **Includes.** `{{@stills/forest}}` embeds another preset as a
  sub-template. *Why:* composable scenes, one source of truth per fragment. ·
  S · preset store.
- **Sweeps next to rolls.** `: grid __style__ × {dawn|noon}` yields the full
  factorial, deterministically. *Why:* a probe run is a structured sweep; this
  is its smallest form (Prompt Galaxy sketch). · S
- **Batch coverage.** `: x8 unique=__creature__` gives eight different
  creatures in eight rolls (stratified, not independent). *Why:* a batch should
  map a region, not resample it. · S
- **Comments.** `# …` lines are ignored. · S

## 2. The learning loop and exploration strategy

- **Pick locks.** Click a pick in the galaxy or in Roll 3 to lock it. Rerolls
  vary only the unlocked picks, and locks are stored per node. *Why:* the
  fastest "keep this, change that" gesture there is. · S
- **More like this.** From a loved output, create N children that each change
  exactly one pick family (one-pick mutations). *Why:* the neighbourhood of a
  good image is where the next good image is. · S · locks.
- **Exploration dial.** One slider per node, from *exploit* (learned weights)
  to *explore* (prefer values tried least). *Why:* one visible control instead
  of hidden hyperparameters. · S
- **Thompson sampling.** Every value keeps a Beta posterior (love and like
  count as successes, nope and hate as failures); each roll samples from it.
  *Why:* fixed multipliers starve unrated values, while posterior sampling
  explores them automatically. It also settles the mismatch between the
  concept's additive deltas and the app's ×1.5 factors. · M
- **Ablation pairs for credit.** For a rated image, roll the same seed with a
  single pick swapped and ask A or B. *Why:* a love on a five-pick image
  credits all five; the pair isolates the one that mattered. · M · locks.
- **Duel mode.** Show two outputs and pick one; the result feeds a dueling
  bandit. *Why:* comparing is cheaper and more honest than absolute verdicts. · M
- **Passive signals.** Opening in the big view, "use template + seed" and
  "save as preset" count as soft likes. *Why:* preference shows in behaviour.
  Rating should be optional, not homework. · S
- **Diversity budget per batch.** Of eight rolls, two go to the least-explored
  values and one re-tests a hated region. *Why:* protects the weird and the
  disconfirming regions until they have been judged. · S · explore dial.
- **Rejected combinations.** A hate on a combination (lighthouse × claymation)
  records the pair as a negative memory, not just ×0.5 on each value. *Why:*
  otherwise the same tempting dead end keeps coming back. · S
- **Taste drift.** Ratings decay with a half-life you can set. *Why:* the
  model should follow your taste now, not your taste in March. · S
- **Weight scopes.** Weights are global by default, with template-local
  weights as an option. *Why:* loving `ink` on a poster shouldn't push ink into
  a deep-sea documentary. · M
- ⚗ **Pair weights.** Learn weights for value pairs (`creature × place`), not
  just singles. *Why:* the sleeping dragon works *because* of the clock tower.
  · M · enough ratings.

## 3. Conditioning and noise: the other two spaces

- **Seeds as coordinates.** A seed-lottery view shows the same prompt over a
  grid of seeds. Loved seeds become a library (`__seed__`), and seeds are
  recorded as modes. *Why:* on the H3 campaign, a seed acted as a mode selector
  once conditioning was weak. · S
- **Conditioning travel.** Encode two picks or prompts and slerp between the
  conditionings. The output records `mix=0.35` as a pick. *Why:* a continuous
  axis between two loved regions. Prior art: ComfyUI-LatentWalk, Conditioning
  (Slerp). · M
- **Breeding.** Crossing two loved outputs makes a child whose picks are
  inherited from both parents, plus optional noise crossover (slerp between the
  parents' initial noise). *Why:* evolution with a human as the fitness
  function. Prior art: interactive evolutionary diffusion, "Diffusion
  Crossover" (arXiv 2604.14790). · M (picks) / L (noise, needs a custom noise
  node)
- **Seed jitter.** "Same, but slightly different" as a noise slerp towards a
  neighbour seed at small t. *Why:* local exploration in noise space. · M
- ⚗ **Token gravity.** Measure how far each pick moves the output (image
  embeddings with and without the pick) and show it per word and per model.
  *Why:* it tells you which words Krea 2 or H3 actually listen to. It is the
  probe-run instrument from the H3 campaign. · L · image embeddings.
- ⚗ **Star map.** SigLIP embeddings → UMAP → a map coloured by rating. Lasso a
  region, get the pick distribution inside it, then roll there. *Why:* the
  galaxy as a picture. It is the v1 idea in `concept.md`. · L
- ⚗ **Reverse prompting.** Drop any image and the wired Qwen3-VL describes it.
  orrery matches the phrases to library entries and proposes a template whose
  picks reproduce it. *Why:* navigating backwards (the Kiln reverse-prompt
  workbench idea). · L · stage 5.

## 4. Galaxy views

- **Quality-diversity grid.** Choose two pick families, e.g. `__light__` ×
  `__place__`. Each cell shows its best-rated output; an empty cell is
  unexplored, and clicking it rolls there. *Why:* MAP-Elites as a view. It
  shows at a glance where you haven't looked, which is the whole point of
  exploration. · M
- **Taste report per library.** A mean rating and a count for each value,
  e.g. which `__light__` you really love. *Why:* self-knowledge you couldn't
  have answered from memory. · S
- **Compare.** Two or four outputs side by side with differing picks
  highlighted. · S
- **Video cards.** Hover-scrub the frames of H3 outputs; ratings work the same.
  · M · Log-less capture.
- **Lineage.** Output → template version → preset, so "this preset descends
  from that loved roll" is visible. · M

## 5. H3 and video

- **Animate this.** On a Krea still: load an I2VA template with the image as
  `<Picture 1>` and carry the still's picks over, so the creature in the still
  becomes `$hero` in the video. *Why:* two models, one coordinate system, and
  H3 is the must-have. · M
- **Storyboard rolls.** Roll four variants of shot 2 only, with the other
  shots' picks locked. · S · locks.
- **Ref2VA writer.** The six-section format with orrery-managed `<Subject N>`
  labels. · M–L
- **Densifier.** An LLM enriches prose only, logged as a pick and re-linted
  afterwards. · M · stage 5.
- **Sound follows picture.** Use structured entries for SFX that match
  weather, place and material. · S · structured entries.

## 6. LLM stage

- **In-flow library generation.** Use the wired Krea 2 text encoder via
  `clip.generate(skip_template=True)`, otherwise the configured model;
  generate, then unload. · M
- **Queued semantic edits.** Edits run in the ComfyUI queue and come back as a
  diff you apply in the Libraries tab. · M
- **Grow from ratings.** Ask for eight more entries like the loved ones and
  unlike the hated ones, with galaxy stats as context. *Why:* the space expands
  exactly where you're happy. · S · in-flow generation.
- **Template doctor.** Model-specific lint plus suggestions: Krea wants the
  medium named, H3 wants verbs in SFX and a noun phrase after a cut. · S–M
- **Executing `>`.** Enhancement instructions finally run, and the rewrite is
  recorded next to the original. · M

## 7. Workflow ergonomics

- **Generate in the node, capture without Log.** A Generate button queues only
  the orrery-driven branch (`app.queuePrompt(0, 1, targetIds)`). `executed`
  events from Save and Preview nodes feed the galaxy, so Orrery Log becomes
  optional. *Why:* one node, which is the whole ask. · M
- **The node honours `: x8`.** It queues N runs with `seed + i`. · S
- **Drag a PNG onto the node.** It restores the template, seed and picks from
  the embedded metadata. · S
- **Preset history.** Saving keeps the previous version, and the preset detail
  shows the diff. · S

## 8. Sharing and portability

- **Preset packs.** One `.orrery` file holds a folder of presets, the
  libraries they use and a few thumbnails, with import in the Presets tab.
  *Why:* Krea and H3 packs worth passing around. · M
- **Portable galaxy.** The JSONL plus a thumbnail folder can be moved between
  machines (Mac-Claude and WSL). Media paths are resolved relative to a
  configurable output root. · S

## Next five

1. **Pick locks + More like this.** Tiny, needs no new infrastructure, and
   turns the existing picks into a precise exploration gesture.
2. **Exploration dial, then Thompson sampling.** It fixes the starving of
   unrated values and replaces the fixed multipliers with one honest control.
3. **Quality-diversity grid.** This is the view that shows the unexplored
   cells, so it is the most "galaxy" feature on the list.
4. **Structured library entries.** Correlated picks (picture ↔ sound) for H3,
   with no new control flow in the grammar.
5. **Animate this.** Krea still → H3 video with the picks carried along: the
   must-have model gets orrery's coordinates end to end.

## Sources in the KG

- `claude-knowledge/sketches/probe-runs-prompt-galaxy.md`: seed lotteries,
  token gravity, structured sweeps, the reverse workbench.
- `insights/Quality diversity archives are the right optimization frame for vector ideation.md`
- `insights/Diversity budgets keep nearest weird and disconfirming regions alive until evaluation.md`
- `insights/Rejected paths are anti-collapse memory for future ideation runs.md`
- `insights/Passive preference learning through rejection and resonance signal tracking refines taste without interrogation.md`
- `insights/Recognition is cognitively cheaper than generation so humans should evaluate proposals not write specs.md`
- `basic-memory/shared/projects/z-explorer/LoRA Feature - Proposed Syntax & Implementation Examples.md`
- `orrery/docs/concept.md` (additive deltas, star-map deferral) and `docs/h3.md`
  (Ref2VA, densifier).

Web prior art:
- [Diffusion Crossover](https://arxiv.org/pdf/2604.14790)
- [Interactive Latent Diffusion Model (GECCO)](https://dl.acm.org/doi/10.1145/3583131.3590471)
- [Preference-Guided Prompt Optimization](https://arxiv.org/html/2602.13131v1)
- [ComfyUI-LatentWalk](https://github.com/rnbwdsh/ComfyUI-LatentWalk)
- [Feel-Good Thompson Sampling for dueling bandits](https://arxiv.org/abs/2404.06013)
