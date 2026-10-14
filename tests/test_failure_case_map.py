"""docs/failure-cases.md names real tests and covers every failure case of the plan."""

import ast
import re

from refund_agent.policy import REPO_ROOT

MAP = (REPO_ROOT / "docs" / "failure-cases.md").read_text(encoding="utf-8")


def test_every_named_test_exists():
    named = re.findall(r"`(tests/[\w/]+\.py)::(test_\w+)`", MAP)
    assert named
    for path, name in named:
        tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
        functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        assert name in functions, f"{path}::{name} is named in docs/failure-cases.md but does not exist"


def test_all_fifteen_failure_cases_and_twelve_acceptance_tests_are_listed():
    plan_cases, acceptance = MAP.split("## The acceptance tests of schema.md")
    assert re.findall(r"^\| (\d+) \|", plan_cases, flags=re.MULTILINE) == [str(n) for n in range(1, 16)]
    assert re.findall(r"^\| (\d+) \|", acceptance, flags=re.MULTILINE) == [str(n) for n in range(1, 13)]
