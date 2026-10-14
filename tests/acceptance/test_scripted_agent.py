"""The scripted model drives the real tools on a real PostgreSQL, for Ana's mug (D01), with every request logged.

The small loop below (model, then tools, until the model answers in words) is what the conversation graph will do
in the next step; here it only shows that the adapter, the mock and the tools fit together.
"""

import json

from refund_agent.agent.model import Call, RecordingAdapter, Say, ScriptedModel, load_instructions
from refund_agent.agent.policy_search import WordSearch
from refund_agent.agent.tools import ToolContext, call_tool, tool_definitions
from refund_agent.fixtures import seed
from refund_agent.refunds import Actor, confirm, decide, open_conversation
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows

D01 = DEVELOPMENT["D01"]
INSTRUCTIONS = load_instructions()

ANA_MUG = [
    Call("list_my_orders"),
    Call("lookup_refund_policy", {"query": "items must be returned first"}),
    Call("propose_refund", {"order_id": "d01-o1", "unit_ids": ["d01-o1-u1"]}),
    Say("I can refund {propose_refund.amount_minor|brl} for the blue mug. Please confirm on the proposal card."),
    Call("execute_refund", {"proposal_id": "{propose_refund.proposal_id}"}),
    Say(
        "Your refund of {execute_refund.receipt.amount_minor|brl} is done: "
        "receipt {execute_refund.receipt.receipt_number}."
    ),
]


def run_turn(model, ctx, messages, max_steps=10):
    for _ in range(max_steps):
        turn = model.respond(INSTRUCTIONS.text, messages, tool_definitions())
        messages.append(turn.as_message())
        if not turn.tool_calls:
            return turn.text
        for call in turn.tool_calls:
            result = call_tool(ctx, call["name"], call["arguments"], call["call_id"])
            messages.append(
                {"role": "tool", "call_id": call["call_id"], "name": call["name"], "content": json.dumps(result)}
            )
    raise AssertionError("the agent did not answer within the step limit")


def test_a_scripted_conversation_refunds_the_mug_through_the_real_tools(db, tmp_path):
    seed(db("owner"), D01, POLICY)
    app = db("app")
    conversation = open_conversation(app, Actor("customer", "d01-ana"), D01.now)
    ctx = ToolContext(app, POLICY, WordSearch(POLICY), lambda: D01.now, "d01-ana", conversation)
    log = tmp_path / "requests.jsonl"
    model = RecordingAdapter(ScriptedModel(ANA_MUG), log)
    messages = [{"role": "customer", "text": D01.customer.opening_message}]

    said = run_turn(model, ctx, messages)
    assert said == "I can refund R$ 49,90 for the blue mug. Please confirm on the proposal card."
    proposal_id = json.loads(messages[-2]["content"])["proposal_id"]
    assert rows(app, "SELECT status, amount_minor FROM proposals") == [("awaiting_customer_confirmation", 4990)]
    policy = json.loads(messages[4]["content"])
    assert policy["sections"][0]["citation"] == "refund-policy/v1/return"

    # The customer's button and the staff decision happen outside the agent; the agent is then told.
    confirm(app, Actor("customer", "d01-ana"), proposal_id, "confirmed", D01.now, POLICY)
    decide(app, Actor("staff", "d01-rui"), proposal_id, "approved", D01.now, POLICY)
    messages.append({"role": "event", "text": f"Request {proposal_id} was approved by a staff member."})

    said = run_turn(model, ctx, messages)
    receipt = rows(app, "SELECT receipt_number FROM refund_operations")[0][0]
    assert said == f"Your refund of R$ 49,90 is done: receipt {receipt}."
    assert rows(app, "SELECT CAST(sum(amount_minor) AS bigint) FROM ledger_lines") == [(4990,)]

    logged = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(logged) == len(ANA_MUG)  # one request per line of the script, each in full
    assert all(entry["instructions"] == INSTRUCTIONS.text and len(entry["tools"]) == 7 for entry in logged)
    assert logged[-1]["messages"][-1]["name"] == "execute_refund"  # the model saw the receipt before speaking
