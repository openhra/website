import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as prettier from "prettier";
import { checkInventory, inventory, packageRoot } from "./format-inventory.mjs";

async function selftest() {
  const policy = JSON.parse(
    await readFile(join(packageRoot, "scripts/public-paths.json"), "utf8"),
  );
  const protectedPaths = new Set(
    (await inventory()).protected_files.map(({ path }) => path),
  );
  const coveragePaths = policy.files.filter((path) =>
    path.startsWith("plans/data/coverage/"),
  );
  assert(coveragePaths.length > 0);
  for (const path of coveragePaths) assert(protectedPaths.has(path), path);
  const workflows = policy.files.filter((path) =>
    path.startsWith(".github/workflows/"),
  );
  for (const path of workflows) {
    const info = await prettier.getFileInfo(join(packageRoot, path), {
      ignorePath: join(packageRoot, ".prettierignore"),
    });
    assert(info.ignored, path);
    JSON.parse(await readFile(join(packageRoot, path), "utf8"));
  }

  const scratch = await mkdtemp(join(tmpdir(), "website-lint-enforce-"));
  try {
    const root = join(scratch, "source");
    for (const path of policy.files) {
      await mkdir(join(root, path, ".."), { recursive: true });
      await cp(join(packageRoot, path), join(root, path));
    }
    await cp(join(packageRoot, "node_modules"), join(root, "node_modules"), {
      recursive: true,
      verbatimSymlinks: true,
    });
    const before = await inventory(root);
    const formatted = spawnSync(
      process.execPath,
      [
        join(root, "node_modules/prettier/bin/prettier.cjs"),
        "--ignore-path",
        ".prettierignore",
        "--write",
        ...workflows,
      ],
      { cwd: root, encoding: "utf8" },
    );
    assert.equal(formatted.status, 0, formatted.stdout + formatted.stderr);
    await checkInventory(before, root);
    const evidence = join(root, coveragePaths[0]);
    const original = await readFile(evidence);
    await writeFile(evidence, Buffer.concat([original, Buffer.from("\n")]));
    await assert.rejects(checkInventory(before, root), /Protected bytes/);
    await writeFile(evidence, original);
    await checkInventory(before, root);

    const mutants = [
      ["plans/lint-mutant.js", "process.cwd();\n", "no-undef"],
      ["plans/api/lint-mutant.js", 'document.title = "server";\n', "no-undef"],
      ["scripts/lint-mutant.py", "import os\n", "F401"],
      [
        "scripts/lint-mutant.mjs",
        "export const synthetic=1\n",
        "Code style issues",
      ],
      [
        "plans/lint-mutant.js",
        "/* eslint-disable no-undef */\nprocess.cwd();\n",
        "no-undef",
      ],
      ["scripts/lint-mutant.py", "# noqa\n", "inline Python lint exception"],
    ];
    const rejectGate = (diagnostic) => {
      const result = spawnSync(join(root, "tools/gate.sh"), ["--full"], {
        cwd: root,
        env: { ...process.env, WEBSITE_LINT_SELFTEST_ACTIVE: "1" },
        encoding: "utf8",
      });
      assert.equal(result.status, 1, result.stdout + result.stderr);
      assert(
        (result.stdout + result.stderr).includes(diagnostic),
        result.stdout + result.stderr,
      );
    };
    for (const [path, source, diagnostic] of mutants) {
      const target = join(root, path);
      await writeFile(target, source);
      rejectGate(diagnostic);
      await rm(target);
    }
    await writeFile(join(root, "plans/lint-mutant.js"), "process.cwd();\n");
    await writeFile(
      join(root, "eslint-suppressions.json"),
      await prettier.format(
        JSON.stringify({
          "plans/lint-mutant.js": { "no-undef": { count: 1 } },
        }),
        { parser: "json" },
      ),
    );
    rejectGate("ESLint suppression baseline");
  } finally {
    await rm(scratch, { recursive: true, force: true });
  }
  console.log(
    "lint selftest: PASS (7 full-gate mutants; scoped globals, Python import, formatting, exceptions and bulk suppressions; coverage inventory and JSON workflows)",
  );
}

// Each mutant runs the full gate, so nesting the same mutations would recurse.
if (process.env.WEBSITE_LINT_SELFTEST_ACTIVE !== "1") await selftest();
