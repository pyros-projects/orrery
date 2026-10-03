"""orrery's boot banner in the ComfyUI console: a small orrery in the app's colours, then the boot log.

Other node packs print banners too, so orrery's few lines at load got lost among them. Parts of
orrery add a boot line with note() while they load; the ComfyUI entry calls show() once, at the end.
Colours are 24-bit ANSI (ComfyUI's own log lines are ANSI too); NO_COLOR turns them off.
"""

import os
import re

# the app's palette (comfyui/web/orrery.css)
BRASS, TEAL, VIOLET, ROSE = "#e2b45c", "#5cc8c2", "#b494f5", "#f07aa0"
INK, MUTED, FAINT, DANGER = "#ebe8f2", "#9d9ab3", "#686680", "#e5645a"
WIDTH = 78

# a sun, two orbits and three planets: ● on the outer orbit, ○ on the inner one
ART = (
    "        · · · · · · · · ·",
    "   · · ·   · · · · · ·   · · ·",
    "  ●     · ·           · ·     ·",
    " ·     ·        ✹        ·     ·",
    "  ·     · ·           · ·     ●",
    "   · · ·   · ○ · · · ·   · · ·",
    "        · · · · · · · · ·",
)
PLANETS = {(2, 2): TEAL, (4, 30): ROSE, (5, 13): VIOLET}  # (row, column): colour
ORBIT = "#807e98"  # the dots, between the app's faint and muted
# "orrery" in figlet's slant font, beside the art from its second row on
WORDMARK = (
    "  ____  _____________  _______  __",
    " / __ \\/ ___/ ___/ _ \\/ ___/ / / /",
    "/ /_/ / /  / /  /  __/ /  / /_/ /",
    "\\____/_/  /_/   \\___/_/   \\__, /",
    "                         /____/",
)
GAP = 3

NOTES: list[tuple[str, str, str]] = []  # (state, label, text): state "ok" or "warn"
_shown = False


def note(label: str, text: str, state: str = "ok") -> None:
    """A boot line: `label` in a column of its own, `text` after it; a "warn" line stands out."""
    NOTES.append((state, label, text))


def _paint(text: str, colour: str, bold: bool = False, on: bool = True) -> str:
    if not on:
        return text
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"\033[{'1;' if bold else ''}38;2;{r};{g};{b}m{text}\033[0m"


def _art_line(row: int, on: bool) -> str:
    out = []
    for col, ch in enumerate(ART[row]):
        if ch == "·":
            out.append(_paint(ch, ORBIT, on=on))
        elif ch == "✹":
            out.append(_paint(ch, BRASS, bold=True, on=on))
        elif (row, col) in PLANETS:
            out.append(_paint(ch, PLANETS[(row, col)], on=on))
        else:
            out.append(ch)
    return "".join(out)


def _wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split(" "):
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    return [*lines, line]


def render(version: str, notes=None, color: bool = True) -> str:
    """The banner as text, `notes` the boot lines (NOTES by default)."""
    notes = NOTES if notes is None else notes
    art_width = max(len(line) for line in ART)
    beside = {row + 1: _paint(text, BRASS, bold=True, on=color) for row, text in enumerate(WORDMARK)}
    beside[len(ART) - 1] = (_paint(version, INK, bold=True, on=color) + "  "
                            + _paint("prompts that remember every pick", MUTED, on=color))
    rule = _paint("─" * WIDTH, FAINT, on=color)
    lines = [rule]
    for row in range(len(ART)):
        line = _art_line(row, color)
        if row in beside:
            line += " " * (art_width - len(ART[row]) + GAP) + beside[row]
        lines.append(line)
    label_width = max((len(label) for _, label, _ in notes), default=0)
    if notes:
        lines.append("")
    for state, label, text in notes:
        mark = _paint("✦", BRASS, on=color) if state == "ok" else _paint("!", DANGER, bold=True, on=color)
        indent = 2 + 2 + label_width + 2
        for i, part in enumerate(_wrap(text, WIDTH - indent)):
            head = f"  {mark} {_paint(label.ljust(label_width), MUTED, on=color)}  " if i == 0 else " " * indent
            lines.append(head + (_paint(part, ROSE, on=color) if state == "warn" else part))
    lines.append(rule)
    return "\n".join(lines)


def show(version: str) -> None:
    """Print the banner once, in colour unless NO_COLOR is set."""
    global _shown
    if _shown:
        return
    _shown = True
    print("\n" + render(version, color=not os.environ.get("NO_COLOR")) + "\n", flush=True)


def plain(text: str) -> str:
    """The text without its ANSI colours."""
    return re.sub(r"\033\[[0-9;]*m", "", text)
