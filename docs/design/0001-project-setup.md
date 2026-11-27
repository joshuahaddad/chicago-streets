# 0001: Project setup

## Context

Every later part of chicago-streets builds on the package layout and the checks. The setup was copied from an earlier project. This note records which parts are kept, which change, and why. The checks run in two places: pre-commit hooks on the developer's machine, and the `checks` and `gitleaks` jobs in [`checks.yml`](../../.github/workflows/checks.yml) on GitHub's runners.

Pre-commit only runs on a clone where someone ran `pre-commit install`, and a human can skip it with `git commit --no-verify`. An agent can't skip it: the `no-verify` Claude Code hook blocks that. Agents make most of the commits here, so the hooks bind them, and CI is the only check that binds everyone.

## Decisions

**Pre-commit fixes, CI checks.** At commit, `ruff format` and `ruff check --fix` (safe fixes only) rewrite the staged files. They get the staged file names, so they never edit a file outside the commit. CI runs `ruff format --check` and `ruff check` on the whole repo and changes nothing: a runner can't change your files, so it can only fail.

**pyright runs on the whole repo on every commit.** A signature change in one file breaks callers in files that aren't staged, so checking only staged files misses the error that matters. On this repo the whole run takes under a second, about the same as one file, because pyright analyses every import anyway.

**pytest runs on push and in CI**, with a 90% line-coverage floor. Coverage measures lines that ran, not cases that were tested, so it's a floor and not proof.

**gitleaks runs in both.** The pre-commit hook prevents a leak by scanning the staged changes. The CI job scans every commit in the history, which catches what skipped the hook: a `--no-verify` commit, a clone without hooks, an edit in GitHub's web editor. The repo is public, so a red CI job means the secret is already out. The response is to rotate the key; rewriting history doesn't undo it.

**The lockfile is kept honest twice.** `uv lock --check`, in pre-commit when `pyproject.toml` or `uv.lock` is staged, keeps the two files in step. Nothing compares `.venv` with the lock: a package installed by hand stays, and `uv run` doesn't remove it. CI catches that case, because the runner builds `.venv` fresh with `uv sync --locked`. Code that imports a package the lock doesn't install fails pyright there first.

**The package lives in `src/chicago_streets/`.** With the package at the repo root, the root on `sys.path` lets tests import the source folder, so files the built package leaves out (data files, undiscovered modules) still work in tests. Day to day, uv's editable install points `.venv` at the source either way. The layout matters at the first non-editable install, the Docker image in S3. Tests live in `tests/`, one file per module. Runtime config, such as the path to the Bus Tracker key file, is read from the environment or an untracked `.env`, never from the repo.

## Alternatives

- **Pre-commit checks without fixing**, as the copied setup did. It forces a second commit for formatting that a tool could do.
- **Fixers on the whole repo.** They would put unrelated edits, for example after a ruff upgrade adds a rule, into whatever commit is next.
- **pyright on staged files at commit, the whole repo on push.** It allows work-in-progress commits. But humans already have `--no-verify` for those, and agents shouldn't make broken commits.
- **No format check in CI.** Then nothing stops an unformatted file from a clone without hooks.

## Tradeoffs

Whole-repo pyright on every commit gets slower as the repo grows. Revisit if a commit takes more than a few seconds. Fixers rewriting staged files mean a commit can change code you didn't type, so read the diff after a hook runs.

## Open questions

- Before S3 ships the Docker image: what check fails CI when the built package is missing a file the code reads at runtime? Options are running the tests inside the built image, or a test that builds the wheel with `uv build` and lists its contents. A test that only looks in the editable `.venv` would pass whatever the wheel holds.
