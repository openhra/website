"""Run the tests of `python3 -m unittest discover -s DIR -p PATTERN` in a few processes at once.

Usage: unittest_shards.py DIR PATTERN

Discover runs once and lists its test ids. The ids are dealt round-robin into shards, and each
shard runs as `python3 -m unittest <id>...` with DIR first on PYTHONPATH. The run fails unless
every shard passes, each shard runs exactly its own ids, and the shards together run exactly the
discovered count. The edge acceptance tests mostly wait on loopback servers, so three shards
finish in less than half the time of one process. GATE_TEST_JOBS sets the shard count (default 3).
"""

import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

LIST_IDS = """
import sys, unittest
suite = unittest.defaultTestLoader.discover(sys.argv[1], pattern=sys.argv[2])
def ids(s):
    if isinstance(s, unittest.TestSuite):
        return [i for t in s for i in ids(t)]
    return [s.id()]
found = ids(suite)
print("\\n".join(["== ids", *found, "== %d" % len(found)]))
"""


def fail(message):
    print("FAIL: " + message)
    sys.exit(1)


def jobs():
    value = os.environ.get("GATE_TEST_JOBS", "3")
    if not re.fullmatch(r"[1-9][0-9]*", value):
        fail(f"GATE_TEST_JOBS must be a positive whole number, got {value!r}")
    return int(value)


def discover(directory, pattern):
    result = subprocess.run(
        [sys.executable, "-c", LIST_IDS, directory, pattern],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines = result.stdout.splitlines()
    if result.returncode != 0 or "== ids" not in lines:
        fail("unittest discovery failed\n" + result.stdout)
    found = lines[lines.index("== ids") + 1 : -1]
    if lines[-1] != f"== {len(found)}":
        fail("unittest discovery output unreadable\n" + result.stdout)
    # A module that fails to import is loaded as a placeholder test, not as its tests.
    broken = [test for test in found if test.startswith("unittest.loader.")]
    if broken:
        fail("unittest discovery failed to import: " + ", ".join(broken))
    if not found:
        fail(f"no tests match {pattern} in {directory}")
    return found


def run_shard(directory, ids):
    started = time.monotonic()
    path = [os.path.abspath(directory)]
    if os.environ.get("PYTHONPATH"):
        path.append(os.environ["PYTHONPATH"])
    result = subprocess.run(
        [sys.executable, "-m", "unittest", *ids],
        check=False,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join(path)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ran = re.findall(r"^Ran (\d+) tests? in ", result.stdout, re.MULTILINE)
    ran = int(ran[-1]) if ran else 0
    return result.returncode, ran, result.stdout, time.monotonic() - started


def main(argv):
    if len(argv) != 2:
        fail("usage: unittest_shards.py DIR PATTERN")
    directory, pattern = argv
    ids = discover(directory, pattern)
    count = jobs()
    shards = [ids[i::count] for i in range(min(count, len(ids)))]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(shards)) as pool:
        results = list(pool.map(lambda shard: run_shard(directory, shard), shards))
    problems = []
    for number, (shard, (code, ran, output, seconds)) in enumerate(
        zip(shards, results), 1
    ):
        name = f"shard {number}/{len(shards)}"
        print(f"-- {directory} {name}: {ran} tests in {seconds:.1f}s")
        if code != 0:
            sys.stdout.write(output)
            problems.append(f"{name} exited {code}")
        elif ran != len(shard):
            sys.stdout.write(output)
            problems.append(f"{name} ran {ran} of its {len(shard)} tests")
    total = sum(ran for _, ran, _, _ in results)
    print(
        f"Ran {total} tests in {len(shards)} shards in {time.monotonic() - started:.1f}s"
    )
    if problems:
        fail("; ".join(problems))
    if total != len(ids):
        fail(f"the shards ran {total} tests, one discover loads {len(ids)}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
