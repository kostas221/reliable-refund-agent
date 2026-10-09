"""Acceptance tests and the evaluator must know the expected outcome on their own.

If they read the backend's declarations (the state machine or the policy decision functions) to work out what
should happen, a mistake in those declarations would be repeated in the expectation and never caught.
"""

import ast

from refund_agent.policy import REPO_ROOT

INDEPENDENT_DIRS = [REPO_ROOT / "tests" / "acceptance", REPO_ROOT / "refund_agent" / "evaluation"]
FORBIDDEN_MODULES = {"refund_agent.states", "refund_agent.eligibility"}


def imported_modules(source: str) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
            modules |= {f"{node.module}.{alias.name}" for alias in node.names}
    return modules


def test_acceptance_tests_and_evaluator_do_not_read_backend_declarations():
    for directory in INDEPENDENT_DIRS:
        for path in directory.rglob("*.py") if directory.exists() else []:
            found = imported_modules(path.read_text(encoding="utf-8")) & FORBIDDEN_MODULES
            assert not found, f"{path.relative_to(REPO_ROOT)} imports {sorted(found)}"


def test_the_import_check_catches_both_import_forms():
    assert imported_modules("import refund_agent.states") >= {"refund_agent.states"}
    assert imported_modules("from refund_agent import eligibility") >= {"refund_agent.eligibility"}
    assert imported_modules("from refund_agent.states import CHECKS") >= {"refund_agent.states"}
