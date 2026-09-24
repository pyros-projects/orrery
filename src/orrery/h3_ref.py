"""The ref2va writer: the six sections of the full-reference guide
(VIDEO_PROMPT_WRITING_GUIDE_ref_en.md), with every label computed from the CAST.

The author names things once (CAST) and mentions them by name; the writer keeps <Subject N>,
<Picture i>, <Video k>, <Audio j> and (Sx) consistent across definitions, summary, retention,
description and sound, and derives the summary's task types from the roles the references play.
"""

import re

from orrery.cast import Labels, Names, article, bracket_sources
from orrery.h3 import Issue, Scene, _cap, _Speakers, music, render_shots, soundscape

TASK_ORDER = ("video editing", "video continuation", "keyframe completion", "reference generation",
              "audio reuse", "audio reference")
WORDS = (350, 500)
DEFAULT_KEEP = ("fully_preserved", "the defined appearance of {who} is retained.")


def _style_sentence(style: str) -> str:
    if not style:
        return ""
    if style.endswith("."):
        return _cap(style)
    noun = "" if re.search(r"\bstyle\b", style, re.IGNORECASE) else " style"
    return f"The target video uses {article(style)} {style}{noun}."


def write_h3_ref(scene: Scene, lint: list[Issue]) -> str:
    prose = [it for shot in scene.shots for it in shot.items if isinstance(it, str)]
    labels = Labels(scene.cast, [s for text in [scene.summary, *prose] for s in bracket_sources(text)])
    names, speakers = Names(scene.cast, labels), _Speakers(scene, labels)
    shots = render_shots(scene, lint, speakers, names, labels)

    definitions, retention, types = [], [], set()
    for m in scene.cast:
        phrase = labels.sources_phrase(m)
        noun, detail = m.split_head() if phrase else (m.head, "")
        detail = f",{detail}" if detail else ""
        definitions.append(f"<Subject {labels.subjects[m.name]}> is {noun}{' in ' + phrase if phrase else ''}{detail}{m.tail}.")
        if m.sources:
            types.add("reference generation")
    for i, shot in enumerate(scene.shots, start=1):
        for anchor, edge, verb in ((shot.first_frame, "first", "begins from"), (shot.last_frame, "last", "ends on")):
            if anchor:
                index, shows = anchor
                definitions.append(f"<Picture {index}> is the {edge} frame of [Shot {i}]{', showing ' + shows if shows else ''}.")
                retention.append(f"<Picture {index}> ([Shot {i}] {edge} frame): fully_preserved - the shot {verb} <Picture {index}>.")
                types.add("keyframe completion")
    for m in scene.cast:
        if not m.voice:
            continue
        who = f"<Subject {labels.subjects[m.name]}>"
        sid = speakers.ids.get(m.name)
        note = f", {m.voice_note}" if m.voice_note else ""
        definitions.append(f"{labels.label(m.voice)} is the voice-timbre reference for {who}{f' ({sid})' if sid else ''}{note}.")
        retention.append(f"{labels.label(m.voice)}: reference - its vocal timbre guides the dialogue delivery of "
                         f"{who} without copying the original signal.")
        types.add("audio reference")

    subjects = []
    for m in scene.cast:
        shots_in = names.appears[m.name]
        if not shots_in:
            lint.append(Issue("warn", f"{m.name} is in the CAST but appears in no shot."))
        where = ", ".join(f"[Shot {i}]" for i in sorted(shots_in)) or "no shot"
        marker, reason = m.keep or (DEFAULT_KEEP[0], None)
        reason = reason or DEFAULT_KEEP[1].format(who=m.short)
        subjects.append(f"<Subject {labels.subjects[m.name]}> (appears in {where}): {marker} - {reason}")
    retention = subjects + retention

    prefix = " + ".join(t for t in TASK_ORDER if t in types) or "reference generation"
    summary = f"[{prefix}] {names.plain(labels.brackets(scene.summary))}".rstrip()
    description = "\n".join(p for p in (_style_sentence(scene.style), *shots) if p)
    words = len(description.split())
    if not WORDS[0] <= words <= WORDS[1]:
        lint.append(Issue("warn", f"detailed_description has {words} words; the guide asks {WORDS[0]}–{WORDS[1]} "
                                  "for generation (dialogue-dense scenes may run longer)."))
    parts = {
        "subject_definitions": "\n".join(definitions),
        "summary": summary,
        "retention_analysis": "\n".join(retention),
        "detailed_description": description,
        "overall_soundscape": soundscape(scene, lint),
        "non_diegetic_music": music(scene, lint),
    }
    return "\n\n".join(f"{k}:\n{v}" for k, v in parts.items())
