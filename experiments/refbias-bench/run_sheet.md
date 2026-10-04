# The refbias bench: run sheet

Issue #146, for the strength calibration (#93). The question: how do per-reference strengths behave
when a subject from one picture is placed into a place from another, and does it depend on the kind
of subject? A person's face, a people's body beyond the human, a creature and an object may hold
at different strengths, and the place may pull them toward its own look at different strengths too.

## The setup

`refbias_bench.orr` casts two pictures by name: `@HERO`, a subject from a Krea creator, and
`@PLACE`, a place from the landscape or setting creator (`cast = backdrop`). `SET:` sweeps both
strengths, 0.2, 0.5 and 1, so Roll renders nine clips per seed (the cross product, the hero's
strength changing slowest).

| `$type` | The subject | From |
|---|---|---|
| people | a person | `krea/09_character_creator` |
| peoples | a people beyond humans (elf, orc, centaur …) | `krea/10_fantasy_creator[people!=human]` |
| creatures | a creature | `krea/13_creature_creator` |
| objects | a specimen cabinet | `krea/08_cabinet_of_curiosities` |

One seed for all four types, so the same place rolls for each (the place's pick does not hang on
`$type`). Workflow: `orrery_h3_reel_refmod_turbo` (the turbo LoRA), 5 s at 0.6MP. 4 types × 9
clips = 36 clips.

**Before it runs:** the gallery needs pictures of each creator above, and at least one place from
`krea/16_landscape_creator` or `krea/17_setting_creator` (a grid's four views come along as one
place).

## What to look at, per clip

| | 0 | 1 | 2 |
|---|---|---|---|
| **Subject** | gone or someone else | the kind and colours, not the identity | clearly the picture's subject |
| **Place** | another place | its kind and light | clearly the picture's place |
| **Together** | pasted on, wrong scale or light | plausible | the subject belongs there |

Plus a word on what bled: the place's style on the subject, the subject's backdrop (the creators'
grey studio) in the place, a second copy of either.

## Results

Not run yet. The scores and what they say go into #143's comments, and into a table here.
