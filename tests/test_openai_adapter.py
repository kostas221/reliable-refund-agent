"""The OpenAI Responses adapter without network or key: a fake client returns answers built from the SDK's own types."""

import json

import httpx2
import openai
import pytest
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseReasoningItem,
)

from refund_agent.agent import openai_adapter
from refund_agent.agent.costs import Budget, BudgetExceeded, cost_usd
from refund_agent.agent.model import ModelError
from refund_agent.agent.openai_adapter import OpenAIResponses, parse, to_input
from refund_agent.agent.tools import tool_definitions

TOOLS = tool_definitions()


class FakeResponse:
    def __init__(self, output, status="completed", usage=(1200, 200, 150, 60), model="gpt-6-luna-2026-09-30"):
        self.id, self.model, self.status, self.output, self.incomplete_details = "resp_1", model, status, output, None
        inputs, cached, outputs, reasoning = usage
        self.usage = openai.types.responses.ResponseUsage(
            input_tokens=inputs,
            input_tokens_details={"cached_tokens": cached, "cache_write_tokens": 0},
            output_tokens=outputs,
            output_tokens_details={"reasoning_tokens": reasoning},
            total_tokens=inputs + outputs,
        )


class FakeClient:
    """Answers or raises in order, and remembers every request it got."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []
        self.responses = self

    def create(self, **request):
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def http_error(cls, status):
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    return cls(f"status {status}", response=httpx2.Response(status, request=request), body=None)


REASONING = ResponseReasoningItem(id="rs_1", type="reasoning", summary=[], encrypted_content="gAAAA-opaque")
CALL = ResponseFunctionToolCall(
    type="function_call", call_id="call_1", name="list_my_orders", arguments="{}", id="fc_1", status="completed"
)


def message(text):
    content = [ResponseOutputText(type="output_text", text=text, annotations=[])]
    return ResponseOutputMessage(id="msg_1", type="message", role="assistant", status="completed", content=content)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(openai_adapter.time, "sleep", lambda seconds: None)


def test_the_request_stores_nothing_at_openai_and_offers_strict_tools():
    adapter = OpenAIResponses("gpt-6-luna", "low")
    request = adapter.request("Be careful.", [{"role": "customer", "text": "Hi"}], TOOLS)
    assert (request["store"], request["include"], request["parallel_tool_calls"]) == (
        False,
        ["reasoning.encrypted_content"],
        False,
    )
    assert request["reasoning"] == {"effort": "low"} and request["instructions"] == "Be careful."
    propose = next(tool for tool in request["tools"] if tool["name"] == "propose_refund")
    assert propose["strict"] is True
    parameters = propose["parameters"]
    assert parameters["required"] == list(parameters["properties"]) and parameters["additionalProperties"] is False
    assert "maxItems" not in json.dumps(request["tools"]) and "maxLength" not in json.dumps(request["tools"])
    assert "reasoning" not in OpenAIResponses("gpt-6-luna", None).request("", [], TOOLS)


def test_messages_become_input_items_in_order():
    messages = [
        {"role": "customer", "text": "Refund my mug."},
        {
            "role": "agent",
            "text": "",
            "tool_calls": [{"call_id": "c1", "name": "list_my_orders", "arguments": "{}"}],
            "continuation": [{"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "x"}],
        },
        {"role": "tool", "call_id": "c1", "name": "list_my_orders", "content": '{"ok": true}'},
        {"role": "agent", "text": "I can refund R$ 49,90.", "tool_calls": [], "continuation": []},
        {"role": "event", "text": "Request p1 was approved by a staff member."},
    ]
    assert to_input(messages) == [
        {"role": "user", "content": "Refund my mug."},
        {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "x"},
        {"type": "function_call", "call_id": "c1", "name": "list_my_orders", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "c1", "output": '{"ok": true}'},
        {"role": "assistant", "content": "I can refund R$ 49,90."},
        {"role": "developer", "content": "Notice from the shop's backend: Request p1 was approved by a staff member."},
    ]


def test_an_answer_becomes_a_turn_and_its_reasoning_goes_back_next_time():
    turn = parse(FakeResponse([REASONING, CALL]))
    assert turn.tool_calls == ({"call_id": "call_1", "name": "list_my_orders", "arguments": "{}"},)
    assert (turn.usage.input_tokens, turn.usage.cached_input_tokens) == (1200, 200)
    assert (turn.usage.output_tokens, turn.usage.reasoning_tokens) == (150, 60)
    assert (turn.model, turn.response_id) == ("gpt-6-luna-2026-09-30", "resp_1")  # the model that really answered
    back = to_input([turn.as_message()])
    assert back[0]["encrypted_content"] == "gAAAA-opaque" and back[1]["type"] == "function_call"
    assert parse(FakeResponse([message("Hello!")])).text == "Hello!"


def test_retries_are_ours_and_counted():
    client = FakeClient(
        http_error(openai.RateLimitError, 429),
        http_error(openai.InternalServerError, 500),
        FakeResponse([message("Hello!")]),
    )
    adapter = OpenAIResponses("gpt-6-luna", "low", client=client, retries=3)
    assert adapter.respond("", [{"role": "customer", "text": "Hi"}], TOOLS).text == "Hello!"
    assert (adapter.retries_used, len(client.requests)) == (2, 3)


def test_failures_become_model_errors():
    always_limited = FakeClient(*[http_error(openai.RateLimitError, 429)] * 4)
    with pytest.raises(ModelError) as limited:
        OpenAIResponses("gpt-6-luna", "low", client=always_limited, retries=3).respond("", [], TOOLS)
    assert (limited.value.kind, limited.value.retryable, len(always_limited.requests)) == ("rate_limit", True, 4)

    bad = FakeClient(http_error(openai.BadRequestError, 400))
    with pytest.raises(ModelError) as refused:
        OpenAIResponses("gpt-6-luna", "low", client=bad).respond("", [], TOOLS)
    assert (refused.value.kind, len(bad.requests)) == ("bad_request", 1)  # never retried

    refusal = ResponseOutputMessage(
        id="m",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputRefusal(type="refusal", refusal="I can't help with that.")],
    )
    for answer, kind in (
        (FakeResponse([refusal]), "refusal"),
        (FakeResponse([REASONING]), "invalid_output"),
        (FakeResponse([message("cut")], status="incomplete"), "invalid_output"),
    ):
        with pytest.raises(ModelError) as failed:
            parse(answer)
        assert failed.value.kind == kind


def test_the_budget_stops_a_request_before_it_is_sent():
    client = FakeClient(FakeResponse([message("Hello!")]))
    budget = Budget(limit_usd=0.0001)
    with pytest.raises(BudgetExceeded):
        OpenAIResponses("gpt-6-luna", "low", client=client, budget=budget).respond("", [], TOOLS)
    assert client.requests == [] and budget.spent_usd == 0  # nothing was sent, nothing was spent


def test_the_budget_counts_what_the_answer_reports():
    budget = Budget(limit_usd=1.0)
    adapter = OpenAIResponses("gpt-6-luna", "low", client=FakeClient(FakeResponse([CALL])), budget=budget)
    adapter.respond("", [{"role": "customer", "text": "Hi"}], TOOLS)
    assert budget.spent_usd == pytest.approx(cost_usd("gpt-6-luna", 1200, 200, 150))
    assert (budget.requests, list(budget.by_role)) == (1, ["agent"])
