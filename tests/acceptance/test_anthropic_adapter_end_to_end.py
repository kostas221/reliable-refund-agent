"""Everything but the network for the comparison's second model: a whole D01 conversation through the real Anthropic
adapter, the graph, the checkpoints, the database and the simulated customer, with fake clients in place of the
providers. It is also the offline form of the provider's check on thinking blocks: every request must begin with the
whole previous one, byte for byte, and keep the same instructions and tools (plan change log, 2026-11-02)."""

import json

from anthropic.types import Message, TextBlock, ThinkingBlock, ToolUseBlock, Usage
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.anthropic_adapter import NOTICE, AnthropicMessages
from refund_agent.agent.costs import Budget
from refund_agent.agent.model import RecordingAdapter
from refund_agent.agent.openai_adapter import OpenAIResponses
from refund_agent.evaluation.customers import SimulatedCustomer
from refund_agent.evaluation.runner import run_scenario
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows
from tests.acceptance.test_openai_adapter_end_to_end import Customerlike

D01 = DEVELOPMENT["D01"]


def answer(*blocks, stop):
    usage = Usage(input_tokens=200, output_tokens=60, cache_creation_input_tokens=900, cache_read_input_tokens=3000)
    return Message(
        id="msg_1",
        type="message",
        role="assistant",
        model="claude-sonnet-5-5",
        content=list(blocks),
        stop_reason=stop,
        stop_sequence=None,
        usage=usage,
    )


def thought(n):
    return ThinkingBlock(type="thinking", thinking="", signature=f"sig-{n}")


def use(n, name, arguments):
    return ToolUseBlock(type="tool_use", id=f"toolu_{n}", name=name, input=arguments)


def last_result(request, name):
    """What the backend answered to the latest call of this tool, read from the request the adapter built."""
    ids = {
        block["id"]
        for message in request["messages"]
        if message["role"] == "assistant"
        for block in message["content"]
        if block["type"] == "tool_use" and block["name"] == name
    }
    results = [
        block["content"]
        for message in request["messages"]
        if message["role"] == "user"
        for block in message["content"]
        if block["type"] == "tool_result" and block["tool_use_id"] in ids
    ]
    return json.loads(results[-1])


class Agentlike:
    """Answers like a careful agent would, one request at a time, and keeps every request it got."""

    def __init__(self):
        self.requests = []
        self.messages = self

    def create(self, **request):
        self.requests.append(json.loads(json.dumps(request)))  # as sent, frozen
        step = len(self.requests)
        if step == 1:
            return answer(thought(1), use(1, "list_my_orders", {}), stop="tool_use")
        if step == 2:
            arguments = {"order_id": "d01-o1", "unit_ids": ["d01-o1-u1"], "summary_for_staff": "Chipped mug returned."}
            return answer(thought(2), use(2, "propose_refund", arguments), stop="tool_use")
        if step == 3:
            amount = last_result(request, "propose_refund")["amount_minor"]
            said = f"I can refund R$ {amount // 100},{amount % 100:02d}. Please confirm on the card."
            return answer(thought(3), TextBlock(type="text", text=said), stop="end_turn")
        if step == 4:
            return answer(thought(4), use(4, "execute_refund", {}), stop="tool_use")
        receipt = last_result(request, "execute_refund")["receipt"]
        said = f"Done: R$ 49,90, receipt {receipt['receipt_number']}."
        return answer(TextBlock(type="text", text=said), stop="end_turn")


def test_a_whole_conversation_through_the_anthropic_adapter_appends_and_never_rewrites(db, tmp_path):
    app = db("app")
    budget = Budget(limit_usd=1.0)
    agent_client, customer_client = Agentlike(), Customerlike()
    agent = AnthropicMessages("claude-sonnet-5-5", "low", role="agent", budget=budget, client=agent_client)
    simulator = OpenAIResponses("gpt-6-luna", "low", role="simulator", budget=budget, client=customer_client)
    with database.checkpoint_connection("app", app.url.database) as connection:
        result = run_scenario(
            D01,
            SimulatedCustomer(D01, RecordingAdapter(simulator, tmp_path / "simulator.jsonl")),
            RecordingAdapter(agent, tmp_path / "agent.jsonl"),
            owner=db("owner"),
            app=app,
            checkpointer=PostgresSaver(connection),
            policy=POLICY,
        )

    assert (result.system_error, result.simulator_error) == (None, None)
    assert result.verdict.names("failed") == [], result.verdict.report()
    assert rows(app, "SELECT count(*), CAST(sum(amount_minor) AS bigint) FROM ledger_lines") == [(1, 4990)]

    requests = agent_client.requests
    assert len(requests) == 5
    for earlier, later in zip(requests, requests[1:], strict=False):
        assert later["system"] == earlier["system"] and later["tools"] == earlier["tools"]
        shared = later["messages"][: len(earlier["messages"])]
        assert json.dumps(shared) == json.dumps(earlier["messages"])  # append-only, byte for byte
    # The thinking blocks came back unchanged, through the checkpoint, before the calls they produced.
    blocks = [(m["role"], b) for m in requests[-1]["messages"] for b in m["content"]]
    signatures = [b["signature"] for role, b in blocks if b["type"] == "thinking"]
    assert signatures == ["sig-1", "sig-2", "sig-3", "sig-4"]
    # The approval reached the agent as a notice from the backend, in a user turn.
    notices = [b["text"] for role, b in blocks if role == "user" and b.get("text", "").startswith(NOTICE)]
    assert len(notices) == 1 and "approved" in notices[0]
    assert customer_client.requests[-1]["input"][-1]["content"].startswith("Done: R$ 49,90")
    assert set(budget.by_role) == {"agent", "simulator"} and budget.requests == 6
