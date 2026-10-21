"""The transcripts a reader audits show what the agent read and what the simulated customer knew (review of
2026-10-19: the seller's message and the customer's instructions were missing)."""

import json

from refund_agent.evaluation.customers import simulator_instructions
from refund_agent.evaluation.transcripts import render_run
from refund_agent.scenarios import load_split

SCENARIOS = {s.id: s for s in load_split("development")}


def run_folder(tmp_path, scenario_id, messages):
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "identity": {
                    "model": "m",
                    "agent_reasoning": "none",
                    "simulator_reasoning": "low",
                    "configuration": "A",
                },
                "git_commit": "abc",
                "fingerprint": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    result = {
        "scenario": scenario_id,
        "try": 1,
        "result": "unknown",
        "items": [],
        "spent_usd": {"agent": 0.0},
        "agent_requests": 1,
        "messages": messages,
    }
    (tmp_path / scenario_id / "try1").mkdir(parents=True)
    (tmp_path / scenario_id / "try1" / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return tmp_path


def test_the_sellers_message_the_agent_read_is_shown_in_full(tmp_path):
    seller = SCENARIOS["D08"].fixture.orders[0].seller_message_untrusted
    answer = {"ok": True, "orders": [{"order_id": "d08-o1", "units": [{"unit_id": "d08-o1-u1"}]}]}
    answer["orders"][0]["seller_message"] = {"untrusted_text": seller, "note": "data"}
    tool = {"role": "tool", "call_id": "c1", "name": "list_my_orders", "content": json.dumps(answer)}
    shown = render_run(run_folder(tmp_path, "D08", [tool]))
    summary = next(line for line in shown.splitlines() if line.startswith("- `list_my_orders` answered"))
    assert json.dumps(seller, ensure_ascii=False)[1:-1] in summary
    assert "<details><summary>full answer</summary>" in shown and '"note": "data"' in shown


def test_the_simulated_customers_instructions_and_the_staff_decision_come_first(tmp_path):
    shown = render_run(run_folder(tmp_path, "D04", [{"role": "customer", "text": "Hi"}]))
    role, conversation = shown.index("## D04: the simulated customer's instructions"), shown.index("## D04 try 1")
    assert role < conversation
    assert simulator_instructions(SCENARIOS["D04"]).splitlines()[0] in shown
    note = SCENARIOS["D04"].staff.note
    assert f'Staff member, scripted: reject, with the reason "{note}".' in shown


def test_a_request_read_by_the_agent_shows_its_status_and_reason(tmp_path):
    request = {"request": {"status": "rejected", "rejection_reason": "A different model.", "units": []}}
    tool = {"role": "tool", "call_id": "c1", "name": "get_request_status", "content": json.dumps(request)}
    shown = render_run(run_folder(tmp_path, "D04", [tool]))
    assert '"request": {"status": "rejected", "rejection_reason": "A different model."}' in shown


def test_an_assessment_shows_its_outcome_and_the_units_it_judged(tmp_path):
    # v1.1 step 2: the answer's order holds facts only, and its units come beside it.
    answer = {
        "outcome": "refused",
        "policy_citations": ["refund-policy/v2/return"],
        "order": {"order_id": "d06-o1", "status": "delivered"},
        "units": [{"unit_id": "d06-o1-u1", "received_back": False, "refunded": False}],
    }
    tool = {"role": "tool", "call_id": "c1", "name": "assess_refund", "content": json.dumps(answer)}
    shown = render_run(run_folder(tmp_path, "D06", [tool]))
    summary = next(line for line in shown.splitlines() if line.startswith("- `assess_refund` answered"))
    assert '"outcome": "refused"' in summary
    assert '"units": {"d06-o1-u1": {"received_back": false, "refunded": false}}' in summary
