#!/usr/bin/env python3
"""Check the public workflow contract and reject incomplete required-job results."""

import argparse
import copy
import json
import os
import re
import runpy
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = {"linux": "ubuntu-24.04", "macos": "macos-15-intel", "python39": "ubuntu-24.04"}
REQUIRED_JOBS = ("linux", "python39")
ACTIONS = {
    "checkout": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
    "node": "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020",
    "python": "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
    "cache": "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
}
# The check jobs run unless the same-commit job found a passing develop run of the commit.
FULL_ONLY = "${{ needs.dedupe.outputs.full == 'true' }}"
SAME_COMMIT = "website-same-commit"
RUN_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/[0-9]+")
SAME_COMMIT_TIMING = {
    # A release pushes develop and main at once; give the develop run time to appear.
    "appear_seconds": 180,
    # Below the job's 60-minute limit, above the longest check job's 45 minutes.
    "wait_seconds": 3300,
    "poll_seconds": 30,
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
    require(
        set(jobs) == set(JOBS) | {"required", "browser", "dedupe"},
        "missing or unexpected required job",
    )
    check_browser(jobs["browser"])
    check_dedupe(jobs["dedupe"])
    for key, runner in JOBS.items():
        job = jobs[key]
        require(
            job["name"] == "website-" + key and job["runs-on"] == runner,
            "job name or platform differs from required contract",
        )
        require(
            set(job) == {"name", "runs-on", "timeout-minutes", "needs", "if", "steps"}
            and job["needs"] == ["dedupe"]
            and job["if"] == FULL_ONLY,
            "check jobs may skip only on a same-commit decision",
        )
        expected_timeout = 45 if key == "macos" else 20
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
            "needs": ["dedupe", *JOBS],
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


def check_dedupe(job):
    """The same-commit job reads workflow runs and decides; it never skips itself."""
    require(
        job
        == {
            "name": SAME_COMMIT,
            "runs-on": "ubuntu-24.04",
            "timeout-minutes": 60,
            "permissions": {"actions": "read", "contents": "read"},
            "outputs": {
                "full": "${{ steps.decide.outputs.full }}",
                "source_run": "${{ steps.decide.outputs.source_run }}",
            },
            "steps": [
                {"uses": ACTIONS["checkout"], "with": {"persist-credentials": False}},
                {
                    "uses": ACTIONS["python"],
                    "with": {"python-version-file": ".python-version"},
                },
                {
                    "id": "decide",
                    "env": {"GH_TOKEN": "${{ github.token }}"},
                    "run": "python3 scripts/check-ci.py --same-commit",
                },
            ],
        },
        "same-commit job must read runs, decide and never skip itself",
    )


def check_browser(job):
    """The real-browser job is advisory: pinned Chrome, bounded, never required.

    It stays out of website-required until it has run for about a week without
    flaky failures; then gate.sh --full runs it and this contract changes.
    """
    require(
        set(job)
        == {"name", "runs-on", "timeout-minutes", "continue-on-error", "env", "steps"}
        and job["name"] == "website-browser"
        and job["runs-on"] == "ubuntu-24.04"
        and job["continue-on-error"] is True
        and 0 < job["timeout-minutes"] <= 15,
        "browser job must be advisory, bounded and on ubuntu-24.04",
    )
    require(
        re.fullmatch(r"\d+\.\d+\.\d+\.\d+", job["env"].get("CHROME_VERSION", ""))
        is not None
        and re.fullmatch(r"[0-9a-f]{64}", job["env"].get("CHROME_SHA256", ""))
        is not None,
        "browser job must pin an exact Chrome build and its SHA-256",
    )
    steps = job["steps"]
    require(
        len(steps) == 5
        and steps[0]
        == {"uses": ACTIONS["checkout"], "with": {"persist-credentials": False}}
        and steps[1]
        == {"uses": ACTIONS["node"], "with": {"node-version-file": ".node-version"}}
        and steps[2]
        == {
            "uses": ACTIONS["python"],
            "with": {"python-version-file": ".python-version"},
        }
        and "sha256sum -c" in steps[3].get("run", "")
        and steps[4]
        .get("run", "")
        .rstrip()
        .endswith("tools/coverage-ui-check/browser-gate.sh"),
        "browser job must verify its Chrome download and run the browser wrapper",
    )


def results(needs):
    require(
        isinstance(needs, dict)
        and set(needs) == set(JOBS) | {"dedupe"}
        and all(isinstance(value, dict) for value in needs.values()),
        "missing or unexpected job result",
    )
    proof = needs["dedupe"]
    require(proof.get("result") == "success", "same-commit job must succeed")
    outputs = proof.get("outputs")
    outputs = outputs if isinstance(outputs, dict) else {}
    if outputs.get("full") == "true":
        require(
            all(needs[key].get("result") == "success" for key in REQUIRED_JOBS),
            "every required Linux job must succeed",
        )
        macos = needs["macos"].get("result")
        require(
            macos in ("success", "cancelled", "skipped"),
            "website-macos failed after running",
        )
        note = (
            "macOS checks passed."
            if macos == "success"
            else f"macOS checks were {macos}; advisory checks were unavailable."
        )
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
                stream.write(note + "\n")
        print(note)
        return "full"
    require(outputs.get("full") == "false", "same-commit job gave no decision")
    # The checks were skipped only because a passing run of this commit already exists.
    require(
        RUN_URL.fullmatch(str(outputs.get("source_run") or "")) is not None,
        "skipped checks need the URL of a passing run",
    )
    require(
        all(needs[key].get("result") == "skipped" for key in JOBS),
        "checks ran or failed in a same-commit run",
    )
    return "same-commit"


def run_decision(env):
    """Only a push to main repeats a commit: main fast-forwards to a develop commit.

    A release pushes develop and main together. Every other event and ref runs the checks.
    """
    if (
        env.get("GITHUB_EVENT_NAME") == "push"
        and env.get("GITHUB_REF") == "refs/heads/main"
    ):
        return "look"
    return "full"


def check_source_run(run, jobs, sha):
    """The develop run must be a full, passing push run of ci.yml for exactly this commit."""
    require(
        isinstance(run, dict)
        and run.get("head_sha") == sha
        and run.get("head_branch") == "develop"
        and run.get("event") == "push"
        and run.get("path") == ".github/workflows/ci.yml"
        and RUN_URL.fullmatch(str(run.get("html_url") or "")) is not None,
        "the develop run is not a push run of this commit",
    )
    require(
        run.get("status") == "completed"
        and run.get("conclusion") in ("success", "failure"),
        "the develop run of this commit did not finish: " + run["html_url"],
    )
    jobs = jobs if isinstance(jobs, list) else []
    for name in [
        SAME_COMMIT,
        *("website-" + key for key in REQUIRED_JOBS),
        "website-required",
    ]:
        matching = [
            job for job in jobs if isinstance(job, dict) and job.get("name") == name
        ]
        require(
            len(matching) == 1
            and matching[0].get("head_sha") == sha
            and matching[0].get("status") == "completed"
            and matching[0].get("conclusion") == "success",
            "the develop run has no passing " + name + " job",
        )
    macos = [
        job
        for job in jobs
        if isinstance(job, dict) and job.get("name") == "website-macos"
    ]
    require(
        len(macos) == 1
        and macos[0].get("head_sha") == sha
        and macos[0].get("status") == "completed"
        and macos[0].get("conclusion") in ("success", "cancelled", "skipped"),
        "the develop run has a failed website-macos job",
    )
    return run["html_url"]


def find_same_commit_run(env, get, sleep, now, timing=None):
    timing = timing or SAME_COMMIT_TIMING
    if run_decision(env) == "full":
        return {"full": "true", "source_run": ""}
    sha = env.get("GITHUB_SHA", "")
    repository = env.get("GITHUB_REPOSITORY", "")
    require(
        re.fullmatch(r"[0-9a-f]{40}", sha) is not None
        and re.fullmatch(r"[\w.-]+/[\w.-]+", repository) is not None,
        "GITHUB_SHA or GITHUB_REPOSITORY is missing",
    )
    start = now()
    while True:
        page = get(
            "repos/"
            + repository
            + "/actions/workflows/ci.yml/runs?head_sha="
            + sha
            + "&branch=develop&event=push&per_page=100"
        )
        runs = [
            run
            for run in (page or {}).get("workflow_runs") or []
            if run.get("head_sha") == sha
            and run.get("head_branch") == "develop"
            and run.get("event") == "push"
        ]
        elapsed = now() - start
        if not runs:
            # No develop push of this commit: main tests it itself.
            if elapsed >= timing["appear_seconds"]:
                return {"full": "true", "source_run": ""}
        else:
            latest = max(runs, key=lambda run: int(run["id"]))
            if latest.get("status") == "completed":
                jobs = get(
                    "repos/"
                    + repository
                    + "/actions/runs/"
                    + str(int(latest["id"]))
                    + "/attempts/"
                    + str(int(latest["run_attempt"]))
                    + "/jobs?per_page=100"
                )
                source = check_source_run(latest, (jobs or {}).get("jobs"), sha)
                return {"full": "false", "source_run": source}
            require(
                elapsed < timing["wait_seconds"],
                "the develop run of this commit did not finish in time: "
                + str(latest.get("html_url")),
            )
        sleep(timing["poll_seconds"])


def github_get(endpoint):
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    request = urllib.request.Request(
        api + "/" + endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + os.environ.get("GH_TOKEN", ""),
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode())
        except OSError:
            if attempt == 2:
                raise
            time.sleep(10)


def same_commit():
    result = find_same_commit_run(os.environ, github_get, time.sleep, time.monotonic)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("full={full}\nsource_run={source_run}\n".format(**result))
    if result["full"] == "true":
        note = "This run tests the commit itself."
    else:
        note = "This commit already passed in " + result["source_run"]
        note += "; the checks are skipped here."
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(note + "\n")
    print(note)


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
    browser_mutants = (
        ("continue-on-error", False),
        ("timeout-minutes", 120),
        ("env", {"CHROME_VERSION": "stable", "CHROME_SHA256": "0" * 64}),
    )
    for field, value in browser_mutants:
        mutant = copy.deepcopy(workflow)
        mutant["jobs"]["browser"][field] = value
        try:
            check(mutant)
        except ValueError:
            pass
        else:
            raise ValueError("unpinned or required browser job was accepted")
    mutant = copy.deepcopy(workflow)
    mutant["jobs"]["browser"]["steps"][3]["run"] = (
        "npx @puppeteer/browsers install chrome@stable"
    )
    try:
        check(mutant)
    except ValueError:
        pass
    else:
        raise ValueError("unverified Chrome download was accepted")
    good = {name: {"result": "success"} for name in JOBS}
    good["dedupe"] = {
        "result": "success",
        "outputs": {"full": "true", "source_run": ""},
    }
    results(good)
    cancelled = copy.deepcopy(good)
    cancelled["macos"]["result"] = "cancelled"
    require(results(cancelled) == "full", "cancelled macOS was not advisory")
    for name, status in (("macos", "failure"), ("linux", "failure")):
        mutant = copy.deepcopy(good)
        mutant[name]["result"] = status
        try:
            results(mutant)
        except ValueError:
            pass
        else:
            raise ValueError(f"failed {name} job was accepted")
    for name in JOBS:
        statuses = ("failure", "skipped", "timed_out", "pending", None)
        if name == "macos":
            statuses = ("failure", "timed_out", "pending", None)
        else:
            statuses += ("cancelled",)
        for status in statuses:
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
    for key, value in (("needs", []), ("if", "${{ github.ref != 'refs/heads/main' }}")):
        mutant = copy.deepcopy(workflow)
        mutant["jobs"]["linux"][key] = value
        try:
            check(mutant)
        except ValueError:
            pass
        else:
            raise ValueError(
                "check job skipped without a same-commit decision was accepted"
            )
    for change in (
        lambda w: w["jobs"]["required"]["needs"].remove("dedupe"),
        lambda w: w["jobs"]["dedupe"].update(permissions={"contents": "read"}),
        lambda w: w["jobs"]["macos"].update(
            {"if": "${{ github.ref != 'refs/heads/develop' }}"}
        ),
        lambda w: w["on"]["push"].update(branches=["develop", "main"]),
    ):
        mutant = copy.deepcopy(workflow)
        change(mutant)
        try:
            check(mutant)
        except ValueError:
            pass
        else:
            raise ValueError("same-commit workflow mutant was accepted")
    namespace = globals()
    proof_is_required(namespace)
    other_refs_run_full(namespace)
    # Mutate only the code above the test fixtures, which repeat each anchor.
    code, marker, fixtures = Path(__file__).read_text().partition("\nSHA = ")
    for name, before, after, prop in SAME_COMMIT_MUTANTS:
        require(code.count(before) == 1, "mutant anchor moved: " + name)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "check_ci_mutant.py"
            path.write_text(code.replace(before, after) + marker + fixtures)
            mutant = runpy.run_path(str(path), run_name="check_ci_mutant")
        try:
            prop(mutant)
        except ValueError:
            continue
        raise ValueError("planted mutant survived: " + name)
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
        "CI contract selftest: PASS (required jobs, results, same-commit runs,"
        " locked tool installs and advisory pinned browser job)"
    )


