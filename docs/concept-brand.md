# orrery: the brand

Status: decided 2026-10-03 (#88, under #23). Pyro picked the first screen of
the mock ("ich will basically genau das"): the name stays, the headline is *One
script. Endless films.*, and real videos replace the wall of text (#91). The
hype video is #90. Open: *Roll* on the button, and which of the six ideas next.
The options side by side, with a working seed crank:
https://claude.ai/artifact/67S9KyLtjVT9AUhR9bdBzQ (source:
`docs/mock/orrery-brand.html`).

## The short version

- **Keep the name, change the story.** The name never came from the galaxy.
  `concept.md` (2026-09-23) chose it for the clockwork: turn the crank and
  every body lands in an exact, reproducible place. That is the seed, and the
  seed is what orrery has that nobody else has. The galaxy only borrowed the
  sky.
- **The story is the seed, not the like button.** orrery's pitch today opens
  with "learns your taste". It should open with what one script does: *one
  script, endless films*, every one of them replayable, every frame traceable
  to the line that made it.
- **Say "films", not "content".** "Infinite content" is the wording of
  faceless-channel autoposters, and 2026 is the year of the slop backlash
  ("Your AI Slop Bores Me", 50M hits; Fruit Love Island, called slop and taken
  down). "Endless films" makes the same promise in an author's words.
- **One visual signature everywhere:** the script beside the film, the rolled
  words lighting up as the clip plays. Nobody else can show that picture,
  because nobody else knows which word made which frame.
- **Make the seed the thing people share,** the way Minecraft seeds, Wordle
  grids and Midjourney `--sref` codes spread: one short line anyone can paste
  and replay.
- **Launch on the H3 wave, not on Hacker News.** The H3 nodes that grew fast
  (Motion Context: 1.1k★ in about two months) were early in a model wave; HN is
  lukewarm on AI-made content.

## The field

Nothing in it does what orrery does: every tool goes from an idea or a script
to one video. None treats a template as a reproducible, branching, endless show
whose every pick can be addressed, shared or rated.

| Neighbour | How it presents itself | Size |
|---|---|---|
| sd-dynamic-prompts | "a tiny template language for random prompt generation" | 2.3k★, no push since July 2024 |
| One Button Prompt | "random, but controlled … press generate, and let it surprise you"; its README opens with a gallery | 1.1k★, 118k downloads |
| Impact Pack, Easy-Use | wildcards as one feature among many | about 3.5M registry downloads each |
| H3 nodes: AIMixer Director, H3 Motion Context, Context-Loop | a multi-segment timeline; clip chaining | 2.1k★, 1.1k★, 490★, all since H3's day 0 (2026-08-03) |
| awesome-minimax-H3 | the curated list of about 60 H3 nodes; orrery is not on it | 542★ |
| LTX Studio, Showrunner, Kling 3.0, Google Flow | script → storyboard → film, hosted; Showrunner: "Watch AI shows. Make your own." | closed |
| MoneyPrinterTurbo | a short video "from a topic or keyword" | 128k★: the idea-to-clip slot is taken, and slop-adjacent |

## What orrery is, seen from outside

April Dunford's positioning canvas (*Obviously Awesome*), filled in from what
is built.

| | |
|---|---|
| **What people use without it** | Writing prompts one by one; wildcard nodes that roll blind and forget; asking a chatbot for ten prompts; chaining video clips by hand in a node graph; hosted storyboard tools that rewrite your prompt and keep the model. |
| **Only orrery** | a template is a program: one text file rolls a different result for every seed, and the same seed always rolls the same one · every random choice keeps its name, so one choice can change while the rest stays · the script is a screenplay (SCENE, CUT TO, END ON, REMEMBER) that compiles to the model's own format · a reel can branch, loop and roll its own path, forever · frames carry over as the cast's references, and a reel can go on from your own video · it runs locally, inside ComfyUI, and every output carries its script |
| **What that is worth** | 1. *Never run out:* one idea becomes as many takes as you want. 2. *Never lose one:* every take can be replayed, and remixed one choice at a time. 3. *Stories, not clips:* a film that holds together scene after scene, and keeps going. |
| **Who cares most** | People making AI video in ComfyUI on their own GPU, who post series (a show, a format, a character) and need volume that stays consistent. Next to them: generative artists who already think in seeds and systems. |
| **Category** | Not "wildcards" (that frame says random and small). A subcategory people already understand: **a screenplay with dice in it**, or by analogy, **seeds for films** (a Minecraft seed is a world from a number; an orrery seed is a film from a script). |
| **Why now** | Local video models became good enough to chain into long films in 2026, and the tools still think in single clips. |

The canvas says the current README is positioned on the weakest attribute: a
rating gallery could be copied; a reproducible, branching screenplay is the
part nobody else has.

## The words

Pyro's line, "One prompt, infinite content", has the right shape: a small input
and an unbounded output. Two words work against it. *Prompt* sounds like a
single string, and orrery's input is a script. *Content* is the autoposters'
word ("one script becomes infinite content" sells faceless YouTube channels),
and the one the anti-slop crowd uses with contempt. Close variants are taken
too ("Infinite Possibilities, Single Prompt", agen8).

| Line | Strength | Weakness |
|---|---|---|
| **One script. Endless films.** | Pyro's idea in an author's words; says the job in four words | "script" needs the visual beside it to read as more than a prompt |
| **A screenplay with dice in it.** | explains the product in six words, and makes people smile | a description, not a promise |
| **Infinite, not random.** | answers the slop critique head-on | needs the main line first |
| **Write it once. Roll it forever.** | the verb *roll* means dice, a film roll and "Roll camera!" at once; `forever` is a real keyword | does not say video |
| **Every seed a new film. Every film its own script.** | both halves of the moat: endless and traceable | long |
| **Turn the crank. Watch the film.** | makes the name mean something at first sight | the crank needs the picture |

Recommendation: **One script. Endless films.** as the headline, **A screenplay
with dice in it** as the one-line explanation under it, **Infinite, not
random** as the line for the provenance section.

**Roll as the house verb.** The app says *Generate*. *Roll* is what the language
does (it rolls picks), what the camera does, and what the AI crowd already says
("reroll it"). "Roll ×10" on the button, "rolled from seed 7" on a clip, "reroll
just the weather" for changing one pick. Cheap, and it ties the UI to the story.

## The name

The name never came from the galaxy. `concept.md`: "An orrery is a clockwork
model of the heavens: turn the crank and every body lands in an exact,
reproducible position. orrery does the same for prompt space." The image is
exact without any galaxy: the template is the machine, the picks are the
planets, the seed is the crank. Turn it to 7 and every planet lands where it
landed last time.

| | orrery (keep) | a new name (Rollfilm, Reroll, Seedreel, Zoetrope …) |
|---|---|---|
| fits the story | yes: the clockwork is the seed | the film-and-dice words fit too |
| free in its space | nothing in creative AI or prompting uses it, and the Comfy Registry id `orrery` is free. But PyPI's `orrery` is an MVC library (0.1.1), five AI-tooling repos from 2026 carry the name (an agent cockpit, an agent workflow CLI), and searches compete with physical orreries. `orrery.ai`, `.dev` and `.com` are taken or parked; `.tv`, `.film`, `.studio`, `.app` did not resolve (check before buying) | crowded: Roll (an AI video app), Rollfilm (an open-source AI photo manager), Reroll (a gaming word, 587 repos), Zoetrope (Coppola's studio) |
| easy to say and spell | no: "OR-uh-ree", people stress it wrong and type "orery" | mostly yes |
| cost to change | none | the repo, every node and preset name, the docs, the banner |

