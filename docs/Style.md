# Style

How code and prose in this repo should read. Agents write most of the code to the owner's designs, so the page states the decisions an agent would otherwise make by copying whichever file it opened first. The rules apply to every new change.

## Where each fact lives

A fact is stated once, where a tool or a test reads it. Other pages link to it instead of restating it.

| Fact | Lives in | Checked by |
|---|---|---|
| Line length, lint rules, complexity limit | `[tool.ruff]` in `pyproject.toml` | `uv run ruff check` |
| Type checking scope and strictness | `[tool.mypy]` in `pyproject.toml` | `uv run mypy` |
| Coverage floor | `[tool.coverage.report]` in `pyproject.toml` | `uv run pytest --cov` |
| Dependencies | `pyproject.toml`, `uv.lock` | `uv lock --check` |
| What one module does and the rules it keeps | the module's docstring | review |
| The shape gates: no namedtuple, frozen keyword-only dataclasses, subprocess only through its owner | [Gates](#gates) | `uv run ruff check`, `tests/test_design_rules.py` |
| Everything else on this page | this page | review |

Ruff, mypy and the format check pass on the code, and CI ([`checks.yml`](../.github/workflows/checks.yml)) runs them on every pull request and every push to `main`. A change that breaks one is not merged.

## Find before you write

Before you write a helper, a class, an exception or a config loader, look for the one that exists:

1. Search the package for the verb: `grep -rn "def <verb>" src/`.
2. If what you need exists only as a local copy inside another module, move it to the module it belongs in and update every caller in the same change ([AGENTS.md](../AGENTS.md) principle 3: no aliases). Don't write another copy.
3. If the standard library or a dependency the design names already does it, use that.

## Code

The base is the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). The rules below are where we differ from it or where agents most often go wrong. Anything a linter can check is in `pyproject.toml`, not here.

### Structure

- **One job per module and per class.** If you can't say what it is for in one sentence without "and", split it. A class that reads files, caches, schedules and validates is four classes.
- **A function earns its name.** A short function is fine when it names a domain idea or hides a conversion a reader would otherwise have to work out, such as `standardize_date(value: str | date) -> date`. A function that only renames or forwards another call is not: write `hashlib.sha256(data).hexdigest()` where it is needed, not `def _hash(data): return hashlib.sha256(data).hexdigest()`.
- **No leading underscore on module-level functions.** A module's public functions are named in its docstring; a helper used by one function stays inside it, or is a plain public function. Methods may be private (`_name`) when they are internal to their class.
- **Explicit over clever.** Dispatch through a fixed table (`{"name": Class}`), not by reflecting over a module's names, so a renamed or moved class fails loudly.
- **Constants at the top of the module**, named, with a comment when the value isn't obvious. A value that differs per host is a config setting, not a constant.
- **Imports at the top of the module.** An import inside a function or behind an `if` hides what a module depends on; don't write one to save start-up time or to step around a circular import (break the cycle by moving the shared name instead).
- **No work at import time.** Importing a module reads no files, opens no connections and builds no clients. The one exception is the module's logger, `logger = logging.getLogger(__name__)`, made once at the top and used throughout.
- **Pass dependencies in.** A function gets its config, clients and paths as arguments, rather than loading them itself.
- **Keep decisions apart from effects.** Decide in plain functions; run network calls, database queries and file I/O in a thin layer around them, so the decisions test without a fixture.
- **Make anything that may run twice idempotent.** A retried job or a re-run migration does nothing more the second time.

### Errors and output

