#!/usr/bin/env python3
"""PreToolUse hook: block `gh pr merge` unless `gh pr view` shows every check passed.

An unexpected input shape or a gh error blocks a merge (fails closed) and passes any other call.
Hook contract: https://code.claude.com/docs/en/hooks (stdin JSON `tool_input.command`, exit 2 blocks).
"""

import json
import re
import subprocess
import sys

from _bash import block, command_of, lead, program, segments

PASSED = {"SUCCESS", "NEUTRAL", "SKIPPED"}
MENTIONS_MERGE = re.compile(r"\bgh\b.*\bpr\b.*\bmerge\b", re.S)


def run_checks(args):
    """(exit code, stdout, stderr) of `gh pr view ARGS --json statusCheckRollup`: the one seam tests replace."""
    done = subprocess.run(
        ["gh", "pr", "view", *args, "--json", "statusCheckRollup"], capture_output=True, text=True, timeout=60
    )
    return done.returncode, done.stdout, done.stderr


def unfinished_or_failed(row):
    """The check's name if it did not pass, else None. A CheckRun has status/conclusion, a StatusContext state."""
    name = row.get("name") or row.get("context") or "?"
    if row.get("__typename") == "StatusContext":
        return None if row.get("state") == "SUCCESS" else name
    return None if row.get("status") == "COMPLETED" and row.get("conclusion") in PASSED else name


MERGE_OPTIONS_WITH_VALUE = {
    "-b",
    "--body",
    "-F",
    "--body-file",
    "-t",
    "--subject",
    "-A",
    "--author-email",
    "--match-head-commit",
}


def merge_args(tokens):
    """`-R repo` (if any, from before or after `pr`) plus the arguments after `gh pr merge`, or None."""
    tokens = lead(tokens)[1]
    if not tokens or program(tokens[0]) != "gh":
        return None
    repo, i = [], 1
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] in ("-R", "--repo") and i + 1 < len(tokens):
            repo, i = ["-R", tokens[i + 1]], i + 2
        elif tokens[i].startswith("--repo="):
            repo, i = ["-R", tokens[i][7:]], i + 1
        else:
            i += 1
    if tokens[i : i + 2] != ["pr", "merge"]:
        return None
    return repo + tokens[i + 2 :]


def selector(args):
    """What `gh pr checks` needs to find the same PR: -R/--repo and the first positional."""
    repo, pr, i = [], [], 0
    while i < len(args):
        if args[i] in ("-R", "--repo") and i + 1 < len(args):
            repo, i = ["-R", args[i + 1]], i + 1
        elif args[i].startswith("--repo="):
            repo = ["-R", args[i][7:]]
        elif args[i] in MERGE_OPTIONS_WITH_VALUE:
            i += 1
        elif not args[i].startswith("-") and not pr:
            pr = [args[i]]
        i += 1
    return repo + pr


def check(raw):
    """The reason to block this tool call, or None."""
    command = command_of(raw)
    all_segments = None if command is None else segments(command)
    if all_segments is None:
        return "merge-on-red: unreadable hook input that mentions a merge" if MENTIONS_MERGE.search(raw) else None
    merges = [a for a in map(merge_args, all_segments) if a is not None]
    if not merges or all("--disable-auto" in a for a in merges):
        return None
    if any(s[0] == "cd" or any(t.startswith("GH_REPO=") for t in s) for s in all_segments):
        return (
            "merge-on-red: a cd or GH_REPO in the same command may point gh at another repo; "
            "run `gh pr merge -R OWNER/REPO N` alone"
        )
    for args in merges:
        try:
            code, out, err = run_checks(selector(args))
            if code != 0:
                return (
                    f"merge-on-red: `gh pr view` failed (exit {code}): {err.strip()}; cannot confirm the checks passed."
                )
            rows = json.loads(out)["statusCheckRollup"]
            bad = [n for n in map(unfinished_or_failed, rows) if n]
        except Exception as error:
            return f"merge-on-red: could not read the checks ({error!r}); cannot confirm they passed."
        if not rows:
            return "merge-on-red: no checks reported for this PR; wait for them to be created."
        if bad:
            return f"merge-on-red: not merging while these checks are failing or unfinished: {', '.join(bad)}."
    return None


if __name__ == "__main__":
    raw = sys.stdin.buffer.read().decode(errors="replace")
    try:
        reason = check(raw)
    except Exception as error:
        reason = f"merge-on-red: hook failed ({error!r})" if "merge" in raw else None
    if reason:
        block(reason)
