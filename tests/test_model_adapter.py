"""The model adapter without a database: the scripted mock, the request log and the agent's instructions."""

import json
import re

import pytest

from refund_agent.agent.model import Call, ModelError, RecordingAdapter, Say, ScriptedModel, load_instructions
from refund_agent.agent.tools import TOOLS, tool_definitions

INSTRUCTIONS = load_instructions()
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
    assert first["usage"] == {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    assert failed["error"]["kind"] == "invalid_output"  # a failure is logged too, then raised


def test_the_instructions_name_only_real_tools():
    named = set(re.findall(r"`([a-z_]+)`", INSTRUCTIONS.text))
    assert named and named <= set(TOOLS)
    assert INSTRUCTIONS.version == "agent-v3" and len(INSTRUCTIONS.sha256) == 64