SHA = "a" * 40
SOURCE_URL = "https://github.com/openhra/website/actions/runs/7"
MAIN_PUSH = {
    "GITHUB_EVENT_NAME": "push",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_SHA": SHA,
    "GITHUB_REPOSITORY": "openhra/website",
}


def source_run(**overrides):
    run = {
        "id": 7,
        "run_attempt": 1,
        "head_sha": SHA,
        "head_branch": "develop",
        "event": "push",
        "path": ".github/workflows/ci.yml",
        "status": "completed",
        "conclusion": "success",
        "html_url": SOURCE_URL,
    }
    run.update(overrides)
    return run


def source_jobs():
    names = [
        SAME_COMMIT,
        *("website-" + key for key in REQUIRED_JOBS),
        "website-macos",
        "website-required",
    ]
    jobs = [
        {
            "id": n,
            "name": name,
            "head_sha": SHA,
            "status": "completed",
            "conclusion": "success",
        }
        for n, name in enumerate(names)
    ]
    jobs[3]["conclusion"] = "cancelled"
    return jobs


class FakeGitHub:
    """Each poll of the run list returns the next entry of `runs`; the clock is virtual."""

    def __init__(self, runs, jobs):
        self.runs, self.jobs, self.clock, self.calls = list(runs), jobs, 0, []

    def get(self, endpoint):
        self.calls.append(endpoint)
        if "/jobs?" in endpoint:
            return {"total_count": len(self.jobs), "jobs": self.jobs}
        return {
            "workflow_runs": self.runs.pop(0) if len(self.runs) > 1 else self.runs[0]
        }

    def sleep(self, seconds):
        self.clock += seconds

    def now(self):
        return self.clock


