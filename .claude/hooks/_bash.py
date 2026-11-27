"""Shared by the PreToolUse hooks: read a Bash call from stdin and split it into simple commands."""

import json
import re
import shlex
import sys
from pathlib import Path


def command_of(raw):
    """The Bash command in the hook's stdin JSON, or None for any other shape."""
    try:
        command = json.loads(raw)["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return None
    return command if isinstance(command, str) else None


HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
BOUNDARY = set(" \t\n;&|()")


def strip_heredocs(command):
    """The command without heredoc bodies, whose text is data. A body with no terminator line is kept."""
    lines, out, i = command.split("\n"), [], 0
    while i < len(lines):
        out.append(lines[i])
        match = HEREDOC.search(lines[i])
        end = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == match[2]), None) if match else None
        i = i + 1 if end is None else end + 1
    return "\n".join(out)


def strip_comments(command):
    """The command without `# ...` comments: a `#` that starts a word outside quotes, up to the newline."""
    out, quote, i = [], "", 0
    while i < len(command):
        char = command[i]
        if char == "\\" and quote != "'" and i + 1 < len(command):
            out.append(command[i : i + 2])
            i += 2
            continue
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "#" and (not out or out[-1] in BOUNDARY):
            newline = command.find("\n", i)
            i = len(command) if newline == -1 else newline
            continue
        out.append(char)
        i += 1
    return "".join(out)


def segments(command):
    """The simple commands of a command line, each a token list, split on ; & | and newlines; None when
    its quotes do not balance.

    shortcut: no subshell, `$(...)` or `bash -c "..."` expansion, and a heredoc is found by its `<<WORD`
    line, so `<<` inside a quoted string with a later WORD line hides the lines between; these hooks
    bind agents that follow the rules, they are not a sandbox.
    """
    try:
        lexer = shlex.shlex(
            strip_comments(strip_heredocs(command)).replace("\n", ";"), posix=True, punctuation_chars=True
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    out = [[]]
    for token in tokens:
        if set(token) <= set(";&|()"):
            out.append([])
        else:
            out[-1].append(token)
    return [s for s in out if s]


def lead(tokens):
    """(names of the VAR=value words before the program, the tokens from the program on)."""
    env = set()
    while tokens and "=" in tokens[0] and not tokens[0].startswith("-"):
        env.add(tokens[0].split("=", 1)[0])
        tokens = tokens[1:]
    return env, tokens


def program(token):
    return Path(token).name


def block(reason):
    print(reason, file=sys.stderr)
    sys.exit(2)
