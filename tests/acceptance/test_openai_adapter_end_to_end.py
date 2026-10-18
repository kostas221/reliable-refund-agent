"""Everything but the network: a whole D01 conversation through the real OpenAI adapter, the graph, the database and
the simulated customer, with fake clients answering in place of OpenAI. The zero-cost check before the pilot.
"""

import json

from langgraph.checkpoint.postgres import PostgresSaver
from openai.types.responses import ResponseFunctionToolCall, ResponseReasoningItem

from refund_agent import db as database
from refund_agent.agent.costs import Budget, BudgetExceeded
from refund_agent.agent.model import RecordingAdapter
from refund_agent.agent.openai_adapter import OpenAIResponses
from refund_agent.evaluation.customers import SimulatedCustomer
from refund_agent.evaluation.runner import run_scenario
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows
from tests.test_openai_adapter import FakeResponse, message

D01 = DEVELOPMENT["D01"]


def thinking(n):
    return ResponseReasoningItem(id=f"rs_{n}", type="reasoning", summary=[], encrypted_content=f"secret-thoughts-{n}")


def call(n, name, arguments):
    return ResponseFunctionToolCall(
        type="function_call", call_id=f"call_{n}", name=name, arguments=json.dumps(arguments), id=f"fc_{n}"
    )


def last_result(request, name):
    """What the backend answered to the latest call of this tool, read from the request the adapter built."""
    calls = {item["call_id"]: item["name"] for item in request["input"] if item.get("type") == "function_call"}
    outputs = [i for i in request["input"] if i.get("type") == "function_call_output" and calls[i["call_id"]] == name]
    return json.loads(outputs[-1]["output"])


class Agentlike:
    """Answers like a careful agent would, one request at a time, and keeps every request it got."""

    def __init__(self):
        self.requests = []
        self.responses = self

    def create(self, **request):
        self.requests.append(request)
        step = len(self.requests)
        if step == 1:
            return FakeResponse([thinking(1), call(1, "list_my_orders", {})])
        if step == 2:
            arguments = {"order_id": "d01-o1", "unit_ids": ["d01-o1-u1"], "summary_for_staff": "Chipped mug returned."}
            return FakeResponse([thinking(2), call(2, "propose_refund", arguments)])
        if step == 3:
            amount = last_result(request, "propose_refund")["amount_minor"]
            return FakeResponse([message(f"I can refund R$ {amount // 100},{amount % 100:02d}. Please confirm.")])
        if step == 4:
            proposal = last_result(request, "propose_refund")["proposal_id"]
            return FakeResponse([thinking(4), call(4, "execute_refund", {"proposal_id": proposal})])
        receipt = last_result(request, "execute_refund")["receipt"]
        return FakeResponse([message(f"Done: R$ 49,90, receipt {receipt['receipt_number']}.")])


class Customerlike:
    def __init__(self):
        self.requests = []
        self.responses = self

    def create(self, **request):
        self.requests.append(request)
        return FakeResponse([message("[END]")], usage=(400, 0, 5, 0))


def test_a_whole_conversation_through_the_real_adapter(db, tmp_path):
    app = db("app")
    budget = Budget(limit_usd=1.0)
    agent_client, customer_client = Agentlike(), Customerlike()
    agent = OpenAIResponses("gpt-6-luna", "low", role="agent", budget=budget, client=agent_client)
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
    # The model's reasoning came back in later requests, before the call it produced, through the checkpoint.
    later = agent_client.requests[2]["input"]
    kinds = [item.get("type", item.get("role")) for item in later]
    assert kinds[:5] == ["user", "reasoning", "function_call", "function_call_output", "reasoning"]
    assert later[1]["encrypted_content"] == "secret-thoughts-1"
    assert all(request["store"] is False for request in agent_client.requests)
    # The approval reached the agent as a notice, and the simulated customer ended the conversation.
    assert any(item.get("role") == "developer" for item in agent_client.requests[3]["input"])
    assert customer_client.requests[-1]["input"][-1]["content"].startswith("Done: R$ 49,90")
    # The budget counted both, apart, and the logs hold every request.
    assert set(budget.by_role) == {"agent", "simulator"} and budget.requests == 6
    assert len((tmp_path / "agent.jsonl").read_text(encoding="utf-8").splitlines()) == 5


class Allowing(Budget):
    """A budget that lets `n` attempts through and stops the next one, wherever the run has got to."""

    def __init__(self, n):
        super().__init__(limit_usd=1.0)
        self.left = n

    def reserve(self, worst_case_usd):
        if self.left == 0:
            raise BudgetExceeded("the test's budget ends here")
        self.left -= 1


def test_a_budget_stop_in_the_middle_is_judged_on_what_was_done(db, tmp_path):
    # Outside review of 2026-10-15: a stop used to end the pilot before any result was saved, losing the judgement of
    # what had been done. Here the budget runs out when the approval wakes the agent to pay: inside the delivery of
    # the notice, which must not swallow it as a failed delivery.
    app = db("app")
    budget = Allowing(3)  # list the orders, propose, tell the customer; the payment's request is stopped
    agent = OpenAIResponses("gpt-6-luna", "low", role="agent", budget=budget, client=Agentlike())
    simulator = OpenAIResponses("gpt-6-luna", "low", role="simulator", budget=budget, client=Customerlike())
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

    assert result.stopped_by_budget == "the test's budget ends here"
    assert (result.system_error, result.simulator_error) == (None, None)
    # Judged on the database as the stop left it: approved, not paid, so the expected refund is missing.
    assert rows(app, "SELECT status FROM proposals") == [("approved",)]
    assert rows(app, "SELECT count(*) FROM refund_operations") == [(0,)]
    assert result.verdict.result == "failed"
    assert "outcome:refunds" in result.verdict.names("failed")
    # The notice was neither marked delivered nor counted as a failed delivery: the run stopped, nothing failed.
    assert rows(app, "SELECT attempts, delivered_at FROM agent_notices") == [(0, None)]
    stop = json.loads((tmp_path / "agent.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert stop["error"]["kind"] == "budget_exceeded"
