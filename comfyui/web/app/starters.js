// What "New" opens: a small working template with the essentials as `# …` comments on top, so the
// syntax is at hand without the Help tab. Comments never reach the model.

const SCENE = `# H3 SCENE · quickstart (# lines are comments: they never reach the model)
# @h3 <mode> [ratio] [0.6MP]    text image first-last last references · 0.6MP sizes width × height by area
# style: …                      medium first: live-action, 2D-animated, claymation, vintage film …
# SHOT 5s: push in, small, slow
#     camera: push in, pull out, zoom in/out, pan/truck left/right, tilt/pedestal up/down, arc,
#     tracking, static, shake slightly/strongly, roll · then small/large and slow/fast
# SHOT 3s: cut, static         a later shot: cut (default), dissolve, fade or wipe
# Prose: what the camera sees and what happens in it, a visible action, never a frozen pose
# @NAME (warm low voice): Line.  speech, about 2.5 words a second · [German] Text for other languages
# SFX: rain on a tin roof; a door slams     sound next to its cause · SFX: silence for none ·
#                                            no SFX: natural foley and ambience that fit the scene
# MUSIC: solo cello at a slow tempo         the score; leave it out and there is none
# __lib__ rolls a library · {a|b:2} a weighted choice · $x = __lib__ binds once · $x.sfx a property
# Tips: name the look by medium, era and defects, not by artist · say what is there, no negatives ·
#       "one continuous unbroken ten-second shot" in the style keeps a single take
@h3 text 16:9
style: live-action, cinematic
$who = __characters/average_joes__

SHOT 5s: push in, small, slow
$who sits alone in a laundromat at night and looks up as the lights flicker.
SFX: dryers tumbling; a fluorescent tube buzzing
`;

const REEL = `# H3 REEL · quickstart: one screenplay, one clip per run, each continuing the one before
# Wiring: picks → Orrery Continue, with the H3 node's latent (length → that node: it counts the 22
#   pinned frames) and conditioning; its latent → the sampler · sampled latent + decoded images and
#   audio → Orrery Film, whose film is the reel so far
# Run it: Roll next N clips · Restart goes back to clip 1 · keep the seed fixed
# Before the first SCENE is the world (header, style, CAST, $bindings, LORA:, MUSIC:, context:):
#   it rolls once, so a $binding there stays the same in every clip
# SCENE [title] [×N | forever] [(test)]   one clip; a $binding inside it rolls again for every clip;
#   (test): rendered and kept, left out of the film, starting afresh
# END ON: …     how this clip ends and the next one opens (the next may paraphrase it)
# START WITH: … this scene's own opening, in place of the END ON: before it
# AFTER: 2      continue scene 2's last clip instead of the one before (branches off one clip)
# CUT TO: the stairs ×2 (30%)   after this scene, jump there (twice, that often); IF $x is …: CUT TO: …
# $x[-1]        binding x as it was one clip ago · $x["the stairs"] when that scene last played
# context: 22   frames each clip continues from (Orrery Continue: 22; Motion Context: 5, 22, 39, 56)
# REMEMBER: first frame as @NAME   reels from references: that frame is NAME's picture from the next
#   clip on (Orrery Refs fetches it) · frame at 1s, frames 34-46, last frame · as image 3 ·
#   every 10th frame as refmod NAME: a RefMod of them · … in clips 2-5, … until the stairs
# Tips: describe recurring people and places again in every clip, the model has no memory ·
#       end each clip on a simple, framed state (a closed door, curtains, the foot of a stair) ·
#       no per-clip music: lay one score over the whole film afterwards
@h3 text 16:9
style: live-action, cinematic, one continuous unbroken ten-second shot at eye level
context: 22
MUSIC: N/A
$house = __tour/architecture__

SCENE the first room
$room = __tour/rooms__
SHOT 10s: push in, slow
The camera glides into $room, inside $house, and in the final second comes to rest facing a closed door.
SFX: $room.sfx; $house.sfx
END ON: the camera rests squarely facing a closed door

SCENE the next room forever
$room = __tour/rooms__
SHOT 10s: push in, slow
The door swings open and the camera glides into $room, inside $house, and in the final second comes to rest facing a closed door.
SFX: $room.sfx; $house.sfx
END ON: the camera rests squarely facing a closed door
`;

