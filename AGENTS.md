# AGENTS.md

Guidance for agents (Claude Code, OpenCode and others) working in this repository. `CLAUDE.md` is a symlink to this file.

## What this repo is

chicago-streets is a learning project built on public Chicago data. Its first part is a live CTA (Chicago Transit Authority) bus-arrival service: FastAPI, Postgres, Redis and OpenTelemetry. Later parts are an evaluated LLM analyst and a causal study.

The project is design-first. The owner designs each part and must understand every line that lands. Agents write code to the owner's designs; they do not choose the design.

- `src/chicago_streets/`: the package.
- `tests/`: the pytest suite.
- `docs/`: how work is done here ([Workflow](docs/Workflow.md)) and how code and prose read ([Style](docs/Style.md)). Design notes in `docs/design/` are the owner's.

The repo is public. Nothing secret and nothing personal goes in it: no keys, tokens, emails, home-directory paths or details about anyone's employer.

## How work is done here

The owner writes the design. An agent turns it into a plan with a flow diagram, the owner approves the plan, and the agent implements it on a branch and opens a GitHub pull request. The owner reviews and merges. The full flow is in [Workflow](docs/Workflow.md).

## Principles

1. **The owner designs.** A design decision (a schema, an interface, a dependency, a module boundary, a new service) is the owner's. When the design does not cover something, ask, or write the options down for the owner to choose. Do not pick one and build on it.
2. **Code the owner can read.** Prefer the plain version over the clever one, small pull requests over large ones, and a standard library or a named dependency over a hand-rolled helper. A pull request explains anything a reader could not work out from the diff.
3. **No aliases for moved code.** When code moves or is renamed, update everything that uses it (callers, tests, docs) in the same change and delete the old one. No shims, re-exports, `sys.path` fallbacks or old names kept "so X keeps working": an alias is a second copy that drifts and hides who still depends on the old path.
4. **Nothing secret.** Name an environment variable or a file, never its value. Secrets for local runs live in an untracked `.env`.

## What to read for the task

Read only what the task needs:

- **Planning or implementing a design**: [Workflow](docs/Workflow.md) and the owner's design note.
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
uv run mypy                               # types, src/ only, strict
uv run pre-commit install                 # once per clone: the checks above as commit and push hooks
```

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
