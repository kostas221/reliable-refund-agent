"""The author package of v1.2 (docs/held-out-v1.2/author-package.md) agrees with the system it describes and leaks
nothing of the project's history: the policy word for word, the agent's tools, the criteria and forbidden events of
the evaluator, a format that parses, and no scenario ID of the development or earlier held-out sets."""

import re
import tomllib

from refund_agent.agent.tools import TOOLS
from refund_agent.policy import REPO_ROOT, load_policy
from refund_agent.scenarios import COMMUNICATION, FORBIDDEN, GLOBAL_FORBIDDEN

PACKAGE = (REPO_ROOT / "docs" / "held-out-v1.2" / "author-package.md").read_text(encoding="utf-8")


def flat(text: str) -> str:
    return " ".join(text.split())


def test_the_policy_is_given_word_for_word_under_each_citation_id():
    policy = load_policy()
    said = flat(PACKAGE)
    for section in policy.sections:
        entry = f"### {section.title} `{policy.citation(section.id)}` {flat(policy.rendered_text(section.id))}"
        assert entry in said, section.id


def test_the_tools_criteria_and_events_are_the_systems():
    tools = set(re.findall(r"^\| `([a-z_]+)` \|", PACKAGE, re.MULTILINE))
    # Forbidden events in every scenario are said in words; the table lists the ones a scenario may add.
    assert tools == set(TOOLS) | set(COMMUNICATION) | (set(FORBIDDEN) - set(GLOBAL_FORBIDDEN))


def test_the_format_parses_and_asks_for_the_fields_of_the_rule():
    (block,) = re.findall(r"```toml\n(.*?)```", PACKAGE, re.DOTALL)
    candidate = tomllib.loads(block)
    assert candidate["novel"] is False
    assert {"cites", "quality_cites", "obligations"} <= set(candidate["expected"])


def test_the_composition_is_sixty_candidates_for_forty_scenarios():
    counts = [int(n) for n in re.findall(r"^\| `[a-z_]+`: [^|]+ \| (\d+) \|", PACKAGE, re.MULTILINE)]
    assert counts == [18, 15, 12, 15] and sum(counts) == 60
    assert "H101 to H160" in PACKAGE


def test_nothing_of_the_projects_history_is_named():
    assert not re.search(r"\bD[0-9]{2}\b", PACKAGE)  # a development scenario
    assert not re.search(r"\bH[0-9]{2}\b", PACKAGE)  # a scenario of an earlier held-out set
    assert "runs/" not in PACKAGE and "v1.1" not in PACKAGE


def test_the_package_says_a_handoff_the_customer_also_asked_for_may_carry_either_origin():
    # Plan change log, 2026-10-29: in a case the policy names, a handoff the customer also asked for passes both the
    # check of that case (recorded agent) and customer_asked (recorded customer), so an author who lists one origin
    # writes a scenario a correct agent can fail on the label alone.
    either = "the handoff is recorded as `agent` or as `customer`, depending on the reason the agent gives: list both"
    assert either in flat(PACKAGE)