Recommendation: **keep orrery**, and never let it stand alone: "orrery,
a screenplay with dice in it". Put the pronunciation in the README once. The
CLI needs another PyPI name when it is published (`orrery-film`, say). A name
for the stunt rides on the main one (orrery.tv), so every mention of it builds
the main name.

The galaxy becomes the **gallery** (#89), as Pyro decided. If the film words
win, *dailies* is the film word for the same thing (the takes of the day,
watched and judged); a thought, not a proposal.

## Ideas to reach people

Scored with Jonah Berger's STEPPS (*Contagious*): social currency, triggers,
emotion, public, practical value, stories. What spread in the precedents:
results that are short and spoiler-free (a seed, a code, a grid), the same
thing for everyone so results compare, proof that you found something first
(Infinite Craft's "First Discovery!"), a live thing to drop into, and one clip
on Reddit or X to set it off.

### 1. The script lights up (the visual signature)

Every clip orrery shows in public is shown the same way: the script on one
side, the film on the other, the rolled words highlighted as their shot plays,
the seed in the corner. It is the one picture only orrery can make, it explains
the product without a word, and once people have seen two of them they
recognise the third. **Public, stories.** It also makes every post a tutorial.

### 2. orrery.tv: a channel that is one text file

A channel (YouTube, TikTok, a Twitch stream) that never ends, made by one
template: the Infinite Runway (`@fashion/infinite_cakewalk`), the Backrooms, the
Dice Dungeon. The template is pinned under every video, with the seed. The
pitch is the story people retell: "this whole channel is one text file". It
can't be retold without the name (Berger's Trojan-horse test). Votes from the
audience can steer the next rolls: the gallery's like button, given to a crowd.
**Emotion (awe, amusement), stories, public.**

The precedent is *Nothing, Forever*, the endless AI Seinfeld: four viewers for
weeks, then about 98k followers once it reached Reddit, then a two-week ban
for a joke nobody had checked. orrery's answer is in its design: every word the
channel can say is in lists a person wrote, so the channel is as safe as its
cartridge. The renders still need a look before they air.

### 3. Seeds as social currency

Minecraft players trade seeds, Midjourney users trade `--sref` codes. Every
orrery output already carries its script and seed: drop an orrery video into
ComfyUI and the workflow opens with them (checked: ComfyUI's front end reads the
workflow from an mp4's metadata). Say it loudly ("every film carries its own
script"), and give every clip **one line anyone can paste**: the cartridge and
the seed, `@fashion/infinite_cakewalk · 4417`, with the roll as a spoiler-free
summary (autumn · a palace ballroom · a copper ponytail · a denim corset gown).
The good seeds get traded; whoever posts a seed first has found it. A
*same script, nine seeds* grid is the second recurring picture. **Social
currency, practical value, public.**

### 4. Cartridges

Presets as cartridges: a template you load and roll, with a title, a cover
frame and a note. The 75 that ship are the first shelf; Civitai is where people
can trade more (wildcard packs there are a niche, about 2k downloads for a big
one, so cartridges have to show films, not lists). The golden corpus (#20)
writes one cartridge per language feature, each worth shipping, so it grows the
shelf while it pins the language (Pyro, 3 October). Template authors are the
hard side of this network (*The Cold Start Problem*): credit them on every
cartridge and every post. Ship the workflow with every cartridge, as
Mickmumpitz ships his with every video. **Practical value, social currency.**

### 5. Seed of the day

One cartridge a day, rolled with the date as its seed: everyone gets the same
film, and the community posts its renders. Wordle's and Spelunky's daily
ritual, for films. **Triggers (daily), public.** It needs a community big
enough to have a conversation, so it comes after 2 and 3.

### 6. A playground in the browser

orrery's language is plain Python with no model in it, so it can run in the
browser (Pyodide). A page where anyone rolls a cartridge, turns the seed and
watches the screenplay change, with no GPU and no install, then takes the
script to ComfyUI. It widens the door from "people with a big GPU and H3" to
"anyone curious"; the playable toys are what Hacker News does like (Infinite
Craft: 1,177 points, against 15 for Nothing, Forever). **Practical value,
public.** The largest build of the six.

## How to present it

- **The first screen shows the output, not the node.** A 20–30 s loop of one
  script beside its films (three seeds and a branch), or the nine-seed grid. One
  Button Prompt opens with its gallery for the same reason. The node screenshot
  moves further down: it shows where orrery lives, not why to want it.
- **Headline, line, button.** "One script. Endless films." / "orrery is a
  screenplay with dice in it: write the scenes once, and every seed rolls a
  different film you can replay, remix and keep going, inside ComfyUI." / Quick
  start.
- **Three value themes, in that order:** never run out, never lose one, stories
  not clips. The like button is one line under "never lose one".
- **Proof:** a few cartridges with their films; the provenance claim made
  concrete ("change the weather, keep the world": two clips from one seed, one
  pick apart).
- **Where people are, in order:** the Comfy Registry (publish with its GitHub
  Action; the id `orrery` is free) and a pull request to awesome-minimax-H3;
  r/comfyui (about 210k) and r/StableDiffusion (about 1M) with a looping clip;
  X's AI-video crowd; ComfyHub; the people who make ComfyUI tutorials (Pixaroma,
  Sebastian Kamph, Olivio Sarikas, Mickmumpitz). Hacker News last, with the
  playground if it exists.
- **Timing:** launch on a model wave (the next H3 release, or next to a busy H3
  node), with everything out within a day or two.

## What follows if Pyro picks a direction

Each becomes a task (under #23 or a feature of its own), none of it built in #88:

- the README and the docs in the new story (the tagline, the order of the
  value themes, the pronunciation, the first-screen video)
- the gallery rename (#89), and *Roll* as the button's word if wanted
- the signature video: a way to render the script beside its film
- the paste line: cartridge and seed as one line on every output
- publishing: the Comfy Registry, awesome-minimax-H3, a PyPI name for the CLI
- orrery.tv: a channel and a first endless cartridge to run on it
- cartridge covers and notes for the presets that ship
- the playground

## Sources

Skills used, from `moat_and_gaps/skills`: positioning (`obviously-awesome`,
`positioning-ideas`), virality (`contagious`), naming (`product-name`),
growth loops (`growth-loops`), beachhead (`beachhead-segment`), networks
(`cold-start-problem`).

Web research, 2026-10-03:
- the field: [sd-dynamic-prompts](https://github.com/adieyal/sd-dynamic-prompts),
  [One Button Prompt](https://github.com/AIrjen/OneButtonPrompt),
  [Impact Pack in the registry](https://api.comfy.org/nodes/comfyui-impact-pack),
  [MiniMaxH3 Director](https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director),
  [H3 Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context),
  [awesome-minimax-H3](https://github.com/wildminder/awesome-minimax-H3),
  [LTX Studio](https://ltx.io/studio), [Showrunner](https://www.showrunnerstudio.com/),
  [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)
- precedents: [Nothing, Forever](https://knowyourmeme.com/memes/sites/nothing-forever-ai-generated-seinfeld-twitch)
  and [its Show HN](https://news.ycombinator.com/item?id=33833645),
  [Infinite Craft](https://knowyourmeme.com/memes/sites/infinite-craft) and
  [on HN](https://news.ycombinator.com/item?id=39205020),
  [AI Dungeon 2](https://aidungeon.medium.com/how-we-scaled-ai-dungeon-2-to-support-over-1-000-000-users-d207d5623de9),
  [Fruit Love Island](https://en.wikipedia.org/wiki/Fruit_Love_Island),
  [Your AI Slop Bores Me](https://en.wikipedia.org/wiki/Your_AI_Slop_Bores_Me),
  [Wordle](https://en.wikipedia.org/wiki/Wordle),
  [Midjourney style references](https://docs.midjourney.com/hc/en-us/articles/32180011136653-Style-Reference)
- channels: [Comfy Registry publishing](https://docs.comfy.org/registry/publishing),
  [ComfyHub](https://blog.comfy.org/p/from-workflow-to-app-introducing),
  [Mickmumpitz](https://www.thedaringcreatives.com/creator-stories/mickmumpitz-comfyui-workflows/)
- the name: [PyPI orrery](https://pypi.org/project/orrery/),
  [an agent cockpit called Orrery](https://github.com/arvelvale/orrery),
  [pronunciation](https://www.howtopronounce.com/orrery);
  the slogan: [agen8](https://www.agen8.io/),
  [faceless-channel wording](https://www.vidau.ai/build-a-faceless-youtube-channel-with-ai-video-now-autopilot-guide/)
