"""The Anthropic Messages adapter without network or key (refund_agent/agent/anthropic_adapter.py): a fake client
returns answers built from the SDK's own types. It keeps the contract of the OpenAI adapter, so the Sol-Sonnet
comparison changes the model and nothing else (plan change log, 2026-11-02)."""

import json

import anthropic
import httpx2
import pytest
from anthropic.types import Message, TextBlock, ThinkingBlock, ToolUseBlock, Usage

from refund_agent.agent import anthropic_adapter
from refund_agent.agent.adapters import missing_key, model_adapter, provider
from refund_agent.agent.anthropic_adapter import NOTICE, AnthropicMessages, parse, to_messages
from refund_agent.agent.costs import Budget, BudgetExceeded, OutOfCredit, cost_usd
from refund_agent.agent.model import ModelError, RecordingAdapter
from refund_agent.agent.openai_adapter import OpenAIResponses, strict_schema
from refund_agent.agent.tools import tool_definitions

TOOLS = tool_definitions()
HI = [{"role": "customer", "text": "Hi"}]
MODEL = "claude-sonnet-5-5"


def answer(*blocks, stop="end_turn", usage=(100, 300, 2000, 5000)):
    """A Message as the SDK builds it. usage: uncached input, output, cache writes, cache reads."""
    fresh, output, written, read = usage
    return Message(
        id="msg_1",
        type="message",
        role="assistant",
        model=MODEL,
        content=list(blocks),
        stop_reason=stop,
        stop_sequence=None,
        usage=Usage(
            input_tokens=fresh,
            output_tokens=output,
            cache_creation_input_tokens=written,
            cache_read_input_tokens=read,
        ),
    )


def text(said):
    return TextBlock(type="text", text=said)


def thought(n):
    return ThinkingBlock(type="thinking", thinking="", signature=f"sig-{n}")


def use(n, name, arguments):
    return ToolUseBlock(type="tool_use", id=f"toolu_{n}", name=name, input=arguments)


