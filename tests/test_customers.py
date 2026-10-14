"""The customer side of a run, without a database: the scripted customer and the simulated one, with a fake model."""

import pytest

from refund_agent.agent.model import ModelError, ModelTurn
from refund_agent.evaluation.customers import (
    ScriptedCustomer,
    SimulatedCustomer,
    SimulatorError,
    simulator_instructions,
)
from refund_agent.scenarios import format_brl, load_split

SCENARIOS = {s.id: s for s in load_split("development")}


class FakeModel:
    name = "fake"

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def respond(self, instructions, messages, tools):
        self.requests.append({"instructions": instructions, "messages": messages, "tools": tools})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ModelTurn(text=answer)


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_the_simulated_customer_knows_its_goal_but_never_the_expected_answer(scenario_id):
    scenario = SCENARIOS[scenario_id]
    instructions = simulator_instructions(scenario)
    assert scenario.customer.goal in instructions
    for fact in scenario.customer.facts:
        assert fact.text in instructions
    expected = scenario.expected
    hidden = [*expected.refunded_units, *expected.cites, *expected.communication, *expected.forbidden]
    hidden += [unit.id for order in scenario.fixture.orders for unit in order.units]
    if expected.refund_amount_minor:
        hidden += [format_brl(expected.refund_amount_minor), str(expected.refund_amount_minor)]
    hidden += [scenario.staff.note] if scenario.staff.note else []
    assert [secret for secret in hidden if secret in instructions] == []


def test_a_fact_to_keep_until_asked_says_so():
    instructions = simulator_instructions(SCENARIOS["D09"])
    assert "You want the refund for the size L shirt. Say this only if you are asked about it." in instructions


def test_the_simulated_customer_sees_the_agent_as_the_other_party():
    model = FakeModel("The size L one.")
    customer = SimulatedCustomer(SCENARIOS["D09"], model)
    transcript = [("customer", customer.opening()), ("agent", "Which one do you mean, size M or size L?")]
    assert customer.next_line(transcript) == "The size L one."
    request = model.requests[0]
    assert [m["role"] for m in request["messages"]] == ["agent", "customer"]  # its own opening, then the agent
    assert request["messages"][1]["text"] == "Which one do you mean, size M or size L?"
    assert request["tools"] == []  # the customer has no buttons


def test_the_simulated_customer_ends_the_conversation():
    customer = SimulatedCustomer(SCENARIOS["D01"], FakeModel("Thanks!", "[END]"))
    assert customer.next_line([("customer", "Hi"), ("agent", "Done.")]) == "Thanks!"
    assert (
        customer.next_line([("customer", "Hi"), ("agent", "Done."), ("customer", "Thanks!"), ("agent", "Bye")]) is None
    )
    limited = SimulatedCustomer(SCENARIOS["D01"], FakeModel("one", "two"), max_lines=1)
    assert limited.next_line([]) == "one" and limited.next_line([]) is None  # the bound on its messages


def test_a_failure_of_the_simulator_is_reported_as_its_own():
    customer = SimulatedCustomer(SCENARIOS["D01"], FakeModel(ModelError("rate_limit", retryable=True, detail="slow")))
    with pytest.raises(SimulatorError, match="rate_limit"):
        customer.next_line([("customer", "Hi"), ("agent", "Hello")])


def test_the_scripted_customer_says_its_lines_in_order():
    customer = ScriptedCustomer(SCENARIOS["D02"], ["Add the plate, please."])
    assert customer.opening() == SCENARIOS["D02"].customer.opening_message
    assert customer.next_line([]) == "Add the plate, please." and customer.next_line([]) is None