- **Library code raises; only `main()` exits.** No `sys.exit` below a command's `main()`.
- **stdout is the command's output; everything else goes to stderr.** Warnings and progress go through the module's `logger` ([Logging](#logging)), never a bare `print`. A test prints nothing: ruff's `T20`, on `tests/` only, refuses it.
- **One exception hierarchy.** The package's exceptions share one base class, so a caller catches one base class without knowing which module raised.
- **Name the field in the message.** A refusal starts with the field or check that failed: `"route: 999 is not a CTA route"`.

### Logging

- **One logger per module.** Make `logger = logging.getLogger(__name__)` once at the top. Never log through the root logger (`logging.warning(...)`): its records skip the package's format.
- **Only `main()` configures logging.** Library code adds no handlers, sets no levels and never calls `logging.basicConfig`.
- **The level says what the reader must do.** `error`: an operation failed, and the command will fail or report it. `warning`: something was ignored or worked around, and the run goes on. `info`: progress a person watching a long run wants. `debug`: detail for diagnosing a fault.
- **Raise or log, not both.** Library code that raises does not also log the error: the `main()` that catches it reports it once. Use `logger.exception` only where an error is handled and not raised again, so its traceback is kept.
- **Never log a secret.** Name the key, the file or the credential, never its value. Don't log a whole config, environment, request or response, which may hold one. Log an exception from a client that holds a key by its type, not its message.
- **One line, about one thing.** Like a refusal, the message names what it is about first. Passing the arguments to the logger rather than an f-string is a ruff rule (`G`).

### Data and types

- **Structured data is a frozen, keyword-only `dataclasses.dataclass`** ([Gates](#gates)), not a `dict` passed between functions or a `namedtuple` with twenty fields. Config is a typed object read once at start-up. Data parsed from outside (an API response, a request body) is parsed into a typed object at the boundary, and the code past it works only with that object.
- **Type hints on every function in `src/`.** Ruff `ANN` requires them, and mypy checks `src/` in strict mode. `tests/` is not type-checked.
- **Builtin generics and `|`:** `list[str]`, `dict[str, int]`, `str | None`, `str | Path`, not `List`, `Optional` or `Union`. Ruff's pyupgrade rules (`UP`) enforce it.
- **The shape comes from the design.** A new schema, record or config object has its fields in the owner's design before anything is built on it.

### Comments and docstrings

- **Module docstring:** one summary sentence first, then what a user or reviewer needs about the module: its public functions or classes, its behaviour, its limits and why. History stays in git.
- **Function docstring:** Google style. A one-sentence first paragraph, then what it returns or raises, and any contract the signature can't show. Add `Args:` only for arguments whose meaning the name and type don't make clear. No `Returns: None`.
- **Comments say why**, at the line that needs it: "Log only the exception type, never the message, so a secret in it isn't written out." Not what the next line does.
- **No plan or task IDs in code.** Plans are split and deleted; code outlives them. Cite a GitHub issue (`#43`) for a temporary state, or the docs page for a lasting reason.
- **No commented-out code and no `TODO` without an issue number.**

### Tests

- **pytest**, one test file per module, the test name saying the behaviour: `test_a_late_prediction_is_dropped`.
- **Shared setup goes in `tests/conftest.py`** as a fixture. Don't write a local copy in each file.
- **Assert what a failure would need to show.** Compare whole values (`assert ran == []`), so the failure prints them.

### Gates

Three code shapes fail the checks in `src/`.

- **No namedtuple.** Ruff's `TID251` refuses `collections.namedtuple` and `typing.NamedTuple`. A namedtuple is built and unpacked by position, so adding or reordering a field silently changes what every caller gets. Use a frozen dataclass built by keyword.
- **Every dataclass is `frozen=True, kw_only=True`.** A frozen record cannot be changed by a function it is passed to, and a keyword-only one cannot get two same-typed fields swapped at a call site. `tests/test_design_rules.py` checks every `@dataclass`.
- **Programs run only through the module that owns them.** Ruff's `TID251` refuses `import subprocess` in `src/`. To call a program, make one module its owner and add that module to `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml` with a comment saying which program.

To exempt a module, add it to that list with a one-line reason, and say why in the PR. Don't loosen a check itself.

## Prose

Applies to docs, docstrings, comments, commit messages, PR descriptions and issues. The rules are a subset of [agent-style](https://github.com/yzhao062/agent-style); their IDs are given so a reviewer can cite one.

- **Don't assume the reader's context (RULE-01).** Say what a thing is before what it does, and expand an acronym on first use.
- **Cut needless words (RULE-04).** If a sentence still says the same thing without a word, drop the word.
- **Keep the actor in the sentence (RULE-02).** "The poller writes the prediction", not "the prediction is written".
- **Short sentences (RULE-12).** One idea each. Split a sentence with more than one colon or semicolon.
- **One term per thing (RULE-F).** Pick one name and use only that one. Define it once.
- **Few bullets and few dashes (RULE-A, RULE-B).** Use a list for items that are parallel; use a paragraph for an argument.
- **Sentence-case headings (RULE-G).**

## Review

A reviewer, human or agent, checks a PR against this page as well as against correctness. A review comment that cites a rule names it: "Structure: a function earns its name", or "RULE-04".