def expect_failure(message, action, *args):
    try:
        action(*args)
    except ValueError:
        return
    raise ValueError(message)


def proof_is_required(ns):
    """A run may skip its checks only with proof that the commit passed a full develop run."""

    def same(**overrides):
        needs = {
            "dedupe": {
                "result": "success",
                "outputs": {"full": "false", "source_run": SOURCE_URL},
            }
        }
        needs.update({key: {"result": "skipped"} for key in JOBS})
        needs.update(overrides)
        return needs

    require(ns["results"](same()) == "same-commit", "same-commit results were rejected")
    for url in (None, "", "https://example.invalid/runs/7"):
        needs = same()
        needs["dedupe"]["outputs"]["source_run"] = url
        expect_failure(
            "skipped checks without a run URL were accepted", ns["results"], needs
        )
    # Outputs set before a later step failed still prove nothing.
    failed = {
        "result": "failure",
        "outputs": {"full": "false", "source_run": SOURCE_URL},
    }
    expect_failure(
        "a failed same-commit job was accepted", ns["results"], same(dedupe=failed)
    )
    expect_failure(
        "a failed check was accepted in a same-commit run",
        ns["results"],
        same(linux={"result": "failure"}),
    )
    jobs = source_jobs()
    require(
        ns["check_source_run"](source_run(), jobs, SHA) == SOURCE_URL,
        "a passing develop run was rejected",
    )
    require(
        ns["check_source_run"](source_run(conclusion="failure"), jobs, SHA)
        == SOURCE_URL,
        "a develop run with cancelled macOS was rejected",
    )
    for run in (
        source_run(status="in_progress", conclusion=None),
        source_run(head_sha="b" * 40),
        source_run(head_branch="main"),
        source_run(event="workflow_dispatch"),
        source_run(path=".github/workflows/other.yml"),
    ):
        expect_failure(
            "a bad develop run was accepted", ns["check_source_run"], run, jobs, SHA
        )
    failed_macos = copy.deepcopy(jobs)
    failed_macos[3]["conclusion"] = "failure"
    expect_failure(
        "a failed macOS test was accepted as proof",
        ns["check_source_run"],
        source_run(conclusion="failure"),
        failed_macos,
        SHA,
    )
    for index, change in (
        (1, {"conclusion": "skipped"}),
        (4, {"conclusion": "failure"}),
        (0, {"head_sha": "b" * 40}),
    ):
        changed = copy.deepcopy(jobs)
        changed[index].update(change)
        expect_failure(
            "a develop run without passing checks was accepted",
            ns["check_source_run"],
            source_run(),
            changed,
            SHA,
        )
    expect_failure(
        "a missing job was accepted",
        ns["check_source_run"],
        source_run(),
        jobs[1:],
        SHA,
    )
    failed_jobs = source_jobs()
    failed_jobs[3]["conclusion"] = "failure"
    github = FakeGitHub([[source_run(conclusion="failure")]], failed_jobs)
    expect_failure(
        "a failed develop run let main skip its checks",
        ns["find_same_commit_run"],
        MAIN_PUSH,
        github.get,
        github.sleep,
        github.now,
    )
    github = FakeGitHub(
        [[source_run(status="in_progress", conclusion=None)], [source_run()]],
        source_jobs(),
    )
    require(
        ns["find_same_commit_run"](MAIN_PUSH, github.get, github.sleep, github.now)
        == {"full": "false", "source_run": SOURCE_URL}
        and github.clock > 0,
        "a pending develop run was not awaited",
    )
    github = FakeGitHub([[source_run(status="queued", conclusion=None)]], source_jobs())
    expect_failure(
        "a develop run that never finished let main skip its checks",
        ns["find_same_commit_run"],
        MAIN_PUSH,
        github.get,
        github.sleep,
        github.now,
    )


