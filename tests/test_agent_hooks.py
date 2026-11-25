"""Tests for the PreToolUse hooks in .claude/hooks/: each is run as a script with sample tool-call JSON on stdin."""

import json
import subprocess
import sys

import pytest
from conftest import REPO

HOOKS = REPO / ".claude" / "hooks"


def run(script, command, stdin=None):
    """(exit code, stderr) of a hook given a Bash call, or the raw `stdin`."""
    payload = stdin if stdin is not None else json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    done = subprocess.run([sys.executable, str(HOOKS / script)], input=payload, capture_output=True, text=True)
    return done.returncode, done.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m x",
        "git commit -n -m x",
        "git commit -anm x",
        "git commit -S -n -m x",
        "git commit -u -n -m x",
        "git -C /tmp/r commit -n",
        "git -c user.name=a push --no-verify origin x",
        "git merge --no-verify topic",
        "make test && git commit -m x --no-verify",
        "cd d; git push --no-verify",
        "FOO=1 git commit -n",
    ],
)
def test_no_verify_blocks(command):
    code, err = run("no-verify.py", command)
    assert code == 2 and "no-verify" in err


@pytest.mark.parametrize(
    "command",
    [
        "git log -n 5",
        "git commit -m 'never use --no-verify'",
        "git commit -m 'fix -n'",
        "git commit -mfix -a",
        "git push -n origin x",
        "git merge -n topic",
        "echo git commit --no-verify",
        "git status",
        "ls -n",
    ],
)
def test_no_verify_allows(command):
    assert run("no-verify.py", command)[0] == 0


def test_hooks_ignore_garbage_input():
    assert run("no-verify.py", "", stdin="not json")[0] == 0
    assert run("no-verify.py", "", stdin='{"tool_input": []}')[0] == 0


@pytest.fixture(scope="module")
def merge():
    import importlib.util

    spec = importlib.util.spec_from_file_location("merge_on_red", HOOKS / "merge-on-red.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS))
    spec.loader.exec_module(module)
    return module


def run_check(name, status="COMPLETED", conclusion="SUCCESS"):
    """A CheckRun as `gh pr view --json statusCheckRollup` prints it."""
    return {
        "__typename": "CheckRun",
        "completedAt": "2026-10-30T16:34:33Z",
        "conclusion": conclusion,
        "detailsUrl": "https://github.com/o/r/actions/runs/1/job/2",
        "name": name,
        "startedAt": "2026-10-30T16:34:31Z",
        "status": status,
        "workflowName": "checks",
    }


def status(context, state):
    """A commit StatusContext in the same payload."""
    return {"__typename": "StatusContext", "context": context, "state": state, "targetUrl": "https://ci"}


def checks(rows, code=0, err=""):
    return lambda args: (code, json.dumps({"statusCheckRollup": rows}), err)


def verdict(merge, monkeypatch, command, runner):
    monkeypatch.setattr(merge, "run_checks", runner)
    return merge.check(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))


def test_merge_on_red_blocks_failing_naming_it(merge, monkeypatch):
    rows = [run_check("lint"), run_check("tests", conclusion="FAILURE"), status("ci/x", "ERROR")]
    reason = verdict(merge, monkeypatch, "gh pr merge 5 --squash", checks(rows))
    assert "tests" in reason and "ci/x" in reason and "lint" not in reason


def test_merge_on_red_blocks_unfinished_missing_and_gh_errors(merge, monkeypatch):
    assert "no checks" in verdict(merge, monkeypatch, "gh pr merge 5", checks([]))
    running = run_check("x", status="IN_PROGRESS", conclusion=None)
    assert "x" in verdict(merge, monkeypatch, "gh pr merge 5", checks([running]))
    assert "y" in verdict(merge, monkeypatch, "gh pr merge 5", checks([status("y", "PENDING")]))
    assert "unknown flag" in verdict(merge, monkeypatch, "gh pr merge 5", lambda a: (1, "", "unknown flag"))
    assert verdict(merge, monkeypatch, "gh pr merge 5", lambda a: (0, "not json", ""))
    assert verdict(merge, monkeypatch, "gh pr merge 5", lambda a: (0, "{}", ""))
    assert verdict(merge, monkeypatch, "gh pr merge 5", lambda a: 1 / 0)


def test_merge_on_red_allows_green_auto_disable_and_other_commands(merge, monkeypatch):
    green = checks([run_check("a"), run_check("b", conclusion="SKIPPED"), run_check("c", conclusion="NEUTRAL")])
    assert verdict(merge, monkeypatch, "gh pr merge 5", green) is None
    assert verdict(merge, monkeypatch, "gh pr merge 5", checks([status("s", "SUCCESS")])) is None
    boom = lambda a: 1 / 0  # noqa: E731
    assert verdict(merge, monkeypatch, "gh pr merge 5 --disable-auto", boom) is None
    assert verdict(merge, monkeypatch, "gh pr view 5", boom) is None
    assert verdict(merge, monkeypatch, "echo gh pr merge", boom) is None
    assert verdict(merge, monkeypatch, "gh pr merge 5 --auto", checks([run_check("a", conclusion="FAILURE")]))


def test_merge_on_red_passes_the_pr_selector(merge, monkeypatch):
    seen = []
    verdict(merge, monkeypatch, "gh pr merge -R o/r --squash 7", lambda a: seen.append(a) or (0, "{}", ""))
    assert seen == [["-R", "o/r", "7"]]


