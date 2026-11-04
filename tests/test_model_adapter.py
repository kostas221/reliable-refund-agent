"""The model adapter without a database: the scripted mock, the request log and the agent's instructions."""

import json
import re

import pytest

from refund_agent.agent.model import Call, ModelError, RecordingAdapter, Say, ScriptedModel, load_instructions
from refund_agent.agent.tools import TOOLS, tool_definitions
from refund_agent.evaluation.diagnostics import shown_sections
from refund_agent.policy import REPO_ROOT, load_policy
from refund_agent.refunds import HANDOFF_REASONS

INSTRUCTIONS = load_instructions(policy=load_policy())
TOOL_LIST = tool_definitions()


def tool_message(name, content, call_id="c1"):
    return {"role": "tool", "call_id": call_id, "name": name, "content": json.dumps(content)}


def test_the_mock_says_its_lines_in_order_and_fills_in_tool_results():
    model = ScriptedModel(
        [
            Call("propose_refund", {"order_id": "d01-o1", "unit_ids": ["d01-o1-u1"]}),
            Say("I can refund {propose_refund.amount_minor|brl} for request {propose_refund.proposal_id}."),
            Call("execute_refund", {"proposal_id": "{propose_refund.proposal_id}"}),
            Say("Done. Your receipt is {execute_refund.receipt.receipt_number}."),
        ]
    )
    messages = [{"role": "customer", "text": "Refund my mug, please."}]
    first = model.respond(INSTRUCTIONS.text, messages, TOOL_LIST)
    assert first.tool_calls == (
        {
            "call_id": "scripted-1",
            "name": "propose_refund",
            "arguments": '{"order_id": "d01-o1", "unit_ids": ["d01-o1-u1"]}',
        },
    )
    messages += [first.as_message(), tool_message("propose_refund", {"proposal_id": "prop-1", "amount_minor": 4990})]
    second = model.respond(INSTRUCTIONS.text, messages, TOOL_LIST)
    assert (second.text, second.tool_calls) == ("I can refund R$ 49,90 for request prop-1.", ())

    messages += [second.as_message(), {"role": "event", "text": "Request prop-1 was approved."}]
    third = model.respond(INSTRUCTIONS.text, messages, TOOL_LIST)
    assert json.loads(third.tool_calls[0]["arguments"]) == {"proposal_id": "prop-1"}
    messages += [third.as_message(), tool_message("execute_refund", {"receipt": {"receipt_number": "R-00000001"}})]
    assert model.respond(INSTRUCTIONS.text, messages, TOOL_LIST).text == "Done. Your receipt is R-00000001."


def test_asking_again_after_a_restart_repeats_the_same_line_and_call_id():
    model = ScriptedModel([Call("list_my_orders"), Say("Here are your orders.")])
    messages = [{"role": "customer", "text": "Hi"}]
    assert model.respond("", messages, TOOL_LIST) == model.respond("", messages, TOOL_LIST)


def test_a_script_that_does_not_fit_fails_loudly():
    with pytest.raises(ModelError, match="no line 1"):
        ScriptedModel([]).respond("", [{"role": "customer", "text": "Hi"}], TOOL_LIST)
    with pytest.raises(ModelError, match="result of propose_refund"):
        ScriptedModel([Say("{propose_refund.amount_minor|brl}")]).respond("", [], TOOL_LIST)


def test_the_log_holds_each_request_in_full(tmp_path):
    log = tmp_path / "requests.jsonl"
    model = RecordingAdapter(ScriptedModel([Call("list_my_orders")]), log)
    messages = [{"role": "customer", "text": "Hi"}]
    model.respond(INSTRUCTIONS.text, messages, TOOL_LIST)
    with pytest.raises(ModelError):
        model.respond(INSTRUCTIONS.text, [*messages, {"role": "agent", "text": "", "tool_calls": []}], TOOL_LIST)

    first, failed = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert (first["instructions"], first["instructions_sha256"]) == (INSTRUCTIONS.text, INSTRUCTIONS.sha256)
    assert first["messages"] == messages and first["tools"] == TOOL_LIST
    assert first["answer"]["tool_calls"][0]["name"] == "list_my_orders"
    assert first["answer"]["message_items"] == []  # each text item with its label, when a provider returns some
    assert first["usage"] == {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }
    assert failed["error"]["kind"] == "invalid_output"  # a failure is logged too, then raised


