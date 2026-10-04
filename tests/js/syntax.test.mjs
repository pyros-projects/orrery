// Every web file parses as the browser loads it, an ES module (#236): the other tests import only some of them, and
// one broken string in help.js kept the whole app from mounting (#234).
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = fileURLToPath(new URL("../../comfyui/web/", import.meta.url));
const FILES = ["", "app/"].flatMap((dir) => readdirSync(join(WEB, dir)).filter((f) => f.endsWith(".js")).map((f) => dir + f));

test("every web file parses", () => {
  const scratch = mkdtempSync(join(tmpdir(), "orrery-syntax-"));
  try {
    for (const file of FILES) {
      const copy = join(scratch, `${file.replace("/", "_")}.mjs`);  // .mjs: parsed as a module
      copyFileSync(join(WEB, file), copy);
      try {
        execFileSync(process.execPath, ["--check", copy], { stdio: "pipe" });
      } catch (err) {
        assert.fail(`${file} does not parse:\n${String(err.stderr).trim()}`);
      }
    }
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
  assert.ok(FILES.includes("app/help.js") && FILES.includes("orrery.js"));
});
