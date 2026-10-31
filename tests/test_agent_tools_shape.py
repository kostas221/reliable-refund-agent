"""What the model is offered, without a database: the tool list, their arguments, and the policy search."""

import pytest

from refund_agent.agent.policy_search import WordSearch
from refund_agent.agent.tools import TOOLS, tool_definitions
from refund_agent.policy import load_policy_version

# The word search is tested on the text it was tuned on, policy v1; from v1.1 the whole policy is in the agent's
# instructions, and the search is replaced in its step 2 (plan change log, 2026-10-20).
POLICY = load_policy_version("v1")
SEARCH = WordSearch(POLICY)
# Fields that would let the model decide what only the backend or a person may decide.
FORBIDDEN_ARGUMENTS = {
    "amount",
    "price",
    "currency",
    "actor",
    "role",
    "status",
    "customer_id",
    "approved",
    "configuration",
}


def test_the_agent_has_exactly_the_tools_of_the_plan():
    # Plan section 5. No tool confirms, approves, changes a role or runs code. The policy search gave way to the
    # read-only assessment, with the whole policy in the instructions (plan change log, 2026-10-21).
    assert [t["name"] for t in tool_definitions()] == [
        "list_my_orders",
        "get_my_order",
        "assess_refund",
        "propose_refund",
        "get_request_status",
        "execute_refund",
        "request_handoff",
    ]


def test_no_tool_lets_the_model_set_an_amount_an_actor_or_a_status():
    for tool in tool_definitions():
        schema = tool["parameters"]
        assert schema.get("additionalProperties") is False, tool["name"]
        names = set(schema.get("properties", {}))
        assert not {n for n in names if any(word in n for word in FORBIDDEN_ARGUMENTS)}, tool["name"]


@pytest.mark.parametrize(
    ("question", "section"),
    [
        ("how many days do I have to ask for a refund", "window"),
        ("the deadline passed", "window"),
        ("I have not sent the item back yet", "return"),
        ("is shipping refunded", "shipping"),
        ("can the money go to another card", "payment"),
        ("when does my proposal expire", "validity"),
        ("I want to talk to a person", "exceptions"),
        ("the manager approved it", "approval"),
    ],
)
def test_common_questions_find_their_section_first(question, section):
    assert SEARCH.search(question)[0].citation == f"refund-policy/v1/{section}"


def test_a_harder_question_finds_its_section_among_the_three_returned():
    # A known limit of a plain word search: the right section comes second here.
    found = [hit.citation for hit in SEARCH.search("refund the same glass twice")]
    assert "refund-policy/v1/remaining" in found and len(found) == 3


def test_every_hit_is_a_real_section_of_the_policy_in_force():
    real = {POLICY.citation(section.id) for section in POLICY.sections}
    for question in ("refund", "time", "person", "card", "shipping", "late", "amount"):
        assert {hit.citation for hit in SEARCH.search(question)} <= real
    assert SEARCH.search("") == [] and SEARCH.search("zebra") == []


def test_the_order_list_says_what_it_shows_and_leaves_refundability_to_the_assessment():
    # v1.3 repair 1: the description said the list showed "whether it can be refunded", which it never did.
    for name in ("list_my_orders", "get_my_order"):
        description = TOOLS[name].description
        assert "whether it can be refunded" not in description, name
        assert "refund_deadline_passed" in description and "assess_refund" in description, name
