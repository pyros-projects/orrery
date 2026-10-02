# Plan: the DSL, second pass

Status: approved and built 2026-10-02 (Pyro: "alles implementieren inkl. grid und bedingtes goto"),
one commit per phase (f89a884 … e38a982). The showcase: `@fashion/infinite_cakewalk`.

## Why

The DSL grew a feature at a time. A review on 2026-10-02 found three bugs, one structural weakness
(seeds that move when the template is edited), syntax that means too many things (`:` seven ways,
`#` comment and filter, `@` directive and LoRA), and two things missing for stories (inline
libraries, loops over several chunks).

## Phases

1. **Bugs.** A weighted optional (`{ in the rain:3|:7}`) keeps its space; Dynamic Prompts'
   separator (`{2$$ and $$a|b|c}`); a backslash escapes `{ } | $ _ @ # [ ] \ <`, so `\__init__`
   and `\{a\}` reach the prompt as written.
2. **Stable seeds.** Every pick draws from its own stream, derived from the seed, its label and how
   many times that label was drawn before, so an edit in one place leaves the other picks of a
   seed alone. `@rng 1` keeps the old single stream; History and Galaxy replay a run recorded
   before this (no `rng` in its row) with `@rng 1` put on top of its template.
3. **One predicate language.** `__creature[myth, !bird, habitat=$a.habitat, size=small|tiny]__`:
   commas all of, `|` either, `!` not, `key=value` a property (a `$var` or `$var.field` value
   allowed). `#key:value` keeps working. Conditions take the same brackets: `? $w[kind=rain|snow]:`
   and `{? $w[kind=rain]: wet|dry}`, against the binding's pick (its tags and properties).
4. **`@` directives.** `@grid`, `@unique`, `@size 832x1216`, `@seed`, `@batch 8`, `@rng`, `@lib`,
   one per line; the `:` line stays as an alias.
5. **Inline libraries and chance.** `@lib crowd` with indented entry lines (templates themselves)
   is `__crowd__` in this template, shadowing a home library of that name; the LLM never writes
   it. `{30% in the rain}` adds the words three times in ten (learned like any pick); an empty
   roll takes the space before it along.
6. **Globs and a lint.** `__clothing/*__` (the folder), `__clothing/**__` (and below),
   `__scenes/features*__` (a name prefix): a library first, each as likely, then its entry; the
   pick learns on the concrete library. What looks like syntax but rolled nothing (`__my-list__`,
   a lone `{`) warns.
7. **LoRA sweeps in the grid.** A LoRA strength is a value like any other: `<lora:x:{0.5|0.7}>`,
   `<lora:x:$s>`, a grid axis over it. The server plans LoRA sweeps and grids together
   (`/orrery/plan`), and the browser stops mirroring the sweep math.
8. **GOTO.** `GOTO: <chunk title or number> [×N]` at a chunk's end jumps instead of going on;
   `×N` jumps N times, then falls through; several GOTO lines, the first that holds wins;
   `? $w[kind=rain]: GOTO: shelter` jumps on what rolled. The server walks the reel at the node's
   seed (up to 500 clips) and hands the path to the app: dividers list the segments a chunk plays
   (`seg 1, 3, 5`), the timeline and the cells follow it. Another seed, another story.

## Out of scope

Weights and props inside inline libraries (use a YAML library), GOTO into the middle of a chunk,
arithmetic.
