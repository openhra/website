import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { format } from "prettier";
import { packageRoot } from "./format-inventory.mjs";

const cssMarker = "/* Static coverage reader:";
export async function budgets(root = packageRoot) {
  const rows = [];
  for (const [path, budget, parser] of [
    ["plans/coverage.js", 24 * 1024, "babel"],
    ["plans/style.css", 8 * 1024, "css"],
  ]) {
    const source = await readFile(resolve(root, path), "utf8");
    const formatted = await format(source, { parser });
    const measured = (text) => {
      if (parser !== "css") return Buffer.byteLength(text);
      assert(text.includes(cssMarker), "coverage CSS marker missing");
      return Buffer.byteLength(text.split(cssMarker)[1]);
    };
    const currentBytes = measured(source);
    assert(currentBytes <= budget, `${path}: current byte budget exceeded`);
    rows.push({
      path,
      budget,
      current_bytes: currentBytes,
      formatted_bytes: measured(formatted),
    });
  }
  return rows;
}
if (
  process.argv[1] &&
  resolve(process.argv[1]) ===
    resolve(packageRoot, "scripts/format-budgets.mjs")
) {
  console.log(JSON.stringify(await budgets(), null, 2));
}
