import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { ESLint } from "eslint";
import * as prettier from "prettier";
import { checkInventory, inventory, packageRoot } from "./format-inventory.mjs";
import { budgets } from "./format-budgets.mjs";

const eslint = new ESLint({ cwd: packageRoot });
for (const [path, sourceType] of [
  ["plans/coverage.js", "script"],
  ["openhra/contact.js", "script"],
  ["plans/api/contact.js", "module"],
  ["scripts/example.mjs", "module"],
  ["scripts/example.cjs", "commonjs"],
]) {
  const config = await eslint.calculateConfigForFile(path);
  assert.equal(config.languageOptions.sourceType, sourceType);
}
for (const [path, source, rule] of [
  ["plans/example.js", "process.cwd();", "no-undef"],
  ["plans/api/example.js", "document.title = 'server';", "no-undef"],
  ["scripts/example.mjs", "window.alert('tool');", "no-undef"],
  ["scripts/example.mjs", "require('node:fs');", "no-undef"],
  ["plans/example.js", "console.log(missingRuntimeValue);", "no-undef"],
  [
    "plans/example.js",
    "const a = true; console.log(a ? a ? 1 : 2 : 3);",
    "no-nested-ternary",
  ],
  [
    "scripts/example.mjs",
    "/* eslint-disable no-alert */\nexport const value = 1;",
    null,
  ],
]) {
  const [result] = await eslint.lintText(source, { filePath: path });
  assert(
    result.errorCount > 0 &&
      result.messages.some((message) => message.ruleId === rule),
  );
}
for (const [path, source] of [
  ["plans/example.js", "document.title = 'browser';"],
  ["plans/api/example.js", "export default () => process.cwd();"],
  ["scripts/example.mjs", "export const value = process.cwd();"],
]) {
  const [result] = await eslint.lintText(source, { filePath: path });
  assert.equal(result.errorCount, 0);
}
assert.deepEqual(
  await prettier.resolveConfig(join(packageRoot, "package.json")),
  {},
);
assert.equal(await prettier.check("const a=1", { parser: "babel" }), false);
assert.equal(
  await prettier.format("One paragraph line.\nAnother paragraph line.\n", {
    parser: "markdown",
  }),
  "One paragraph line.\nAnother paragraph line.\n",
);
const baseline = await inventory();
for (const path of baseline.fixture_sources.filter((path) =>
  /\.[cm]?js$/.test(path),
)) {
  assert.equal(await eslint.isPathIgnored(resolve(packageRoot, path)), false);
}
const scratch = await mkdtemp(join(tmpdir(), "website-lint-setup-"));
const runPython = (source, args = []) =>
  execFileSync("python3", ["-B", "-c", source, ...args], {
    cwd: packageRoot,
    stdio: "pipe",
  });
