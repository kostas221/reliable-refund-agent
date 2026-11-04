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


def test_the_checks_of_2026_10_23_are_counted_where_they_acted():
    # How often the question brake held a call, the selection check refused a proposal, and the handoff check refused
    # a yes it could not pair with an offer: the next run shows whether each acted, and a repeated refusal of the
    # selection in one conversation shows a loop.
    from refund_agent.evaluation.diagnostics import checks_acted, summarize
    from refund_agent.refunds import YES_WITHOUT_OFFER

    held = tool("propose_refund", {"ok": False, "not_run": "question_to_customer", "explanation": "Not run"})
    unnamed = tool("propose_refund", {"ok": False, "refused": "units_named", "explanation": "..."})
    yes = tool("request_handoff", {"ok": False, "refused": "handoff_reason", "explanation": f"{YES_WITHOUT_OFFER}."})
    other = tool("request_handoff", {"ok": False, "refused": "handoff_reason", "explanation": "that message does not"})
    counted = checks_acted([held, unnamed, unnamed, yes, other])
    assert counted == {
        "calls held after a question": 1,
        "proposals refused, the customer's words do not say which": 2,
        "handoffs refused, a yes to no offer in view": 1,
        "handoffs refused, other reasons": 1,
    }
    per_try = [{"citations": {}, "handoffs": {}, "proposals_after_receipt": 0, "checks_acted": counted}]
    assert summarize(per_try)["checks_acted"]["conversations with the selection refused twice or more"] == 1


def test_a_citation_only_the_fact_line_gave_is_counted_apart():
    # Review of the model comparison, 2026-10-24: the fact line's citations must not pass for the model's own.
    from refund_agent.evaluation.diagnostics import of_try
    from refund_agent.scenarios import load_split

    d20 = next(s for s in load_split("development") if s.id == "D20")
    remaining = POLICY.citation("remaining")
    listed = tool("list_my_orders", {"orders": [], "policy_citation": remaining})
    model = {"role": "agent", "text": "Both items were refunded, receipt R-H10-0001 (refund-policy/v2/payout)."}
    line = {"role": "agent", "text": f"... cannot be refunded again ({remaining}).", "fact_line": True}
    items = {f"cites:{remaining}": "passed"}
    found = of_try({"messages": [listed, model, line]}, set(), items, d20, "", POLICY)
    assert found["citations"] == {"shown, cited only by the fact line": 1}
    cited = {"role": "agent", "text": f"Refunded, receipt R-H10-0001; not again ({remaining})."}
    assert of_try({"messages": [listed, cited]}, set(), items, d20, "", POLICY)["citations"] == {"shown, cited": 1}


def test_a_conversation_that_fails_on_citations_alone_is_counted():
    # Decided before the final evaluation of v1.1 (docs/held-out-v1.1/quality-targets.md): the report shows apart the
    # conversations whose only failed items are required citations, so a citation the author required where a correct
    # agent need not cite (H30, set-aside.md section 11) is seen for what it is.
    from refund_agent.evaluation.diagnostics import of_try, summarize
    from refund_agent.scenarios import load_split

    d20 = next(s for s in load_split("development") if s.id == "D20")
    remaining = f"cites:{POLICY.citation('remaining')}"
    alone = of_try({"messages": []}, {remaining}, {remaining: "failed"}, d20, "", POLICY)
    besides = of_try({"messages": []}, {remaining, "handoff"}, {remaining: "failed"}, d20, "", POLICY)
    passed = of_try({"messages": []}, set(), {remaining: "passed"}, d20, "", POLICY)
    assert (alone["failed_on_citations_alone"], besides["failed_on_citations_alone"]) == (True, False)
    assert passed["failed_on_citations_alone"] is False
    assert summarize([alone, besides, passed])["failed_on_citations_alone"] == 1


def test_the_simulators_reminders_are_counted_apart():
    # Review of 2026-10-27: a reminder changes the conversation's course, and a second [END] read as an ordinary end.
    from refund_agent.evaluation.diagnostics import of_try, summarize
    from refund_agent.scenarios import load_split

    d40 = next(s for s in load_split("development") if s.id == "D40")
    first = of_try({"messages": [], "simulator_reminders": ["answered", "ended"]}, set(), {}, d40, "", POLICY)
    second = of_try({"messages": [], "simulator_reminders": ["answered"]}, set(), {}, d40, "", POLICY)
    older = of_try({"messages": []}, set(), {}, d40, "", POLICY)  # saved before reminders existed
    assert summarize([first, second, older])["simulator_reminders"] == {"answered": 2, "ended": 1}


def test_a_refused_yes_and_a_card_turned_down_are_counted_from_the_conversation():
    # Review of 2026-10-28: signals of the process that need no reading, counted per conversation. A yes the backend
    # refused, for a person or for the shipping charge, means the customer is asked again; a card declined or cancelled
    # with its button was not wanted. Neither is a fault by itself: the reader marks the faults (audit.PROCESS).
    from refund_agent.evaluation.diagnostics import of_try, summarize
    from refund_agent.refunds import YES_WITHOUT_OFFER
    from refund_agent.scenarios import load_split

    d40 = next(s for s in load_split("development") if s.id == "D40")
    shipping_yes = "that message is a yes, but your message just before it offers no staff member for the shipping"
    refused = [
        tool("request_handoff", {"ok": False, "refused": "handoff_reason", "explanation": f"{YES_WITHOUT_OFFER}."}),
        tool("request_handoff", {"ok": False, "refused": "handoff_reason", "explanation": f"{shipping_yes} charge."}),
        tool("request_handoff", {"ok": False, "refused": "handoff_reason", "explanation": "that message is not a yes"}),
    ]
    events = [
        {"role": "event", "text": "declined", "notice_id": "notice-decline-prop-1"},
        {"role": "event", "text": "cancelled", "notice_id": "notice-cancel-prop-2"},
        {"role": "event", "text": "approved", "notice_id": "notice-approved-prop-3"},
    ]
    first = of_try({"messages": [*refused, *events]}, set(), {}, d40, "", POLICY)
    assert first["process"] == {"a customer's yes refused": 2, "cards declined or cancelled with the button": 2}
    quiet = of_try({"messages": []}, set(), {}, d40, "", POLICY)
    assert summarize([first, quiet, {"citations": {}, "handoffs": {}, "proposals_after_receipt": 0}])["process"] == {
        "a customer's yes refused": {"times": 2, "conversations": 1},
        "cards declined or cancelled with the button": {"times": 2, "conversations": 1},
    }