def test_the_instructions_name_only_real_tools_and_handoff_reasons():
    named = set(re.findall(r"`([a-z_]+)`", INSTRUCTIONS.text))
    arguments = {name for tool in TOOLS.values() for name in tool.args.model_fields}
    assert named and named <= set(TOOLS) | arguments | set(HANDOFF_REASONS)
    assert set(HANDOFF_REASONS) <= named  # every reason the backend accepts is explained to the agent
    assert INSTRUCTIONS.version == "agent-v11" and len(INSTRUCTIONS.sha256) == 64


def test_every_citation_the_instructions_quote_exists_in_their_policy():
    # An example in the instructions' own text must name a section of the policy they are loaded with.
    policy = load_policy()
    own_text = INSTRUCTIONS.text.split("The shop's refund policy,")[0]
    quoted = set(re.findall(r"refund-policy/v[0-9]+/[a-z-]+", own_text))
    assert quoted and quoted <= {policy.citation(s.id) for s in policy.sections}


# The whole policy in the instructions (v1.1, step 1)


def test_the_instructions_hold_every_section_of_the_policy_under_its_id():
    policy = load_policy()
    for section in policy.sections:
        entry = f"{policy.citation(section.id)} ({section.title})\n{policy.rendered_text(section.id).strip()}"
        assert entry in INSTRUCTIONS.text, section.id
    assert "{policy" not in INSTRUCTIONS.text  # nothing left unfilled
    assert shown_sections([], INSTRUCTIONS.text, policy) == {policy.citation(s.id) for s in policy.sections}


def test_instructions_that_include_the_policy_need_it():
    with pytest.raises(ValueError, match="agent-v11.md includes the policy"):
        load_instructions()


def test_earlier_instructions_load_as_they_were():
    v3 = load_instructions(REPO_ROOT / "prompts" / "agent-v3.md")
    assert v3.text == (REPO_ROOT / "prompts" / "agent-v3.md").read_text(encoding="utf-8")
    assert v3.sha256 == "79f5219850395d5cef092b58f09db2aa63e9239760bb1fd5950fa5fba24fdb67"  # the final run of v1


# Version 9 (plan change log, 2026-10-27): the instructions agree with the tools of the v1.2 fixes, one change each.

SAID = " ".join(INSTRUCTIONS.text.split())  # the file wraps its lines


def test_a_case_for_staff_is_handed_off_with_its_order_and_units():
    # Fix 2 (H77): the backend records the request itself when the handoff names it.
    assert "(`shop_decided`, with the order and the units: the backend records the request" in SAID


def test_the_agent_cites_the_sections_its_tool_results_and_the_shops_records_rest_on():
    # Fixes 4 and 6 give the sections in the results; H55 told what the return records show without their section.
    assert "cite the section the result gives with it" in SAID
    assert "cite the section that makes those records decide" in SAID


def test_what_the_policy_allows_after_a_refusal_is_offered_in_words_first():
    # H60 and H61 of the final evaluation of v1.1: the same proposal again, just after the customer turned it down.
    assert "say in words what the policy allows, and propose it only when the customer says they want it" in SAID
    assert "Never propose again what the customer has just turned down." in SAID


def test_the_agent_knows_it_is_told_of_the_customers_buttons():
    # Fix 3: seven times a declined request was said to wait for the customer's button.
    assert "You are told when the customer declines or cancels a card with its button" in SAID


# Version 10 (v1.3 repair 1, plan change log 2026-10-31): v9 told the agent only that an item sent later "must arrive
# first", and in H255 of v1.2's final run every agent said or implied it could then be refunded, past its deadline.


def test_an_item_sent_later_past_its_deadline_is_not_promised_a_refund_on_arrival():
    assert "If the customer will send an item later, explain that it must arrive first" in SAID
    assert (
        "if its order's refund deadline has passed (refund_deadline_passed in the order), say that a request after it "
        "arrives would be late too, and never that it can be refunded once it arrives." in SAID
    )


