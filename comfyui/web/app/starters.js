// What "New" opens: a small working template with the essentials as `# …` comments on top, so the
// syntax is at hand without the Help tab. Comments never reach the model.

const SCENE = `# H3 SCENE · quickstart (# lines are comments: they never reach the model)
# @h3 <mode> [ratio] [0.6MP]    t2va i2va fl2va l2va ref2va · 0.6MP sizes width × height by area
# style: …                      medium first: live-action, 2D-animated, claymation, vintage film …
# SHOT 5s | push in, small, slow
#     camera: push in, pull out, zoom in/out, pan/truck left/right, tilt/pedestal up/down, arc,
#     tracking, static, shake slightly/strongly, roll · then small/large and slow/fast
# SHOT 3s | cut, static         a later shot: cut (default), dissolve, fade or wipe
# Prose: what the camera sees and what happens in it, a visible action, never a frozen pose
# NAME (warm low voice): Line.  speech, about 2.5 words a second · [German] Text for other languages
# SFX: rain on a tin roof; a door slams     sound next to its cause · SFX: silence for none
# MUSIC: solo cello at a slow tempo         the score; leave it out and there is none
# __lib__ rolls a library · {a|b:2} a weighted choice · $x = __lib__ binds once · $x.sfx a property
# Tips: name the look by medium, era and defects, not by artist · say what is there, no negatives ·
#       "one continuous unbroken ten-second shot" in the style keeps a single take
@h3 t2va 16:9
style: live-action, cinematic
$who = __characters/average_joes__

SHOT 5s | push in, small, slow
$who sits alone in a laundromat at night and looks up as the lights flicker.
SFX: dryers tumbling; a fluorescent tube buzzing
`;

const REEL = `# H3 REEL · quickstart: one screenplay, one clip per run, chained by H3 Motion Context
# Wiring: load_index → Load Latent's clip_index · save_index → Save Latent's clip_index ·
#         length → the latent (it counts the frames Motion Context pins)
# Run it: Generate ×N plays N clips · Restart goes back to segment 0 · keep the seed fixed
# Before the first CHUNK is the world (header, style, CAST, $bindings, LORA:, MUSIC:, context:):
#   it rolls once, so a $binding there stays the same in every clip
# CHUNK [title] [repeat N|forever]   one clip; a $binding inside it rolls again for every clip
# HANDOFF: …    how this clip ends and the next one opens (the next may paraphrase it)
# $x~1          binding x as it was one clip ago · $x~1.open one of its properties
# context: 22   frames Motion Context pins: 5, 22, 39 or 56
# Tips: describe recurring people and places again in every clip, the model has no memory ·
#       end each clip on a simple, framed state (a closed door, curtains, the foot of a stair) ·
#       no per-clip music: lay one score over the whole film afterwards
@h3 t2va 16:9
style: live-action, cinematic, one continuous unbroken ten-second shot at eye level
context: 22
MUSIC: N/A
$house = __tour/architecture__

CHUNK the first room
$room = __tour/rooms__
SHOT 10s | push in, slow
The camera glides into $room, inside $house, and in the final second comes to rest facing a closed door.
SFX: $room.sfx; $house.sfx
HANDOFF: the camera rests squarely facing a closed door

CHUNK the next room repeat forever
$room = __tour/rooms__
SHOT 10s | push in, slow
The door swings open and the camera glides into $room, inside $house, and in the final second comes to rest facing a closed door.
SFX: $room.sfx; $house.sfx
HANDOFF: the camera rests squarely facing a closed door
`;

const REF = `# H3 REF2VA · quickstart: for the MiniMax H3 Reference to Video node
# CAST, before the first SHOT, names every reference once; shots, lines and summary use the NAME
#   NAME (image 1): the head noun, then details      NAME (image 2, image 3): several views of it
#   NAME (video 1): …      NAME (video 1 + audio): with its soundtrack wired too
#   voice: audio 1         the timbre the member above speaks with
#   keep: fully_preserved - what stays   (partially_preserved, attribute_transfer, weak_reference)
# summary: The target video shows NAME … (the task prefix is added for you)
# SHOT 4s | from image 3   the shot starts on <Picture 3> · to image 3: it ends on it
# SHOT 4s | after video 1  continues <Video 1> from its last frame (wire the node's previous output)
# --directions--           a slot the language model writes when the node runs
# Orrery Refs between your images and the node hands each clip only the references its CAST uses
# @h3 ref2va 16:9 lite     writes <Subject N> = … lines instead of the six full sections
# Tip: the guide wants 350–500 words of shot description, so write rich prose (the lint counts)
@h3 ref2va 16:9
style: live-action, cinematic
summary: The target video shows HERO walking through PLACE at dusk.

CAST
PLACE (image 1): the street, with wet cobblestones and warm shop windows
HERO (image 2): the woman, with short black hair and a red raincoat
keep: fully_preserved - her face, short black hair and red raincoat are retained.

SHOT 5s | tracking, slow
HERO walks through PLACE, turns her head toward a shop window and smiles.
SFX: footsteps on wet stone; distant traffic
`;

const KEYFRAMES = `# H3 KEYFRAMES · quickstart
# @h3 i2va    the clip starts on your still: wire it as the first frame, call it <Picture 1>
# @h3 fl2va   first and last frame: <Picture 1> opens the clip, <Picture 2> closes it (one shot)
# @h3 l2va    the clip ends on <Picture 1>
# The alignment sentence H3 expects is written for you; describe what happens in between
# Tips: stay true to the picture, then change one thing · say what moves (hair, fabric, light,
#       the subject's first action) · a small camera move brings a still to life
@h3 i2va 16:9

SHOT 5s | push in, small, slow
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
  h3: { label: "H3 scene", hint: "t2va: shots, camera, voices, sound", target: "h3-base", text: SCENE },
  reel: { label: "H3 reel", hint: "several clips on Motion Context: CHUNK, HANDOFF", target: "h3-base", text: REEL },
  ref: { label: "H3 references", hint: "ref2va: a CAST from images, videos, voices", target: "h3-base", text: REF },
  keyframes: { label: "H3 keyframes", hint: "i2va, fl2va, l2va: start or end on a still", target: "h3-base", text: KEYFRAMES },
  krea: { label: "Krea prompt", hint: "a still: medium first, size", target: "text", text: KREA },
};