def test_quality_citations_are_counted_shown_or_not():
    # The citation rule of v1.2: a quality citation never fails a conversation, and the report counts it.
    from refund_agent.evaluation.diagnostics import of_try, summarize
    from refund_agent.scenarios import load_split

    d35 = next(s for s in load_split("development") if s.id == "D35")
    quality = d35.model_copy(
        update={"expected": d35.expected.model_copy(update={"quality_cites": ("refund-policy/v2/eligible-orders",)})}
    )
    said = {"role": "agent", "text": "It is on its way (refund-policy/v2/eligible-orders)."}
    shown = of_try({"messages": [said]}, set(), {}, quality, "", POLICY)
    missed = of_try({"messages": []}, set(), {}, quality, "", POLICY)
    assert summarize([shown, missed])["quality_citations"] == {"shown": 1, "not shown": 1}


# Citations the model wrote (plan change log, 2026-11-04): instructions v11 ask for more of them, so the report shows
# how many per message, how many name no section of the run's policy, and where `exceptions` and `scope` were cited
# where the scenario lists them neither as required nor as quality. Only IDs are counted, never the words beside them.


def test_the_citations_the_model_wrote_are_counted_with_unknown_and_unlisted_ones():
    from refund_agent.evaluation.diagnostics import of_try, summarize
    from refund_agent.scenarios import load_split

    window, amount = POLICY.citation("window"), POLICY.citation("amount")
    exceptions, scope = POLICY.citation("exceptions"), POLICY.citation("scope")
    d01 = next(s for s in load_split("development") if s.id == "D01")
    expected = d01.expected.model_copy(update={"cites": (window,), "quality_cites": (amount,), "obligations": {}})
    scenario = d01.model_copy(update={"expected": expected})
    calls = [{"call_id": "c", "name": "list_my_orders", "arguments": "{}"}]
    messages = [
        tool("list_my_orders", {"orders": [], "policy_citation": scope}),  # a tool result is not the model's
        {"role": "agent", "text": "", "tool_calls": calls},  # no text: not a message to the customer
        {"role": "agent", "text": f"Too late ({window}); no exception either ({exceptions})."},
        {
            "role": "agent",
            # an ID of another policy version, and one of no section at all
            "text": f"Paid at its price ({amount}), not (refund-policy/v1/window) or (refund-policy/v2/refunds).",
        },
        {"role": "agent", "text": f"As the records show ({scope}).", "fact_line": True},  # the graph's, counted apart
        {"role": "agent", "text": f"Again, no exception ({exceptions})."},
    ]
    found = of_try({"messages": messages}, set(), {}, scenario, "", POLICY)
    assert found["citations_written"] == {"messages": 3, "citations": 6}
    assert found["unknown_citations"] == {"refund-policy/v1/window": 1, "refund-policy/v2/refunds": 1}
    assert found["unlisted_sections"] == {"exceptions": 1}  # once per conversation; window and amount are listed
    quiet = of_try({"messages": [messages[2]]}, set(), {}, scenario, "", POLICY)
    total = summarize([found, quiet, {"citations": {}, "handoffs": {}, "proposals_after_receipt": 0}])
    assert total["citations_written"] == {"messages": 4, "citations": 8}
    assert total["unknown_citations"] == {"refund-policy/v1/window": 1, "refund-policy/v2/refunds": 1}
    assert total["unlisted_sections"] == {"exceptions": 2, "scope": 0}  # the two v11 names, shown even at zero


def test_the_citation_counts_reproduce_the_baselines_v11_is_measured_against():
    # docs/pilot/predictions.md, "v1.3, instructions v11": Sol low with v10 on D01 to D89 (joined run of 2026-11-01)
    # and on the 39 scenarios of the comparison, configuration A.
    joined = REPO_ROOT / "runs" / "pilot-20261101T163038Z-gpt-6.1-sol-low-joined"
    development = report.build(joined)["configurations"]["A"]["diagnostics"]
    assert development["citations_written"] == {"messages": 609, "citations": 919}  # 1.51 per message
    assert development["unknown_citations"] == {}
    assert (development["unlisted_sections"]["exceptions"], development["unlisted_sections"]["scope"]) == (24, 3)
    comparison = report.build(REPO_ROOT / "runs" / "comparison-v1.3-20261103T155348Z")["configurations"]
    sol = comparison["A"]["diagnostics"]
    assert sol["citations_written"] == {"messages": 261, "citations": 584}  # 2.24 per message
    assert sol["unknown_citations"] == {} == comparison["B"]["diagnostics"]["unknown_citations"]
    assert (sol["unlisted_sections"]["exceptions"], sol["unlisted_sections"]["scope"]) == (0, 0)
