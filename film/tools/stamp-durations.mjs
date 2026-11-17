// ProofFlow film: set every section file's root data-duration to its window in timing.json.
//   node tools/stamp-durations.mjs        (then node tools/sync.mjs)
// Scenes key beats to spoken words through FILM, so a new narration fit only needs the windows re-stamped.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const timing = JSON.parse(readFileSync(join(root, "timing.json"), "utf8"));
for (const section of timing.sections) {
  const file = join(root, section.file);
  const html = readFileSync(file, "utf8");
  const pattern = new RegExp(`(data-composition-id="${section.composition}"[^>]*?data-duration=")[^"]*(")`);
  if (!pattern.test(html)) {
    console.error(`stamp: ${section.file} has no root with data-composition-id="${section.composition}" and data-duration`);
    process.exitCode = 1;
    continue;
  }
  const next = html.replace(pattern, `$1${section.duration}$2`);
  if (next !== html) writeFileSync(file, next);
  console.log(`stamp: ${section.id} ${section.composition} = ${section.duration}s${next !== html ? "" : " (unchanged)"}`);
}
