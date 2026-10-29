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
from refund_agent.agent.costs import Budget, BudgetExceeded, cost_usd, estimated_tokens
from refund_agent.agent.model import ModelError
from refund_agent.agent.openai_adapter import OpenAIResponses, parse, to_input
from refund_agent.agent.tools import tool_definitions

TOOLS = tool_definitions()


class FakeResponse:
    def __init__(
        self, output, status="completed", usage=(1200, 200, 150, 60), model="gpt-6-luna-2026-09-30", written=0
    ):
        self.id, self.model, self.status, self.output, self.incomplete_details = "resp_1", model, status, output, None
        inputs, cached, outputs, reasoning = usage
        self.usage = openai.types.responses.ResponseUsage(
            input_tokens=inputs,
            input_tokens_details={"cached_tokens": cached, "cache_write_tokens": written},
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


def labelled(text, phase, item_id="msg_1"):
    content = [ResponseOutputText(type="output_text", text=text, annotations=[])]
    return ResponseOutputMessage(
        id=item_id, type="message", role="assistant", status="completed", content=content, phase=phase
    )


def test_the_customer_sees_the_final_answer_and_the_model_gets_back_all_it_said():
    # The contrasting baseline (2026-10-22): every clarifying question reached the customer twice in one message.
    # The third review: what is shown is not what the model said, and the model must get back what it said.
    question = "Which scarf would you like refunded, the olive or the rust one?"
    commentary = "I found two scarves. " + question
    turn = parse(FakeResponse([labelled(commentary, "commentary"), labelled(question, "final_answer", "msg_2")]))
    assert turn.text == question
    assert turn.message_items == (
        {"phase": "commentary", "text": commentary},
        {"phase": "final_answer", "text": question},
    )
    assert to_input([turn.as_message()]) == [
        {"role": "assistant", "content": commentary, "phase": "commentary"},
        {"role": "assistant", "content": question, "phase": "final_answer"},
    ]


def test_labelled_text_goes_back_in_the_order_the_model_gave_it():
    second = ResponseReasoningItem(id="rs_2", type="reasoning", summary=[], encrypted_content="gAAAA-second")
    output = [REASONING, labelled("Let me check.", "commentary"), second, labelled("Done.", "final_answer", "msg_2")]
    back = to_input([parse(FakeResponse(output)).as_message()])
    assert [item.get("id") or item["content"] for item in back] == ["rs_1", "Let me check.", "rs_2", "Done."]


def test_a_final_answer_repeated_word_for_word_right_after_itself_is_shown_once():
    # Plan change log, 2026-10-29: in D09 try 2 of runs/pilot-20261029T113311Z-gpt-6-luna-none the model gave the same
    # final answer twice in one response (1 of 2,572 answers since 2026-10-22), and the customer saw the question twice.
    question = "I found two returned navy T-shirts in that order: size M and size L. Which one would you like refunded?"
    turn = parse(FakeResponse([labelled(question, "final_answer"), labelled(question, "final_answer", "msg_2")]))
    assert turn.text == question
    assert turn.message_items == ({"phase": "final_answer", "text": question},) * 2  # the log keeps both
    back = to_input([turn.as_message()])
    assert back == [{"role": "assistant", "content": question, "phase": "final_answer"}] * 2  # and the model gets both
    # Only the same text right after itself goes: the same text later, or a text that differs at all, stays.
    later = [labelled("A.", "final_answer"), labelled("B.", "final_answer", "m2"), labelled("A.", "final_answer", "m3")]
    assert parse(FakeResponse(later)).text == "A.\nB.\nA."
    near = [labelled("Which one?", "final_answer"), labelled("Which one? ", "final_answer", "msg_2")]
    assert parse(FakeResponse(near)).text == "Which one?\nWhich one? "
    # Unlabelled text goes back to the model as it is shown, so it is shown as it came.
    assert parse(FakeResponse([message("One."), message("One.")])).text == "One.\nOne."


def test_commentary_before_a_tool_call_is_still_shown_and_unlabelled_text_is_unchanged():
    turn = parse(FakeResponse([labelled("Let me look up your orders.", "commentary"), CALL]))
    assert (turn.text, len(turn.tool_calls)) == ("Let me look up your orders.", 1)
    assert to_input([turn.as_message()])[0] == {
        "role": "assistant",
        "content": "Let me look up your orders.",
        "phase": "commentary",
    }
    plain = parse(FakeResponse([message("One."), message("Two.")]))
    assert plain.text == "One.\nTwo." and plain.continuation == ()
    assert to_input([plain.as_message()]) == [{"role": "assistant", "content": "One.\nTwo."}]


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


# Every attempt counts (outside review of 2026-10-15)

HI = [{"role": "customer", "text": "Hi"}]
SEEN = cost_usd("gpt-6-luna", 1200, 200, 150)  # what FakeResponse's usage reports


def timeout():
    return openai.APITimeoutError(request=httpx2.Request("POST", "https://api.openai.com/v1/responses"))


def test_an_answer_that_turns_out_unusable_was_still_counted():
    # The review's case: two billed answers, both unusable, left the counter at zero calls and zero dollars.
    cut = [FakeResponse([message("cut")], status="incomplete") for _ in range(2)]
    budget = Budget(limit_usd=1.0)
    adapter = OpenAIResponses("gpt-6-luna", "low", client=FakeClient(*cut), budget=budget)
    for _ in range(2):
        with pytest.raises(ModelError):
            adapter.respond("", HI, TOOLS)
    assert budget.requests == 2
    assert budget.spent_usd == pytest.approx(2 * SEEN)
    assert budget.uncertain_usd == 0


def test_each_attempt_is_counted_on_its_own_and_an_unknown_charge_counts_its_worst_case():
    client = FakeClient(timeout(), http_error(openai.RateLimitError, 429), FakeResponse([message("Hello!")]))
    budget = Budget(limit_usd=1.0)
    adapter = OpenAIResponses("gpt-6-luna", "low", client=client, budget=budget)
    worst = adapter.worst_case_usd(adapter.request("", HI, TOOLS))
    assert adapter.respond("", HI, TOOLS).text == "Hello!"
    assert adapter.last_attempts == [
        {"outcome": "timeout", "usd": worst, "uncertain": True},  # it may have been billed: nobody knows
        {"outcome": "rate_limit", "usd": 0.0, "uncertain": False},  # refused before any work
        {"outcome": "answered", "usd": pytest.approx(SEEN), "uncertain": False},
    ]
    assert budget.requests == 3
    assert budget.spent_usd == pytest.approx(worst + SEEN)
    assert budget.uncertain_usd == pytest.approx(worst)


def test_a_retry_the_budget_cannot_cover_is_not_sent():
    client = FakeClient(timeout(), FakeResponse([message("Hello!")]))
    adapter = OpenAIResponses("gpt-6-luna", "low", client=client)
    worst = adapter.worst_case_usd(adapter.request("", HI, TOOLS))
    adapter.budget = Budget(limit_usd=1.5 * worst)  # room for one worst case, not two
    with pytest.raises(BudgetExceeded):
        adapter.respond("", HI, TOOLS)
    assert len(client.requests) == 1  # the retry was stopped before it was sent
    assert adapter.budget.spent_usd == pytest.approx(worst)


def test_the_request_log_holds_every_attempt_and_a_budget_stop(tmp_path):
    from refund_agent.agent.model import RecordingAdapter

    log = tmp_path / "requests.jsonl"
    client = FakeClient(timeout(), FakeResponse([message("Hello!")]), timeout())
    inner = OpenAIResponses("gpt-6-luna", "low", client=client, budget=Budget(limit_usd=1.0))
    recorded = RecordingAdapter(inner, log)
    recorded.respond("", HI, TOOLS)
    worst = inner.last_attempts[0]["usd"]
    inner.budget = Budget(limit_usd=1.5 * worst)  # room for one more attempt, not for its retry
    with pytest.raises(BudgetExceeded):
        recorded.respond("", HI, TOOLS)
    answered, stopped = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [a["outcome"] for a in answered["attempts"]] == ["timeout", "answered"]
    assert stopped["error"]["kind"] == "budget_exceeded"
    assert [a["outcome"] for a in stopped["attempts"]] == ["timeout"]  # what was tried before the stop


# The worst case is a bound (review of 2026-10-19, R6)


@pytest.mark.parametrize("text", ["a" * 300, "€" * 300, "R$ 49,90; d01-o1-u1; " * 20, '{"a": [1, 2, 3]}' * 30])
def test_the_input_estimate_is_at_least_one_token_per_byte(text):
    # About three characters a token was an average: text of symbols, IDs or other alphabets can need more.
    assert estimated_tokens(text) >= len(text.encode("utf-8"))


def test_after_an_attempt_that_cost_more_than_its_reservation_nothing_more_is_sent():
    reported = (10_000_000, 0, 0, 0)  # far more input than the request could hold: $1.00 at Luna's price
    client = FakeClient(FakeResponse([message("Hello!")], usage=reported), FakeResponse([message("Again")]))
    budget = Budget(limit_usd=5.0)
    adapter = OpenAIResponses("gpt-6-luna", "low", client=client, budget=budget)
    assert adapter.respond("", HI, TOOLS).text == "Hello!"
    assert budget.spent_usd == pytest.approx(1.0)  # counted as reported
    assert "more than the" in budget.overrun
    with pytest.raises(BudgetExceeded, match="cost more than its worst case"):
        adapter.respond("", HI, TOOLS)
    assert len(client.requests) == 1


# Prices as checked on 2026-10-19: Sol's cached input, and cache writes


def test_cache_writes_are_billed_at_their_own_price():
    # 1000 input tokens: 200 read from the cache, 300 written to it, 500 plain; 100 output tokens.
    paid = (500 * 2.00 + 200 * 0.10 + 300 * 2.50 + 100 * 10.00) / 1_000_000
    assert cost_usd("gpt-6.1-sol", 1000, 200, 100, cache_write_tokens=300) == pytest.approx(paid)


def test_the_adapter_counts_the_cache_writes_an_answer_reports():
    budget = Budget(limit_usd=1.0)
    answer = FakeResponse([message("Hello!")], written=1000)
    adapter = OpenAIResponses("gpt-6-luna", "low", client=FakeClient(answer), budget=budget)
    turn = adapter.respond("", HI, TOOLS)
    assert turn.usage.cache_write_tokens == 1000
    assert budget.spent_usd == pytest.approx(cost_usd("gpt-6-luna", 1200, 200, 150, cache_write_tokens=1000))


def test_the_worst_case_holds_even_if_every_input_token_is_written_to_the_cache():
    adapter = OpenAIResponses("gpt-6.1-sol", "low")
    request = adapter.request("", HI, TOOLS)
    tokens = estimated_tokens(json.dumps(request, ensure_ascii=False))
    assert adapter.worst_case_usd(request) == pytest.approx(cost_usd("gpt-6.1-sol", tokens, 0, 4000, tokens))


def test_every_argument_of_every_tool_reaches_the_model_with_a_type():
    # Strict mode refuses a property without a type, and the strict schema keeps no anyOf: an optional "str | None"
    # argument would fail every request of a paid run (found before the run of v1.1 step 3).
    def untyped(schema, path):
        for name, prop in schema.get("properties", {}).items():
            if "type" not in prop:
                yield f"{path}.{name}"
            yield from untyped(prop, f"{path}.{name}")
        if "items" in schema:
            yield from untyped(schema["items"], f"{path}[]")

    missing = [p for tool in TOOLS for p in untyped(openai_adapter.strict_schema(tool["parameters"]), tool["name"])]
    assert missing == []


def test_a_refused_request_keeps_the_providers_request_id():
    # The two 403s of the step 3 run said only "Error code: 403" (review of 2026-10-21): the ID lets them be traced.
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    answer = httpx2.Response(403, request=request, headers={"x-request-id": "req_403"})
    denied = FakeClient(openai.PermissionDeniedError("status 403", response=answer, body=None))
    with pytest.raises(ModelError) as refused:
        OpenAIResponses("gpt-6-luna", "low", client=denied).respond("", [], TOOLS)
    assert (refused.value.kind, refused.value.detail) == ("bad_request", "403: status 403 (request req_403)")
