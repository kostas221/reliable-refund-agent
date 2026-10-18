"""Whole conversations in mock mode (phase 3 of the plan): the scripted agent and customer, the real backend, graph and
database, and the evaluator's verdict at the end. No API calls.
"""

import json

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from refund_agent import db as database
from refund_agent.agent.model import ScriptedModel
from refund_agent.evaluation.customers import ScriptedCustomer
from refund_agent.evaluation.mock_scripts import CARELESS_D01, MOCK, MockRun
from refund_agent.evaluation.runner import run_scenario
from tests.acceptance.flows import DEVELOPMENT, POLICY, rows


@pytest.fixture
def play(db):
    connections = []

    def run(scenario_id, mock, configuration="A", scenario=None):
        app = db("app")
        connections.append(database.checkpoint_connection("app", app.url.database))
        scenario = scenario or DEVELOPMENT[scenario_id]
        return run_scenario(
            scenario,
            ScriptedCustomer(scenario, mock.customer),
            ScriptedModel(mock.agent),
            owner=db("owner"),
            app=app,
            checkpointer=PostgresSaver(connections[-1]),
            policy=POLICY,
            configuration=configuration,
        )

    yield run
    for connection in connections:
        connection.close()


def lenient_audit(verdict):
    return {name: "passed" for name in verdict.names("pending")}


def test_every_development_scenario_has_a_mock_script():
    assert set(MOCK) == set(DEVELOPMENT)


@pytest.mark.parametrize("scenario_id", sorted(MOCK))
def test_every_development_scenario_runs_end_to_end_in_mock_mode(play, scenario_id):
    result = play(scenario_id, MOCK[scenario_id])
    assert result.system_error is None
    assert result.verdict.names("failed") == [], result.verdict.report()
    assert result.verdict.result == "unknown"  # a person still has to read the conversation
    assert result.verdict.with_audit(lenient_audit(result.verdict)).result == "passed"


def with_cards(scenario_id, **cards):
    """The scenario with another plan for the customer's cards."""
    scenario = DEVELOPMENT[scenario_id]
    plan = scenario.customer.cards.model_copy(update=cards)
    return scenario.model_copy(update={"customer": scenario.customer.model_copy(update={"cards": plan})})


STATUSES = "SELECT status, status_reason FROM proposals ORDER BY created_at, created_xact"


def test_a_customer_who_waits_gets_the_open_proposal_replaced(play, db):
    # D02 as written: the bowl alone stays open while the customer asks to add the plate (outside review of
    # 2026-10-15: until then the runner declined it at once, so the replacement itself was never tested).
    result = play("D02", MOCK["D02"])
    assert rows(db("app"), STATUSES) == [("invalidated", "superseded"), ("refunded", None)]
    assert result.verdict.names("failed") == [], result.verdict.report()
    assert result.verdict.item("outcome:refunds").evidence == "refunded d02-o1-u1 for 6990, d02-o1-u2 for 3490"


def test_a_customer_who_declines_other_cards_declines_them_at_once(play, db):
    play("D02", MOCK["D02"], scenario=with_cards("D02", other="decline"))
    assert rows(db("app"), STATUSES) == [("cancelled", "declined"), ("refunded", None)]


def test_a_customer_who_cancels_after_confirming_stops_the_refund_before_the_staff_decision(play, db):
    play("D01", MOCK["D01"], scenario=with_cards("D01", after_confirming="cancel"))
    assert rows(db("app"), STATUSES) == [("cancelled", "cancelled_by_customer")]
    assert rows(db("app"), "SELECT decision FROM customer_confirmations") == [("confirmed",)]
    assert rows(db("app"), "SELECT count(*) FROM staff_decisions") == [(0,)]
    assert rows(db("app"), "SELECT count(*) FROM refund_operations") == [(0,)]


@pytest.mark.parametrize(
    ("configuration", "paid_early", "failed"),
    [
        # The backend refuses the early payment; the refund is paid once approved.
        ("A", False, []),
        # Nothing stops it, and the evaluator catches it; this agent also never gave the receipt number.
        ("C", True, ["communication:gives_this_receipt", "forbidden:unauthorized_refund"]),
    ],
)
def test_a_careless_agent_in_configurations_a_and_c(play, db, configuration, paid_early, failed):
    result = play("D01", CARELESS_D01, configuration)
    early = next(json.loads(m["content"]) for m in result.messages if m.get("name") == "execute_refund")
    assert early["ok"] is paid_early
    if not paid_early:
        assert early["refused"] == "status_approved"
    assert result.verdict.names("failed") == failed
    assert rows(db("app"), "SELECT count(*) FROM refund_operations") == [(1,)]


def test_a_model_failure_is_kept_and_the_run_is_still_judged(play):
    result = play("D01", MockRun(agent=()))  # the model cannot say anything
    assert result.system_error.startswith("ModelError: invalid_output")
    assert result.verdict.result == "failed"  # nothing was done, so the scenario fails; the error is not hidden
