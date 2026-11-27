# AGENTS.md

Guidance for agents (Claude Code, OpenCode and others) working in this repository. `CLAUDE.md` is a symlink to this file.

## What this repo is

chicago-streets is a project built on public Chicago data. Its first part is a live CTA (Chicago Transit Authority) bus-arrival service: FastAPI, Postgres, Redis and OpenTelemetry. Later parts are an evaluated LLM analyst and a causal study.

The project is design-first. The owner designs each part and must understand every line that lands. Agents write code to the owner's designs; they do not choose the design.

- `src/chicago_streets/`: the package.
- `tests/`: the pytest suite.
- `docs/`: how code and prose read ([Style](docs/Style.md)). Design notes in `docs/design/` are the owner's.

The repo is public. Nothing secret and nothing personal goes in it: no keys, tokens, emails, home-directory paths or details about anyone's employer.

## How work is done here

Work here is interactive. The owner checks their understanding of every step before it lands, so the agent works in small steps the owner can follow. Subagents may help, for research, a review or a long check, but the session agent reports what they did and the owner still approves each step.

1. **Design.** The owner writes the design note in `docs/design/`. An agent may answer questions about it or list options, but doesn't write or change a design note unless the owner asks.
2. **Sketch the shape first.** When a change adds requests, data flows or steps, draw a mermaid `flowchart` or `sequenceDiagram` in chat before writing code, so the owner can check the shape.
3. **Build in steps the owner can follow.** A failing test that states the behaviour, then the code. Say what each step does and why. Stop when the design doesn't cover something.
4. **Pull request.** One task per branch, off `main`. Push the branch and open a pull request with `gh pr create`. Watch `gh pr checks` and fix failures on the branch. Never push to `main`, and never merge: the owner does.

## Principles

1. **The owner designs.** A design decision (a schema, an interface, a dependency, a module boundary, a new service) is the owner's. When the design does not cover something, ask, or write the options down for the owner to choose. Do not pick one and build on it.
2. **Code the owner can read.** Prefer the plain version over the clever one, small pull requests over large ones, and a standard library or a named dependency over a hand-rolled helper. A pull request explains anything a reader could not work out from the diff.
3. **No aliases for moved code.** When code moves or is renamed, update everything that uses it (callers, tests, docs) in the same change and delete the old one. No shims, re-exports, `sys.path` fallbacks or old names kept "so X keeps working": an alias is a second copy that drifts and hides who still depends on the old path.
4. **Nothing secret.** Name an environment variable or a file, never its value. Secrets for local runs live in an untracked `.env`.

## What to read for the task

Read only what the task needs:

- **Implementing a design**: the owner's design note.
- **Writing or changing code**: [Style](docs/Style.md).
- **Writing docs**: the Documentation section below.
- **Answering a question about specific code**: the code itself.

## Setup and checks

Python packages are managed with uv (`uv.lock` is committed). Add dependencies
with `uv add <pkg>`, not pip, and only those the design names.

```bash
uv sync                                   # env in .venv
uv run pytest                             # all tests
uv run pytest tests/test_package.py -k name   # a single test
uv run ruff check                         # lint (see Style)
uv run ruff format --check                # formatting
uv run pyright                            # types, src/ only
uv run pre-commit install                 # once per clone: the checks above as commit and push hooks
```

[`.github/workflows/checks.yml`](.github/workflows/checks.yml) runs on every pull request and push to `main`, on GitHub's hosted runners:

- `checks`: `uv sync --locked`, ruff, the format check, pyright and `pytest --cov`, which fails below the `fail_under` floor in `pyproject.toml`.
- `gitleaks`: every commit in the history. `.gitleaksignore` lists, by fingerprint, the findings that aren't secrets.

The pre-commit hooks run the same commands: gitleaks, `uv lock --check`, ruff and pyright on commit, and pytest on push. Actions are pinned to commits, and Dependabot proposes weekly bumps at least a week old.

Two Claude Code hooks in `.claude/settings.json` (tested in `tests/test_agent_hooks.py`) block an agent's Bash call: `no-verify` blocks skipping git hooks, and `merge-on-red` blocks `gh pr merge` unless every check passed.

## Documentation

Documentation lives in `docs/`, next to the code it describes.

1. **Group by subject, not by fact.** One page per component holds everything
   about it: summary first, detail below. Link rather than repeat, and don't
   split one subject across files.
2. **Detail lives next to the code.** A module's rules are its docstring, which
   the page links, so a change edits its own file.
3. **A behaviour change updates its page or docstring in the same PR.**
4. **Cite code by file and function or test name** (never line numbers), and link
   to code rather than paste it.
5. **State what is true at this commit.** No history ("now", "used to"); plans
   and wishes go in GitHub issues.