def other_refs_run_full(ns):
    """Every event and ref except a push to main runs the checks without asking GitHub."""
    for event, ref in (
        ("push", "refs/heads/develop"),
        ("push", "refs/heads/lane/x/feature"),
        ("push", "refs/heads/release/1.0"),
        ("push", "refs/heads/mainline"),
        ("push", "refs/tags/v1.0.0"),
        ("pull_request", "refs/pull/1/merge"),
        ("pull_request", "refs/heads/main"),
        ("workflow_dispatch", "refs/heads/main"),
    ):
        env = dict(MAIN_PUSH, GITHUB_EVENT_NAME=event, GITHUB_REF=ref)
        github = FakeGitHub([[source_run()]], source_jobs())
        require(
            ns["run_decision"](env) == "full"
            and ns["find_same_commit_run"](env, github.get, github.sleep, github.now)
            == {"full": "true", "source_run": ""}
            and github.calls == [],
            "a non-release ref skipped the checks: " + event + " " + ref,
        )
    require(
        ns["run_decision"](MAIN_PUSH) == "look",
        "main did not look for a same-commit run",
    )
    # A main commit that develop never ran gets the checks after a short wait.
    github = FakeGitHub([[]], source_jobs())
    require(
        ns["find_same_commit_run"](MAIN_PUSH, github.get, github.sleep, github.now)
        == {"full": "true", "source_run": ""}
        and github.clock >= SAME_COMMIT_TIMING["appear_seconds"],
        "a main commit without a develop run skipped the checks",
    )
    needs = {key: {"result": "success"} for key in JOBS}
    needs["dedupe"] = {
        "result": "success",
        "outputs": {"full": "true", "source_run": ""},
    }
    require(ns["results"](needs) == "full", "a full run was rejected")
    needs["linux"] = {"result": "skipped"}
    expect_failure("a skipped check passed a full run", ns["results"], needs)
    needs["linux"] = {"result": "success"}
    needs["macos"] = {"result": "failure"}
    expect_failure("a failed macOS test passed a full run", ns["results"], needs)


