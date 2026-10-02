from orrery import banner

NOTES = [("ok", "nodes", "Prompt · Log · Refs · Continue · Film · Write"),
         ("ok", "home", "/home/someone/.orrery (default)"),
         ("warn", "refmods", ("RefMod strengths are off: H3 is not as orrery expects, so every RefMod runs at 1 "
                              "and the sentence runs on long enough to wrap onto a second line"))]


def test_the_banner_shows_the_art_the_wordmark_and_the_boot_lines():
    text = banner.render("0.1.0", NOTES, color=False)
    lines = text.splitlines()
    assert lines[0] == lines[-1] == "─" * banner.WIDTH
    assert "✹" in text and "0.1.0" in text and banner.WORDMARK[1] in text
    assert "  ✦ nodes    Prompt · Log · Refs · Continue · Film · Write" in lines
    assert any(line.startswith("  ! refmods  RefMod strengths are off") for line in lines)
    assert max(len(line) for line in lines) <= banner.WIDTH  # long lines wrap


def test_colour_is_ansi_and_leaves_the_same_text():
    coloured = banner.render("0.1.0", NOTES)
    assert "\033[1;38;2;226;180;92m" in coloured  # brass, bold: the sun and the wordmark
    assert banner.plain(coloured) == banner.render("0.1.0", NOTES, color=False)


def test_show_prints_once_and_no_color_turns_colour_off(capsys, monkeypatch):
    monkeypatch.setattr(banner, "_shown", False)
    monkeypatch.setattr(banner, "NOTES", list(NOTES))
    monkeypatch.setenv("NO_COLOR", "1")
    banner.show("0.1.0")
    banner.show("0.1.0")
    out = capsys.readouterr().out
    assert out.count("0.1.0") == 1 and "\033[" not in out and "refmods" in out


def test_a_note_lands_in_the_boot_lines(monkeypatch):
    monkeypatch.setattr(banner, "NOTES", [])
    banner.note("home", "/somewhere (ORRERY_HOME)")
    assert banner.NOTES == [("ok", "home", "/somewhere (ORRERY_HOME)")]
