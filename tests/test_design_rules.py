"""The Gates in docs/Style.md that ruff cannot check: every dataclass in src/ is frozen and keyword-only."""

import ast

from conftest import REPO

PACKAGE = REPO / "src" / "chicago_streets"


def unfrozen_dataclasses(source):
    """The names of the classes in `source` whose @dataclass is not `frozen=True, kw_only=True`."""
    bad = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            target = call.func if call else decorator
            name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
            if name != "dataclass":
                continue
            keywords = {k.arg: k.value for k in call.keywords} if call else {}
            if not all(
                isinstance(keywords.get(k), ast.Constant) and keywords[k].value is True for k in ("frozen", "kw_only")
            ):
                bad.append(node.name)
    return bad


def test_every_dataclass_is_frozen_and_keyword_only():
    bad = [
        f"{path.relative_to(REPO)}: {name}"
        for path in PACKAGE.rglob("*.py")
        for name in unfrozen_dataclasses(path.read_text())
    ]
    assert bad == []


def test_the_dataclass_check_finds_each_form():
    source = """
import dataclasses
from dataclasses import dataclass
@dataclass
class A: pass
@dataclass(frozen=True)
class B: pass
@dataclasses.dataclass(kw_only=True)
class C: pass
@dataclass(frozen=True, kw_only=True)
class D: pass
"""
    assert unfrozen_dataclasses(source) == ["A", "B", "C"]
