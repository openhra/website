#!/usr/bin/env python3
"""Check the public workflow contract and reject incomplete required-job results."""

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = {"linux": "ubuntu-24.04", "macos": "macos-15", "python39": "ubuntu-24.04"}
ACTIONS = {
    "checkout": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
    "node": "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",
    "python": "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
    "cache": "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(workflow):
    require(
        workflow["permissions"] == {"contents": "read"},
        "CI permissions must be read-only",
    )
    require(
        workflow["on"]
        == {
            "push": {"branches": ["develop", "main", "release/**"]},
            "pull_request": {},
            "workflow_dispatch": {},
        },
        "CI must cover pull requests and release branches without path filters",
    )
    jobs = workflow["jobs"]
    require(set(jobs) == set(JOBS) | {"required"}, "missing or unexpected required job")
    for key, runner in JOBS.items():
        job = jobs[key]
        require(
            job["name"] == "website-" + key and job["runs-on"] == runner,
            "job name or platform differs from required contract",
        )
        require(
            set(job) == {"name", "runs-on", "timeout-minutes", "steps"},
            "check jobs cannot be conditional or depend on other jobs",
        )
        expected_timeout = 30 if key == "macos" else 20
        require(
            job["timeout-minutes"] == expected_timeout,
            "check timeout must be bounded (macOS receives cold-cache headroom)",
        )
        steps = job["steps"]
        python_input = (
            {"python-version": "3.9.25"}
            if key == "python39"
            else {"python-version-file": ".python-version"}
        )
        require(
            len(steps) == 5
            and steps[:3]
            == [
                {"uses": ACTIONS["checkout"], "with": {"persist-credentials": False}},
                {
                    "uses": ACTIONS["node"],
                    "with": {"node-version-file": ".node-version"},
                },
                {"uses": ACTIONS["python"], "with": python_input},
            ]
            and steps[3].get("name") == "Restore website tool caches"
            and steps[3].get("uses") == ACTIONS["cache"]
            and steps[3].get("with", {}).get("path")
            == "node_modules\n.venv\n.cache/ruff-wheels"
            and "package-lock.json" in steps[3].get("with", {}).get("key", "")
            and "requirements-dev.txt" in steps[3].get("with", {}).get("key", "")
            and steps[4] == {"run": "scripts/ci.sh"},
            "check steps must use pinned tools and the standalone CI command",
        )
    required = jobs["required"]
    require(
        required
        == {
            "name": "website-required",
            "runs-on": "ubuntu-24.04",
            "timeout-minutes": 5,
            "needs": list(JOBS),
            "if": "${{ always() }}",
            "steps": [
                {"uses": ACTIONS["checkout"], "with": {"persist-credentials": False}},
                {
                    "uses": ACTIONS["python"],
                    "with": {"python-version-file": ".python-version"},
                },
                {
                    "run": "python3 scripts/check-ci.py --results",
                    "env": {"WEBSITE_JOB_RESULTS": "${{ toJSON(needs) }}"},
                },
            ],
        },
        "required status must inspect every job even after failure or skip",
    )
    require(
        set(workflow) == {"name", "on", "permissions", "jobs"},
        "unexpected workflow settings",
    )
    for name in (".node-version", ".python-version"):
        require(
            re.fullmatch(r"\d+\.\d+\.\d+\n", (ROOT / name).read_text()) is not None,
            "runtime must pin an exact patch version",
        )


def results(needs):
    require(
        isinstance(needs, dict) and set(needs) == set(JOBS),
        "missing or unexpected job result",
    )
    require(
        all(
            isinstance(value, dict) and value.get("result") == "success"
            for value in needs.values()
        ),
        "every required job must succeed",
    )


def selftest(workflow):
    check(workflow)
    for key in JOBS:
        mutant = copy.deepcopy(workflow)
        del mutant["jobs"][key]
        try:
            check(mutant)
        except ValueError:
            pass
        else:
            raise ValueError("missing required job was accepted")
    good = {name: {"result": "success"} for name in JOBS}
    results(good)
    for name in JOBS:
        for status in ("failure", "skipped", "cancelled", "timed_out", "pending", None):
            mutant = copy.deepcopy(good)
            mutant[name]["result"] = status
            try:
                results(mutant)
            except ValueError:
                pass
            else:
                raise ValueError("incomplete required job was accepted")
        mutant = dict(good)
        del mutant[name]
        try:
            results(mutant)
        except ValueError:
            pass
        else:
            raise ValueError("absent job result was accepted")
    ci = (ROOT / "scripts/ci.sh").read_text()
    require(
        "scripts/install-tools.sh" in ci, "CI must install locked development tools"
    )
    installer = (ROOT / "scripts/install-tools.sh").read_text()
    require("npm ci --ignore-scripts" in installer, "CI must use the npm lockfile")
    require(
        "--require-hashes -r requirements-dev.txt" in installer,
        "CI must use hashed Python requirements",
    )
    print(
        "CI contract selftest: PASS (required jobs, results and locked tool installs)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--results", action="store_true")
    args = parser.parse_args()
    try:
        # JSON is a YAML subset; no parser dependency is needed in a clean checkout.
        workflow = json.loads((ROOT / ".github/workflows/ci.yml").read_text())
        check(workflow)
        if args.selftest:
            selftest(workflow)
        if args.results:
            results(json.loads(os.environ.get("WEBSITE_JOB_RESULTS", "{}")))
        print("website CI contract: PASS")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("website CI contract: FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
