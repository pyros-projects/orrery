from pathlib import Path

from orrery.dsl import expand
from orrery.home import Home
from orrery.importer import plan_import, run_import


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_names_are_cleaned_and_references_follow_them(tmp_path, home):
    src = tmp_path / "wildcards"
    write(src, "80s-pack/Women/daily-clothing.txt", "# 80s clothes\r\nleg warmers\r\nshoulder pads\r\n")
    write(src, "80s-pack/combined.txt", "{|neon }__80s-pack/Women/daily-clothing__, big hair\n")
    plan = plan_import(src, set())
    assert sorted(plan.libraries) == ["80s_pack/Women/daily_clothing", "80s_pack/combined"]
    assert plan.libraries["80s_pack/combined"] == ["{|neon }__80s_pack/Women/daily_clothing__, big hair"]
    run_import(Home(home), plan)
    text = expand("__80s_pack/combined__", 1, Home(home).libraries()).text
    assert text.endswith(", big hair") and "__" not in text


def test_a_folder_prefix_moves_the_references_along(tmp_path):
    src = tmp_path / "wildcards"
    write(src, "colors.txt", "red\n")
    write(src, "outfit.txt", "a __colors__ coat\n")
    plan = plan_import(src, set(), into="dp")
    assert plan.libraries["dp/outfit"] == ["a __dp/colors__ coat"]


def test_readmes_duplicates_empties_and_existing_names_are_skipped(tmp_path):
    src = tmp_path / "wildcards"
    write(src, "a/animals.txt", "fox\nowl\n")
    write(src, "b/animals.txt", "fox\nowl\n")
    write(src, "Readme-Textual_Inversion.txt", "how to use\n")
    write(src, "empty.txt", "# nothing\n")
    write(src, "style.txt", "linocut\n")
    plan = plan_import(src, {"style"})
    assert sorted(plan.libraries) == ["a/animals"]
    reasons = sorted(reason.split(" ")[0] for _, reason in plan.skipped)
    assert reasons == ["duplicate", "empty", "exists", "readme"]


def test_merge_turns_a_folder_of_single_prompts_into_one_library(tmp_path):
    src = tmp_path / "civitai"
    for i, prompt in enumerate(["an elf in a forest", "a robot at dawn", "an elf in a forest"]):
        write(src, f"civitai-prompt-{i}.txt", prompt)
    plan = plan_import(src, set(), merge="civitai/prompts")
    assert plan.libraries == {"civitai/prompts": ["an elf in a forest", "a robot at dawn"]}