try {
  const payloadRoot = join(scratch, "payloads");
  await mkdir(join(payloadRoot, "tests/fixtures"), { recursive: true });
  await cp(
    join(packageRoot, ".prettierignore"),
    join(payloadRoot, ".prettierignore"),
  );
  const payload = join(payloadRoot, "tests/fixtures/payload.json");
  const generator = join(payloadRoot, "tests/fixtures/generate.mjs");
  await writeFile(payload, '{"synthetic":true,"value":[1,2]}\n');
  await writeFile(generator, "export const value=1;\n");
  const inventoryBefore = await inventory(payloadRoot);
  assert.deepEqual(inventoryBefore.fixture_sources, [
    "tests/fixtures/generate.mjs",
  ]);
  const bytes = await readFile(payload, "utf8");
  execFileSync(
    process.execPath,
    [
      join(packageRoot, "node_modules/prettier/bin/prettier.cjs"),
      "--ignore-path",
      ".prettierignore",
      "--write",
      ".",
    ],
    { cwd: payloadRoot, stdio: "pipe" },
  );
  await checkInventory(inventoryBefore, payloadRoot);
  assert.equal(await readFile(payload, "utf8"), bytes);
  assert.equal(await readFile(generator, "utf8"), "export const value = 1;\n");
  await writeFile(payload, await prettier.format(bytes, { parser: "json" }));
  await assert.rejects(
    checkInventory(inventoryBefore, payloadRoot),
    /Protected bytes/,
  );

  const copyRoot = join(scratch, "public");
  const policy = JSON.parse(
    await readFile(join(packageRoot, "scripts/public-paths.json"), "utf8"),
  );
  for (const path of policy.files) {
    await mkdir(resolve(copyRoot, path, ".."), { recursive: true });
    await cp(resolve(packageRoot, path), resolve(copyRoot, path));
  }
  const protectedBefore = await inventory(copyRoot);
  // Format only permitted source in the disposable tree. Exempt/legal bytes stay intact.
  for (const path of policy.files) {
    const target = resolve(copyRoot, path);
    const info = await prettier.getFileInfo(target, {
      ignorePath: join(copyRoot, ".prettierignore"),
    });
    if (!info.ignored && info.inferredParser) {
      await writeFile(
        target,
        await prettier.format(await readFile(target, "utf8"), {
          filepath: target,
        }),
      );
    }
  }
  execFileSync("python3", ["-m", "ruff", "format", "--no-cache", "."], {
    cwd: copyRoot,
    stdio: "pipe",
  });
  await checkInventory(protectedBefore, copyRoot);
  // Exercise generated-table whitespace without formatting any surrounding legal prose.
  for (const [layer, pages] of [
    ["providers", ["coverage-table.html"]],
    ["premiums", ["index.html", "availability.html"]],
  ]) {
    const fragment = (
      await readFile(
        join(copyRoot, `tools/coverage-scan/default-${layer}-2026.html`),
        "utf8",
      )
    ).trim();
    const formatted = (
      await prettier.format(fragment, { parser: "html" })
    ).trim();
    assert.notEqual(formatted, fragment);
    for (const name of pages) {
      const path = join(copyRoot, "plans", name);
      const page = await readFile(path, "utf8");
      assert(page.includes(fragment));
      await writeFile(path, page.replace(fragment, formatted));
    }
  }
  const syntheticPolicy = join(scratch, "synthetic-policy");
  await writeFile(syntheticPolicy, "SyntheticLintSetup" + "BlockedTerm42\n");
  const gateOutput = execFileSync(join(copyRoot, "tools/gate.sh"), ["--full"], {
    cwd: copyRoot,
    env: {
      ...process.env,
      OPENPLANS_DENYLIST_FILE: syntheticPolicy,
      PYTHONDONTWRITEBYTECODE: "1",
    },
    stdio: "pipe",
    encoding: "utf8",
  });
  assert.match(gateOutput, /\nPASS\n$/);
  console.log("formatted website gate: PASS");
  runPython(
    `import importlib.util, sys
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('coverage_ui', root / 'tools/coverage-ui-check/check.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.check(root)
module.negatives(root)
print('formatted equivalent: PASS')`,
    [copyRoot],
  );
  // Raw formatter output for exempt files must also preserve the individual safety checks.
  const reader = await prettier.format(
    await readFile(join(packageRoot, "plans/coverage.js"), "utf8"),
    { parser: "babel" },
  );
  const css = await prettier.format(
    await readFile(join(packageRoot, "plans/style.css"), "utf8"),
    { parser: "css" },
  );
  await writeFile(join(scratch, "reader.js"), reader);
  await writeFile(join(scratch, "style.css"), css);
  runPython(
    `import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('coverage_ui', 'tools/coverage-ui-check/check.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.reader_safety(Path(sys.argv[1]).read_text()); m.coverage_css(Path(sys.argv[2]).read_text())`,
    [join(scratch, "reader.js"), join(scratch, "style.css")],
  );
  runPython(
    `import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from public_paths import artifact_files, public_paths
root = Path(sys.argv[1])
artifact_files(root)
(root / 'node_modules').mkdir()
(root / 'node_modules/private-note.md').write_text('synthetic private note')
try:
    artifact_files(root)
except ValueError as exc:
    assert 'unexpected' in str(exc)
else:
    raise AssertionError('private dependency state accepted')
print('private dependency state: rejected')`,
    [copyRoot],
  );
  const ruff = spawnSync(
    "python3",
    [
      "-m",
      "ruff",
      "check",
      "--no-cache",
      "--output-format",
      "json",
      "--stdin-filename",
      "tools/synthetic.py",
      "-",
    ],
    { cwd: packageRoot, input: "import os\n", encoding: "utf8" },
  );
  assert.equal(ruff.status, 1, ruff.stderr);
  assert(JSON.parse(ruff.stdout).some((item) => item.code === "F401"));
} finally {
  await rm(scratch, { recursive: true, force: true });
}
console.log(JSON.stringify(await budgets(), null, 2));
console.log(
  `lint setup: PASS (scoped globals, stale disables, formatting, protected bytes, ${baseline.fixture_sources.length} fixture sources, formatted-equivalent safety mutants, dependency state and unused Python import)`,
);
