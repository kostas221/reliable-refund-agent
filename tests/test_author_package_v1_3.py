"""The author package of the v1.3 comparison set (docs/held-out-v1.3/author-package.md) agrees with the system and the
development set it describes, and names nothing else of the project: the policy word for word, the agent's tools,
the evaluator's criteria and events, a format that parses, Appendix A equal to the development scenarios as they are,
the coverage counts of section 1.3 recomputed, and no model, run or earlier held-out scenario."""

import importlib.util
import re
import tomllib
from collections import Counter

from refund_agent.agent.tools import TOOLS
from refund_agent.policy import REPO_ROOT, load_policy
from refund_agent.scenarios import COMMUNICATION, FORBIDDEN, GLOBAL_FORBIDDEN, load_split

PACKAGE = (REPO_ROOT / "docs" / "held-out-v1.3" / "author-package.md").read_text(encoding="utf-8")
DEVELOPMENT = load_split("development")


def flat(text: str) -> str:
    return " ".join(text.split())


def catalogue_module():
    spec = importlib.util.spec_from_file_location("catalogue", REPO_ROOT / "scripts" / "development_catalogue.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_policy_is_given_word_for_word_under_each_citation_id():
    policy = load_policy()
    said = flat(PACKAGE)
    for section in policy.sections:
        entry = f"### {section.title} `{policy.citation(section.id)}` {flat(policy.rendered_text(section.id))}"
        assert entry in said, section.id


def test_the_tools_criteria_and_events_are_the_systems():
    names = set(re.findall(r"^\| `([a-z_]+)` \|", PACKAGE, re.MULTILINE))
    assert names == set(TOOLS) | set(COMMUNICATION) | (set(FORBIDDEN) - set(GLOBAL_FORBIDDEN))


def test_the_format_parses_asks_for_the_nearest_scenario_and_has_one_clock():
    (block,) = re.findall(r"```toml\n(.*?)```", PACKAGE, re.DOTALL)
    candidate = tomllib.loads(block)
    assert candidate["nearest"] == "D13" and candidate["difference"]
    assert "now" not in candidate  # every time is relative to now, given once (fact 1 of section 5.1)
    assert {"cites", "quality_cites", "obligations"} <= set(candidate["expected"])


def test_the_composition_is_sixty_candidates_with_required_handoffs():
    counts = [int(n) for n in re.findall(r"^\| `[a-z_]+`: [^|]+ \| (\d+) \|", PACKAGE, re.MULTILINE)]
    assert counts == [18, 12, 12, 18] and sum(counts) == 60
    assert "H401 to H460" in PACKAGE and 'at least 8 of them with `handoff = "required"`' in PACKAGE


def test_appendix_a_is_the_development_set_as_it_is_now():
    module = catalogue_module()
    rows = [
        f"| {s.id} | {s.category} | {s.title} | {module.records(s)} | {module.outcome(s)} | {s.expected.handoff} | "
        for s in DEVELOPMENT
    ]
    appendix = PACKAGE.split("## Appendix A.")[1]
    assert len(re.findall(r"^\| D\d+ \|", appendix, re.MULTILINE)) == len(DEVELOPMENT) == 89
    for row in rows:
        assert row in appendix, row
    assert f"The {len(DEVELOPMENT)} situations already used" in PACKAGE


def test_the_coverage_counts_of_section_1_3_are_the_development_sets():
    def mine(s):
        return sum(1 for o in s.fixture.orders if o.customer == s.customer.id)

    counted = {
        "The customer has two orders": sum(mine(s) == 2 for s in DEVELOPMENT),
        "The customer has three or more orders": sum(mine(s) >= 3 for s in DEVELOPMENT),
        'A person must take over (`handoff = "required"`)': sum(s.expected.handoff == "required" for s in DEVELOPMENT),
        "A staff member rejects the proposal": sum(s.staff.decision == "reject" for s in DEVELOPMENT),
        "An earlier proposal expired or stopped being valid": sum(
            any(p.status in ("expired", "invalidated") for p in s.fixture.past_proposals) for s in DEVELOPMENT
        ),
        'The customer keeps a card open to ask for a change (`cards.other = "wait"`)': Counter(
            s.customer.cards.other for s in DEVELOPMENT
        )["wait"],
        "Another customer's order is in the data": sum(
            any(o.customer != s.customer.id for o in s.fixture.orders) for s in DEVELOPMENT
        ),
        "A required citation of `exceptions`": sum(
            any(c.endswith("/exceptions") for c in s.expected.cites) for s in DEVELOPMENT
        ),
        "The customer must be asked which item is meant": sum(
            "resolves_ambiguity_first" in s.expected.communication for s in DEVELOPMENT
        ),
    }
    for feature, count in counted.items():
        assert f"| {feature} | {count} |" in PACKAGE, (feature, count)


def test_the_facts_earlier_candidates_got_wrong_are_stated():
    said = flat(PACKAGE)
    for fact in (
        "Identical items of one order have one price.",
        "A unit is returned before it is refunded or proposed.",
        "Every item has a price above zero.",
        "One refund per conversation.",
        "One staff decision.",
        "A staff case ends `ineligible`.",
        "Each required citation is checked alone.",
        "the handoff is recorded as `agent` or as `customer`, depending on the reason the agent gives: list both",
    ):
        assert fact in said, fact


def test_nothing_else_of_the_project_is_named():
    outside_appendix = PACKAGE.split("## Appendix A.")[0]
    named = set(re.findall(r"\bD\d{2}\b", outside_appendix))
    assert named <= {"D13"}, named  # the format's example of `nearest` only
    assert not re.search(r"\bH(?!4[0-9]{2}\b)[0-9]{2,3}\b", PACKAGE)  # no scenario of an earlier held-out set
    for word in ("runs/", "v1.1", "v1.2", "v1.3", "Luna", "Sol", "Sonnet", "GPT", "Claude", "OpenAI", "Anthropic"):
        assert not re.search(rf"\b{re.escape(word)}\b", PACKAGE), word
