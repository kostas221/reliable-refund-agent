"""What the model is offered, without a database: the tool list, their arguments, and the policy search."""

import pytest

from refund_agent.agent.policy_search import WordSearch
from refund_agent.agent.tools import tool_definitions
from refund_agent.policy import load_policy

POLICY = load_policy()
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
    # Plan section 5. No tool confirms, approves, changes a role or runs code.
    assert [t["name"] for t in tool_definitions()] == [
        "list_my_orders",
        "get_my_order",
        "lookup_refund_policy",
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