const REF = `# H3 REFERENCES · quickstart: for the MiniMax H3 Reference to Video node
# CAST, before the first SHOT, names every reference once; shots and lines use @NAME (@ lists them)
#   @NAME (image 1): the head noun, then details      @NAME (image 2, image 3): several views of it
#   @NAME (video 1): …      @NAME (video 1 + audio): with its soundtrack wired too
#   @NAME (refmod NAME): a RefMod from models/refmods · always: in every clip, named or not
#   voice: audio 1         the timbre the member above speaks with
#   keep: face, outfit     what of the member above stays: a retention block goes into the prompt
#     (all · face, hair, body, outfit · style · place · loose, or fully_preserved - your own reason)
# SHOT 4s: from image 3   the shot starts on <Picture 3> · to image 3: it ends on it
# SHOT 4s: after video 1  continues <Video 1> from its last frame (wire that video into ref_video)
# --directions--           a slot the language model writes when the node runs
# Orrery Refs between your images and the node hands each clip only the references its CAST uses
# SET: @HERO(0.6) turns all of HERO's pictures and RefMods (0.6, refmods: only the RefMods) · SET:
#   image_1(1, 35%) one picture from 35% of sampling · most of the change comes below 0.3
# In a reel: REMEMBER: first frame as @HERO inside a SCENE makes that frame HERO's picture for the
#   clips after it; Orrery Refs fetches it from the reel's clips, a picture wired there stands in until then
# @h3 references 16:9 full     the six sections of MiniMax's guide instead of <Subject N> = … lines, with a
#   summary: The target video shows NAME … (the task prefix is added for you) and 350–500 words of prose
@h3 references 16:9
style: live-action, cinematic

CAST
@PLACE (image 1): the street, with wet cobblestones and warm shop windows
@HERO (image 2): the woman, with short black hair and a red raincoat
keep: face, hair, outfit

SHOT 5s: tracking, slow
@HERO walks through @PLACE, turns her head toward a shop window and smiles.
SFX: footsteps on wet stone; distant traffic
`;

const KEYFRAMES = `# H3 KEYFRAMES · quickstart
# @h3 image        the clip starts on your still: wire it as the first frame, call it <Picture 1>
# @h3 first-last   first and last frame: <Picture 1> opens the clip, <Picture 2> closes it (one shot)
# @h3 last         the clip ends on <Picture 1>
# The alignment sentence H3 expects is written for you; describe what happens in between
# Tips: stay true to the picture, then change one thing · say what moves (hair, fabric, light,
#       the subject's first action) · a small camera move brings a still to life
@h3 image 16:9

SHOT 5s: push in, small, slow
The scene begins exactly as in <Picture 1>. Then a light breeze moves hair and fabric, and the main subject slowly turns toward the camera.
SFX: a light breeze; faint room tone
`;

const KREA = `# KREA 2 · quickstart: full sentences, as if describing a photograph to a friend
# Name the medium first: a 35mm photograph, a watercolor, a woodblock print, a claymation still
# Then the subject, the place, the light and the framing · text to render goes in "quotes"
# No quality tags (masterpiece, 8k) and no negatives: say what is there
# __lib__ rolls a library · {a|b:2} a weighted choice · $x = __lib__ binds once
# : w832 h1216 sets the size (the node's width and height)
a 35mm photograph of {a quiet street|an empty diner|a greenhouse} at {dawn|dusk}, soft grain, a hand-painted sign reading "OPEN"
: w832 h1216
`;

export const STARTERS = {
  h3: { label: "H3 scene", hint: "from text: shots, camera, voices, sound", target: "h3-base", text: SCENE },
  reel: { label: "H3 reel", hint: "several clips, each continuing the last: SCENE, END ON, REMEMBER", target: "h3-base", text: REEL },
  ref: { label: "H3 references", hint: "a CAST from images, videos, voices, RefMods", target: "h3-base", text: REF },
  keyframes: { label: "H3 keyframes", hint: "image, first-last, last: start or end on a still", target: "h3-base", text: KEYFRAMES },
  krea: { label: "Krea prompt", hint: "a still: medium first, size", target: "text", text: KREA },
};
