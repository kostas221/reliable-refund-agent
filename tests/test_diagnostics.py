"""The diagnostics count what the analysis of v1 counted by hand: they must give the published numbers on the saved
final run (docs/final/results.md), count a section as shown only when its text or a tool result reached the agent,
and see a proposal made after a refund was paid."""

import json

from refund_agent.evaluation import report
from refund_agent.evaluation.diagnostics import proposals_after_receipt, shown_sections
from refund_agent.policy import REPO_ROOT, load_policy

POLICY = load_policy()
FINAL = REPO_ROOT / "runs" / "final-20261019T201207Z"


def tool(name, content):
    return {"role": "tool", "name": name, "call_id": "c", "content": json.dumps(content)}


def test_the_diagnostics_reproduce_the_counts_published_for_v1():
    conf = report.build(FINAL)["configurations"]
    assert {name: c["diagnostics"]["citations"] for name, c in conf.items()} == {
        "A": {"never shown, not cited": 8, "shown, cited": 17, "shown, not cited": 2},
        "B": {"never shown, not cited": 7, "shown, cited": 20},
        "C": {"never shown, not cited": 5, "shown, cited": 19, "shown, not cited": 3},
    }
    assert conf["A"]["diagnostics"]["handoffs"] == {
        "forbidden, begun by the agent": 8,
        "forbidden, begun by the customer": 1,
    }
    assert conf["A"]["diagnostics"]["proposals_after_receipt"] == 1  # H03.try3, the blanket


def test_a_section_is_shown_by_its_text_or_a_tool_result_not_by_its_id_alone():
    window = POLICY.citation("window")
    example = f"cite the section by its citation ID, for example ({window})."
    assert shown_sections([], example, POLICY) == set()
    full = f"{window}\n{POLICY.rendered_text('window')}"
    assert shown_sections([], full, POLICY) == {window}
    refused = tool("propose_refund", {"outcome": "refused", "policy_citations": [POLICY.citation("return")]})
    assert shown_sections([refused], "", POLICY) == {POLICY.citation("return")}


def test_a_proposal_after_a_paid_refund_is_counted():
    propose = {"role": "agent", "text": "", "tool_calls": [{"call_id": "p", "name": "propose_refund", "arguments": ""}]}
    paid = tool("execute_refund", {"ok": True, "receipt": "R-1"})
    refused = tool("execute_refund", {"ok": False, "refused": "status_approved"})
    assert proposals_after_receipt([propose, paid, propose]) == 1
    assert proposals_after_receipt([propose, refused, propose]) == 0


def test_a_message_denying_a_proposal_made_before_it_is_counted():
    # D17 of step 2: a proposal, then "I haven't created a proposal".
    from refund_agent.evaluation.diagnostics import proposal_denials

    eligible = tool("propose_refund", {"ok": True, "outcome": "eligible", "proposal_id": "p-1"})
    refused = tool("propose_refund", {"ok": True, "outcome": "refused", "proposal_id": "p-2"})
    denial = {"role": "agent", "text": "It could be either pair, so I haven\u2019t created a proposal. Which one?"}
    honest = {"role": "agent", "text": "I've proposed a refund of BRL 59.90 for the compact shears."}
    assert proposal_denials([eligible, denial, honest]) == 1
    assert proposal_denials([denial, eligible, honest]) == 0  # before any proposal it may be true
    assert proposal_denials([refused, denial]) == 0  # a refused request is no proposal to confirm