def test_version_10_changes_only_that_sentence():
    v9 = (REPO_ROOT / "prompts" / "agent-v9.md").read_text(encoding="utf-8")
    v10 = (REPO_ROOT / "prompts" / "agent-v10.md").read_text(encoding="utf-8")
    added = " if its order's refund deadline has passed (refund_deadline_passed in the order), say that a request "
    added += "after it arrives would be late too, and never that it can be refunded once it arrives."
    flat9, flat10 = " ".join(v9.split()), " ".join(v10.split())
    assert flat10 == flat9.replace("refund already under way.", "refund already under way;" + added, 1)


# Version 11 (plan change log, 2026-11-04): all 16 failed conversations of the v1.3 comparison failed on a required
# citation alone, in each the right words under the wrong section or none: "a staff member cannot grant an exception"
# cited under the refused rule, another customer's order refused with no section, three refusals in one answer under
# one citation. No tool result gives `exceptions` or `scope`, so v10 left the agent to find them unprompted.


def test_a_section_no_tool_result_gives_is_found_in_the_policy():
    assert (
        "When no tool result gives the section, as for a refusal you give without calling a tool, find it in the "
        "policy at the end of these instructions, where each section is under its citation ID." in SAID
    )


def test_each_item_or_request_of_one_answer_gets_its_own_section():
    assert (
        "When one answer rests on the policy for several items or requests, cite the section for each: one citation "
        "does not cover the others." in SAID
    )


def test_a_refused_exception_cites_exceptions_beside_the_rules_reason():
    assert "is refused with that rule's reason and section;" in SAID
    assert (
        "When the customer asks for an exception, or for a staff member to allow what a rule refuses, say also that a "
        "staff member cannot approve a refund the policy does not allow (refund-policy/v2/exceptions)." in SAID
    )
    assert (
        "When the customer says that another rule, such as one that sends a case to a staff member, should change a "
        "refusal, explain that a request one rule refuses does not become a staff case because of another rule "
        "(refund-policy/v2/exceptions)." in SAID
    )


def test_citing_exceptions_is_no_offer_of_a_person():
    # The section that refuses exceptions also names the cases for a person; citing it must not become a handoff.
    assert (
        "Citing (refund-policy/v2/exceptions) in a refusal neither offers a person nor makes the request a case for "
        "one." in SAID
    )


def test_an_order_that_is_not_the_customers_cites_scope():
    assert (
        "A request about an order that is not the signed-in customer's own order with this shop, such as another "
        "customer's order or a purchase from another store, is refused with the reason that the policy covers only "
        "those orders (refund-policy/v2/scope)." in SAID
    )


def test_version_11_changes_only_those_sentences():
    v10 = " ".join((REPO_ROOT / "prompts" / "agent-v10.md").read_text(encoding="utf-8").split())
    v11 = " ".join((REPO_ROOT / "prompts" / "agent-v11.md").read_text(encoding="utf-8").split())
    exceptions, scope = "(refund-policy/v2/exceptions)", "(refund-policy/v2/scope)"
    changes = [
        (
            "The whole policy is at the end of these instructions, each section under its citation ID.",
            "When no tool result gives the section, as for a refusal you give without calling a tool, find it in the "
            "policy at the end of these instructions, where each section is under its citation ID. When one answer "
            "rests on the policy for several items or requests, cite the section for each: one citation does not cover "
            "the others.",
        ),
        (
            "is refused with that rule's reason; say in words what the policy allows, and propose it only when the "
            "customer says they want it.",
            "is refused with that rule's reason and section; say in words what the policy allows, and propose it only "
            "when the customer says they want it. When the customer asks for an exception, or for a staff member to "
            "allow what a rule refuses, say also that a staff member cannot approve a refund the policy does not allow "
            f"{exceptions}. When the customer says that another rule, such as one that sends a case to a staff member, "
            "should change a refusal, explain that a request one rule refuses does not become a staff case because of "
            f"another rule {exceptions}.",
        ),
        (
            "the customer can still ask for one. Use",
            f"the customer can still ask for one. Citing {exceptions} in a refusal neither offers a person nor makes "
            "the request a case for one. Use",
        ),
        (
            "Never reveal anything about other customers.",
            "Never reveal anything about other customers. A request about an order that is not the signed-in "
            "customer's own order with this shop, such as another customer's order or a purchase from another store, "
            f"is refused with the reason that the policy covers only those orders {scope}.",
        ),
    ]
    for old, new in changes:
        assert v10.count(old) == 1, old
        v10 = v10.replace(old, new)
    assert v11 == v10