class FakeClient:
    """Answers or raises in order, and remembers every request it got."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []
        self.messages = self

    def create(self, **request):
        self.requests.append(request)
        reply = self.answers.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def status_error(cls, status, error_type, message="status"):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    body = {"type": "error", "error": {"type": error_type, "message": message}}
    return cls(message, response=httpx2.Response(status, request=request), body=body)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(anthropic_adapter.time, "sleep", lambda seconds: None)


# The request: the compared setting and nothing more


def test_the_request_is_the_compared_setting_and_nothing_more():
    request = AnthropicMessages(MODEL, "low").request("Policy and instructions.", HI, TOOLS)
    assert request["model"] == MODEL and request["max_tokens"] == 4000  # the same output limit as the OpenAI adapter
    # The instructions are marked for the cache, so every conversation reads them instead of writing them again (the
    # first paid check, 2026-11-03: cache writes 21% of the input, the agent 4.6 times Sol's cost a conversation).
    assert request["system"] == [
        {"type": "text", "text": "Policy and instructions.", "cache_control": {"type": "ephemeral"}}
    ]
    assert request["output_config"] == {"effort": "low"}
    assert request["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}  # one call per answer
    assert request["cache_control"] == {"type": "ephemeral"}
    assert [t["name"] for t in request["tools"]] == [t["name"] for t in TOOLS]
    for sent, tool in zip(request["tools"], TOOLS, strict=True):
        assert sent["input_schema"] == strict_schema(tool["parameters"]) and sent["strict"] is True
    # The model's own thinking mode, no sampling settings, no fallback to another model, no beta.
    assert not {"thinking", "temperature", "top_p", "top_k", "fallbacks", "betas", "metadata"} & set(request)
    assert request["messages"] == [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}]


HISTORY = [
    {"role": "customer", "text": "My mug arrived chipped."},
    {
        "role": "agent",
        "text": "",
        "tool_calls": [{"call_id": "toolu_1", "name": "list_my_orders", "arguments": "{}"}],
        "continuation": [
            {"type": "thinking", "thinking": "", "signature": "sig-1"},
            {"type": "tool_use", "id": "toolu_1", "name": "list_my_orders", "input": {}},
        ],
    },
    {"role": "tool", "call_id": "toolu_1", "name": "list_my_orders", "content": '{"ok": true}'},
    {
        "role": "agent",
        "text": "I can refund R$ 49,90.",
        "tool_calls": [],
        "continuation": [
            {"type": "thinking", "thinking": "", "signature": "sig-2"},
            {"type": "text", "text": "I can refund R$ 49,90."},
        ],
    },
    {"role": "agent", "text": "Earlier refund told by the records (refund-policy/v2/remaining).", "fact_line": True},
    {"role": "event", "text": "The customer confirmed request p-1 and a staff member approved it."},
    {"role": "customer", "text": "Thanks!"},
]


def test_each_message_becomes_one_api_message_and_every_request_begins_with_the_previous_one():
    whole = to_messages(HISTORY)
    assert [m["role"] for m in whole] == ["user", "assistant", "user", "assistant", "assistant", "user", "user"]
    assert whole[1]["content"] == HISTORY[1]["continuation"]  # the answer's blocks, unchanged and in order
    assert whole[2]["content"] == [{"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"ok": true}'}]
    assert whole[4]["content"] == [{"type": "text", "text": HISTORY[4]["text"]}]  # a fact line: appended, not merged
    assert whole[5]["content"][0]["text"] == NOTICE + HISTORY[5]["text"]
    # Append-only: the API checks that nothing before a thinking block changed since it was made.
    for k in range(1, len(HISTORY)):
        shorter = to_messages(HISTORY[:k])
        assert json.dumps(whole[: len(shorter)]) == json.dumps(shorter), k


# The answer


def test_an_answer_carries_every_block_back_unchanged_and_in_order():
    turn = parse(answer(thought(1), text("Let me check your orders."), use(1, "list_my_orders", {}), stop="tool_use"))
    assert turn.text == "Let me check your orders."
    assert turn.tool_calls == ({"call_id": "toolu_1", "name": "list_my_orders", "arguments": "{}"},)
    assert turn.continuation == (
        {"type": "thinking", "thinking": "", "signature": "sig-1"},
        {"type": "text", "text": "Let me check your orders."},
        {"type": "tool_use", "id": "toolu_1", "name": "list_my_orders", "input": {}},
    )
    assert to_messages([turn.as_message()])[0] == {"role": "assistant", "content": list(turn.continuation)}


def test_an_empty_text_block_is_not_sent_back():
    turn = parse(answer(thought(1), text(""), text("Hello!")))
    assert turn.text == "Hello!"
    assert [block["type"] for block in turn.continuation] == ["thinking", "text"]


def test_usage_counts_cache_reads_and_writes_apart():
    turn = parse(answer(text("Hello!"), usage=(100, 300, 2000, 5000)))
    usage = turn.usage
    assert (usage.input_tokens, usage.cached_input_tokens, usage.cache_write_tokens) == (7100, 5000, 2000)
    assert usage.output_tokens == 300
    budget = Budget(limit_usd=1.0)
    AnthropicMessages(MODEL, "low", budget=budget, client=FakeClient(answer(text("Hello!")))).respond("", HI, TOOLS)
    paid = (100 * 2.00 + 5000 * 0.20 + 2000 * 2.50 + 300 * 10.00) / 1_000_000
    assert budget.spent_usd == pytest.approx(paid) == pytest.approx(cost_usd(MODEL, 7100, 5000, 300, 2000))


def test_a_refusal_an_answer_cut_short_and_an_empty_answer_are_model_errors():
    for reply, kind in (
        (answer(text("I can't help with that."), stop="refusal"), "refusal"),
        (answer(text("I can refund"), stop="max_tokens"), "invalid_output"),
        (answer(thought(1)), "invalid_output"),
    ):
        with pytest.raises(ModelError) as failed:
            parse(reply)
        assert failed.value.kind == kind


# Sending: retries, the budget, the provider's refusals


def test_retries_are_ours_and_each_attempt_is_counted():
    timeout = anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    client = FakeClient(
        status_error(anthropic.RateLimitError, 429, "rate_limit_error"),
        status_error(anthropic.OverloadedError, 529, "overloaded_error"),
        timeout,
        answer(text("Hello!")),
    )
    budget = Budget(limit_usd=1.0)
    adapter = AnthropicMessages(MODEL, "low", budget=budget, client=client, retries=3)
    worst = adapter.worst_case_usd(adapter.request("", HI, TOOLS))
    assert adapter.respond("", HI, TOOLS).text == "Hello!"
    assert (adapter.retries_used, len(client.requests)) == (3, 4)
    assert [a["outcome"] for a in adapter.last_attempts] == ["rate_limit", "server", "timeout", "answered"]
    # A rate limit is refused before any work; an overloaded server or a timeout counts its worst case, uncertain.
    assert budget.uncertain_usd == pytest.approx(2 * worst) and budget.held_usd == 0


def test_a_bad_request_is_never_retried():
    client = FakeClient(status_error(anthropic.BadRequestError, 400, "invalid_request_error", "messages: bad"))
    with pytest.raises(ModelError) as refused:
        AnthropicMessages(MODEL, "low", client=client).respond("", HI, TOOLS)
    assert (refused.value.kind, len(client.requests)) == ("bad_request", 1)


@pytest.mark.parametrize(
    ("status", "error_type", "message"),
    [
        (402, "billing_error", "Billing problem."),
        (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API."),
    ],
)
def test_no_credit_stops_at_once_and_is_never_retried(status, error_type, message):
    cls = anthropic.BadRequestError if status == 400 else anthropic.APIStatusError
    client = FakeClient(status_error(cls, status, error_type, message), answer(text("Hello!")))
    budget = Budget(limit_usd=1.0)
    with pytest.raises(OutOfCredit, match="no credit left"):
        AnthropicMessages(MODEL, "low", budget=budget, client=client).respond("", HI, TOOLS)
    assert len(client.requests) == 1 and budget.spent_usd == 0 and budget.held_usd == 0
    assert "no credit left" in budget.last_stop


def test_the_budget_stops_a_request_before_it_is_sent():
    client = FakeClient(answer(text("Hello!")))
    with pytest.raises(BudgetExceeded):
        AnthropicMessages(MODEL, "low", budget=Budget(limit_usd=0.0001), client=client).respond("", HI, TOOLS)
    assert client.requests == []


def test_an_unexpected_failure_counts_its_worst_case_and_frees_what_it_held():
    budget = Budget(limit_usd=1.0)
    adapter = AnthropicMessages(MODEL, "low", budget=budget, client=FakeClient(ValueError("unexpected")))
    worst = adapter.worst_case_usd(adapter.request("", HI, TOOLS))
    with pytest.raises(ValueError):
        adapter.respond("", HI, TOOLS)
    assert budget.spent_usd == pytest.approx(worst) and budget.held_usd == 0


def test_the_request_log_holds_the_attempts_and_names_a_refusal_for_credit(tmp_path):
    log = tmp_path / "requests.jsonl"
    client = FakeClient(answer(text("Hello!")), status_error(anthropic.APIStatusError, 402, "billing_error"))
    recorded = RecordingAdapter(AnthropicMessages(MODEL, "low", client=client), log)
    recorded.respond("", HI, TOOLS)
    with pytest.raises(OutOfCredit):
        recorded.respond("", HI, TOOLS)
    answered, stopped = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert answered["adapter"] == "claude-sonnet-5-5/low" and answered["answer"]["text"] == "Hello!"
    assert stopped["error"]["kind"] == "no_credit"


# Which adapter serves a model


def test_a_claude_model_is_served_by_the_anthropic_adapter_and_needs_its_key(monkeypatch):
    assert (provider(MODEL), provider("gpt-6.1-sol")) == ("anthropic", "openai")
    assert isinstance(model_adapter(MODEL, "low"), AnthropicMessages)
    assert isinstance(model_adapter("gpt-6.1-sol", "low"), OpenAIResponses)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert missing_key("gpt-6.1-sol") is None
    assert missing_key("gpt-6.1-sol", MODEL) == "ANTHROPIC_API_KEY"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert missing_key(MODEL, "gpt-6-luna") is None
