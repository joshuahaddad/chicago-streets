#!/usr/bin/env python3
"""PreToolUse hook: block git commit, push and merge that skip the git hooks (--no-verify, commit's -n)."""

import sys

from _bash import block, command_of, lead, program, segments

GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
COMMIT_VALUE = set("mFcCt")
COMMIT_ATTACHED_VALUE_ONLY = set("Su")


def short_flags(token):
    """(whether the cluster holds -n, whether the next token is a value) for a commit short option."""
    for n, char in enumerate(token[1:], 1):
        if char == "n":
            return True, False
        if char in COMMIT_ATTACHED_VALUE_ONLY:
            return False, False
        if char in COMMIT_VALUE:
            return False, n == len(token) - 1
    return False, False


def skips_hooks(tokens):
    tokens = lead(tokens)[1]
    if not tokens or program(tokens[0]) != "git":
        return False
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in GLOBAL_WITH_VALUE else 1
    if i >= len(tokens) or tokens[i] not in ("commit", "push", "merge"):
        return False
    sub, skip = tokens[i], False
    for arg in tokens[i + 1 :]:
        if skip:
            skip = False
        elif arg == "--":
            return False
        elif arg == "--no-verify":
            return True
        elif sub == "commit" and arg[:1] == "-" and arg[:2] != "--":
            short, skip = short_flags(arg)
            if short:
                return True
    return False


def main():
    command = command_of(sys.stdin.read())
    if command and any(skips_hooks(s) for s in segments(command) or []):
        block("no-verify: git commit, push and merge must not skip the git hooks. Fix what they report instead.")


main()