def test_merge_on_red_unexpected_shape_fails_closed_only_for_merge(merge):
    assert merge.check("not json gh pr merge 5")
    assert merge.check('{"tool_input": {"command": 5}, "x": "gh pr merge"}')
    assert merge.check("not json at all") is None
    assert merge.check('{"tool_input": []}') is None
    assert merge.check("not json: it's high time to merge") is None


@pytest.mark.parametrize(
    "command", ["cd /tmp/other && gh pr merge 5", "GH_REPO=o/r gh pr merge 5", "GH_REPO=o/r; gh pr merge 5"]
)
def test_merge_on_red_blocks_cd_and_gh_repo_chains(merge, monkeypatch, command):
    assert "GH_REPO" in verdict(merge, monkeypatch, command, checks([run_check("a")]))


def test_settings_wire_all_hooks_through_the_project_dir():
    hooks = json.loads((REPO / ".claude" / "settings.json").read_text())["hooks"]["PreToolUse"]
    commands = [h["command"] for group in hooks for h in group["hooks"]]
    for name in ("no-verify", "merge-on-red"):
        (command,) = [c for c in commands if f"{name}.py" in c]
        assert "$CLAUDE_PROJECT_DIR" in command and (HOOKS / f"{name}.py").exists()
        assert command.startswith("test -f")  # a missing script must not exit 2, which would block Bash


@pytest.mark.parametrize(
    "command",
    [
        "gh -R o/r pr merge 1",
        "gh --repo o/r pr merge 1",
        "gh --repo=o/r pr merge 1",
        "gh pr merge 5 --body 'x y'",
        "gh pr merge",
        "gh pr merge --squash --subject s",
        'gh pr merge 5 --body "unbalanced',
    ],
)
def test_merge_on_red_catches_every_form(merge, monkeypatch, command):
    assert verdict(merge, monkeypatch, command, checks([run_check("t", conclusion="FAILURE")]))


def test_segments_tells_an_empty_command_from_unbalanced_quotes(merge):
    assert merge.segments("") == []
    assert merge.segments('gh pr merge 5 --body "unbalanced') is None


def test_merge_on_red_selector_skips_flag_values_and_keeps_repo(merge, monkeypatch):
    seen = []
    runner = lambda a: seen.append(a) or (0, "{}", "")  # noqa: E731
    verdict(merge, monkeypatch, "gh --repo=o/r pr merge --body 'x y' -t s 5", runner)
    verdict(merge, monkeypatch, "gh pr merge", runner)
    assert seen == [["-R", "o/r", "5"], []]


def test_merge_on_red_ignores_a_heredoc_commit_message(merge, monkeypatch):
    command = "git commit -m \"$(cat <<'EOF'\nnote: gh pr merge later\nEOF\n)\""
    assert verdict(merge, monkeypatch, command, lambda a: 1 / 0) is None


def test_merge_on_red_blocks_undecodable_input_that_mentions_a_merge():
    bad = b'{"tool_input": {"command": "gh pr merge 1"}} \xff'
    done = subprocess.run([sys.executable, str(HOOKS / "merge-on-red.py")], input=bad, capture_output=True)
    assert done.returncode == 2
    done = subprocess.run([sys.executable, str(HOOKS / "merge-on-red.py")], input=b"\xff ls", capture_output=True)
    assert done.returncode == 0


@pytest.mark.parametrize(
    "command",
    [
        "# skip hooks\ngit commit --no-verify -m x",
        "echo a # note\ngit commit -n -m x",
        "echo a#b; git commit -n",
        "echo 'a # b'; git commit -n",
    ],
)
def test_comments_do_not_hide_later_lines(command):
    assert run("no-verify.py", command)[0] == 2


def test_comment_hiding_does_not_work_on_the_other_hooks(merge, monkeypatch):
    red = checks([run_check("t", conclusion="FAILURE")])
    assert verdict(merge, monkeypatch, "echo a#b; gh pr merge 99999", red)
    assert verdict(merge, monkeypatch, "# note\ngh pr merge 5", red)
    assert run("no-verify.py", "git commit -m 'a # b'")[0] == 0
    assert run("no-verify.py", "git status # git commit -n")[0] == 0


@pytest.mark.parametrize(
    "command",
    [
        "cat > notes.md <<'EOF'\nIt's high time to merge\nEOF",
        "git commit -F - <<'EOF'\ngates: don't merge through red\nEOF",
        "cat <<'EOF'\ngit commit --no-verify\ngh pr merge 1\nEOF\nls",
        "cat <<-EOF\n\tgit commit -n\n\tEOF",
    ],
)
def test_heredoc_bodies_are_data(merge, monkeypatch, command):
    assert merge.check(json.dumps({"tool_input": {"command": command}})) is None
    assert run("no-verify.py", command)[0] == 0
    assert run("merge-on-red.py", command)[0] == 0


def test_a_command_after_a_heredoc_is_still_checked():
    assert run("no-verify.py", "cat <<'EOF'\nx\nEOF\ngit commit -n")[0] == 2
    assert run("no-verify.py", 'echo "a << b"\ngit commit -n')[0] == 2  # no terminator line: nothing is hidden