# Planted mutants: each must make proof_is_required or other_refs_run_full fail.
SAME_COMMIT_MUTANTS = (
    (
        "skipped checks accepted without a source run",
        'RUN_URL.fullmatch(str(outputs.get("source_run") or "")) is not None,',
        "True,",
        proof_is_required,
    ),
    (
        "skipped checks accepted after a failed same-commit job",
        'require(proof.get("result") == "success", "same-commit job must succeed")',
        "pass",
        proof_is_required,
    ),
    (
        "a failed macOS test accepted as proof",
        'macos[0].get("conclusion") in ("success", "cancelled", "skipped"),',
        'macos[0].get("conclusion") is not None,',
        proof_is_required,
    ),
    (
        "a develop run with skipped checks accepted as proof",
        '\n            and matching[0].get("conclusion") == "success",',
        ",",
        proof_is_required,
    ),
    (
        "develop pushes that skip the checks",
        'env.get("GITHUB_REF") == "refs/heads/main"',
        'env.get("GITHUB_REF", "").startswith("refs/heads/")',
        other_refs_run_full,
    ),
    (
        "manual and pull request runs on main that skip the checks",
        'env.get("GITHUB_EVENT_NAME") == "push"\n        and env',
        "env",
        other_refs_run_full,
    ),
    (
        "a main commit without a develop run that skips the checks",
        'return {"full": "true", "source_run": ""}\n        else:',
        'return {"full": "false", "source_run": ""}\n        else:',
        other_refs_run_full,
    ),
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--results", action="store_true")
    parser.add_argument(
        "--same-commit",
        action="store_true",
        help="decide whether this run relies on a passing develop run of the same commit",
    )
    args = parser.parse_args()
    try:
        # JSON is a YAML subset; no parser dependency is needed in a clean checkout.
        workflow = json.loads((ROOT / ".github/workflows/ci.yml").read_text())
        check(workflow)
        if args.selftest:
            selftest(workflow)
        if args.results:
            results(json.loads(os.environ.get("WEBSITE_JOB_RESULTS", "{}")))
        if args.same_commit:
            same_commit()
        print("website CI contract: PASS")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("website CI contract: FAIL: " + str(error), file=sys.stderr)
        sys.exit(1)
