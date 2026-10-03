You continue a reel for the MiniMax H3 video model, which makes video with sound. A reel is a film made of clips: each clip is a SCENE, and every clip continues the one before.

How a scene is written:

SCENE <a short title>
SHOT <seconds>s: <camera move>, <size>, <speed>
Two or three sentences in the present tense: what the camera sees and what happens in it.
NAME (how it sounds): A line of speech.
SFX: a sound; another sound
END ON: the simple, framed state the next clip opens on

- One or two SHOT blocks per scene, together under 15 seconds; a shot lasts 2 to 10 seconds.
- Camera moves: push in, pull out, zoom in, zoom out, pan left, pan right, truck left, truck right, tilt up, tilt down, pedestal up, pedestal down, arc, tracking, static, shake slightly, roll. Size is small or large, speed slow or fast; both may be left out. Choose the move the action needs; do not copy the moves of the example or of the earlier scenes.
- The prose shows a visible action, never a frozen pose. Sentences start with a capital letter.
- People and animals: a name in CAPITALS from the CAST stays that name. Anyone without a CAST entry is described in full again in every scene, with the same words the earlier scenes use ("a tall man in a grey trench coat", not "the man"): the clips are made one by one and do not see each other.
- Speech goes on a NAME line, never in SFX: `NAME (how it sounds): the line.` About two and a half words per second of the shot. When the earlier scenes have speech or a narrator, the new scene has a line too, by the same kind of speaker: a narrator stays the narrator, and an animal or a thing speaks only if it spoke before.
- SFX: the sounds you hear, each next to its cause, separated by semicolons; always at least one sound.
- END ON: a simple state that is easy to pick up: a closed door, a turned back, a hand on a railing.

Never write wildcards (__name__), variables ($name), choices ({a|b}), slots (--text--), LoRA tags, comments (# …), headers (@h3 …), markdown or explanations.

An example of a scene, from another reel:

SCENE the market
SHOT 6s: tracking, slow
A young baker in a flour-dusted apron carries a tray of bread through the crowded morning market, nodding to the stall keepers as she passes.
BAKER (cheerful, calling out): Fresh bread, still warm!
SFX: market chatter; a cart rattles over cobblestones
SHOT 3s: tilt up
The bell in the church tower above the square swings and rings out the hour.
SFX: a heavy bell tolls
END ON: the young baker in the flour-dusted apron stops at the fountain and sets the tray down

The reel you continue, its world and every clip so far, as it was made:

{world}

{chunks}

Write clip {next}, the next SCENE. It opens exactly where the last one ended ({handoff}), keeps the same people, place and style, and moves the story one step on. Start with "SCENE" and a short title, end with an END ON line. Answer with the scene alone.
